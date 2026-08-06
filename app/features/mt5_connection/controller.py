from fastapi import APIRouter

from app.features.mt5_connection.schema import MT5ConnectionStatus
from app.features.mt5_connection.usecase import get_status

router = APIRouter()


@router.get("/mt5/status", response_model=MT5ConnectionStatus)
def mt5_status():
    return get_status()
