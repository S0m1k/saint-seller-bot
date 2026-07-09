from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from core.database import async_session
from core.models import User
from bot.keyboards.common import shop_inline_keyboard, shop_reply_keyboard

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
    inline = shop_inline_keyboard()
    if inline is not None:
        # Inline-кнопка отдаёт initData корректно (в отличие от reply-клавиатуры).
        # Заодно убираем возможную устаревшую reply-клавиатуру.
        await message.answer(WELCOME, reply_markup=ReplyKeyboardRemove())
        await message.answer("Каталог открывается кнопкой ниже 👇", reply_markup=inline)
    else:
        # dev/http: web_app-кнопки недоступны, показываем обычную клавиатуру
        await message.answer(WELCOME, reply_markup=shop_reply_keyboard())


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    await upsert_user(message)
    u = message.from_user
    await message.answer(
        f"🆔 Ваш Telegram ID: <code>{u.id}</code>\n"
        f"Username: {'@' + u.username if u.username else '—'}"
    )
