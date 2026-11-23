from datetime import datetime, timedelta, timezone

import jwt

from app.core.config import settings


def create_github_app_jwt() -> str:
    """
    Generate a short-lived JWT to authenticate as a GitHub App.
    """

    if not settings.GITHUB_APP_ID:
        raise ValueError("GITHUB_APP_ID is not configured")

    if not settings.GITHUB_PRIVATE_KEY_PATH.is_file():
        raise FileNotFoundError(
            f"GitHub private key not found: "
            f"{settings.GITHUB_PRIVATE_KEY_PATH}"
        )

    private_key = settings.GITHUB_PRIVATE_KEY_PATH.read_text(
        encoding="utf-8"
    )

    now = datetime.now(timezone.utc)

    payload = {
        "iat": int((now - timedelta(seconds=60)).timestamp()),
        "exp": int((now + timedelta(minutes=9)).timestamp()),
        "iss": settings.GITHUB_APP_ID,
    }

    return jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
    )