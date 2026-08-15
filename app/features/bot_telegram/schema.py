import datetime as dt
from typing import Literal

from pydantic import BaseModel

ReportPeriod = Literal["daily", "weekly", "monthly"]
DrawdownKind = Literal["DAILY", "MONTHLY", "TOTAL"]


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


class DrawdownAlertEvent(BaseModel):
    kind: DrawdownKind
    reason: str
    triggered_at: dt.datetime
    equity: float
    dd_pct: float
