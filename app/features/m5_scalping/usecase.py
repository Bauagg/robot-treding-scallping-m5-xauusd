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
    load_drawdown_state,
    save_drawdown_state,
    update_trade_close,
)
from app.features.m5_scalping.schema import DrawdownState, SignalCheckResult, TradeLogEntry
from app.utils.indicators import add_all_indicators
from app.utils.signals import Signal, generate_signal_v12

PARAMS_PATH = Path("models") / "m5_scalping" / "v13" / "params.json"

MAGIC_NUMBER = 100001
H1_CANDLES_FOR_CONTEXT = 210  # cukup utk ema_200 H1 (warm-up period)
M5_CANDLES_FOR_SIGNAL = 210  # cukup utk ema_200/sma_200 M5

# Jumat mulai jam segini SESUAI JAM SISTEM LAPTOP LIVE (bukan UTC asli) sampai market buka
# lagi (Minggu malam) -- gak boleh open posisi BARU. Posisi yang sudah OPEN sebelum jam ini
# dibiarkan jalan terus (SL/TP sendiri yang nutup), cuma entry baru yang diblok.
#
# Target sebenarnya: UTC 15:00 = WIB 22:00 Jumat malam. Awalnya user minta UTC 13:00
# (WIB 20:00) krn khawatir candle gak beraturan/whipsaw menjelang tutup weekend (contoh
# nyata: trade 2026-08-14 15:30 & 18:51 UTC closing LOSS). Tapi backtest v06
# (dataset/processed/m5_scalping/v06/trade_log_full.csv, dicek 2026-08-15) nunjukkin UTC
# 13:00 terlalu awal -- trade Jumat jam 13:00-14:59 UTC justru net_pnl POSITIF (+$160.66
# dari 112 trade, win rate 50%, khususnya jam 13:00 net_pnl=$104 & jam 14:00 net_pnl=$78).
# UTC 15:00 adalah titik pertama net_pnl trade yg ke-blok berubah NEGATIF (-$21.21 dari 61
# trade, win rate 42.6%) -- jadi dipilih sbg batas yg gak buang jam produktif tapi tetap
# hindari jam yg terbukti merugikan menjelang closing.
#
# PENTING -- nilainya BUKAN 15 (UTC asli): ditemukan 2026-08-15 jam sistem laptop yang
# menjalankan bot live drift ~3 jam DI BELAKANG UTC asli (dicek dari 10 sampel trade,
# entry_time hasil now() lokal semua selisih persis 3 jam dari time_done order di MT5).
# Selama jam sistem laptop belum disinkronkan (Settings > Time & Language > sync now di
# laptop live), guard ini dikompensasi mundur 3 jam (15-3=12) spy efeknya tetap UTC 15:00
# (WIB 22:00) yang benar. INI TAMBALAN, BUKAN FIX PERMANEN -- begitu jam laptop live
# disinkronkan ulang, nilai ini HARUS dikembalikan ke 15, kalau tidak entry malah diblok
# 3 jam KELEWAT AWAL. Guard ini juga TIDAK memperbaiki masalah serupa di _check_drawdown_guard
# (reset baseline daily/monthly ikut pakai now() yg sama, blm dikompensasi).
WEEKEND_CLOSE_BLOCK_HOUR_UTC = 12


def _is_weekend_close_window(now: dt.datetime) -> bool:
    """True kalau sekarang Jumat >= jam blok, atau Sabtu, atau Minggu (market XAUUSD tutup
    Sabtu penuh & buka lagi Minggu malam -- diblok sepanjang itu juga spy gak entry pas
    baru buka & masih dalam window yg sama blom di-clear manual)."""
    weekday = now.weekday()  # Monday=0 ... Friday=4, Saturday=5, Sunday=6
    if weekday == 4:  # Friday
        return now.hour >= WEEKEND_CLOSE_BLOCK_HOUR_UTC
    return weekday == 5  # Saturday penuh; Minggu (6) dianggap sudah boleh entry lagi


def _day_key(now: dt.datetime) -> str:
    return now.strftime("%Y-%m-%d")


def _month_key(now: dt.datetime) -> str:
    return now.strftime("%Y-%m")


def compute_total_dd_pct(state: DrawdownState, equity: float) -> float:
    return (state.peak_equity - equity) / state.peak_equity * 100 if state.peak_equity > 0 else 0.0


def compute_daily_dd_pct(state: DrawdownState, equity: float) -> float:
    return (
        (state.day_start_equity - equity) / state.day_start_equity * 100
        if state.day_start_equity > 0
        else 0.0
    )


def compute_monthly_dd_pct(state: DrawdownState, equity: float) -> float:
    return (
        (state.month_start_equity - equity) / state.month_start_equity * 100
        if state.month_start_equity > 0
        else 0.0
    )


def _check_drawdown_guard(now: dt.datetime) -> str | None:
    """Kill-switch drawdown: cek equity sekarang vs peak equity (total), vs equity awal
    hari (daily), dan vs equity awal bulan (monthly). Kalau salah satu turun melebihi
    threshold di .env, robot skip entry baru & return alasan pause-nya.

    Baseline daily/monthly di-reset otomatis begitu tanggal/bulan kalender (UTC) berganti
    -- jadi pause karena daily/monthly limit otomatis lepas di hari/bulan berikutnya. Override
    manual (daily_override_active/monthly_override_active, diset True lewat tombol "Lanjutkan
    Trading" di alert Telegram) BUKAN bypass permanen sepanjang hari/bulan -- begitu equity
    pulih balik di atas limit, override langsung di-reset ke False lagi di sini. Jadi kalau
    breach lagi setelahnya (equity jatuh ke bawah limit lagi di hari/bulan yg sama), itu
    dianggap kejadian BARU: robot pause lagi & alert Telegram terkirim lagi minta resume ulang
    -- bukan otomatis lanjut trading terus krn 1x resume sebelumnya. Override juga ikut
    lepas otomatis di rollover hari/bulan, spy gak "nempel" ke periode berikutnya.
    Peak equity (buat total drawdown) TIDAK pernah reset otomatis & begitu ke-trigger,
    ditandai `total_dd_paused=True` yang permanen sampai file drawdown_state.json
    dihapus/direset manual -- karena breach total dianggap sinyal akun rusak, bukan
    sekadar bad day/bulan. Total drawdown TIDAK PERNAH bisa di-override lewat bot_telegram
    (sengaja, lihat DrawdownState). PENTING: reset ini HANYA menghapus drawdown_state.json
    (peak equity & baseline), TIDAK PERNAH menyentuh trade_log.csv (histori trade) --
    kedua file itu independen, tidak ada kode drawdown yang membaca/menulis trade_log.csv.

    Return None kalau aman (boleh entry), atau string alasan pause kalau tidak.
    """
    account_info = mt5.account_info()
    if account_info is None:
        raise RuntimeError(f"Gagal ambil account_info MT5: {mt5.last_error()}")
    equity = float(account_info.equity)

    day_key = _day_key(now)
    month_key = _month_key(now)

    state = load_drawdown_state()
    if state is None:
        state = DrawdownState(
            peak_equity=equity,
            day_key=day_key,
            day_start_equity=equity,
            month_key=month_key,
            month_start_equity=equity,
        )
    else:
        if equity > state.peak_equity:
            state.peak_equity = equity
        if state.day_key != day_key:
            state.day_key = day_key
            state.day_start_equity = equity
            state.daily_override_active = False
        if state.month_key != month_key:
            state.month_key = month_key
            state.month_start_equity = equity
            state.monthly_override_active = False

    reason = None

    total_dd_pct = compute_total_dd_pct(state, equity)
    if state.total_dd_paused or total_dd_pct >= settings.max_total_drawdown_pct:
        state.total_dd_paused = True
        reason = (
            f"Kill-switch: total drawdown {total_dd_pct:.2f}% dari peak equity "
            f"{state.peak_equity:.2f} (limit {settings.max_total_drawdown_pct}%). "
            "Robot pause PERMANEN sampai direset manual."
        )

    daily_dd_pct = compute_daily_dd_pct(state, equity)
    if daily_dd_pct < settings.max_daily_drawdown_pct:
        # Equity udah pulih di atas limit -- lepas override manual supaya breach
        # berikutnya di hari yg sama dianggap kejadian BARU (pause + minta resume lagi),
        # bukan ke-bypass otomatis terus-terusan sepanjang hari krn 1x resume dulu.
        state.daily_override_active = False
    elif reason is None and not state.daily_override_active:
        reason = (
            f"Kill-switch: daily drawdown {daily_dd_pct:.2f}% (limit "
            f"{settings.max_daily_drawdown_pct}%). Robot pause sampai di-resume manual lewat "
            "Telegram atau hari berikutnya (UTC)."
        )

    monthly_dd_pct = compute_monthly_dd_pct(state, equity)
    if monthly_dd_pct < settings.max_monthly_drawdown_pct:
        state.monthly_override_active = False
    elif reason is None and not state.monthly_override_active:
        reason = (
            f"Kill-switch: monthly drawdown {monthly_dd_pct:.2f}% (limit "
            f"{settings.max_monthly_drawdown_pct}%). Robot pause sampai di-resume manual lewat "
            "Telegram atau bulan berikutnya (UTC)."
        )

    save_drawdown_state(state)

    if reason:
        logger.warning(reason)
    return reason


def load_params() -> dict:
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


def build_signal_row(params: dict) -> pd.Series:
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


def has_opposing_order_block(row: pd.Series, direction: str) -> bool:
    """True kalau ada Order Block (SMC) M5 atau H1 yang melawan arah sinyal -- BUY vs
    ob_bear/h1_ob_bear, SELL vs ob_bull/h1_ob_bull.

    Divalidasi di notebooks/m5_scalping/v10_ob_reversal.ipynb: 57.8% dari semua LOSS backtest
    v06 terjadi saat kondisi ini muncul (padahal cuma 41% dari total trade) -- kelompok trade
    dgn OB lawan arah rugi bersih -$2050 scr agregat, sementara kelompok tanpa OB lawan arah
    untung +$4375. Kalau OB M5 & H1 aktif BERSAMAAN, win rate anjlok ke 8.6% (vs 66.7% baseline).

    Sempat dicoba 2 alternatif selain SKIP, keduanya gagal validasi out-of-sample (overfitting):
    - REVERSE PENUH (balik arah, TP/SL sama besar): win rate trade reverse turun dari 56.8%
      (train) ke 51.2% (test), profit factor kalah dari SKIP.
    - SMALL-REVERSE (balik arah, TP/SL kecil - scalp jendela reversal singkat yg terbukti ada
      di price path 77.5% kasus): net_pnl trade reverse +$2421 di train tapi -$131 di test.
    SKIP dipilih krn satu-satunya yang konsisten robust di TRAIN & TEST out-of-sample."""
    if direction == Signal.BUY:
        return bool(row["ob_bear"] > 0 or row["h1_ob_bear"] > 0)
    return bool(row["ob_bull"] > 0 or row["h1_ob_bull"] > 0)


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


_FILLING_MODE_MAP = {
    "FOK": mt5.ORDER_FILLING_FOK,
    "IOC": mt5.ORDER_FILLING_IOC,
    "RETURN": mt5.ORDER_FILLING_RETURN,
}


def _resolve_filling_mode(symbol: str) -> int:
    """Broker/symbol beda-beda dukung filling mode yang beda (FOK/IOC/RETURN) —
    baca dari symbol_info() supaya gak hardcode mode yang mungkin ditolak (retcode 10030).
    Bisa di-override manual lewat MT5_FILLING_MODE di .env kalau auto-detect salah
    untuk broker/simbol tertentu."""
    override = settings.mt5_filling_mode.strip().upper()
    if override:
        if override not in _FILLING_MODE_MAP:
            raise ValueError(f"MT5_FILLING_MODE tidak valid: {override!r} (pilihan: FOK/IOC/RETURN)")
        return _FILLING_MODE_MAP[override]

    # symbol_info().filling_mode adalah bitmask MQL5 SYMBOL_FILLING_MODE (FOK=1, IOC=2) —
    # Python module MetaTrader5 gak expose konstanta ini, cuma ORDER_FILLING_* buat request.
    SYMBOL_FILLING_FOK = 1
    SYMBOL_FILLING_IOC = 2

    info = mt5.symbol_info(symbol)
    if info is not None:
        if info.filling_mode & SYMBOL_FILLING_FOK:
            return mt5.ORDER_FILLING_FOK
        if info.filling_mode & SYMBOL_FILLING_IOC:
            return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN


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
        "comment": "m5_scalping v13",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": _resolve_filling_mode(symbol),
    }

    result = mt5.order_send(request)
    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        raise RuntimeError(f"order_send gagal: {result}")

    return result


def _get_order_entry_time(ticket: int, fallback: dt.datetime) -> dt.datetime:
    """Ambil waktu eksekusi order YANG SESUNGGUHNYA dari histori MT5 (time_done, Unix
    epoch UTC) -- bukan dt.datetime.now() lokal. Ditemukan 2026-08-15: entry_time yang
    dicatat pakai jam sistem laptop selisih ~3 jam dari waktu order asli di MT5 (jam
    sistem laptop live drift/salah) -- 10 sampel trade dicek, semua selisih persis 3 jam.
    MT5 adalah sumber kebenaran waktu (server yang benar-benar eksekusi order), bukan jam
    laptop yang menjalankan bot, supaya histori order_time gak ambigu saat ditelusuri
    ulang lewat mt5.history_orders_get()/history_deals_get(). fallback dipakai kalau MT5
    entah kenapa belum mencatat order ini (delay replikasi) -- seharusnya jarang terjadi
    krn order_send() sudah TRADE_RETCODE_DONE."""
    orders = mt5.history_orders_get(ticket=ticket)
    if orders:
        return dt.datetime.fromtimestamp(orders[0].time_done, tz=dt.UTC)
    logger.warning(f"Gagal ambil time_done dari MT5 utk ticket={ticket}, pakai fallback waktu lokal")
    return fallback


def check_signal_and_trade() -> SignalCheckResult:
    """Fungsi utama: fetch candle terbaru, generate sinyal, kalau ada sinyal -> order -> catat.
    Dipanggil oleh loop polling di main.py atau endpoint manual trigger.

    Cuma boleh ada 1 posisi OPEN pada satu waktu -- kalau masih ada trade yang belum closed,
    skip cek sinyal & order baru sampai posisi itu ditutup. Tanpa guard ini, sinyal yang
    tetap valid di beberapa candle berturut-turut (mis. harga masih tren naik) bikin robot
    numpuk banyak posisi BUY di titik harga yang makin tinggi tiap polling (~1 menit sekali),
    bukan 1 sinyal = 1 trade seperti asumsi backtest -- ditemukan 2026-08-11 setelah 21 trade
    BUY beruntun (banyak berjarak ~1 menit) kena SL nyaris bersamaan saat harga koreksi.

    Juga gak boleh open posisi BARU dari Jumat jam WEEKEND_CLOSE_BLOCK_HOUR_UTC sampai market
    buka lagi (Sabtu penuh + Minggu sebelum candle pertama masuk) -- posisi yang sudah OPEN
    sebelum window ini dibiarkan jalan terus, SL/TP-nya sendiri yang nutup.

    Kill-switch drawdown (daily/monthly/total, lihat _check_drawdown_guard) dicek paling
    awal -- kalau breach, robot skip entry baru sama sekali walau posisi lain sudah closed.

    Sinyal BUY/SELL yang berlawanan dengan Order Block (SMC) di M5/H1 juga di-skip (lihat
    has_opposing_order_block) -- divalidasi via backtest train/test split, kondisi ini
    berkorelasi kuat dgn win rate rendah (turun sampai 8.6% kalau OB M5+H1 aktif bersamaan).
    Filter ini WAJIB tetap aktif -- ablation test (notebooks/m5_scalping/v13_momentum_exhaustion.ipynb)
    nunjukkin tanpa filter ini max_drawdown melebar dari -34% jadi -87% di TEST out-of-sample,
    meski sudah pakai scoring de-redundant v12.

    Scoring pakai generate_signal_v12 (bukan generate_signal asli) -- menggabungkan kategori
    indikator berkorelasi tinggi (cluster oscillator RSI/Stoch/Williams%R/CCI/BB/VWAP, cluster
    trend-follower SMA/Ichimoku/Supertrend) jadi skor komposit median, mengurangi redundansi yg
    bikin skor gabungan "palsu" tinggi cuma krn banyak oscillator align bersamaan (analisis
    breadth-vs-depth di trade_log v06: skor tinggi krn SMC win rate 55.7%, skor tinggi krn
    breadth/oscillator doang win rate 41.4%). Lihat app.utils.signals.scoring_v12.

    SL/TP juga disesuaikan kalau momentum_chain (bull_chain/bear_chain) sudah exhaustion
    (>= exhaustion_chain_threshold, default 8 dari skala 0-8) -- pakai SL/TP lebih kecil
    (exhaustion_sl_atr_multiplier/exhaustion_tp_atr_multiplier) drpd normal, krn chain penuh
    artinya momentum sudah "matang"/rawan melambat, TAPI TIDAK berarti harus reverse arah
    (REVERSE terbukti gagal validasi: win rate cuma 18-24% baik train maupun test).
    """
    now = dt.datetime.now(dt.UTC)

    drawdown_reason = _check_drawdown_guard(now)
    if drawdown_reason:
        return SignalCheckResult(
            checked_at=now,
            symbol=settings.xauusd_symbol,
            direction=Signal.WAIT,
            signal_score=0.0,
            order_placed=False,
            message=drawdown_reason,
        )

    if _is_weekend_close_window(now):
        return SignalCheckResult(
            checked_at=now,
            symbol=settings.xauusd_symbol,
            direction=Signal.WAIT,
            signal_score=0.0,
            order_placed=False,
            message="Mendekati/dalam periode tutup weekend, tidak buka posisi baru",
        )

    if list_open_tickets():
        return SignalCheckResult(
            checked_at=now,
            symbol=settings.xauusd_symbol,
            direction=Signal.WAIT,
            signal_score=0.0,
            order_placed=False,
            message="Masih ada posisi OPEN, tunggu sampai closed sebelum cek sinyal baru",
        )

    params = load_params()
    sig_params = params["signal_params"]
    trade_params = params["trade_params"]

    row = build_signal_row(params)

    result = generate_signal_v12(
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

    if has_opposing_order_block(row, result.direction):
        return SignalCheckResult(
            checked_at=now,
            symbol=settings.xauusd_symbol,
            direction=Signal.WAIT,
            signal_score=result.final_score,
            order_placed=False,
            message=f"Sinyal {result.direction} tapi ada Order Block lawan arah, skip entry",
        )

    close = float(row["close"])
    atr = float(row["atr"])

    dominant_chain = row["bull_chain"] if result.direction == Signal.BUY else row["bear_chain"]
    is_exhausted = dominant_chain >= trade_params["exhaustion_chain_threshold"]

    if is_exhausted:
        sl_mult = trade_params["exhaustion_sl_atr_multiplier"]
        tp_mult = trade_params["exhaustion_tp_atr_multiplier"]
    else:
        sl_mult = trade_params["sl_atr_multiplier"]
        tp_mult = trade_params["tp_atr_multiplier"]

    sl_points = sl_mult * atr
    tp_points = tp_mult * atr
    if result.direction == Signal.BUY:
        sl, tp = close - sl_points, close + tp_points
    else:
        sl, tp = close + sl_points, close - tp_points

    order_result = _send_order(result.direction, settings.xauusd_lot_size, sl, tp)
    entry_time = _get_order_entry_time(order_result.order, fallback=now)

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
            is_exhausted=is_exhausted,
            entry_time=entry_time,
            indicators=_row_to_indicator_dict(row),
        )
    )

    logger.info(
        f"Order {result.direction} {settings.xauusd_symbol} ticket={order_result.order} "
        f"score={result.final_score:.2f} entry={order_result.price} sl={sl} tp={tp} "
        f"exhausted={is_exhausted}"
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

    PENTING: mt5.history_deals_get(date_from, date_to, position=X) TIDAK memfilter by
    position ketika date_from/date_to disertakan (bug/perilaku undocumented MT5 Python API
    -- ditemukan 2026-08-07 setelah 69 trade live salah dicatat, semua ke-assign exit deal
    yang sama). Solusi: tarik SEMUA deal dalam rentang tanggal sekali, filter manual by
    `order` (order ticket entry kita) untuk dapat `position_id`, baru cari deal exit
    (entry==DEAL_ENTRY_OUT) dengan position_id yang sama.
    """
    open_tickets = list_open_tickets()
    if not open_tickets:
        return 0

    # Buffer +/-6 jam di kedua ujung -- jam sistem laptop yang jalanin bot pernah ketahuan
    # drift ~3 jam dari UTC asli (lihat _get_order_entry_time), jadi date_to yg pakai
    # dt.datetime.now(dt.UTC) bisa "ketinggalan" dari deal yg sebenarnya sudah terjadi
    # di waktu MT5 (server) yang asli. Buffer generus drpd query gak nangkep deal terbaru.
    date_from = dt.datetime.now(dt.UTC) - dt.timedelta(days=30)
    date_to = dt.datetime.now(dt.UTC) + dt.timedelta(hours=6)
    all_deals = mt5.history_deals_get(date_from, date_to)
    if not all_deals:
        return 0

    updated = 0
    for ticket in open_tickets:
        entry_deal = next((d for d in all_deals if d.order == ticket and d.entry == 0), None)
        if entry_deal is None:
            continue  # entry deal belum tercatat di histori, coba lagi nanti

        exit_deals = [
            d for d in all_deals if d.position_id == entry_deal.position_id and d.entry == 1
        ]
        if not exit_deals:
            continue  # posisi masih benar-benar terbuka

        exit_deal = max(exit_deals, key=lambda d: d.time)
        pnl = float(exit_deal.profit)
        result = "WIN" if pnl > 0 else "LOSS"
        exit_time = dt.datetime.fromtimestamp(exit_deal.time, tz=dt.UTC).isoformat()

        if update_trade_close(ticket, float(exit_deal.price), exit_time, result, pnl):
            updated += 1
            logger.info(f"Trade ticket={ticket} closed: {result} pnl={pnl:.2f}")

    return updated
