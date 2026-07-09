import asyncio
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import FSInputFile
from sqlalchemy import select

from core.config import settings
from core.database import async_session
from core.models import Product, User
from bot.keyboards.common import shop_inline_keyboard

logger = logging.getLogger(__name__)


def _format_product_caption(product: Product) -> str:
    lines = [f"🆕 <b>Новый товар</b>\n", f"<b>{product.name}</b>"]
    if product.brand:
        lines.append(f"Бренд: {product.brand}")
    if product.size:
        lines.append(f"Размер: {product.size}")
    if product.condition:
        lines.append(f"Состояние: {product.condition}")
    if product.price is not None:
        lines.append(f"Цена: {product.price:g} ₽")
    if product.description:
        lines.append(f"\n{product.description}")
    return "\n".join(lines)


async def broadcast_new_product(bot: Bot, product: Product) -> int:
    """Рассылает всем активным пользователям (кроме админов) уведомление о
    новом товаре с первым фото и кнопкой перехода в каталог.
    Возвращает число успешных отправок."""
    caption = _format_product_caption(product)
    keyboard = shop_inline_keyboard()

    photo: FSInputFile | None = None
    if product.photos:
        abs_path = Path(settings.media_dir) / product.photos[0].file_path
        if abs_path.exists():
            photo = FSInputFile(abs_path)

    async with async_session() as session:
        result = await session.execute(select(User.telegram_id).where(User.is_active.is_(True)))
        user_ids = [row[0] for row in result.all()]

    admin_ids = set(settings.admin_id_list)
    sent = 0
    for uid in user_ids:
        if uid in admin_ids:
            continue
        try:
            if photo is not None:
                await bot.send_photo(uid, photo=photo, caption=caption, reply_markup=keyboard)
            else:
                await bot.send_message(uid, caption, reply_markup=keyboard)
            sent += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
        except TelegramForbiddenError:
            await _deactivate_user(uid)
        except Exception as e:  # noqa: BLE001
            logger.warning("Не удалось отправить уведомление %s: %s", uid, e)
        await asyncio.sleep(0.05)  # ~20 сообщений/сек — в пределах лимитов Telegram

    return sent


async def _deactivate_user(telegram_id: int) -> None:
    async with async_session() as session:
        user = await session.get(User, telegram_id)
        if user:
            user.is_active = False
            await session.commit()
