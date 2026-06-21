from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import TransactionKind, User, WalletTransaction
from app.services.settings import SettingsService


class WalletService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, user: User, amount: int, kind: TransactionKind, description: str, metadata: dict | None = None) -> None:
        user.wallet_balance_toman += amount
        self.session.add(
            WalletTransaction(
                user_id=user.id,
                amount_toman=amount,
                kind=kind.value,
                description=description,
                metadata_=metadata or {},
            )
        )

    async def deduct(
        self,
        user: User,
        amount: int,
        description: str,
        metadata: dict | None = None,
        allow_negative: bool = False,
        kind: TransactionKind = TransactionKind.traffic_charge,
    ) -> bool:
        if amount <= 0:
            return True
        if user.wallet_balance_toman < amount and not allow_negative:
            return False
        user.wallet_balance_toman -= amount
        self.session.add(
            WalletTransaction(
                user_id=user.id,
                amount_toman=-amount,
                kind=kind.value,
                description=description,
                metadata_=metadata or {},
            )
        )
        return True

    async def pay_referral_cashback(self, spender: User, spent_amount: int) -> None:
        if not spender.referred_by_id or spent_amount <= 0:
            return
        percent = await SettingsService(self.session).get_int("referral_cashback_percent", 0)
        cashback = spent_amount * percent // 100
        if cashback <= 0:
            return
        inviter = await self.session.get(User, spender.referred_by_id)
        if inviter:
            await self.add(
                inviter,
                cashback,
                TransactionKind.referral_cashback,
                f"کش‌بک معرفی از کاربر {spender.telegram_id}",
                {"spender_id": spender.id, "spent_amount_toman": spent_amount},
            )
