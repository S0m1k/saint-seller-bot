import uuid
from pathlib import Path

from aiogram import Bot

from core.config import settings

PRODUCTS_SUBDIR = "products"


async def save_product_photo(bot: Bot, file_id: str, product_id: int) -> str:
    """Скачивает фото из Telegram в media/products/<product_id>/ и возвращает
    относительный путь (для хранения в БД и раздачи через /media)."""
    rel_dir = f"{PRODUCTS_SUBDIR}/{product_id}"
    abs_dir = Path(settings.media_dir) / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.jpg"
    abs_path = abs_dir / filename

    await bot.download(file_id, destination=abs_path)

    return f"{rel_dir}/{filename}"
