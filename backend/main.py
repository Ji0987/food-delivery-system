"""FastAPI 應用進入點。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
import sys


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.database import engine
from backend.models import Base
from backend.routers import admin, auth, cart, delivery, menu, orders

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    get_settings().require_jwt_secret()
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="餐點外送系統 API",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(auth.router)
app.include_router(menu.router)
app.include_router(cart.router)
# delivery 必須先於 orders 註冊，避免 /orders/{order_id} 攔截 /orders/available。
app.include_router(delivery.router)
app.include_router(orders.router)
app.include_router(admin.router)


@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "food-delivery-api"}


# 前端靜態檔掛載於 /app（與 API 同源，避免 CORS）。
# 掛在子路徑而非根路徑，以保留 GET / 健康檢查與既有測試。
if FRONTEND_DIR.is_dir():
    app.mount(
        "/app",
        StaticFiles(directory=FRONTEND_DIR, html=True),
        name="frontend",
    )
