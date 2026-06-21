import logging
from datetime import UTC, datetime, timedelta

from aiohttp import ClientSession, ClientTimeout

from app.core.config import settings

logger = logging.getLogger(__name__)


class PasarGuardError(RuntimeError):
    pass


class PasarGuardClient:
    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        group_ids: list[int] | None = None,
        subscription_client_type: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.pasarguard_base_url).rstrip("/")
        self.username = username or settings.pasarguard_username
        self.password = password or settings.pasarguard_password
        self.group_ids = group_ids if group_ids is not None else settings.pasarguard_default_group_ids
        self.subscription_client_type = subscription_client_type or settings.pasarguard_subscription_client_type
        self._token: str | None = None
        self._token_until: datetime | None = None

    async def _request(self, method: str, path: str, **kwargs) -> dict | list | str | None:
        if not self.base_url:
            raise PasarGuardError("PASARGUARD_BASE_URL is not configured")
        headers = kwargs.pop("headers", {})
        if path != "/api/admin/token":
            headers["Authorization"] = f"Bearer {await self.token()}"
        async with ClientSession(timeout=ClientTimeout(total=30)) as session:
            async with session.request(method, f"{self.base_url}{path}", headers=headers, **kwargs) as response:
                text = await response.text()
                if response.status >= 400:
                    raise PasarGuardError(f"PasarGuard {method} {path} failed: {response.status} {text[:300]}")
                if not text:
                    return None
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    return await response.json()
                return text

    async def token(self) -> str:
        if self._token and self._token_until and self._token_until > datetime.now(UTC):
            return self._token
        payload = {"username": self.username, "password": self.password}
        data = await self._request("POST", "/api/admin/token", data=payload)
        if not isinstance(data, dict) or "access_token" not in data:
            raise PasarGuardError("PasarGuard token response did not include access_token")
        self._token = str(data["access_token"])
        self._token_until = datetime.now(UTC) + timedelta(minutes=20)
        return self._token

    async def create_user(self, username: str, data_limit_bytes: int = 0, expire: int = 0) -> dict:
        payload = {
            "username": username,
            "status": "active",
            "expire": expire,
            "data_limit": data_limit_bytes,
            "data_limit_reset_strategy": "no_reset",
            "group_ids": self.group_ids,
            "note": "Created by Telegram sales bot",
        }
        data = await self._request("POST", "/api/user", json=payload)
        if not isinstance(data, dict):
            raise PasarGuardError("PasarGuard create_user returned invalid payload")
        return data

    async def get_user(self, username: str) -> dict:
        data = await self._request("GET", f"/api/user/{username}")
        if not isinstance(data, dict):
            raise PasarGuardError("PasarGuard get_user returned invalid payload")
        return data

    async def set_disabled(self, username: str, disabled: bool) -> dict:
        data = await self._request("PUT", f"/api/user/{username}/disabled", json={"disabled": disabled})
        if not isinstance(data, dict):
            raise PasarGuardError("PasarGuard set_disabled returned invalid payload")
        return data

    async def delete_user(self, username: str) -> None:
        await self._request("DELETE", f"/api/user/{username}")

    async def subscription_url(self, user_id: int, fallback: str | None = None) -> str:
        client_type = self.subscription_client_type
        data = await self._request("GET", f"/api/user/{user_id}/subscription/{client_type}")
        if isinstance(data, str) and data.startswith(("http://", "https://")):
            return data
        return fallback or f"{self.base_url}/sub/{user_id}/{client_type}"

    async def total_used_mb(self, username: str) -> int:
        user = await self.get_user(username)
        used_bytes = int(user.get("used_traffic") or user.get("lifetime_used_traffic") or 0)
        return used_bytes // (1024 * 1024)
