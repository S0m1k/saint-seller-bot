from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from core.config import settings


def _webapp_https() -> bool:
    """Telegram открывает Web App только по HTTPS. Локально (http) кнопки
    web_app недопустимы — иначе Telegram отклонит отправку сообщения."""
    return settings.webapp_url.lower().startswith("https://")


def shop_reply_keyboard() -> ReplyKeyboardMarkup:
    """Кнопка внизу экрана, открывающая каталог как Telegram Web App.
    В dev-режиме (http) — обычная кнопка без web_app, чтобы сообщение отправилось."""
    if _webapp_https():
        button = KeyboardButton(text="🛍 Открыть каталог", web_app=WebAppInfo(url=settings.webapp_url))
    else:
        button = KeyboardButton(text="🛍 Открыть каталог")
    return ReplyKeyboardMarkup(keyboard=[[button]], resize_keyboard=True)


def shop_inline_keyboard() -> InlineKeyboardMarkup | None:
    """Inline-кнопка каталога для рассылок. Возвращает None в dev-режиме (http),
    когда web_app-кнопку прикрепить нельзя."""
    if not _webapp_https():
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛍 Смотреть в каталоге", web_app=WebAppInfo(url=settings.webapp_url))]
        ]
    )
