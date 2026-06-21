from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings as env_settings
from app.core.security import decrypt_secret, encrypt_secret
from app.db.models import Setting


DEFAULTS: dict[str, str] = {
    "price_multi_smart_per_gb": "9000",
    "price_multi_economy_per_gb": "2000",
    "min_new_service_balance": "50000",
    "low_balance_threshold": "10000",
    "referral_cashback_percent": "0",
    "payment_card_enabled": "true",
    "payment_plisio_enabled": "false",
    "payment_nowpayments_enabled": "false",
    "payment_stars_enabled": "false",
    "stars_to_toman_rate": "1000",
    "card_number": "",
    "card_holder": "",
    "admin_ids": "",
}

SECRET_KEYS = {"plisio_api_token", "nowpayments_api_token"}


class SettingsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, key: str, default: str | None = None) -> str | None:
        row = await self.session.get(Setting, key)
        if row is None:
            return DEFAULTS.get(key, default)
        if row.encrypted:
            return decrypt_secret(row.value)
        return row.value

    async def get_int(self, key: str, default: int = 0) -> int:
        value = await self.get(key, str(default))
        return int(value or default)

    async def get_bool(self, key: str, default: bool = False) -> bool:
        value = await self.get(key, str(default).lower())
        return str(value).lower() in {"1", "true", "yes", "on"}

    async def set(self, key: str, value: str, encrypted: bool | None = None) -> None:
        encrypted = key in SECRET_KEYS if encrypted is None else encrypted
        stored_value = encrypt_secret(value) if encrypted else value
        row = await self.session.get(Setting, key)
        if row:
            row.value = stored_value
            row.encrypted = encrypted
        else:
            self.session.add(Setting(key=key, value=stored_value, encrypted=encrypted))

    async def admin_ids(self) -> set[int]:
        configured = await self.get("admin_ids", "")
        ids = set(env_settings.env_admin_ids)
        ids.update(int(item.strip()) for item in (configured or "").split(",") if item.strip())
        return ids

    async def all_public(self) -> dict[str, str | None]:
        keys = set(DEFAULTS) | {"plisio_api_token", "nowpayments_api_token"}
        result = {}
        for key in sorted(keys):
            result[key] = "***" if key in SECRET_KEYS and await self.get(key) else await self.get(key)
        return result

