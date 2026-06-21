from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    bot_token: str = Field(default="")
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/vpnbot")
    redis_url: str = Field(default="redis://localhost:6379/0")
    env_admin_ids: list[int] = Field(default_factory=list)
    secret_key: str = Field(default="change-me")
    support_username: str = Field(default="kasrazandi")
    log_level: str = Field(default="INFO")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @field_validator("env_admin_ids", mode="before")
    @classmethod
    def parse_int_list(cls, value: int | str | list[int] | None) -> list[int]:
        if not value:
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, list):
            return [int(item) for item in value]
        return [int(item.strip()) for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
