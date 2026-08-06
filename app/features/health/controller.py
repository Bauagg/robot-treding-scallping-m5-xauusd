from fastapi import APIRouter

from app.features.health.schema import HealthStatus
from app.features.health.usecase import check_health

router = APIRouter()


@router.get("/health", response_model=HealthStatus)
def health():
    return check_health()
