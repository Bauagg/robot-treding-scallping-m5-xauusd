import datetime as dt
import json
from pathlib import Path

import MetaTrader5 as mt5
import pandas as pd

from app.core.config import settings
from app.core.logging import logger
from app.features.m5_scalping.repository import (
    append_trade,
    list_open_tickets,
    update_trade_close,
)
from app.features.m5_scalping.schema import SignalCheckResult, TradeLogEntry
from app.utils.indicators import add_all_indicators
from app.utils.signals import Signal, generate_signal

PARAMS_PATH = Path("models") / "m5_scalping" / "v04" / "params.json"

MAGIC_NUMBER = 100001
H1_CANDLES_FOR_CONTEXT = 210  # cukup utk ema_200 H1 (warm-up period)
M5_CANDLES_FOR_SIGNAL = 210  # cukup utk ema_200/sma_200 M5


def _load_params() -> dict:
    with open(PARAMS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _fetch_candles(symbol: str, timeframe: int, count: int) -> pd.DataFrame:
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"Gagal fetch candle {symbol}: {mt5.last_error()}")

    df = pd.DataFrame(rates)
    df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.rename(columns={"tick_volume": "volume"})
    return df[["datetime", "open", "high", "low", "close", "volume"]]


def _build_signal_row(params: dict) -> pd.Series:
    """Fetch candle M5+H1 terbaru dari MT5, hitung indikator, gabungkan jadi 1 row
    (candle M5 terakhir + kolom h1_* dari candle H1 terakhir yang sudah closed)."""
    df_m5 = _fetch_candles(settings.xauusd_symbol, mt5.TIMEFRAME_M5, M5_CANDLES_FOR_SIGNAL)
    df_h1 = _fetch_candles(settings.xauusd_symbol, mt5.TIMEFRAME_H1, H1_CANDLES_FOR_CONTEXT)

    df_m5 = add_all_indicators(df_m5)
    df_h1 = add_all_indicators(df_h1)

    h1_last = df_h1.iloc[-1]
    m5_last_row = df_m5.iloc[-1].copy()
    for col, value in h1_last.items():
        m5_last_row[f"h1_{col}"] = value

    return m5_last_row


def _row_to_indicator_dict(row: pd.Series) -> dict:
    """Konversi row sinyal (OHLCV + indikator M5 + h1_*) jadi dict serializable (CSV/JSON),
    exclude datetime (sudah dicatat terpisah sbg entry_time)."""
    excluded = {"datetime"}
    result = {}
    for col, value in row.items():
        if col in excluded:
            continue
        if hasattr(value, "item"):  # numpy scalar -> python native
            value = value.item()
        result[col] = value
    return result


def _send_order(direction: str, lot: float, sl: float, tp: float) -> mt5.OrderSendResult:
    symbol = settings.xauusd_symbol
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"Gagal ambil tick {symbol}: {mt5.last_error()}")

    price = tick.ask if direction == "BUY" else tick.bid
    order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "deviation": 10,
        "magic": MAGIC_NUMBER,
        "comment": "m5_scalping v04",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        raise RuntimeError(f"order_send gagal: {result}")

    return result


def check_signal_and_trade() -> SignalCheckResult:
    """Fungsi utama: fetch candle terbaru, generate sinyal, kalau ada sinyal -> order -> catat.
    Dipanggil oleh loop polling di main.py atau endpoint manual trigger.
    """
    params = _load_params()
    sig_params = params["signal_params"]
    trade_params = params["trade_params"]

    row = _build_signal_row(params)
    now = dt.datetime.now(dt.UTC)

    result = generate_signal(
        row,
        min_signal_score=sig_params["min_signal_score"],
        adx_min=sig_params["adx_min"],
        atr_min_pct=sig_params["atr_min_pct"],
        require_h1_alignment=sig_params["require_h1_alignment"],
    )

    if result.direction == Signal.WAIT:
        return SignalCheckResult(
            checked_at=now,
            symbol=settings.xauusd_symbol,
            direction=Signal.WAIT,
            signal_score=result.final_score,
            order_placed=False,
            message=result.filtered_reason or "Skor sinyal di bawah threshold",
        )

    close = float(row["close"])
    tp_points = trade_params["tp_points"]
    sl_points = trade_params["sl_points"]
    if result.direction == Signal.BUY:
        sl, tp = close - sl_points, close + tp_points
    else:
        sl, tp = close + sl_points, close - tp_points

    order_result = _send_order(result.direction, settings.xauusd_lot_size, sl, tp)

    append_trade(
        TradeLogEntry(
            ticket=order_result.order,
            symbol=settings.xauusd_symbol,
            direction=result.direction,
            lot=settings.xauusd_lot_size,
            entry_price=order_result.price,
            sl=sl,
            tp=tp,
            signal_score=result.final_score,
            entry_time=now,
            indicators=_row_to_indicator_dict(row),
        )
    )

    logger.info(
        f"Order {result.direction} {settings.xauusd_symbol} ticket={order_result.order} "
        f"score={result.final_score:.2f} entry={order_result.price} sl={sl} tp={tp}"
    )

    return SignalCheckResult(
        checked_at=now,
        symbol=settings.xauusd_symbol,
        direction=result.direction,
        signal_score=result.final_score,
        order_placed=True,
        ticket=order_result.order,
        message="Order berhasil ditempatkan",
    )


def sync_closed_trades() -> int:
    """Cek tiket OPEN di trade_log.csv, cocokkan dengan histori deal MT5 — kalau sudah
    closed di MT5, update baris CSV jadi CLOSED dengan hasil (WIN/LOSS/pnl).
    Return jumlah trade yang di-update.
    """
    open_tickets = list_open_tickets()
    if not open_tickets:
        return 0

    updated = 0
    date_from = dt.datetime.now(dt.UTC) - dt.timedelta(days=7)
    date_to = dt.datetime.now(dt.UTC)

    for ticket in open_tickets:
        deals = mt5.history_deals_get(date_from, date_to, position=ticket)
        if not deals:
            continue

        # Deal terakhir utk posisi ini = deal exit (entry_in sudah dicatat saat order dibuka)
        exit_deals = [d for d in deals if d.entry == 1]  # DEAL_ENTRY_OUT
        if not exit_deals:
            continue

        exit_deal = exit_deals[-1]
        pnl = float(exit_deal.profit)
        result = "WIN" if pnl > 0 else "LOSS"
        exit_time = dt.datetime.fromtimestamp(exit_deal.time, tz=dt.UTC).isoformat()

        if update_trade_close(ticket, float(exit_deal.price), exit_time, result, pnl):
            updated += 1
            logger.info(f"Trade ticket={ticket} closed: {result} pnl={pnl:.2f}")

    return updated
