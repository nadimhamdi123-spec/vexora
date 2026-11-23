
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    JSON,
    String,
    Text,
)
from app.db.base import Base


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
    Index(
        "uq_projects_github_repo_id",
        "github_repo_id",
        unique=True,
        ),
    )
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    git_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    default_branch: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="main",
    )

    github_repo_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    is_private: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    primary_language: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    languages: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )

    readme: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
