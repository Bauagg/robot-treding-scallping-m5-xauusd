from app.features.health.schema import HealthStatus


def check_health() -> HealthStatus:
    return HealthStatus(status="ok")
