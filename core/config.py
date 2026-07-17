from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Конфигурация приложения. Все значения читаются из .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram
    bot_token: str = ""
    admin_ids: str = ""  # список id через запятую
    manager_username: str = ""  # username менеджера (без @) для оформления заказа

    # Web App
    webapp_url: str = "http://localhost:8000"

    # API / сервер
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # База данных
    database_url: str = f"sqlite+aiosqlite:///{(BASE_DIR / 'saint_seller.db').as_posix()}"

    # Медиа
    media_dir: Path = BASE_DIR / "media"

    # Статистика / расписание
    timezone: str = "Europe/Moscow"
    daily_stats_hour: int = 21  # час (по локальному TZ) отправки дневной статистики

    # Разработка
    debug: bool = False
    dev_user_id: int | None = None

    @property
    def admin_id_list(self) -> list[int]:
        return [int(x) for x in self.admin_ids.replace(" ", "").split(",") if x.strip()]

    def is_admin(self, telegram_id: int) -> bool:
        return telegram_id in self.admin_id_list

    @property
    def effective_dev_user_id(self) -> int | None:
        if self.dev_user_id:
            return self.dev_user_id
        ids = self.admin_id_list
        return ids[0] if ids else None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
