from fastapi import APIRouter

from app.features.health.controller import router as health_router
from app.features.mt5_connection.controller import router as mt5_connection_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["health"])
api_router.include_router(mt5_connection_router, tags=["mt5"])
