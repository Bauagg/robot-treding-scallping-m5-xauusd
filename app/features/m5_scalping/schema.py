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
    is_exhausted: bool = False  # legacy (selalu False sejak 2026-09-01) -- exhaustion skrg di-SKIP total, tidak pernah masuk ke trade log sbg entry tercatat; kolom dipertahankan utk kompatibilitas baca CSV lama
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


class DrawdownState(BaseModel):
    """Baseline equity buat hitung drawdown harian/bulanan/total. Persisted ke JSON supaya
    tahan restart robot -- tanpa ini, peak equity & baseline hari/bulan berjalan akan
    ke-reset tiap kali app restart, bikin kill-switch gak akurat."""

    peak_equity: float
    day_key: str  # "YYYY-MM-DD" (UTC), baseline reset kalau tanggal berubah
    day_start_equity: float
    month_key: str  # "YYYY-MM" (UTC), baseline reset kalau bulan berubah
    month_start_equity: float
    total_dd_paused: bool = False
    # Override manual dari fitur bot_telegram (command /start_tuning_harian /start_tuning_bulanan
    # + tombol "Lanjutkan Trading") -- begitu True, _check_drawdown_guard() skip pengecekan
    # threshold harian/bulanan meski masih breach, TANPA menyentuh baseline/peak. Otomatis
    # ke-reset False lagi begitu day_key/month_key berganti (lihat _check_drawdown_guard),
    # jadi override ini bukan bypass permanen -- cuma "izinkan lanjut sampai reset otomatis
    # berikutnya". Total drawdown TIDAK PERNAH punya override (sengaja, lihat kelas ini &
    # _check_drawdown_guard -- itu sinyal akun rusak, harus direset manual hapus file).
    daily_override_active: bool = False
    monthly_override_active: bool = False
