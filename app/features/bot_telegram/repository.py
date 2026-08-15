import csv
import datetime as dt

from telegram import Bot, InlineKeyboardMarkup

from app.core.config import settings
from app.features.m5_scalping.repository import TRADE_LOG_PATH

_bot = Bot(token=settings.telegram_token_xauusd)


async def send_message(text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    await _bot.send_message(
        chat_id=settings.telegram_chat_id,
        text=text,
        reply_markup=reply_markup,
    )


def _parse_dt(value: str) -> dt.datetime | None:
    if not value:
        return None
    return dt.datetime.fromisoformat(value)


def get_trades_in_range(start: dt.datetime, end: dt.datetime) -> list[dict]:
    """Baca TRADE_LOG_PATH (m5_scalping.repository, nama file dari Settings), filter baris
    yang entry_time-nya jatuh di [start, end). Dipakai buat susun laporan periodik -- baca
    file yang sama persis dgn yang ditulis m5_scalping.usecase.check_signal_and_trade, bukan
    duplikat data, supaya laporan selalu konsisten dgn histori trade live yang sesungguhnya."""
    if not TRADE_LOG_PATH.exists():
        return []

    rows = []
    with open(TRADE_LOG_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            entry_time = _parse_dt(row["entry_time"])
            if entry_time is None:
                continue
            if start <= entry_time < end:
                rows.append(row)
    return rows
