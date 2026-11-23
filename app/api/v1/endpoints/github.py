
import httpx

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.integrations.github.client import get_installation_repositories
from app.services import project_service


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
