"""Единая точка запуска: поднимает FastAPI (webapp + API) и Telegram-бота
в одном процессе/событийном цикле."""
import asyncio
import logging

import uvicorn

from core.config import settings
from core.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("saint_seller")


async def main() -> None:
    await init_db()

    from api.main import app
    from bot.main import run_bot

    config = uvicorn.Config(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    logger.info("Запуск: API на %s:%s, WebApp URL=%s",
                settings.api_host, settings.api_port, settings.webapp_url)

    await asyncio.gather(server.serve(), run_bot())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Остановлено.")
