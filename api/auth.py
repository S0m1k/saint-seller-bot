import hashlib
import hmac
import json
import logging
from urllib.parse import parse_qsl

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_session
from core.models import User

logger = logging.getLogger(__name__)


def _check_signature(init_data: str) -> dict:
    """Проверяет подпись Telegram WebApp initData и возвращает распарсенные поля.

    Алгоритм: secret_key = HMAC_SHA256(key="WebAppData", msg=bot_token);
    hash = HMAC_SHA256(key=secret_key, msg=data_check_string).
    """
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise ValueError("hash отсутствует")

    data_check_string = "\n".join(f"{k}={parsed[k]}" for k in sorted(parsed))
    secret_key = hmac.new(b"WebAppData", settings.bot_token.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calc_hash, received_hash):
        raise ValueError("Неверная подпись")
    return parsed


def parse_init_data(init_data: str) -> dict:
    """Возвращает данные пользователя из проверенного initData."""
    if not settings.bot_token:
        raise ValueError("BOT_TOKEN не настроен на сервере")
    parsed = _check_signature(init_data)
    user_raw = parsed.get("user")
    if not user_raw:
        raise ValueError("user отсутствует")
    return json.loads(user_raw)


async def _upsert_user(session: AsyncSession, tg_user: dict) -> User:
    stmt = (
        sqlite_insert(User)
        .values(
            telegram_id=tg_user["id"],
            username=tg_user.get("username"),
            first_name=tg_user.get("first_name"),
            last_name=tg_user.get("last_name"),
        )
        .on_conflict_do_update(
            index_elements=[User.telegram_id],
            set_={
                "username": tg_user.get("username"),
                "first_name": tg_user.get("first_name"),
                "last_name": tg_user.get("last_name"),
                "is_active": True,
            },
        )
    )
    await session.execute(stmt)
    await session.commit()
    return await session.get(User, tg_user["id"])


async def get_current_user(
    x_telegram_init_data: str | None = Header(default=None),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Аутентификация Telegram Web App через заголовок X-Telegram-Init-Data."""
    if x_telegram_init_data:
        try:
            tg_user = parse_init_data(x_telegram_init_data)
        except Exception as e:  # noqa: BLE001
            logger.info("Отклонён initData: %s", e)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Некорректные данные авторизации Telegram",
            ) from e
        return await _upsert_user(session, tg_user)

    # Режим разработки: без Telegram, для теста каталога в обычном браузере.
    if settings.debug and settings.effective_dev_user_id:
        dev_id = settings.effective_dev_user_id
        return await _upsert_user(
            session,
            {"id": dev_id, "username": "dev", "first_name": "Dev", "last_name": "User"},
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Требуется открыть приложение внутри Telegram",
    )
