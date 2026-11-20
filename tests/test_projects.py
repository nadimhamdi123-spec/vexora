
import pytest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db


@pytest.fixture
def client():
    # Base de données SQLite temporaire pour les tests
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )

    # Création des tables
    Base.metadata.create_all(bind=test_engine)

    # Remplacement de la connexion à la base de données
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Nettoyage après les tests
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


def test_create_project(client):
    response = client.post(
        "/api/v1/projects/",
        json={
            "name": "Vexora",
            "description": "Automation platform",
            "git_url": "https://github.com/user/vexora",
            "default_branch": "main",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Vexora"
    assert data["description"] == "Automation platform"
    assert data["git_url"] == "https://github.com/user/vexora"
    assert data["default_branch"] == "main"
    assert "id" in data


def test_list_projects(client):
    client.post(
        "/api/v1/projects/",
        json={
            "name": "Project One",
            "description": "First project",
            "git_url": "https://github.com/user/project-one",
            "default_branch": "main",
        },
    )

    response = client.get("/api/v1/projects/")

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["name"] == "Project One"


def test_retrieve_project(client):
    create_response = client.post(
        "/api/v1/projects/",
        json={
            "name": "Project Retrieve",
            "description": "Test retrieval",
            "git_url": "https://github.com/user/retrieve",
            "default_branch": "main",
        },
    )

    project_id = create_response.json()["id"]

    response = client.get(f"/api/v1/projects/{project_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "Project Retrieve"


def test_update_project(client):
    create_response = client.post(
        "/api/v1/projects/",
        json={
            "name": "Old Name",
            "description": "Old description",
            "git_url": "https://github.com/user/old",
            "default_branch": "main",
        },
    )

    project_id = create_response.json()["id"]

    response = client.patch(
        f"/api/v1/projects/{project_id}",
        json={
            "name": "New Name",
            "description": "Updated description",
            "git_url": "https://github.com/user/new",
            "default_branch": "develop",
        },
    )

    assert response.status_code == 200
    assert response.json()["name"] == "New Name"
    assert response.json()["default_branch"] == "develop"


def test_delete_project(client):
    create_response = client.post(
        "/api/v1/projects/",
        json={
            "name": "Project Delete",
            "description": "To delete",
            "git_url": "https://github.com/user/delete",
            "default_branch": "main",
        },
    )

    project_id = create_response.json()["id"]

    response = client.delete(f"/api/v1/projects/{project_id}")

    assert response.status_code in (200, 204)

    retrieve_response = client.get(
        f"/api/v1/projects/{project_id}"
    )

    assert retrieve_response.status_code == 404


def test_project_validation(client):
    response = client.post(
        "/api/v1/projects/",
        json={
            "name": "",
            "description": "Invalid project",
            "git_url": "https://github.com/user/invalid",
            "default_branch": "main",
        },
    )

    assert response.status_code == 422


def test_project_not_found(client):
    response = client.get("/api/v1/projects/99999")

    assert response.status_code == 404
