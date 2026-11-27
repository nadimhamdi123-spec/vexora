
import hashlib
import hmac

from app.core.config import settings


def verify_webhook_signature(
    payload: bytes,
    signature: str | None,
) -> bool:
    """
    Verify GitHub webhook signature using HMAC SHA-256.
    """

    secret = settings.GITHUB_WEBHOOK_SECRET

    if not secret or not signature:
        return False

    expected_signature = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(
        expected_signature,
        signature,
    )
