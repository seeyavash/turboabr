import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import ClassVar

from aiohttp import ClientError, ClientSession, ClientTimeout

logger = logging.getLogger(__name__)


class PasarGuardError(RuntimeError):
    pass


@dataclass
class CachedToken:
    value: str
    until: datetime


class PasarGuardClient:
    _token_cache: ClassVar[dict[str, CachedToken]] = {}

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        group_ids: list[int] | None = None,
        subscription_client_type: str | None = None,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.username = username or ""
        self.password = password or ""
        self.group_ids = group_ids if group_ids is not None else []
        self.subscription_client_type = subscription_client_type or "v2ray"

    @property
    def cache_key(self) -> str:
        raw = f"{self.base_url}|{self.username}|{self.password}"
        return sha256(raw.encode()).hexdigest()

    async def _request(self, method: str, path: str, **kwargs) -> dict | list | str | None:
        if not self.base_url:
            raise PasarGuardError("PasarGuard panel is not configured")
        auth_retry = kwargs.pop("_auth_retry", False)
        headers = dict(kwargs.pop("headers", {}))
        if path != "/api/admin/token":
            headers["Authorization"] = f"Bearer {await self.token()}"
        try:
            async with (
                ClientSession(timeout=ClientTimeout(total=30)) as session,
                session.request(
                    method, f"{self.base_url}{path}", headers=headers, **kwargs
                ) as response,
            ):
                if response.status == 401 and path != "/api/admin/token" and not auth_retry:
                    self._token_cache.pop(self.cache_key, None)
                    return await self._request(method, path, _auth_retry=True, **kwargs)
                text = await response.text()
                if response.status >= 400:
                    raise PasarGuardError(
                        f"PasarGuard {method} {path} failed: HTTP {response.status}"
                    )
                if not text:
                    return None
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    return await response.json()
                return text
        except (ClientError, TimeoutError, ValueError) as exc:
            raise PasarGuardError(
                f"PasarGuard {method} {path} failed: {type(exc).__name__}"
            ) from exc

    async def token(self) -> str:
        cached = self._token_cache.get(self.cache_key)
        if cached and cached.until > datetime.now(UTC):
            return cached.value
        payload = {"username": self.username, "password": self.password}
        data = await self._request("POST", "/api/admin/token", data=payload)
        if not isinstance(data, dict) or "access_token" not in data:
            raise PasarGuardError("PasarGuard token response did not include access_token")
        token = str(data["access_token"])
        self._token_cache[self.cache_key] = CachedToken(
            token, datetime.now(UTC) + timedelta(hours=23)
        )
        return token

    async def create_user(self, username: str, data_limit_bytes: int = 0, expire: int = 0) -> dict:
        if not self.group_ids:
            raise PasarGuardError(
                "برای این پنل هیچ گروهی تنظیم نشده است. از مدیریت پنل‌ها برای این پنل یک تمپلیت با شناسه گروه معتبر اضافه کنید."
            )
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
        data = await self._request(
            "PUT", f"/api/user/{username}/disabled", json={"disabled": disabled}
        )
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
        # A missing field is not proof of zero usage. Never fall back from an
        # explicit zero to a lifetime counter with a different billing baseline.
        raw = user.get("used_traffic")
        if raw is None:
            raw = user.get("lifetime_used_traffic")
        try:
            if raw is None or isinstance(raw, bool):
                raise ValueError("missing traffic")
            used_bytes = int(raw)
            if used_bytes < 0:
                raise ValueError("negative traffic")
        except (TypeError, ValueError) as exc:
            raise PasarGuardError("PasarGuard returned an invalid traffic counter") from exc
        return used_bytes // (1024 * 1024)
