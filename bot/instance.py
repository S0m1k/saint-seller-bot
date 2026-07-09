from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from core.config import settings

_bot: Bot | None = None


def get_bot() -> Bot | None:
    """Единый экземпляр Bot для отправки сообщений.

    Возвращает None, если BOT_TOKEN не задан (например, локальная разработка
    без реального бота). Опрос (polling) ведёт только процесс бота, а API
    использует этот же экземпляр только для отправки уведомлений — конфликтов нет.
    """
    global _bot
    if _bot is None and settings.bot_token:
        _bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    return _bot
