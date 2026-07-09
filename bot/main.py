import logging

from aiogram import Dispatcher
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo

from core.config import settings
from bot.handlers import get_router
from bot.instance import get_bot

logger = logging.getLogger(__name__)


async def _setup_bot_profile(bot) -> None:
    await bot.set_my_commands([
        BotCommand(command="start", description="Открыть магазин"),
        BotCommand(command="admin", description="Админ-панель"),
    ])
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Каталог", web_app=WebAppInfo(url=settings.webapp_url))
        )
    except Exception as e:  # noqa: BLE001  (localhost url в деве не примет Telegram)
        logger.warning("Не удалось установить кнопку меню Web App: %s", e)


async def run_bot() -> None:
    bot = get_bot()
    if bot is None:
        logger.warning("BOT_TOKEN не задан — бот не запущен (работает только API).")
        return

    dp = Dispatcher()
    dp.include_router(get_router())

    await _setup_bot_profile(bot)
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот запущен, начинаю polling...")
    await dp.start_polling(bot)
