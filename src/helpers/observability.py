"""LangSmith observability helpers.

Provides a `traceable` decorator that degrades to a no-op when the optional
`langsmith` package is missing, and a `configure_langsmith` function that exports
the env vars the LangSmith SDK reads. Tracing stays fully off unless enabled in
settings, so importing this module is always safe.
"""
import logging
import os

logger = logging.getLogger(__name__)

try:
    from langsmith import traceable as _traceable

    _LANGSMITH_AVAILABLE = True
except Exception:  # pragma: no cover - exercised when langsmith is not installed
    _LANGSMITH_AVAILABLE = False

    def _traceable(*d_args, **d_kwargs):
        """No-op stand-in supporting both @traceable and @traceable(...) usage."""
        if len(d_args) == 1 and callable(d_args[0]) and not d_kwargs:
            return d_args[0]

        def decorator(func):
            return func

        return decorator


traceable = _traceable


def add_llm_run_metadata(model: str = None, provider: str = None) -> None:
    """Tag the current LangSmith run with `ls_model_name`/`ls_provider`.

    LangSmith uses these to price token usage. The model id is only known at
    call time (set_genaration_model), so it cannot live in the decorator's
    static metadata. Silently does nothing without langsmith or an active run.
    """
    if not _LANGSMITH_AVAILABLE:
        return
    try:
        from langsmith.run_helpers import get_current_run_tree

        run_tree = get_current_run_tree()
        if run_tree is None:
            return
        metadata = {}
        if provider:
            metadata["ls_provider"] = provider
        if model:
            metadata["ls_model_name"] = model
        if metadata:
            run_tree.add_metadata(metadata)
    except Exception:
        logger.debug("Could not attach LLM metadata to the current run", exc_info=True)


def configure_langsmith(settings) -> bool:
    """Export LangSmith env vars when tracing is enabled.

    pydantic-settings loads values into the Settings object but not into
    os.environ, while the LangSmith SDK reads from os.environ -- so we bridge
    them here. Returns True only when tracing is actually active.
    """
    if not getattr(settings, "LANGSMITH_TRACING", False):
        return False
    if not _LANGSMITH_AVAILABLE:
        logger.warning(
            "LANGSMITH_TRACING is enabled but the 'langsmith' package is not "
            "installed; tracing disabled. Run: pip install langsmith"
        )
        return False
    # Export both prefixes so any langsmith version picks them up.
    for tracing in ("LANGSMITH_TRACING", "LANGCHAIN_TRACING_V2"):
        os.environ[tracing] = "true"
    os.environ["LANGSMITH_ENDPOINT"] = os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    os.environ["LANGSMITH_PROJECT"] = os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
    if settings.LANGSMITH_API_KEY:
        os.environ["LANGSMITH_API_KEY"] = os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
    else:
        logger.warning("LANGSMITH_TRACING is enabled but LANGSMITH_API_KEY is empty")
    logger.info("LangSmith tracing enabled (project=%s)", settings.LANGSMITH_PROJECT)
    return True
