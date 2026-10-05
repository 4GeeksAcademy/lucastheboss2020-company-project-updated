import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import get_settings


class EmailDeliveryError(RuntimeError):
    pass


def send_password_reset_email(email: str, reset_url: str) -> None:
    settings = get_settings()
    api_key = str(settings["resend_api_key"])
    if not api_key:
        raise EmailDeliveryError("RESEND_API_KEY is not configured")

    sender = str(settings["password_reset_from_email"])
    payload = json.dumps(
        {
            "from": sender,
            "to": [email],
            "subject": "Reset your TrackFlow password",
            "html": (
                '<p>We received a request to reset your TrackFlow password.</p>'
                f'<p><a href="{reset_url}">Set a new password</a></p>'
                '<p>This link expires in the configured reset window and can only be used once. '
                'If you did not request this, you can ignore this email.</p>'
            ),
            "text": (
                "We received a request to reset your TrackFlow password. "
                f"Set a new password here: {reset_url} "
                "This link expires in the configured reset window and can only be used once. "
                "If you did not request this, you can ignore this email."
            ),
        }
    ).encode("utf-8")
    request = Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "TrackFlowBackend/1.0",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            if response.status < 200 or response.status >= 300:
                raise EmailDeliveryError("Email provider rejected the reset email")
    except (HTTPError, URLError, TimeoutError) as exc:
        raise EmailDeliveryError("Password reset email could not be delivered") from exc