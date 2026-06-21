"""add service disabled reason

Revision ID: 0004_service_disabled_reason
Revises: 0003_plan_description
Create Date: 2026-06-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_service_disabled_reason"
down_revision: str | None = "0003_plan_description"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("services", sa.Column("disabled_reason", sa.String(32)))


def downgrade() -> None:
    op.drop_column("services", "disabled_reason")
