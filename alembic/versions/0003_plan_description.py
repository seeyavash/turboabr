"""add plan description

Revision ID: 0003_plan_description
Revises: 0002_panel_templates
Create Date: 2026-06-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_plan_description"
down_revision: str | None = "0002_panel_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("product_plans", sa.Column("description", sa.Text()))


def downgrade() -> None:
    op.drop_column("product_plans", "description")
