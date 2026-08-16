import datetime as dt
from typing import Literal

from pydantic import BaseModel

ReportPeriod = Literal["daily", "weekly", "monthly"]
DrawdownKind = Literal["DAILY", "MONTHLY", "TOTAL"]


class DailyPnl(BaseModel):
    date: str  # "YYYY-MM-DD"
    pnl: float
    trades: int


class TradeSummary(BaseModel):
    period: ReportPeriod
    period_label: str
    range_start: dt.datetime
    range_end: dt.datetime
    total_trades: int
    wins: int
    losses: int
    open_trades: int
    win_rate_pct: float
    total_pnl: float
    avg_pnl: float
    best_trade_pnl: float | None = None
    worst_trade_pnl: float | None = None
    # Portofolio-style: kurva equity kumulatif dalam periode (basis 0, bukan equity akun
    # absolut -- laporan cuma peduli PERGERAKAN dalam periode itu, bukan saldo total akun).
    equity_curve: list[float] = []
    max_drawdown_pct: float = 0.0
    # Perbandingan vs periode sebelumnya yang durasinya sama (mis. 7 hari sebelum 7 hari ini)
    prev_period_pnl: float | None = None
    return_pct: float | None = None  # total_pnl / |prev_period_pnl basis| kalau ada, else None
    daily_breakdown: list[DailyPnl] = []


class DrawdownAlertEvent(BaseModel):
    kind: DrawdownKind
    reason: str
    triggered_at: dt.datetime
    equity: float
    dd_pct: float
