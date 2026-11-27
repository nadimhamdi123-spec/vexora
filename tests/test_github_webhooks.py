
import hashlib
import hmac

from unittest.mock import MagicMock, patch
from app.integrations.github.webhooks import (
    verify_webhook_signature,
)
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)

def generate_signature(payload: bytes, secret: str) -> str:
    digest = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return f"sha256={digest}"


def test_valid_webhook_signature():
    payload = b'{"action":"push"}'
    secret = "test-secret"

    signature = generate_signature(payload, secret)

    with patch(
        "app.integrations.github.webhooks.settings.GITHUB_WEBHOOK_SECRET",
        secret,
    ):
        assert verify_webhook_signature(payload, signature)


def test_invalid_webhook_signature():
    payload = b'{"action":"push"}'

    with patch(
        "app.integrations.github.webhooks.settings.GITHUB_WEBHOOK_SECRET",
        "test-secret",
    ):
        assert not verify_webhook_signature(
            payload,
            "sha256=invalid",
        )


def test_missing_webhook_signature():
    with patch(
        "app.integrations.github.webhooks.settings.GITHUB_WEBHOOK_SECRET",
        "test-secret",
    ):
        assert not verify_webhook_signature(
            b'{"action":"push"}',
            None,
        )


def test_missing_webhook_secret():
    with patch(
        "app.integrations.github.webhooks.settings.GITHUB_WEBHOOK_SECRET",
        "",
    ):
        assert not verify_webhook_signature(
            b'{"action":"push"}',
            "sha256=anything",
        )

def test_github_webhook_valid_signature():
    payload = {
        "action": "opened",
        "repository": {
            "id": 123,
            "name": "vexora",
            "full_name": "nadim/vexora",
        },
    }

    mock_project = MagicMock()
    mock_project.name = "vexora"
    mock_project.github_repo_id = 123

    with patch(
        "app.api.v1.endpoints.github.verify_webhook_signature",
        return_value=True,
    ), patch(
        "app.api.v1.endpoints.github.project_service.synchronize_github_project",
        return_value=mock_project,
    ) as mock_sync:

        response = client.post(
            "/api/v1/integrations/github/webhook",
            json=payload,
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "push",
            },
        )

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "synchronized"
    assert data["event"] == "push"
    assert data["repository"] == "vexora"
    assert data["repository_id"] == 123

    mock_sync.assert_called_once()

def test_github_webhook_invalid_signature():
    with patch(
        "app.api.v1.endpoints.github.verify_webhook_signature",
        return_value=False,
    ):
        response = client.post(
            "/api/v1/integrations/github/webhook",
            json={"action": "opened"},
            headers={
                "X-Hub-Signature-256": "sha256=invalid",
                "X-GitHub-Event": "push",
            },
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid webhook signature"


def test_github_webhook_invalid_json():
    with patch(
        "app.api.v1.endpoints.github.verify_webhook_signature",
        return_value=True,
    ):
        response = client.post(
            "/api/v1/integrations/github/webhook",
            content=b"invalid-json",
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "push",
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid JSON payload"