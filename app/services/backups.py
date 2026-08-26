import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from aiogram import Bot
from aiogram.types import BufferedInputFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.settings import SettingsService


@dataclass(frozen=True)
class DatabaseBackup:
    filename: str
    data: bytes


def pg_dump_url() -> str:
    return settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


async def create_database_backup() -> DatabaseBackup:
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"turboabr_db_{timestamp}.dump"
    with TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / filename
        process = await asyncio.create_subprocess_exec(
            "pg_dump",
            "--format=custom",
            "--no-owner",
            "--no-acl",
            "--file",
            str(path),
            pg_dump_url(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            error = stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(error or "pg_dump failed")
        return DatabaseBackup(filename=filename, data=path.read_bytes())


async def send_database_backup_to_admins(bot: Bot, session: AsyncSession, caption: str) -> int:
    admin_ids = await SettingsService(session).admin_ids()
    if not admin_ids:
        return 0
    backup = await create_database_backup()
    sent = 0
    for admin_id in admin_ids:
        try:
            await bot.send_document(
                admin_id,
                BufferedInputFile(backup.data, filename=backup.filename),
                caption=caption,
            )
            sent += 1
        except Exception:
            continue
    return sent
