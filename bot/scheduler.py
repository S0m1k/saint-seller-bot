"""Фоновые задачи по расписанию: дневная статистика админам."""
import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import BufferedInputFile

from core.config import settings
from core.database import async_session
from bot.stats import collect_stats, fetch_users, format_stats, local_day_bounds_utc, users_to_xlsx

logger = logging.getLogger(__name__)


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.timezone)
    except Exception:  # noqa: BLE001
        return ZoneInfo("UTC")


def _seconds_until_next_run() -> float:
    tz = _tz()
    now = datetime.now(tz)
    target = now.replace(hour=settings.daily_stats_hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


async def send_daily_stats(bot: Bot) -> None:
    """Считает статистику за сегодня и рассылает админам (+ Excel новых за день)."""
    async with async_session() as session:
        stats = await collect_stats(session)
        today_start, today_end = local_day_bounds_utc(0)
        new_users = await fetch_users(session, today_start, today_end)

    date_str = datetime.now(_tz()).strftime("%d.%m.%Y")
    text = format_stats(stats, title=f"📊 <b>Итоги дня {date_str}</b>")
    text += f"\n\n🆕 Пришло за сегодня: <b>{len(new_users)}</b>"

    document = None
    if new_users:
        xlsx = users_to_xlsx(new_users)
        document = BufferedInputFile(xlsx, filename=f"new_subscribers_{date_str}.xlsx")

    for admin_id in settings.admin_id_list:
        try:
            await bot.send_message(admin_id, text)
            if document is not None:
                # BufferedInputFile можно переиспользовать для каждого админа
                await bot.send_document(admin_id, document)
        except Exception as e:  # noqa: BLE001
            logger.warning("Не удалось отправить дневную статистику %s: %s", admin_id, e)


async def daily_stats_loop(bot: Bot) -> None:
    """Бесконечный цикл: спит до daily_stats_hour и шлёт статистику."""
    logger.info(
        "Планировщик статистики запущен (ежедневно в %02d:00 %s)",
        settings.daily_stats_hour, settings.timezone,
    )
    while True:
        delay = _seconds_until_next_run()
        await asyncio.sleep(delay)
        try:
            await send_daily_stats(bot)
            logger.info("Дневная статистика отправлена админам")
        except Exception as e:  # noqa: BLE001
            logger.exception("Ошибка отправки дневной статистики: %s", e)
        await asyncio.sleep(60)  # чтобы не сработать дважды в ту же минуту
