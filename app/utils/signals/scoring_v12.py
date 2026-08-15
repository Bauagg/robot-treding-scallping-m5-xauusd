"""Scoring de-redundant (v12) — versi `generate_signal()` yang menggabungkan kategori indikator
berkorelasi tinggi jadi 1 skor komposit, alih-alih menjumlah semuanya terpisah.

Latar belakang: analisis korelasi 20 kategori skor generate_signal() asli (di scoring.py) di
~107K candle 2025-2026 menemukan redundansi kuat -- cluster oscillator (RSI, Stochastic,
Williams %R, CCI, Bollinger Bands, VWAP) korelasi antar-pasangan 0.67-0.94 (Stoch vs Williams %R
= 0.94, nyaris duplikat sempurna), cluster trend-follower (SMA, Ichimoku, Supertrend) korelasi
0.65-0.71. Analisis breadth-vs-depth di trade_log v06 menemukan skor total tinggi krn breadth
(banyak oscillator align bersamaan) TIDAK menjamin kualitas lebih baik -- trade dgn skor tinggi
krn SMC signifikan win rate 55.7%, yang cuma breadth/oscillator win rate 41.4%.

Divalidasi via train/test split (notebooks/m5_scalping/v12_deredundant_scoring.ipynb): di TEST
out-of-sample, threshold=9.0 (skala baru, dipilih by profit_factor bukan final_equity yg bias
volume) hasilnya win_rate 68.75% vs 60.95% baseline v06, profit_factor 3.20 vs 2.32.
"""

import numpy as np
import pandas as pd

from app.utils.signals.scoring import (
    score_adx,
    score_bb,
    score_candle,
    score_cci,
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

OSCILLATOR_CLUSTER = ["rsi", "stoch", "williams_r", "cci", "bb", "vwap"]
TREND_CLUSTER = ["sma", "ichimoku", "supertrend"]

# Bobot asli tiap anggota cluster (dari scoring.py WEIGHTS) -- dipakai utk "un-weight" (bagi balik
# ke skor mentah) sebelum digabung jadi median, lalu bobot komposit = rata-rata bobot anggota asli
# supaya skala skor total tetap sebanding dgn skema lama, bukan angka baru yg asal comot.
_MEMBER_WEIGHTS = {
    "rsi": 1.0,
    "stoch": 1.0,
    "williams_r": 1.0,
    "cci": 1.0,
    "bb": 1.0,
    "vwap": 1.5,
    "sma": 1.5,
    "ichimoku": 2.5,
    "supertrend": 2.5,
}
OSCILLATOR_WEIGHT = round(float(np.mean([_MEMBER_WEIGHTS[c] for c in OSCILLATOR_CLUSTER])), 2)
TREND_WEIGHT = round(float(np.mean([_MEMBER_WEIGHTS[c] for c in TREND_CLUSTER])), 2)


def score_de_redundant(row: pd.Series) -> tuple[float, dict[str, float]]:
    """Hitung skor total v12 (de-redundant) + breakdown per kategori. Kategori independen
    (korelasi rendah thd cluster manapun di analisis) dipakai apa adanya dari scoring.py."""
    close = float(row["close"])
    atr = float(row.get("atr", close * 0.001))

    raw_scores = {
        "rsi": score_rsi(row)[0] / _MEMBER_WEIGHTS["rsi"],
        "stoch": score_stoch(row)[0] / _MEMBER_WEIGHTS["stoch"],
        "williams_r": score_williams_r(row)[0] / _MEMBER_WEIGHTS["williams_r"],
        "cci": score_cci(row)[0] / _MEMBER_WEIGHTS["cci"],
        "bb": score_bb(row, close)[0] / _MEMBER_WEIGHTS["bb"],
        "vwap": score_vwap(row, close)[0] / _MEMBER_WEIGHTS["vwap"],
        "sma": score_sma(row, close)[0] / _MEMBER_WEIGHTS["sma"],
        "ichimoku": score_ichimoku(row, close)[0] / _MEMBER_WEIGHTS["ichimoku"],
        "supertrend": score_supertrend(row)[0] / _MEMBER_WEIGHTS["supertrend"],
    }
    oscillator_raw = float(np.median([raw_scores[c] for c in OSCILLATOR_CLUSTER]))
    trend_raw = float(np.median([raw_scores[c] for c in TREND_CLUSTER]))

    components = {
        "oscillator_composite": oscillator_raw * OSCILLATOR_WEIGHT,
        "trend_composite": trend_raw * TREND_WEIGHT,
        "macd": score_macd(row)[0],
        "adx": score_adx(row)[0],
        "candle": score_candle(row)[0],
        "extra_patterns": score_extra_patterns(row)[0],
        "obv": score_obv(row)[0],
        "mfi": score_mfi(row)[0],
        "fibonacci": score_fibonacci(row, close, atr)[0],
        "rsi_divergence": score_rsi_divergence(row)[0],
        "momentum_chain": score_momentum_chain(row)[0],
        "psar": score_psar(row)[0],
        "smc": score_smc(row)[0],
    }

    final_score = round(sum(components.values()), 3)
    return final_score, components
