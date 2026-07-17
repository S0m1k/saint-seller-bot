"""Ручная рассылка от админа всем подписчикам бота."""
import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InputMediaPhoto
from sqlalchemy import select

from core.database import async_session
from core.models import User

logger = logging.getLogger(__name__)

CAPTION_LIMIT = 1024


async def _active_user_ids() -> list[int]:
    async with async_session() as session:
        result = await session.execute(select(User.telegram_id).where(User.is_active.is_(True)))
        return [row[0] for row in result.all()]


async def _deactivate(telegram_id: int) -> None:
    async with async_session() as session:
        user = await session.get(User, telegram_id)
        if user:
            user.is_active = False
            await session.commit()


async def _send_to_user(bot: Bot, uid: int, text: str, photos: list[str]) -> None:
    """Отправляет одному пользователю текст и/или фото."""
    if photos:
        if len(photos) == 1:
            await bot.send_photo(uid, photo=photos[0], caption=text or None)
        else:
            caption = text if text and len(text) <= CAPTION_LIMIT else None
            media = [
                InputMediaPhoto(media=fid, caption=caption if i == 0 else None)
                for i, fid in enumerate(photos)
            ]
            await bot.send_media_group(uid, media=media)
            # длинный текст не влезает в подпись — шлём отдельным сообщением
            if text and caption is None:
                await bot.send_message(uid, text)
    elif text:
        await bot.send_message(uid, text)


async def broadcast(bot: Bot, text: str, photos: list[str]) -> tuple[int, int]:
    """Рассылает сообщение всем активным подписчикам.
    Возвращает (успешно, ошибок)."""
    user_ids = await _active_user_ids()
    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await _send_to_user(bot, uid, text, photos)
            sent += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await _send_to_user(bot, uid, text, photos)
                sent += 1
            except Exception:  # noqa: BLE001
                failed += 1
        except TelegramForbiddenError:
            await _deactivate(uid)
            failed += 1
        except Exception as e:  # noqa: BLE001
            logger.warning("Рассылка: не доставлено %s: %s", uid, e)
            failed += 1
        await asyncio.sleep(0.05)  # ~20 сообщений/сек
    return sent, failed
