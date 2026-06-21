from aiogram.types import User as TgUser
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, tg_user: TgUser, referral_code: str | None = None) -> User:
        result = await self.session.execute(select(User).where(User.telegram_id == tg_user.id))
        user = result.scalar_one_or_none()
        if user:
            user._was_created = False
            user.username = tg_user.username
            user.full_name = tg_user.full_name
            return user

        referrer = None
        if referral_code and referral_code.startswith("ref_"):
            try:
                referrer_id = int(referral_code.removeprefix("ref_"))
                referrer = (await self.session.execute(select(User).where(User.telegram_id == referrer_id))).scalar_one_or_none()
            except ValueError:
                referrer = None

        user = User(
            telegram_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name,
            referred_by_id=referrer.id if referrer else None,
        )
        try:
            async with self.session.begin_nested():
                self.session.add(user)
                await self.session.flush()
            user._was_created = True
            return user
        except IntegrityError:
            result = await self.session.execute(select(User).where(User.telegram_id == tg_user.id))
            user = result.scalar_one()
            user._was_created = False
            user.username = tg_user.username
            user.full_name = tg_user.full_name
            return user

    async def by_telegram_id(self, telegram_id: int) -> User | None:
        return (await self.session.execute(select(User).where(User.telegram_id == telegram_id))).scalar_one_or_none()
