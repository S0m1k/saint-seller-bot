from aiogram import Router

from bot.handlers import admin, start


def get_router() -> Router:
    router = Router()
    router.include_router(admin.router)
    router.include_router(start.router)
    return router
