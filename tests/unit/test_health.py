from app.features.health.usecase import check_health


def test_check_health_returns_ok():
    assert check_health().status == "ok"
