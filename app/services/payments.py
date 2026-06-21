from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PaymentMethod, PaymentRequest, PaymentStatus, TransactionKind, User
from app.integrations.payments import NowPaymentsClient, PlisioClient
from app.services.service_lifecycle import reactivate_user_disabled_services
from app.services.settings import SettingsService
from app.services.wallet import WalletService


class PaymentService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = SettingsService(session)

    async def create_card_request(self, user: User, amount: int) -> PaymentRequest:
        payment = PaymentRequest(
            user_id=user.id,
            method=PaymentMethod.card.value,
            amount_toman=amount,
            status=PaymentStatus.waiting_receipt.value,
        )
        self.session.add(payment)
        await self.session.flush()
        return payment

    async def create_crypto_request(self, user: User, amount: int, method: PaymentMethod) -> PaymentRequest:
        payment = PaymentRequest(user_id=user.id, method=method.value, amount_toman=amount, status=PaymentStatus.pending.value)
        self.session.add(payment)
        await self.session.flush()
        order_id = f"wallet-{payment.id}"
        if method == PaymentMethod.plisio:
            token = await self.settings.get("plisio_api_token")
            invoice_id, url = await PlisioClient(token or "").create_invoice(amount, order_id)
        elif method == PaymentMethod.nowpayments:
            token = await self.settings.get("nowpayments_api_token")
            invoice_id, url = await NowPaymentsClient(token or "").create_invoice(amount, order_id)
        else:
            raise ValueError("روش پرداخت پشتیبانی نمی‌شود.")
        payment.provider_invoice_id = invoice_id
        payment.provider_url = url
        return payment

    async def approve(self, payment: PaymentRequest, admin_note: str | None = None, bot: Bot | None = None) -> None:
        if payment.status == PaymentStatus.approved.value:
            return
        user = await self.session.get(User, payment.user_id)
        if not user:
            raise ValueError("کاربر پرداخت پیدا نشد.")
        payment.status = PaymentStatus.approved.value
        payment.admin_note = admin_note
        await WalletService(self.session).add(
            user,
            payment.amount_toman,
            TransactionKind.deposit,
            f"شارژ کیف پول از طریق {payment.method}",
            {"payment_id": payment.id},
        )
        if bot:
            await reactivate_user_disabled_services(self.session, bot, user)

    async def reject(self, payment: PaymentRequest, admin_note: str | None = None) -> None:
        payment.status = PaymentStatus.rejected.value
        payment.admin_note = admin_note

    async def pending_provider_payments(self) -> list[PaymentRequest]:
        result = await self.session.execute(
            select(PaymentRequest).where(
                PaymentRequest.status == PaymentStatus.pending.value,
                PaymentRequest.method.in_([PaymentMethod.plisio.value, PaymentMethod.nowpayments.value]),
            )
        )
        return list(result.scalars())
