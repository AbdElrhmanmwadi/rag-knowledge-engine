import asyncio

from fastapi import HTTPException, status

try:
    from resend import Resend
except ImportError:
    Resend = None
    import resend

from helpers.config import Settings


def _send_email(settings: Settings, payload: dict) -> None:
    if Resend is not None:
        client = Resend(settings.RESEND_API_KEY)
        client.emails.send(payload)
        return

    resend.api_key = settings.RESEND_API_KEY
    resend.Emails.send(payload)


async def send_verification_email(to_email: str, token: str, settings: Settings) -> None:
    if not settings.RESEND_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="RESEND_API_KEY is not configured",
        )

    verification_url = f"{settings.FRONTEND_BASE_URL.rstrip('/')}/auth/verify-email?token={token}"
    await asyncio.to_thread(
        _send_email,
        settings,
        {
            "from": settings.RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": "Verify your email",
            "html": (
                "<p>Welcome. Verify your email address to activate your account.</p>"
                f'<p><a href="{verification_url}">Verify email</a></p>'
                "<p>If you did not create this account, you can ignore this email.</p>"
            ),
        },
    )
