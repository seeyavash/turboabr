from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class ServiceType(StrEnum):
    multi_smart = "multi_smart"
    multi_economy = "multi_economy"


class ServiceStatus(StrEnum):
    active = "active"
    disabled = "disabled"
    deleted = "deleted"


class PaymentMethod(StrEnum):
    card = "card"
    plisio = "plisio"
    nowpayments = "nowpayments"
    stars = "stars"


class PaymentStatus(StrEnum):
    pending = "pending"
    waiting_receipt = "waiting_receipt"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"


class TransactionKind(StrEnum):
    deposit = "deposit"
    admin_adjustment = "admin_adjustment"
    traffic_charge = "traffic_charge"
    referral_cashback = "referral_cashback"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))
    wallet_balance_toman: Mapped[int] = mapped_column(BigInteger, default=0)
    referred_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    has_test_account: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    referred_by: Mapped["User | None"] = relationship(remote_side=[id])
    services: Mapped[list["VpnService"]] = relationship(back_populates="user")


class PasarGuardPanel(Base):
    __tablename__ = "pasarguard_panels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    base_url: Mapped[str] = mapped_column(Text)
    username: Mapped[str] = mapped_column(String(255))
    password_secret: Mapped[str] = mapped_column(Text)
    group_ids: Mapped[list[int]] = mapped_column(JSONB, default=list)
    subscription_client_type: Mapped[str] = mapped_column(String(64), default="v2ray")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ProductPlan(Base):
    __tablename__ = "product_plans"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    price_per_gb_toman: Mapped[int] = mapped_column(BigInteger)
    panel_id: Mapped[int | None] = mapped_column(ForeignKey("pasarguard_panels.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)
    encrypted: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class VpnService(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("product_plans.id"))
    panel_id: Mapped[int | None] = mapped_column(ForeignKey("pasarguard_panels.id"))
    type: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(32), index=True)
    pasarguard_username: Mapped[str] = mapped_column(String(64), unique=True)
    pasarguard_user_id: Mapped[int | None] = mapped_column(BigInteger)
    subscription_url: Mapped[str | None] = mapped_column(Text)
    last_traffic_mb: Mapped[int] = mapped_column(BigInteger, default=0)
    total_billed_mb: Mapped[int] = mapped_column(BigInteger, default=0)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="services")


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    amount_toman: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaymentRequest(Base):
    __tablename__ = "payment_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    method: Mapped[str] = mapped_column(String(32), index=True)
    amount_toman: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(32), index=True)
    provider_invoice_id: Mapped[str | None] = mapped_column(String(255))
    provider_url: Mapped[str | None] = mapped_column(Text)
    receipt_file_id: Mapped[str | None] = mapped_column(String(255))
    admin_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TrafficUsageLog(Base):
    __tablename__ = "traffic_usage_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), index=True)
    used_mb_delta: Mapped[int] = mapped_column(BigInteger)
    cost_toman: Mapped[int] = mapped_column(BigInteger)
    wallet_balance_after: Mapped[int] = mapped_column(BigInteger)
    raw_total_mb: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    admin_telegram_id: Mapped[int] = mapped_column(BigInteger, index=True)
    action: Mapped[str] = mapped_column(String(120))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
