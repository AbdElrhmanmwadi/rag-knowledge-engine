"""Helpers shared by the SSE streaming path.

The LLM provider SDKs expose synchronous generators; iterating them directly in
a coroutine would block the event loop for the whole generation. aiter_in_thread
pulls each chunk on a worker thread instead, keeping the loop free to flush SSE
events to the client as they arrive.
"""
import asyncio
import itertools
import json
import time

_SENTINEL = object()


async def aiter_in_thread(generator):
    """Iterate a blocking sync generator from async code, one chunk per thread hop."""
    iterator = iter(generator)
    try:
        while True:
            chunk = await asyncio.to_thread(next, iterator, _SENTINEL)
            if chunk is _SENTINEL:
                break
            yield chunk
    finally:
        # Client disconnects close this async generator mid-iteration; closing the
        # sync one too releases the provider's underlying HTTP stream.
        close = getattr(iterator, "close", None)
        if close is not None:
            await asyncio.to_thread(close)


def sse(event: str, data: dict) -> str:
    """Format one Server-Sent Events block."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def is_rate_limit_error(exc: Exception) -> bool:
    if getattr(exc, "status_code", None) == 429:
        return True
    name = exc.__class__.__name__.lower()
    return "toomanyrequests" in name or "ratelimit" in name


def open_stream_with_retry(open_fn, max_attempts: int = 3, base_delay: float = 2.0, logger=None):
    """Open a provider stream and pull its first event, retrying on rate limits.

    Retrying is only safe before the first chunk reaches the caller — after
    tokens have been forwarded, a retry would duplicate text — so the retry
    window is exactly: open the stream and read one event. Returns an iterator
    that replays that first event followed by the rest of the stream.
    """
    attempt = 1
    while True:
        try:
            iterator = iter(open_fn())
            first = next(iterator, _SENTINEL)
            if first is _SENTINEL:
                return iter(())
            return itertools.chain([first], iterator)
        except Exception as exc:
            if not is_rate_limit_error(exc) or attempt >= max_attempts:
                raise
            delay = base_delay * attempt
            if logger is not None:
                logger.warning(
                    "Rate limited opening LLM stream (attempt %d/%d), retrying in %.1fs",
                    attempt, max_attempts, delay,
                )
            time.sleep(delay)
            attempt += 1
