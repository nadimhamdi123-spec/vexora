
"""add github fields to projects"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a214e2db97dc"
down_revision: Union[str, Sequence[str], None] = "ceb7368077c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_columns = {
        column["name"]
        for column in inspector.get_columns("projects")
    }

    if "github_repo_id" not in existing_columns:
        op.add_column(
            "projects",
            sa.Column("github_repo_id", sa.BigInteger(), nullable=True),
        )

    if "is_private" not in existing_columns:
        op.add_column(
            "projects",
            sa.Column(
                "is_private",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )

    # SQLite supports unique indexes even though it does not
    # support adding unique constraints with ALTER TABLE.
    inspector = sa.inspect(bind)

    existing_indexes = {
        index["name"]
        for index in inspector.get_indexes("projects")
    }

    if "uq_projects_github_repo_id" not in existing_indexes:
        op.create_index(
            "uq_projects_github_repo_id",
            "projects",
            ["github_repo_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_indexes = {
        index["name"]
        for index in inspector.get_indexes("projects")
    }

    if "uq_projects_github_repo_id" in existing_indexes:
        op.drop_index(
            "uq_projects_github_repo_id",
            table_name="projects",
        )

    existing_columns = {
        column["name"]
        for column in inspector.get_columns("projects")
    }

    if "is_private" in existing_columns:
        op.drop_column("projects", "is_private")

    if "github_repo_id" in existing_columns:
        op.drop_column("projects", "github_repo_id")
