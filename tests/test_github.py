from datetime import datetime, timezone
from unittest.mock import ANY, MagicMock, patch
from fastapi.testclient import TestClient as FastAPIClient
import httpx
import pytest
from app.integrations.github import auth, client
from app.main import app
from app.services import project_service
from app.models.project import Project
from app.services import project_service
from app.db.session import get_db

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization


test_client = FastAPIClient(app)

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
        response = test_client.get(
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
        response = test_client.get(
            "/api/v1/integrations/github/repositories"
        )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Unable to retrieve repositories from GitHub"
    )


def test_get_repository_by_id():
    repository_id = 123456

    repository_data = {
        "id": repository_id,
        "name": "vexora",
        "full_name": "nadim/vexora",
        "owner": {"login": "nadim"},
        "html_url": "https://github.com/nadim/vexora",
        "description": "DevOps Automation Platform",
        "default_branch": "main",
        "private": True,
        "language": "Python",
    }

    mock_response = MagicMock()
    mock_response.json.return_value = repository_data

    with (
        patch(
            "app.integrations.github.client.create_installation_access_token",
            return_value={"token": "test-token"},
        ),
        patch(
            "app.integrations.github.client.httpx.Client"
        ) as mock_http_client,
        patch(
            "app.integrations.github.client.get_repository_languages",
            return_value={"Python": 15000},
        ) as mock_languages,
        patch(
            "app.integrations.github.client.get_repository_readme",
            return_value="# Vexora",
        ) as mock_readme,
    ):
        mock_session = mock_http_client.return_value.__enter__.return_value
        mock_session.get.return_value = mock_response

        result = client.get_repository_by_id(repository_id)

    mock_session.get.assert_called_once_with(
        f"{client.GITHUB_API_URL}/repositories/{repository_id}"
    )

    mock_languages.assert_called_once_with(
        mock_session,
        "nadim/vexora",
    )

    mock_readme.assert_called_once_with(
        mock_session,
        "nadim/vexora",
    )

    assert result == {
        "id": repository_id,
        "name": "vexora",
        "full_name": "nadim/vexora",
        "owner": "nadim",
        "html_url": "https://github.com/nadim/vexora",
        "description": "DevOps Automation Platform",
        "default_branch": "main",
        "private": True,
        "primary_language": "Python",
        "languages": {"Python": 15000},
        "readme": "# Vexora",
    }


def test_synchronize_github_project_creates_project():
    repository = {
        "id": 123,
        "name": "vexora",
        "html_url": "https://github.com/nadim/vexora",
        "description": "Vexora project",
        "default_branch": "main",
        "private": False,
        "primary_language": "Python",
        "languages": {"Python": 15000},
        "readme": "# Vexora",
    }

    db = MagicMock()
    db.scalar.return_value = None

    with patch.object(
        project_service,
        "get_repository_by_id",
        return_value=repository,
    ):
        project = project_service.synchronize_github_project(
            db,
            123,
        )

    assert project.name == "vexora"
    assert project.github_repo_id == 123
    assert project.primary_language == "Python"

    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(project)


def test_synchronize_github_project_updates_project():
    repository = {
        "id": 123,
        "name": "vexora-updated",
        "html_url": "https://github.com/nadim/vexora",
        "description": "Updated description",
        "default_branch": "develop",
        "private": True,
        "primary_language": "Python",
        "languages": {"Python": 20000},
        "readme": "# Updated Vexora",
    }

    existing_project = Project(
        name="vexora",
        github_repo_id=123,
    )

    db = MagicMock()
    db.scalar.return_value = existing_project

    with patch.object(
        project_service,
        "get_repository_by_id",
        return_value=repository,
    ):
        project = project_service.synchronize_github_project(
            db,
            123,
        )

    assert project is existing_project
    assert project.name == "vexora-updated"
    assert project.description == "Updated description"
    assert project.default_branch == "develop"
    assert project.is_private is True
    assert project.languages == {"Python": 20000}

    db.add.assert_not_called()
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(existing_project)


def test_synchronize_github_project_rollbacks_on_commit_error():
    repository = {
        "id": 123,
        "name": "vexora",
        "html_url": "https://github.com/nadim/vexora",
        "description": "Vexora project",
        "default_branch": "main",
        "private": False,
        "primary_language": "Python",
        "languages": {"Python": 15000},
        "readme": "# Vexora",
    }

    db = MagicMock()
    db.scalar.return_value = None
    db.commit.side_effect = Exception("Database error")

    with patch.object(
        project_service,
        "get_repository_by_id",
        return_value=repository,
    ):
        with pytest.raises(Exception, match="Database error"):
            project_service.synchronize_github_project(
                db,
                123,
            )

    db.rollback.assert_called_once()



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

        response = test_client.post(
            "/api/v1/integrations/github/webhook",
            json=payload,
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "push",
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "synchronized"
    assert response.json()["repository"] == "vexora"

    mock_sync.assert_called_once()

def test_github_webhook_invalid_signature():
    with patch(
        "app.api.v1.endpoints.github.verify_webhook_signature",
        return_value=False,
    ):
        response = test_client.post(
            "/api/v1/integrations/github/webhook",
            json={"repository": {"id": 123}},
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
        response = test_client.post(
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

def test_github_webhook_ignored_event():
    with patch(
        "app.api.v1.endpoints.github.verify_webhook_signature",
        return_value=True,
    ), patch.object(
        project_service,
        "synchronize_github_project",
    ) as mock_sync:

        response = test_client.post(
            "/api/v1/integrations/github/webhook",
            json={"repository": {"id": 123}},
            headers={
                "X-Hub-Signature-256": "sha256=test",
                "X-GitHub-Event": "issues",
            },
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ignored",
        "event": "issues",
    }

    mock_sync.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"repository": {"name": "vexora"}},
    ],
)
def test_github_webhook_missing_repository_information(payload):
    mock_db = MagicMock()

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch(
            "app.api.v1.endpoints.github.verify_webhook_signature",
            return_value=True,
        ), patch.object(
            project_service,
            "synchronize_github_project",
        ) as mock_sync:

            response = test_client.post(
                "/api/v1/integrations/github/webhook",
                json=payload,
                headers={
                    "X-Hub-Signature-256": "sha256=test",
                    "X-GitHub-Event": "push",
                },
            )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            "Missing repository information"
        )
        mock_sync.assert_not_called()

    finally:
        app.dependency_overrides.pop(get_db, None)


def test_github_webhook_github_http_error():
    mock_db = MagicMock()

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch(
            "app.api.v1.endpoints.github.verify_webhook_signature",
            return_value=True,
        ), patch.object(
            project_service,
            "synchronize_github_project",
            side_effect=httpx.ConnectError("GitHub unavailable"),
        ) as mock_sync:

            response = test_client.post(
                "/api/v1/integrations/github/webhook",
                json={"repository": {"id": 123}},
                headers={
                    "X-Hub-Signature-256": "sha256=test",
                    "X-GitHub-Event": "push",
                },
            )

        assert response.status_code == 502
        assert response.json()["detail"] == (
            "Unable to synchronize repository from GitHub"
        )

        mock_sync.assert_called_once_with(mock_db, 123)
        mock_db.rollback.assert_called_once()

    finally:
        app.dependency_overrides.pop(get_db, None)


def test_github_webhook_unexpected_error_rollbacks():
    mock_db = MagicMock()

    app.dependency_overrides[get_db] = lambda: mock_db

    try:
        with patch(
            "app.api.v1.endpoints.github.verify_webhook_signature",
            return_value=True,
        ), patch.object(
            project_service,
            "synchronize_github_project",
            side_effect=RuntimeError("Unexpected database error"),
        ) as mock_sync:

            response = FastAPIClient(
                app,
                raise_server_exceptions=False,
            ).post(
                "/api/v1/integrations/github/webhook",
                json={"repository": {"id": 123}},
                headers={
                    "X-Hub-Signature-256": "sha256=test",
                    "X-GitHub-Event": "push",
                },
            )

        assert response.status_code == 500

        mock_sync.assert_called_once_with(mock_db, 123)
        mock_db.rollback.assert_called_once()

    finally:
        app.dependency_overrides.pop(get_db, None)


def test_synchronize_github_projects_creates_projects():
    repositories = [
        {
            "id": 123,
            "name": "vexora",
            "html_url": "https://github.com/nadim/vexora",
            "description": "Vexora project",
            "default_branch": "main",
            "private": False,
            "primary_language": "Python",
            "languages": {"Python": 15000},
            "readme": "# Vexora",
        },
        {
            "id": 456,
            "name": "other-project",
            "html_url": "https://github.com/nadim/other-project",
            "description": "Another project",
            "default_branch": "main",
            "private": True,
            "primary_language": "JavaScript",
            "languages": {"JavaScript": 5000},
            "readme": "# Other project",
        },
    ]

    mock_db = MagicMock()
    mock_db.scalar.return_value = None

    with patch.object(
        project_service,
        "get_installation_repositories",
        return_value=repositories,
    ):
        result = project_service.synchronize_github_projects(mock_db)

    assert result == {
        "total": 2,
        "created": 2,
        "updated": 0,
    }

    assert mock_db.add.call_count == 2
    mock_db.commit.assert_called_once()


def test_synchronize_github_projects_updates_projects():
    repositories = [
        {
            "id": 123,
            "name": "vexora-updated",
            "html_url": "https://github.com/nadim/vexora",
            "description": "Updated description",
            "default_branch": "develop",
            "private": True,
            "primary_language": "Python",
            "languages": {"Python": 20000},
            "readme": "# Updated Vexora",
        },
    ]

    existing_project = MagicMock()
    mock_db = MagicMock()
    mock_db.scalar.return_value = existing_project

    with patch.object(
        project_service,
        "get_installation_repositories",
        return_value=repositories,
    ):
        result = project_service.synchronize_github_projects(mock_db)

    assert result == {
        "total": 1,
        "created": 0,
        "updated": 1,
    }

    assert existing_project.name == "vexora-updated"
    assert existing_project.description == "Updated description"
    assert existing_project.default_branch == "develop"
    assert existing_project.is_private is True
    assert existing_project.languages == {"Python": 20000}
    assert existing_project.readme == "# Updated Vexora"

    mock_db.add.assert_not_called()
    mock_db.commit.assert_called_once()
