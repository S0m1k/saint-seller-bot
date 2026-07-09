from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import settings

engine = create_async_engine(settings.database_url, echo=False, future=True)

async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    """Создаёт таблицы, если их ещё нет, и применяет лёгкие миграции."""
    from core import models  # noqa: F401  (регистрация моделей)

    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
        await _ensure_columns(conn)


async def _ensure_columns(conn) -> None:
    """Добавляет недостающие колонки в существующие таблицы (SQLite)."""
    from sqlalchemy import text

    result = await conn.execute(text("PRAGMA table_info(products)"))
    columns = {row[1] for row in result.fetchall()}
    if "stock" not in columns:
        await conn.execute(
            text("ALTER TABLE products ADD COLUMN stock INTEGER NOT NULL DEFAULT 1")
        )


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
