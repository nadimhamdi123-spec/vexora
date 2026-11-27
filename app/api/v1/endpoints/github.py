
import httpx

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.integrations.github.client import get_installation_repositories
from app.services import project_service
from app.integrations.github.webhooks import verify_webhook_signature

router = APIRouter(
    prefix="/integrations/github",
    tags=["GitHub Integration"],
)


@router.get("/repositories")
def list_github_repositories():
    try:
        repositories = get_installation_repositories()

        return {
            "total": len(repositories),
            "repositories": repositories,
        }

    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve repositories from GitHub",
        ) from exc


@router.post("/synchronize")
def synchronize_github_repositories(
    db: Session = Depends(get_db),
):
    try:
        return project_service.synchronize_github_projects(db)

    except httpx.HTTPError as exc:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail="Unable to synchronize repositories from GitHub",
        ) from exc

    except Exception:
        db.rollback()
        raise

@router.post("/webhook")
async def github_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Receive GitHub webhook events and synchronize repositories.
    """

    payload = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not verify_webhook_signature(payload, signature):
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature",
        )

    event = request.headers.get("X-GitHub-Event")

    try:
        data = await request.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON payload",
        ) from exc

    if event != "push":
        return {
            "status": "ignored",
            "event": event,
        }

    repository = data.get("repository")

    if not repository or not repository.get("id"):
        raise HTTPException(
            status_code=400,
            detail="Missing repository information",
        )

    try:
        project = project_service.synchronize_github_project(
            db,
            repository["id"],
        )

    except httpx.HTTPError as exc:
        db.rollback()
        raise HTTPException(
            status_code=502,
            detail="Unable to synchronize repository from GitHub",
        ) from exc

    except Exception:
        db.rollback()
        raise

    return {
        "status": "synchronized",
        "event": event,
        "repository": project.name,
        "repository_id": project.github_repo_id,
    }