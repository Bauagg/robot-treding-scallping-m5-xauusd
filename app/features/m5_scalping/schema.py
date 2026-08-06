import datetime as dt
from typing import Any

from pydantic import BaseModel


class TradeLogEntry(BaseModel):
    ticket: int
    symbol: str
    direction: str  # "BUY" | "SELL"
    lot: float
    entry_price: float
    sl: float
    tp: float
    signal_score: float
    entry_time: dt.datetime
    exit_price: float | None = None
    exit_time: dt.datetime | None = None
    result: str | None = None  # "WIN" | "LOSS" | None (masih open)
    pnl: float | None = None
    status: str = "OPEN"  # "OPEN" | "CLOSED"
    # Snapshot semua indikator M5+H1 saat entry (prefix "ind_"), sama cakupannya dengan
    # trade_log_full.csv hasil backtest, supaya trade live bisa dibandingkan apple-to-apple.
    indicators: dict[str, Any] = {}


class SignalCheckResult(BaseModel):
    checked_at: dt.datetime
    symbol: str
    direction: str  # "BUY" | "SELL" | "WAIT"
    signal_score: float
    order_placed: bool
    ticket: int | None = None
    message: str
