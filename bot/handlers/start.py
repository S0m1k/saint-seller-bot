from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from core.database import async_session
from core.models import User
from bot.keyboards.common import shop_reply_keyboard

router = Router()

WELCOME = (
    "👋 Добро пожаловать в <b>Saint Seller</b>!\n\n"
    "Здесь ты найдёшь отобранные вещи: бренды, размеры, состояние — всё в каталоге.\n\n"
    "Нажми <b>«🛍 Открыть каталог»</b>, чтобы посмотреть товары, "
    "добавить в избранное и оформить заказ."
)


async def upsert_user(message: Message) -> None:
    """Регистрирует/обновляет пользователя, не затирая is_active."""
    u = message.from_user
    async with async_session() as session:
        stmt = (
            sqlite_insert(User)
            .values(
                telegram_id=u.id,
                username=u.username,
                first_name=u.first_name,
                last_name=u.last_name,
            )
            .on_conflict_do_update(
                index_elements=[User.telegram_id],
                set_={
                    "username": u.username,
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "is_active": True,
                },
            )
        )
        await session.execute(stmt)
        await session.commit()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await upsert_user(message)
    await message.answer(WELCOME, reply_markup=shop_reply_keyboard())
