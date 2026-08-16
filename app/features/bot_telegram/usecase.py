import datetime as dt
import io

import matplotlib

matplotlib.use("Agg")  # backend non-interaktif, wajib sebelum import pyplot (server tanpa display)
import matplotlib.pyplot as plt
import MetaTrader5 as mt5
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.core.config import settings
from app.core.logging import logger
from app.features.bot_telegram.repository import get_trades_in_range, send_message, send_photo
from app.features.bot_telegram.schema import DailyPnl, DrawdownAlertEvent, DrawdownKind, ReportPeriod, TradeSummary
from app.features.m5_scalping.repository import load_drawdown_state, save_drawdown_state
from app.features.m5_scalping.usecase import (
    build_signal_row,
    compute_daily_dd_pct,
    compute_monthly_dd_pct,
    compute_total_dd_pct,
    has_opposing_order_block,
    load_params,
)
from app.utils.signals import Signal, generate_signal_v12
from app.utils.signals.decision import _check_htf_alignment

# Snapshot in-memory (bukan persisted) status breach terakhir tiap jenis drawdown -- dipakai
# check_and_alert_drawdown() buat deteksi transisi False->True supaya alert cuma dikirim SEKALI
# per kejadian, bukan tiap 30 detik selama masih breach. Restart app boleh reset ini ke False
# semua (re-alert sekali kalau kebetulan masih breach saat restart) -- itu OK, lebih aman drpd
# ketinggalan alert daripada spam ulang.
_last_alert_state = {"DAILY": False, "MONTHLY": False, "TOTAL": False}


def is_authorized_user(user_id: int) -> bool:
    return user_id == settings.telegram_allowed_user_id


def _period_range(period: ReportPeriod, now: dt.datetime) -> tuple[dt.datetime, dt.datetime, str]:
    """Return (start, end, label) rentang UTC utk periode laporan.
    daily -> hari kalender UTC SEBELUMNYA, weekly -> 7 hari kalender UTC terakhir
    (Senin-Minggu sebelumnya), monthly -> bulan kalender UTC sebelumnya."""
    today = now.date()
    if period == "daily":
        end_date = today
        start_date = end_date - dt.timedelta(days=1)
        label = f"Harian ({start_date.isoformat()})"
    elif period == "weekly":
        # Senin minggu ini
        this_monday = today - dt.timedelta(days=today.weekday())
        start_date = this_monday - dt.timedelta(days=7)
        end_date = this_monday
        label = f"Mingguan ({start_date.isoformat()} s/d {(end_date - dt.timedelta(days=1)).isoformat()})"
    else:  # monthly
        first_of_this_month = today.replace(day=1)
        end_date = first_of_this_month
        last_month_end = first_of_this_month - dt.timedelta(days=1)
        start_date = last_month_end.replace(day=1)
        label = f"Bulanan ({start_date.strftime('%Y-%m')})"

    start = dt.datetime.combine(start_date, dt.time.min, tzinfo=dt.UTC)
    end = dt.datetime.combine(end_date, dt.time.min, tzinfo=dt.UTC)
    return start, end, label


def _closed_sorted(rows: list[dict]) -> list[dict]:
    closed = [r for r in rows if r["status"] == "CLOSED" and r["pnl"]]
    closed.sort(key=lambda r: r["exit_time"] or r["entry_time"])
    return closed


def _max_drawdown_pct(equity_curve: list[float], initial_capital: float) -> float:
    """Drawdown dalam periode laporan -- basis peak KUMULATIF (mulai dari initial_capital,
    bukan 0), konsisten dgn cara m5_scalping.usecase menghitung drawdown live."""
    if not equity_curve:
        return 0.0
    peak = initial_capital
    worst = 0.0
    for equity in equity_curve:
        peak = max(peak, equity)
        if peak > 0:
            worst = min(worst, (equity - peak) / peak * 100)
    return worst


def build_report(period: ReportPeriod, now: dt.datetime) -> TradeSummary:
    start, end, label = _period_range(period, now)
    rows = get_trades_in_range(start, end)

    total_trades = len(rows)
    closed = _closed_sorted(rows)
    wins = sum(1 for r in closed if r["result"] == "WIN")
    losses = sum(1 for r in closed if r["result"] == "LOSS")
    open_trades = total_trades - len(closed)

    pnls = [float(r["pnl"]) for r in closed]
    total_pnl = sum(pnls)
    avg_pnl = total_pnl / len(pnls) if pnls else 0.0
    win_rate_pct = (wins / len(closed) * 100) if closed else 0.0

    initial_capital = settings.initial_capital_usd
    equity_curve: list[float] = []
    running = initial_capital
    for pnl in pnls:
        running += pnl
        equity_curve.append(running)
    max_dd_pct = _max_drawdown_pct(equity_curve, initial_capital)

    daily_totals: dict[str, list] = {}
    for r, pnl in zip(closed, pnls, strict=True):
        exit_time = r["exit_time"] or r["entry_time"]
        day = exit_time[:10]  # "YYYY-MM-DD" prefix dari ISO string
        bucket = daily_totals.setdefault(day, [0.0, 0])
        bucket[0] += pnl
        bucket[1] += 1
    daily_breakdown = [
        DailyPnl(date=day, pnl=round(vals[0], 2), trades=vals[1])
        for day, vals in sorted(daily_totals.items())
    ]

    prev_start = start - (end - start)
    prev_rows = get_trades_in_range(prev_start, start)
    prev_pnls = [float(r["pnl"]) for r in _closed_sorted(prev_rows)]
    prev_period_pnl = sum(prev_pnls) if prev_pnls else None
    return_pct = (total_pnl / initial_capital * 100) if initial_capital > 0 else None

    return TradeSummary(
        period=period,
        period_label=label,
        range_start=start,
        range_end=end,
        total_trades=total_trades,
        wins=wins,
        losses=losses,
        open_trades=open_trades,
        win_rate_pct=win_rate_pct,
        total_pnl=total_pnl,
        avg_pnl=avg_pnl,
        best_trade_pnl=max(pnls) if pnls else None,
        worst_trade_pnl=min(pnls) if pnls else None,
        equity_curve=equity_curve,
        max_drawdown_pct=max_dd_pct,
        prev_period_pnl=prev_period_pnl,
        return_pct=return_pct,
        daily_breakdown=daily_breakdown,
    )


def format_report_message(summary: TradeSummary) -> str:
    lines = [
        f"📊 Laporan Trading {summary.period_label}",
        f"Simbol: {settings.xauusd_symbol}",
        "",
        f"Total trade: {summary.total_trades} (open: {summary.open_trades})",
        f"Menang/Kalah: {summary.wins}/{summary.losses}",
        f"Win rate: {summary.win_rate_pct:.1f}%",
        f"Total PnL: ${summary.total_pnl:.2f}",
        f"Rata-rata PnL/trade: ${summary.avg_pnl:.2f}",
    ]
    if summary.best_trade_pnl is not None:
        lines.append(f"Trade terbaik: ${summary.best_trade_pnl:.2f}")
    if summary.worst_trade_pnl is not None:
        lines.append(f"Trade terburuk: ${summary.worst_trade_pnl:.2f}")

    lines.append("")
    if summary.return_pct is not None:
        lines.append(f"Return: {summary.return_pct:+.2f}% (basis modal ${settings.initial_capital_usd:.0f})")
    lines.append(f"Max drawdown periode ini: {summary.max_drawdown_pct:.2f}%")
    if summary.prev_period_pnl is not None:
        delta = summary.total_pnl - summary.prev_period_pnl
        arrow = "🔼" if delta > 0 else ("🔽" if delta < 0 else "▪️")
        lines.append(
            f"vs periode sebelumnya: ${summary.prev_period_pnl:.2f} "
            f"({arrow} {delta:+.2f})"
        )
    return "\n".join(lines)


def render_report_chart(summary: TradeSummary) -> io.BytesIO | None:
    """Generate 1 gambar gabungan: equity curve kumulatif (atas) + bar PnL harian (bawah),
    dikirim sbg foto Telegram supaya laporan lebih mirip laporan portofolio drpd teks polos.
    Return None kalau gak ada trade closed sama sekali dalam periode (gak ada yang digambar)."""
    if not summary.equity_curve and not summary.daily_breakdown:
        return None

    fig, axes = plt.subplots(2, 1, figsize=(8, 6), height_ratios=[2, 1])
    fig.suptitle(f"Portofolio -- {summary.period_label}", fontsize=13, fontweight="bold")

    ax_equity = axes[0]
    if summary.equity_curve:
        x = list(range(len(summary.equity_curve)))
        curve = [settings.initial_capital_usd, *summary.equity_curve]
        ax_equity.plot(range(len(curve)), curve, color="#2E7D32" if summary.total_pnl >= 0 else "#C62828", linewidth=1.8)
        ax_equity.axhline(settings.initial_capital_usd, color="gray", linestyle="--", linewidth=0.8, label="Modal awal")
        ax_equity.fill_between(range(len(curve)), settings.initial_capital_usd, curve, alpha=0.15,
                                color="#2E7D32" if summary.total_pnl >= 0 else "#C62828")
        ax_equity.set_ylabel("Equity ($)")
        ax_equity.set_xlabel("Urutan trade closed")
        ax_equity.set_title(f"Equity curve (return {summary.return_pct:+.2f}%, max DD {summary.max_drawdown_pct:.2f}%)"
                             if summary.return_pct is not None else "Equity curve")
        ax_equity.legend(loc="upper left", fontsize=8)
        ax_equity.grid(alpha=0.3)
    else:
        ax_equity.text(0.5, 0.5, "Tidak ada trade closed", ha="center", va="center", transform=ax_equity.transAxes)
        ax_equity.set_xticks([])
        ax_equity.set_yticks([])

    ax_daily = axes[1]
    if summary.daily_breakdown:
        days = [d.date[5:] for d in summary.daily_breakdown]  # "MM-DD" saja, biar muat
        pnls = [d.pnl for d in summary.daily_breakdown]
        colors = ["#2E7D32" if p >= 0 else "#C62828" for p in pnls]
        ax_daily.bar(days, pnls, color=colors)
        ax_daily.axhline(0, color="black", linewidth=0.6)
        ax_daily.set_ylabel("PnL harian ($)")
        ax_daily.tick_params(axis="x", rotation=60, labelsize=7)
        ax_daily.grid(alpha=0.3, axis="y")
    else:
        ax_daily.text(0.5, 0.5, "Tidak ada breakdown harian", ha="center", va="center", transform=ax_daily.transAxes)
        ax_daily.set_xticks([])
        ax_daily.set_yticks([])

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130)
    plt.close(fig)
    buf.seek(0)
    return buf


async def _generate_and_send_report(period: ReportPeriod) -> None:
    now = dt.datetime.now(dt.UTC)
    summary = build_report(period, now)
    caption = format_report_message(summary)
    chart = render_report_chart(summary)
    if chart is not None:
        await send_photo(chart, caption=caption)
    else:
        await send_message(caption)


async def check_and_alert_drawdown() -> None:
    """Job tiap 30 detik: bandingkan kondisi breach drawdown saat ini vs snapshot terakhir,
    kirim alert cuma saat transisi False->True (bukan tiap kali masih breach)."""
    state = load_drawdown_state()
    if state is None:
        return

    account_info = mt5.account_info()
    if account_info is None:
        return
    equity = float(account_info.equity)
    now = dt.datetime.now(dt.UTC)

    total_dd_pct = compute_total_dd_pct(state, equity)
    daily_dd_pct = compute_daily_dd_pct(state, equity)
    monthly_dd_pct = compute_monthly_dd_pct(state, equity)
    checks: list[tuple[DrawdownKind, float, float, bool]] = [
        ("TOTAL", total_dd_pct, settings.max_total_drawdown_pct, state.total_dd_paused),
        ("DAILY", daily_dd_pct, settings.max_daily_drawdown_pct, False),
        ("MONTHLY", monthly_dd_pct, settings.max_monthly_drawdown_pct, False),
    ]

    for kind, dd_pct, limit, forced in checks:
        breaching = forced or dd_pct >= limit
        if breaching and not _last_alert_state[kind]:
            event = DrawdownAlertEvent(
                kind=kind,
                reason=f"{kind} drawdown {dd_pct:.2f}% (limit {limit}%)",
                triggered_at=now,
                equity=equity,
                dd_pct=dd_pct,
            )
            await _send_drawdown_alert(event)
        _last_alert_state[kind] = breaching


async def _send_drawdown_alert(event: DrawdownAlertEvent) -> None:
    text = (
        f"🚨 Kill-switch {event.kind} drawdown ke-trigger\n"
        f"{event.reason}\n"
        f"Equity saat ini: ${event.equity:.2f}\n"
        f"Waktu: {event.triggered_at.isoformat()}"
    )
    if event.kind == "TOTAL":
        text += "\n\nRobot pause PERMANEN. Reset manual (hapus drawdown_state.json) diperlukan."
        await send_message(text)
        return

    text += "\n\nRobot pause sampai reset otomatis berikutnya, atau override manual di bawah."
    period = "daily" if event.kind == "DAILY" else "monthly"
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Lanjutkan Trading", callback_data=f"resume:{period}"),
                InlineKeyboardButton("⏸ Tetap Skip", callback_data=f"skip:{period}"),
            ]
        ]
    )
    await send_message(text, reply_markup=keyboard)


def build_market_condition_report(period: ReportPeriod) -> str:
    """Evaluasi kondisi market TERKINI pakai pipeline persis yang dipakai robot beneran
    (build_signal_row + generate_signal_v12 dari m5_scalping.usecase) -- supaya laporan
    mencerminkan apa yang bakal terjadi kalau kill-switch di-resume sekarang, bukan
    reimplementasi terpisah yang bisa nyimpang dari logic live."""
    params = load_params()
    sig_params = params["signal_params"]

    row = build_signal_row(params)
    close = float(row["close"])
    adx = float(row.get("adx", 0))
    h1_adx = float(row.get("h1_adx", 0)) if row.get("h1_adx") is not None else None
    atr = float(row.get("atr", 0))
    atr_pct = (atr / close * 100) if close > 0 else 0.0

    aligned, h1_reason = _check_htf_alignment(row, Signal.BUY)  # cuma buat baca trend H1-nya
    h1_ema_50 = row.get("h1_ema_50")
    h1_ema_200 = row.get("h1_ema_200")
    if h1_ema_50 is not None and h1_ema_200 is not None:
        h1_trend = "UP" if h1_ema_50 > h1_ema_200 else ("DOWN" if h1_ema_50 < h1_ema_200 else "FLAT")
    else:
        h1_trend = "tidak tersedia"

    result = generate_signal_v12(
        row,
        min_signal_score=sig_params["min_signal_score"],
        adx_min=sig_params["adx_min"],
        atr_min_pct=sig_params["atr_min_pct"],
        require_h1_alignment=sig_params["require_h1_alignment"],
    )

    lines = [
        "📈 Evaluasi Kondisi Market Saat Ini",
        f"Simbol: {settings.xauusd_symbol}",
        "",
        f"ADX M5: {adx:.1f} (min {sig_params['adx_min']})",
    ]
    if h1_adx is not None:
        lines.append(f"ADX H1: {h1_adx:.1f}")
    lines.append(f"Trend H1 (EMA50 vs EMA200): {h1_trend}")
    lines.append(f"ATR%: {atr_pct:.3f}% (min {sig_params['atr_min_pct']}%)")
    lines.append("")

    if result.direction == Signal.WAIT:
        lines.append(f"Sinyal saat ini: WAIT (score={result.final_score:.2f})")
        if result.filtered_reason:
            lines.append(f"Alasan: {result.filtered_reason}")
    else:
        ob_block = has_opposing_order_block(row, result.direction)
        dominant_chain = row["bull_chain"] if result.direction == Signal.BUY else row["bear_chain"]
        lines.append(f"Sinyal saat ini: {result.direction} (score={result.final_score:.2f})")
        lines.append(f"Order Block lawan arah: {'YA (akan di-skip)' if ob_block else 'Tidak ada'}")
        lines.append(f"Momentum chain: {dominant_chain}/8")

    return "\n".join(lines)


async def handle_start_tuning_command(period: ReportPeriod) -> None:
    report = build_market_condition_report(period)
    await send_message(report)

    label = "harian" if period == "daily" else "bulanan"
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Lanjutkan Trading", callback_data=f"resume:{period}"),
                InlineKeyboardButton("⏸ Tetap Skip Sampai Reset Otomatis", callback_data=f"skip:{period}"),
            ]
        ]
    )
    await send_message(
        f"Kill-switch {label} sedang aktif. Lanjutkan trading sekarang berdasarkan evaluasi di atas?",
        reply_markup=keyboard,
    )


async def handle_callback_query(period: ReportPeriod, action: str) -> str:
    """Return teks konfirmasi singkat buat di-reply ke callback query."""
    if action != "resume":
        return "Tetap skip, kill-switch masih aktif sampai reset otomatis berikutnya."

    state = load_drawdown_state()
    if state is None:
        return "Gagal: state drawdown belum ada."

    if period == "daily":
        state.daily_override_active = True
    else:
        state.monthly_override_active = True
    save_drawdown_state(state)

    label = "harian" if period == "daily" else "bulanan"
    logger.info(f"[bot_telegram] Override kill-switch {label} diaktifkan lewat Telegram")
    return f"Kill-switch {label} di-override. Trading dilanjutkan sampai reset otomatis berikutnya."
