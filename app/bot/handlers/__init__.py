from aiogram import Router

from app.bot.handlers import admin, user


def build_router() -> Router:
    router = Router()
    router.include_router(admin.router)
    router.include_router(user.router)
    return router

