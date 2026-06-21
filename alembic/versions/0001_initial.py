"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True, index=True),
        sa.Column("username", sa.String(255)),
        sa.Column("full_name", sa.String(255)),
        sa.Column("wallet_balance_toman", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("referred_by_id", sa.BigInteger(), sa.ForeignKey("users.id")),
        sa.Column("has_test_account", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "settings",
        sa.Column("key", sa.String(120), primary_key=True),
        sa.Column("value", sa.Text()),
        sa.Column("encrypted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "pasarguard_panels",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("username", sa.String(255), nullable=False),
        sa.Column("password_secret", sa.Text(), nullable=False),
        sa.Column("group_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("subscription_client_type", sa.String(64), nullable=False, server_default="v2ray"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "product_plans",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("price_per_gb_toman", sa.BigInteger(), nullable=False),
        sa.Column("panel_id", sa.BigInteger(), sa.ForeignKey("pasarguard_panels.id")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "services",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("plan_id", sa.BigInteger(), sa.ForeignKey("product_plans.id")),
        sa.Column("panel_id", sa.BigInteger(), sa.ForeignKey("pasarguard_panels.id")),
        sa.Column("type", sa.String(120), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, index=True),
        sa.Column("pasarguard_username", sa.String(64), nullable=False, unique=True),
        sa.Column("pasarguard_user_id", sa.BigInteger()),
        sa.Column("subscription_url", sa.Text()),
        sa.Column("last_traffic_mb", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("total_billed_mb", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "wallet_transactions",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("amount_toman", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, index=True),
        sa.Column("description", sa.Text()),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "payment_requests",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("method", sa.String(32), nullable=False, index=True),
        sa.Column("amount_toman", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, index=True),
        sa.Column("provider_invoice_id", sa.String(255)),
        sa.Column("provider_url", sa.Text()),
        sa.Column("receipt_file_id", sa.String(255)),
        sa.Column("admin_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "traffic_usage_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("service_id", sa.BigInteger(), sa.ForeignKey("services.id"), nullable=False, index=True),
        sa.Column("used_mb_delta", sa.BigInteger(), nullable=False),
        sa.Column("cost_toman", sa.BigInteger(), nullable=False),
        sa.Column("wallet_balance_after", sa.BigInteger(), nullable=False),
        sa.Column("raw_total_mb", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("admin_telegram_id", sa.BigInteger(), nullable=False, index=True),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("admin_audit_logs")
    op.drop_table("traffic_usage_logs")
    op.drop_table("payment_requests")
    op.drop_table("wallet_transactions")
    op.drop_table("services")
    op.drop_table("product_plans")
    op.drop_table("pasarguard_panels")
    op.drop_table("settings")
    op.drop_table("users")
