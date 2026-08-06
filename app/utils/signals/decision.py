"""Decision engine: gabungkan semua skor indikator jadi 1 keputusan BUY/SELL/WAIT + final_score.

Alur:
1. Hard filter dulu (wajib lolos semua, else WAIT): ADX minimum (market harus trending), ATR minimum
   (volatilitas cukup, hindari market sepi/spread-eating), candle konfirmasi (searah momentum).
2. Kalau lolos, hitung skor gabungan dari semua kategori indikator (trend, momentum, volume, SMC,
   struktur) — dijumlah jadi final_score.
3. final_score >= +MIN_SIGNAL_SCORE -> BUY, <= -MIN_SIGNAL_SCORE -> SELL, selain itu -> WAIT.

Ini penyederhanaan dari pipeline quant-trader-ai (yang punya ~15 filter berlapis) supaya mudah
di-tuning & dievaluasi di awal. Threshold (MIN_SIGNAL_SCORE, ADX_MIN, ATR_MIN) sengaja dibuat
parameter eksplisit supaya bisa dioptimasi lewat notebook riset tanpa ubah kode.
"""

from dataclasses import dataclass, field

import pandas as pd

from app.utils.signals._base import Signal
from app.utils.signals.scoring import (
    score_adx,
    score_bb,
    score_cci,
    score_candle,
    score_extra_patterns,
    score_fibonacci,
    score_ichimoku,
    score_macd,
    score_mfi,
    score_momentum_chain,
    score_obv,
    score_psar,
    score_rsi,
    score_rsi_divergence,
    score_sma,
    score_smc,
    score_stoch,
    score_supertrend,
    score_vwap,
    score_williams_r,
)

DEFAULT_MIN_SIGNAL_SCORE = 6.0
DEFAULT_ADX_MIN = 18.0
DEFAULT_ATR_MIN_PCT = 0.03  # ATR minimal sbg % dari harga close, hindari market terlalu sepi


@dataclass
class SignalResult:
    direction: str
    final_score: float
    breakdown: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    filtered_reason: str | None = None


def _check_hard_filters(
    row: pd.Series, close: float, adx_min: float, atr_min_pct: float
) -> tuple[bool, str]:
    adx = row.get("adx", 0)
    if adx < adx_min:
        return False, f"ADX terlalu lemah ({adx:.1f} < {adx_min})"

    atr = row.get("atr", 0)
    if close > 0 and (atr / close * 100) < atr_min_pct:
        return False, f"ATR terlalu kecil ({atr:.3f}, {atr / close * 100:.3f}% < {atr_min_pct}%)"

    return True, "OK"


def _check_htf_alignment(row: pd.Series, direction: str) -> tuple[bool, str]:
    """Cek arah sinyal searah trend higher-timeframe (H1: EMA50 vs EMA200).

    Butuh kolom h1_ema_50 & h1_ema_200 di row (hasil merge_asof dgn candle H1 yg sudah closed).
    Kalau kolom tidak ada / NaN, filter di-skip (tidak menahan sinyal) supaya fungsi ini tetap
    bisa dipakai tanpa data H1.
    """
    h1_ema_50 = row.get("h1_ema_50")
    h1_ema_200 = row.get("h1_ema_200")
    if h1_ema_50 is None or h1_ema_200 is None or pd.isna(h1_ema_50) or pd.isna(h1_ema_200):
        return True, "H1 trend: data tidak tersedia — skip"

    h1_trend = "UP" if h1_ema_50 > h1_ema_200 else ("DOWN" if h1_ema_50 < h1_ema_200 else "FLAT")

    if direction == "BUY" and h1_trend == "DOWN":
        return False, f"Melawan trend H1 (DOWN) untuk sinyal BUY"
    if direction == "SELL" and h1_trend == "UP":
        return False, f"Melawan trend H1 (UP) untuk sinyal SELL"
    return True, f"Searah/netral trend H1 ({h1_trend})"


def generate_signal(
    row: pd.Series,
    min_signal_score: float = DEFAULT_MIN_SIGNAL_SCORE,
    adx_min: float = DEFAULT_ADX_MIN,
    atr_min_pct: float = DEFAULT_ATR_MIN_PCT,
    require_h1_alignment: bool = False,
) -> SignalResult:
    close = float(row["close"])
    atr = float(row.get("atr", close * 0.001))

    passed, filter_reason = _check_hard_filters(row, close, adx_min, atr_min_pct)
    if not passed:
        return SignalResult(direction=Signal.WAIT, final_score=0.0, filtered_reason=filter_reason)

    components: dict[str, tuple[float, str]] = {
        "rsi": score_rsi(row),
        "macd": score_macd(row),
        "bb": score_bb(row, close),
        "stoch": score_stoch(row),
        "adx": score_adx(row),
        "candle": score_candle(row),
        "extra_patterns": score_extra_patterns(row),
        "obv": score_obv(row),
        "vwap": score_vwap(row, close),
        "williams_r": score_williams_r(row),
        "cci": score_cci(row),
        "mfi": score_mfi(row),
        "sma": score_sma(row, close),
        "fibonacci": score_fibonacci(row, close, atr),
        "rsi_divergence": score_rsi_divergence(row),
        "momentum_chain": score_momentum_chain(row),
        "supertrend": score_supertrend(row),
        "psar": score_psar(row),
        "ichimoku": score_ichimoku(row, close),
        "smc": score_smc(row),
    }

    breakdown = {name: score for name, (score, _) in components.items()}
    reasons = [reason for _, (score, reason) in components.items() if score != 0]
    final_score = round(sum(breakdown.values()), 3)

    if final_score >= min_signal_score:
        direction = Signal.BUY
    elif final_score <= -min_signal_score:
        direction = Signal.SELL
    else:
        direction = Signal.WAIT

    if direction != Signal.WAIT and require_h1_alignment:
        aligned, h1_reason = _check_htf_alignment(row, direction)
        if not aligned:
            return SignalResult(
                direction=Signal.WAIT,
                final_score=final_score,
                breakdown=breakdown,
                reasons=reasons,
                filtered_reason=h1_reason,
            )

    return SignalResult(
        direction=direction,
        final_score=final_score,
        breakdown=breakdown,
        reasons=reasons,
    )


def generate_signals_batch(
    df: pd.DataFrame,
    min_signal_score: float = DEFAULT_MIN_SIGNAL_SCORE,
    adx_min: float = DEFAULT_ADX_MIN,
    atr_min_pct: float = DEFAULT_ATR_MIN_PCT,
    require_h1_alignment: bool = False,
) -> pd.DataFrame:
    """Terapkan generate_signal ke tiap baris DataFrame (sudah punya indikator lengkap).
    Return df dengan kolom tambahan: signal_direction, signal_score.
    """
    directions = []
    scores = []
    for _, row in df.iterrows():
        result = generate_signal(row, min_signal_score, adx_min, atr_min_pct, require_h1_alignment)
        directions.append(result.direction)
        scores.append(result.final_score)

    df = df.copy()
    df["signal_direction"] = directions
    df["signal_score"] = scores
    return df
