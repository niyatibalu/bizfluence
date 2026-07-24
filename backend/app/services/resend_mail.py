from app.config import get_settings
from app.schemas import SendEmailOut


def send_outreach_email(to_email: str, subject: str, body: str) -> SendEmailOut:
    settings = get_settings()
    if not settings.resend_api_key:
        mailto = f"mailto:{to_email}?subject={_q(subject)}&body={_q(body)}"
        return SendEmailOut(
            ok=True,
            message=f"Resend not configured. Open mailto link to send manually: {mailto}",
            mode="mailto",
        )

    try:
        import resend

        resend.api_key = settings.resend_api_key
        resend.Emails.send(
            {
                "from": settings.resend_from_email,
                "to": [to_email],
                "subject": subject,
                "text": body,
            }
        )
        return SendEmailOut(ok=True, message="Email sent via Resend", mode="resend")
    except Exception as exc:  # noqa: BLE001
        mailto = f"mailto:{to_email}?subject={_q(subject)}&body={_q(body)}"
        return SendEmailOut(
            ok=False,
            message=f"Resend failed ({exc}). Fallback mailto: {mailto}",
            mode="mailto",
        )


def _q(value: str) -> str:
    from urllib.parse import quote

    return quote(value)
