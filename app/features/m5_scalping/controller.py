"""Loop polling m5_scalping: tiap interval, sinkronkan trade closed lalu cek sinyal & order
kalau ada. Tidak diekspos lewat HTTP — main.py cukup panggil start_polling()/stop_polling()
saat startup/shutdown app."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.logging import logger
from app.features.m5_scalping.usecase import check_signal_and_trade, sync_closed_trades

POLLING_INTERVAL_SECONDS = 60
JOB_ID = "m5_scalping_poll"

_scheduler = AsyncIOScheduler()


def _poll_job() -> None:
    try:
        sync_closed_trades()
        result = check_signal_and_trade()
        if result.order_placed:
            logger.info(f"[poll] Order ditempatkan: {result.direction} ticket={result.ticket}")
    except Exception:
        logger.exception("[poll] Gagal cek sinyal / eksekusi order")


def start_polling() -> None:
    _scheduler.add_job(_poll_job, "interval", seconds=POLLING_INTERVAL_SECONDS, id=JOB_ID)
    _scheduler.start()
    logger.info(f"Polling m5_scalping tiap {POLLING_INTERVAL_SECONDS} detik")


def stop_polling() -> None:
    _scheduler.shutdown(wait=False)
