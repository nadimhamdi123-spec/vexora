from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    git_url: str = Field(min_length=1, max_length=500)
    default_branch: str = Field(default="main", max_length=100)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    git_url: str | None = Field(default=None, min_length=1, max_length=500)
    default_branch: str | None = Field(default=None, max_length=100)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    git_url: str
    default_branch: str
    github_repo_id: int | None
    is_private: bool

    primary_language: str | None
    languages: dict | None
    readme: str | None

    created_at: datetime
    updated_at: datetime
