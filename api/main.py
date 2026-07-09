from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.config import BASE_DIR, settings
from api.routers import account, cart, catalog, favorites, orders

WEBAPP_DIR = BASE_DIR / "webapp"

app = FastAPI(title="Saint Seller", docs_url="/api/docs", openapi_url="/api/openapi.json")

# CORS: Telegram WebView открывает страницу с нашего же домена, но во время
# разработки удобно разрешить любые источники.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API-роутеры
app.include_router(catalog.router)
app.include_router(favorites.router)
app.include_router(cart.router)
app.include_router(orders.router)
app.include_router(account.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/config")
async def public_config():
    """Публичная конфигурация для веб-приложения."""
    return {"manager_username": settings.manager_username}


# Медиа (фото товаров) и статика веб-приложения
Path(settings.media_dir).mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(settings.media_dir)), name="media")
app.mount("/static", StaticFiles(directory=str(WEBAPP_DIR / "static")), name="static")


@app.get("/")
async def index():
    return FileResponse(WEBAPP_DIR / "index.html")
