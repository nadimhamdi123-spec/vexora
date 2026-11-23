import pytest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.project import Project
from app.services import project_service


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    db = TestingSessionLocal()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def make_repo(
    repo_id,
    name,
    private=False,
):
    return {
        "id": repo_id,
        "name": name,
        "full_name": f"nadim/{name}",
        "owner": "nadim",
        "html_url": f"https://github.com/nadim/{name}",
        "default_branch": "main",
        "private": private,
    }


def test_synchronize_creates_github_projects(db_session):
    repositories = [
        make_repo(123, "vexora"),
        make_repo(456, "private-project", private=True),
    ]

    from unittest.mock import patch

    with patch.object(
        project_service,
        "get_installation_repositories",
        return_value=repositories,
    ):
        result = project_service.synchronize_github_projects(db_session)

    assert result == {
        "total": 2,
        "created": 2,
        "updated": 0,
    }

    projects = db_session.scalars(select(Project)).all()

    assert len(projects) == 2

    projects_by_repo_id = {
        project.github_repo_id: project
        for project in projects
    }

    assert projects_by_repo_id[123].name == "vexora"
    assert projects_by_repo_id[123].is_private is False

    assert projects_by_repo_id[456].name == "private-project"
    assert projects_by_repo_id[456].is_private is True


def test_synchronize_updates_existing_projects_without_duplicates(
    db_session,
):
    initial_repositories = [
        make_repo(123, "vexora"),
        make_repo(456, "private-project", private=True),
    ]

    updated_repositories = [
        {
            **make_repo(123, "vexora-updated"),
            "default_branch": "develop",
        },
        make_repo(456, "private-project", private=False),
    ]

    from unittest.mock import patch

    with patch.object(
        project_service,
        "get_installation_repositories",
        side_effect=[
            initial_repositories,
            updated_repositories,
        ],
    ):
        first_result = project_service.synchronize_github_projects(
            db_session
        )

        second_result = project_service.synchronize_github_projects(
            db_session
        )

    assert first_result == {
        "total": 2,
        "created": 2,
        "updated": 0,
    }

    assert second_result == {
        "total": 2,
        "created": 0,
        "updated": 2,
    }

    projects = db_session.scalars(select(Project)).all()

    assert len(projects) == 2

    projects_by_repo_id = {
        project.github_repo_id: project
        for project in projects
    }

    assert projects_by_repo_id[123].name == "vexora-updated"
    assert projects_by_repo_id[123].default_branch == "develop"

    assert projects_by_repo_id[456].is_private is False


from fastapi.testclient import TestClient

from app.main import app
from app.db.session import get_db


@pytest.fixture
def api_client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.pop(get_db, None)


def test_synchronize_github_repositories_endpoint(api_client):
    repositories = [
        make_repo(789, "api-project"),
        make_repo(101, "private-api-project", private=True),
    ]

    from unittest.mock import patch

    with patch.object(
        project_service,
        "get_installation_repositories",
        return_value=repositories,
    ):
        response = api_client.post(
            "/api/v1/integrations/github/synchronize"
        )

    assert response.status_code == 200
    assert response.json() == {
        "total": 2,
        "created": 2,
        "updated": 0,
    }


def test_synchronize_github_repositories_endpoint_github_error(
    api_client,
):
    import httpx
    from unittest.mock import patch

    with patch.object(
        project_service,
        "get_installation_repositories",
        side_effect=httpx.ConnectError("GitHub unavailable"),
    ):
        response = api_client.post(
            "/api/v1/integrations/github/synchronize"
        )

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Unable to synchronize repositories from GitHub"
    )
