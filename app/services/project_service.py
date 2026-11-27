
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.integrations.github.client import (
    get_installation_repositories,
    get_repository_by_id,
)
def create_project(db: Session, data: ProjectCreate) -> Project:
    project = Project(**data.model_dump())
    
    db.add(project)
    db.commit()
    db.refresh(project)
    
    return project


def get_projects(db: Session) -> list[Project]:
    statement = select(Project).order_by(Project.created_at.desc())
    return list(db.scalars(statement).all())


def get_project(db: Session, project_id: str) -> Project | None:
    return db.get(Project, project_id)


def update_project(
    db: Session,
    project: Project,
    data: ProjectUpdate,
) -> Project:
    updates = data.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(project, field, value)

    db.commit()
    db.refresh(project)

    return project


def delete_project(db: Session, project: Project) -> None:
    db.delete(project)
    db.commit()


def synchronize_github_projects(db: Session) -> dict:
    repositories = get_installation_repositories()

    created = 0
    updated = 0

    for repo in repositories:
        project = db.scalar(
            select(Project).where(
                Project.github_repo_id == repo["id"]
            )
        )

        if project is None:
            project = Project(
                name=repo["name"],
                description=repo.get("description"),
                git_url=repo["html_url"],
                default_branch=repo["default_branch"],
                github_repo_id=repo["id"],
                is_private=repo["private"],
                primary_language=repo.get("primary_language"),
                languages=repo.get("languages"),
                readme=repo.get("readme"),
            )
            db.add(project)
            created += 1

        else:
            project.name = repo["name"]
            project.description = repo.get("description")
            project.git_url = repo["html_url"]
            project.default_branch = repo["default_branch"]
            project.is_private = repo["private"]
            project.primary_language = repo.get("primary_language")
            project.languages = repo.get("languages")
            project.readme = repo.get("readme")
            updated += 1

    db.commit()

    return {
        "total": len(repositories),
        "created": created,
        "updated": updated,
    }


def synchronize_github_project(
    db: Session,
    repository_id: int,
) -> Project:
    """
    Synchronize one GitHub repository with the local database.
    Create the project if it does not exist, otherwise update it.
    """

    repo = get_repository_by_id(repository_id)

    try:
        project = db.scalar(
            select(Project).where(
                Project.github_repo_id == repository_id
            )
        )

        if project is None:
            project = Project(
                name=repo["name"],
                description=repo.get("description"),
                git_url=repo["html_url"],
                default_branch=repo["default_branch"],
                github_repo_id=repo["id"],
                is_private=repo["private"],
                primary_language=repo.get("primary_language"),
                languages=repo.get("languages"),
                readme=repo.get("readme"),
            )

            db.add(project)

        else:
            project.name = repo["name"]
            project.description = repo.get("description")
            project.git_url = repo["html_url"]
            project.default_branch = repo["default_branch"]
            project.is_private = repo["private"]
            project.primary_language = repo.get("primary_language")
            project.languages = repo.get("languages")
            project.readme = repo.get("readme")

        db.commit()
        db.refresh(project)

        return project

    except Exception:
        db.rollback()
        raise
