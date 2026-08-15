from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.features.bot_telegram.controller import start_bot, stop_bot
from app.features.m5_scalping.controller import start_polling, stop_polling
from app.features.mt5_connection.usecase import connect, disconnect


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    connect()
    start_polling()
    await start_bot()

    yield

    await stop_bot()
    stop_polling()
    disconnect()


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
app.include_router(api_router, prefix="/api/v1")
