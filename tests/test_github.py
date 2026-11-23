from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import httpx
import pytest

from app.integrations.github import auth, client
from app.main import app
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

def test_github_modules_import():
    assert auth is not None
    assert client is not None


def test_create_installation_access_token():
    mock_response = {
        "token": "fake-installation-token",
        "expires_at": "2026-11-23T12:00:00Z",
    }

    with patch.object(
        client,
        "create_github_app_jwt",
        return_value="fake-jwt",
    ), patch.object(
        client.httpx,
        "post",
    ) as mock_post:

        mock_post.return_value.json.return_value = mock_response
        mock_post.return_value.raise_for_status.return_value = None

        result = client.create_installation_access_token()

    assert result["token"] == "fake-installation-token"
    assert result["expires_at"] == datetime(
        2026, 11, 23, 12, 0, tzinfo=timezone.utc
    )
    mock_post.assert_called_once()


def test_create_installation_access_token_without_installation_id():
    with patch.object(
        client.settings,
        "GITHUB_INSTALLATION_ID",
        "",
    ):
        with pytest.raises(
            ValueError,
            match="GITHUB_INSTALLATION_ID is not configured",
        ):
            client.create_installation_access_token()

def test_get_installation_repositories():
    mock_repo = {
        "id": 123,
        "name": "vexora",
        "full_name": "nadim/vexora",
        "owner": {"login": "nadim"},
        "html_url": "https://github.com/nadim/vexora",
        "description": "Vexora project",
        "default_branch": "main",
        "private": False,
        "language": "Python",
    }

    def mock_get(url, **kwargs):
        response = MagicMock()
        response.status_code = 200

        if url.endswith("/installation/repositories"):
            response.json.return_value = {
                "repositories": [mock_repo]
            }

        elif url.endswith("/languages"):
            response.json.return_value = {
                "Python": 15000,
                "JavaScript": 3000,
            }

        elif url.endswith("/readme"):
            response.text = "# Vexora\nMy project README"

        return response

    with patch.object(
        client,
        "create_installation_access_token",
        return_value={"token": "fake-token"},
    ), patch.object(
        client.httpx,
        "Client",
    ) as mock_http_client:

        mock_session = mock_http_client.return_value.__enter__.return_value
        mock_session.get.side_effect = mock_get

        repositories = client.get_installation_repositories()

    assert len(repositories) == 1

    repo = repositories[0]

    assert repo["full_name"] == "nadim/vexora"
    assert repo["owner"] == "nadim"
    assert repo["default_branch"] == "main"
    assert repo["private"] is False
    assert repo["description"] == "Vexora project"
    assert repo["primary_language"] == "Python"
    assert repo["languages"] == {
        "Python": 15000,
        "JavaScript": 3000,
    }
    assert repo["readme"] == "# Vexora\nMy project README"

    assert mock_session.get.call_count == 3

def test_get_installation_repositories_pagination():

    def make_repo(index):
        return {
            "id": index,
            "name": f"repo-{index}",
            "full_name": f"nadim/repo-{index}",
            "owner": {"login": "nadim"},
            "html_url": f"https://github.com/nadim/repo-{index}",
            "description": None,
            "default_branch": "main",
            "private": False,
            "language": "Python",
        }

    first_page = {
        "repositories": [make_repo(i) for i in range(100)]
    }

    second_page = {
        "repositories": [make_repo(100)]
    }

    def mock_get(url, **kwargs):
        response = MagicMock()
        response.status_code = 200

        if url.endswith("/installation/repositories"):
            page = kwargs["params"]["page"]

            response.json.return_value = (
                first_page if page == 1 else second_page
            )

        elif url.endswith("/languages"):
            response.json.return_value = {"Python": 1000}

        elif url.endswith("/readme"):
            response.text = "# Repository README"

        return response

    with patch.object(
        client,
        "create_installation_access_token",
        return_value={"token": "fake-token"},
    ), patch.object(
        client.httpx,
        "Client",
    ) as mock_http_client:

        mock_session = mock_http_client.return_value.__enter__.return_value
        mock_session.get.side_effect = mock_get

        repositories = client.get_installation_repositories()

    assert len(repositories) == 101

    assert repositories[0]["full_name"] == "nadim/repo-0"
    assert repositories[100]["full_name"] == "nadim/repo-100"

    assert repositories[0]["languages"] == {"Python": 1000}
    assert repositories[0]["readme"] == "# Repository README"

    repository_calls = [
        call
        for call in mock_session.get.call_args_list
        if call.args[0].endswith("/installation/repositories")
    ]

    assert len(repository_calls) == 2

    assert repository_calls[0].kwargs["params"]["page"] == 1
    assert repository_calls[1].kwargs["params"]["page"] == 2

def test_create_github_app_jwt():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    from unittest.mock import mock_open

    with patch.object(
        auth.settings,
        "GITHUB_APP_ID",
        "123456",
    ), patch.object(
        auth.settings,
        "GITHUB_PRIVATE_KEY_PATH",
    ) as mock_path:

        mock_path.is_file.return_value = True
        mock_path.read_text.return_value = pem.decode("utf-8")

        token = auth.create_github_app_jwt()

    decoded = jwt.decode(
        token,
        private_key.public_key(),
        algorithms=["RS256"],
    )

    assert decoded["iss"] == "123456"
    assert "iat" in decoded
    assert "exp" in decoded
    assert decoded["exp"] > decoded["iat"]


def test_create_github_app_jwt_without_app_id():
    with patch.object(auth.settings, "GITHUB_APP_ID", ""):
        with pytest.raises(
            ValueError,
            match="GITHUB_APP_ID is not configured",
        ):
            auth.create_github_app_jwt()


def test_create_github_app_jwt_without_private_key():
    with patch.object(
        auth.settings,
        "GITHUB_APP_ID",
        "123456",
    ), patch.object(
        auth.settings,
        "GITHUB_PRIVATE_KEY_PATH",
    ) as mock_path:

        mock_path.is_file.return_value = False

        with pytest.raises(FileNotFoundError):
            auth.create_github_app_jwt()

def test_list_github_repositories_endpoint():
    mock_repositories = [
        {
            "id": 123,
            "name": "vexora",
            "full_name": "nadim/vexora",
            "owner": "nadim",
            "html_url": "https://github.com/nadim/vexora",
            "default_branch": "main",
            "private": False,
        }
    ]

    with patch(
        "app.api.v1.endpoints.github.get_installation_repositories",
        return_value=mock_repositories,
    ):
        response = TestClient(app).get(
            "/api/v1/integrations/github/repositories"
        )

    assert response.status_code == 200
    assert response.json() == {
        "total": 1,
        "repositories": mock_repositories,
    }


def test_list_github_repositories_endpoint_github_error():
    with patch(
        "app.api.v1.endpoints.github.get_installation_repositories",
        side_effect=httpx.ConnectError("GitHub unavailable"),
    ):
        response = TestClient(app).get(
            "/api/v1/integrations/github/repositories"
        )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Unable to retrieve repositories from GitHub"
    )
