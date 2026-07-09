from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from core.config import settings


def shop_reply_keyboard() -> ReplyKeyboardMarkup:
    """Кнопка внизу экрана, открывающая каталог как Telegram Web App."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Открыть каталог", web_app=WebAppInfo(url=settings.webapp_url))]
        ],
        resize_keyboard=True,
    )


def shop_inline_keyboard() -> InlineKeyboardMarkup:
    """Inline-кнопка, открывающая каталог (используется в рассылках)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛍 Смотреть в каталоге", web_app=WebAppInfo(url=settings.webapp_url))]
        ]
    )
