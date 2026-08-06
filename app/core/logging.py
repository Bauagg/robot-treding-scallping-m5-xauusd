import sys

from loguru import logger

from app.core.config import settings


def setup_logging() -> None:
    logger.remove()
    logger.add(sys.stdout, level=settings.log_level, backtrace=False, diagnose=False)
    logger.add(
        "logs/app.log",
        level=settings.log_level,
        rotation="10 MB",
        retention="14 days",
        enqueue=True,
    )


__all__ = ["logger", "setup_logging"]
