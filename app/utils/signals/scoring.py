"""Scoring sinyal per indikator — tiap fungsi terima 1 baris (pd.Series) hasil add_all_indicators
dan mengembalikan (score: float, alasan: str). Score positif = bias BUY, negatif = bias SELL.

Bobot (WEIGHTS) mengikuti skala relatif ala quant-trader-ai: SMC & divergence dibobot lebih besar
karena secara statistik sinyal reversal/struktur lebih jarang tapi lebih kuat dibanding indikator
momentum umum (RSI/MACD/Stoch) yang sering "netral"/noise.
"""

import pandas as pd

WEIGHTS = {
    "rsi": 1.0,
    "macd": 1.0,
    "ema": 1.5,
    "bb": 1.0,
    "stoch": 1.0,
    "adx": 1.5,
    "candle": 1.0,
    "obv": 1.5,
    "vwap": 1.5,
    "williams_r": 1.0,
    "cci": 1.0,
    "mfi": 1.5,
    "sma": 1.5,
    "fibonacci": 2.0,
    "rsi_div": 4.0,
    "momentum_chain": 2.0,
    "supertrend": 2.5,
    "psar": 1.5,
    "ichimoku": 2.5,
    "smc": 3.0,
    "pattern_ex": 1.5,
}


def score_rsi(row: pd.Series) -> tuple[float, str]:
    rsi = row.get("rsi", 50)
    if rsi <= 30:
        return WEIGHTS["rsi"], f"RSI Oversold {rsi:.1f}"
    if rsi >= 70:
        return -WEIGHTS["rsi"], f"RSI Overbought {rsi:.1f}"
    if rsi < 45:
        return WEIGHTS["rsi"] * 0.5, f"RSI bullish zone {rsi:.1f}"
    if rsi > 55:
        return -WEIGHTS["rsi"] * 0.5, f"RSI bearish zone {rsi:.1f}"
    return 0.0, f"RSI netral {rsi:.1f}"


def score_macd(row: pd.Series) -> tuple[float, str]:
    macd = row.get("macd", 0)
    hist = row.get("histogram", 0)
    if macd > 0 and hist > 0:
        return WEIGHTS["macd"], "MACD bullish"
    if macd < 0 and hist < 0:
        return -WEIGHTS["macd"], "MACD bearish"
    if hist > 0:
        return WEIGHTS["macd"] * 0.5, "MACD histogram positif"
    if hist < 0:
        return -WEIGHTS["macd"] * 0.5, "MACD histogram negatif"
    return 0.0, "MACD netral"


def score_ema(row: pd.Series, close: float) -> tuple[float, str]:
    fast = row.get("ema_9", close)
    slow = row.get("ema_20", close)
    trend = row.get("ema_50", close)
    if fast > slow and close > trend:
        return WEIGHTS["ema"], "EMA bullish aligned"
    if fast < slow and close < trend:
        return -WEIGHTS["ema"], "EMA bearish aligned"
    if fast > slow:
        return WEIGHTS["ema"] * 0.5, "EMA fast>slow"
    if fast < slow:
        return -WEIGHTS["ema"] * 0.5, "EMA fast<slow"
    return 0.0, "EMA netral"


def score_bb(row: pd.Series, close: float) -> tuple[float, str]:
    pct = row.get("bb_pct", 0.5)
    if pct <= 0:
        return WEIGHTS["bb"], "Harga di BB lower"
    if pct >= 1:
        return -WEIGHTS["bb"], "Harga di BB upper"
    if pct < 0.2:
        return WEIGHTS["bb"] * 0.5, "Dekat BB lower"
    if pct > 0.8:
        return -WEIGHTS["bb"] * 0.5, "Dekat BB upper"
    return 0.0, "BB netral"


def score_stoch(row: pd.Series) -> tuple[float, str]:
    k = row.get("stoch_k", 50)
    d = row.get("stoch_d", 50)
    if k <= 20 and k > d:
        return WEIGHTS["stoch"], "Stoch oversold + cross up"
    if k >= 80 and k < d:
        return -WEIGHTS["stoch"], "Stoch overbought + cross down"
    if k < 20:
        return WEIGHTS["stoch"] * 0.5, "Stoch oversold"
    if k > 80:
        return -WEIGHTS["stoch"] * 0.5, "Stoch overbought"
    return 0.0, "Stoch netral"


def score_adx(row: pd.Series) -> tuple[float, str]:
    adx = row.get("adx", 20)
    di_pos = row.get("di_pos", 25)
    di_neg = row.get("di_neg", 25)
    if adx < 20:
        return 0.0, f"ADX lemah ({adx:.1f})"
    if di_pos > di_neg:
        return WEIGHTS["adx"], f"ADX uptrend ({adx:.1f})"
    return -WEIGHTS["adx"], f"ADX downtrend ({adx:.1f})"


def score_candle(row: pd.Series) -> tuple[float, str]:
    pat = row.get("candle_pat", 0)
    if pat == 1:
        return WEIGHTS["candle"], "Candle bullish"
    if pat == -1:
        return -WEIGHTS["candle"], "Candle bearish"
    return 0.0, "Tidak ada pola candle"


def score_extra_patterns(row: pd.Series) -> tuple[float, str]:
    pat = row.get("candle_ex", 0)
    w = WEIGHTS["pattern_ex"]
    if pat == 2:
        return w, "Three White Soldiers"
    if pat == 1:
        return w * 0.6, "Morning Star / Bullish Harami"
    if pat == -2:
        return -w, "Three Black Crows"
    if pat == -1:
        return -w * 0.6, "Evening Star / Bearish Harami"
    return 0.0, "Tidak ada pola multi-candle"


def score_obv(row: pd.Series) -> tuple[float, str]:
    obv = row.get("obv", 0)
    obv_ema = row.get("obv_ema", 0)
    w = WEIGHTS["obv"]
    if obv > obv_ema:
        return w * 0.5, "OBV di atas EMA (volume bullish)"
    if obv < obv_ema:
        return -w * 0.5, "OBV di bawah EMA (volume bearish)"
    return 0.0, "OBV netral"


def score_vwap(row: pd.Series, close: float) -> tuple[float, str]:
    vwap = row.get("vwap", close)
    if not vwap or vwap != vwap:
        return 0.0, "VWAP N/A"
    dist_pct = (close - vwap) / vwap * 100
    w = WEIGHTS["vwap"]
    if dist_pct > 0.1:
        return min(w * dist_pct / 0.3, w), f"Harga {dist_pct:+.2f}% di atas VWAP"
    if dist_pct < -0.1:
        return -min(w * -dist_pct / 0.3, w), f"Harga {dist_pct:+.2f}% di bawah VWAP"
    return 0.0, f"Harga dekat VWAP ({dist_pct:+.2f}%)"


def score_williams_r(row: pd.Series) -> tuple[float, str]:
    wr = row.get("williams_r", -50)
    w = WEIGHTS["williams_r"]
    if wr <= -80:
        return w, f"Williams %R oversold ({wr:.1f})"
    if wr >= -20:
        return -w, f"Williams %R overbought ({wr:.1f})"
    return 0.0, f"Williams %R netral ({wr:.1f})"


def score_cci(row: pd.Series) -> tuple[float, str]:
    cci = row.get("cci", 0)
    w = WEIGHTS["cci"]
    if cci <= -100:
        return w, f"CCI oversold ({cci:.0f})"
    if cci >= 100:
        return -w, f"CCI overbought ({cci:.0f})"
    return 0.0, f"CCI netral ({cci:.0f})"


def score_mfi(row: pd.Series) -> tuple[float, str]:
    mfi = row.get("mfi", 50)
    w = WEIGHTS["mfi"]
    if mfi <= 20:
        return w, f"MFI oversold ({mfi:.1f})"
    if mfi >= 80:
        return -w, f"MFI overbought ({mfi:.1f})"
    return 0.0, f"MFI netral ({mfi:.1f})"


def score_sma(row: pd.Series, close: float) -> tuple[float, str]:
    sma50 = row.get("sma_50", close)
    sma200 = row.get("sma_200", close)
    w = WEIGHTS["sma"]
    if sma50 > sma200 and close > sma50:
        return w, "Golden cross SMA50>SMA200"
    if sma50 < sma200 and close < sma50:
        return -w, "Death cross SMA50<SMA200"
    return 0.0, "SMA netral"


def score_fibonacci(row: pd.Series, close: float, atr: float) -> tuple[float, str]:
    w = WEIGHTS["fibonacci"]
    fib_high = row.get("fib_swing_high", close)
    fib_low = row.get("fib_swing_low", close)
    rng = fib_high - fib_low
    if rng < atr * 0.5 or atr <= 0:
        return 0.0, "Fibonacci: range terlalu kecil"

    levels = {
        "38.2%": (row.get("fib_382", close), 0.7),
        "50.0%": (row.get("fib_500", close), 0.6),
        "61.8%": (row.get("fib_618", close), 0.8),
    }
    tolerance = atr * 0.3
    nearest_name, nearest_lvl, nearest_w, nearest_dist = None, None, 0.0, float("inf")
    for name, (lvl, lw) in levels.items():
        dist = abs(close - lvl)
        if dist < nearest_dist:
            nearest_name, nearest_lvl, nearest_w, nearest_dist = name, lvl, lw, dist

    if nearest_dist > tolerance:
        return 0.0, "Fibonacci: jauh dari level kunci"

    fib_mid = (fib_high + fib_low) / 2
    if close < fib_mid:
        return w * nearest_w, f"Fib {nearest_name} support @ {nearest_lvl:.2f}"
    return -w * nearest_w, f"Fib {nearest_name} resistance @ {nearest_lvl:.2f}"


def score_rsi_divergence(row: pd.Series) -> tuple[float, str]:
    w = WEIGHTS["rsi_div"]
    if row.get("rsi_bull_div", 0):
        return w, "RSI bullish divergence"
    if row.get("rsi_bear_div", 0):
        return -w, "RSI bearish divergence"
    if row.get("rsi_hid_bull", 0):
        return w * 0.6, "RSI hidden bullish divergence"
    if row.get("rsi_hid_bear", 0):
        return -w * 0.6, "RSI hidden bearish divergence"
    return 0.0, "Tidak ada RSI divergence"


def score_momentum_chain(row: pd.Series) -> tuple[float, str]:
    w = WEIGHTS["momentum_chain"]
    bull_chain = row.get("bull_chain", 0)
    bear_chain = row.get("bear_chain", 0)
    slope = row.get("close_slope", 0)
    max_chain = 8.0
    bull_norm = min(bull_chain / max_chain, 1.0)
    bear_norm = min(bear_chain / max_chain, 1.0)
    if bull_norm > bear_norm:
        return w * bull_norm * (1.2 if slope > 0 else 0.7), f"Bull chain {bull_chain:.0f}/8"
    if bear_norm > bull_norm:
        return -w * bear_norm * (1.2 if slope < 0 else 0.7), f"Bear chain {bear_chain:.0f}/8"
    return 0.0, "Struktur netral"


def score_supertrend(row: pd.Series) -> tuple[float, str]:
    w = WEIGHTS["supertrend"]
    d = row.get("supertrend_dir", 0)
    flip = row.get("supertrend_flip", 0)
    if flip == 1:
        return w, "Supertrend FLIP bullish"
    if flip == -1:
        return -w, "Supertrend FLIP bearish"
    if d == 1:
        return w * 0.6, "Supertrend bullish"
    if d == -1:
        return -w * 0.6, "Supertrend bearish"
    return 0.0, "Supertrend N/A"


def score_psar(row: pd.Series) -> tuple[float, str]:
    w = WEIGHTS["psar"]
    d = row.get("psar_dir", 0)
    if d == 1:
        return w, "PSAR bullish"
    if d == -1:
        return -w, "PSAR bearish"
    return 0.0, "PSAR N/A"


def score_ichimoku(row: pd.Series, close: float) -> tuple[float, str]:
    w = WEIGHTS["ichimoku"]
    cloud_top = row.get("ichi_cloud_top", close)
    cloud_bot = row.get("ichi_cloud_bot", close)
    tk_bull = row.get("ichi_tk_bull", 0)
    tk_bear = row.get("ichi_tk_bear", 0)

    score = 0.0
    if close > cloud_top:
        score += w * 0.4
    elif close < cloud_bot:
        score -= w * 0.4
    if tk_bull:
        score += w * 0.4
    if tk_bear:
        score -= w * 0.4
    return score, "Ichimoku composite"


def score_smc(row: pd.Series) -> tuple[float, str]:
    w = WEIGHTS["smc"]
    score = 0.0
    parts = []

    if row.get("fvg_bull", 0):
        score += w * 0.4
        parts.append("Bullish FVG")
    if row.get("fvg_bear", 0):
        score -= w * 0.4
        parts.append("Bearish FVG")
    if row.get("ob_bull", 0):
        score += w * 0.35
        parts.append("Bullish OB")
    if row.get("ob_bear", 0):
        score -= w * 0.35
        parts.append("Bearish OB")
    if row.get("bos_bull", 0):
        score += w * 0.3
        parts.append("BOS bullish")
    if row.get("bos_bear", 0):
        score -= w * 0.3
        parts.append("BOS bearish")
    if row.get("choch_bull", 0):
        score += w * 0.5
        parts.append("ChoCH bullish")
    if row.get("choch_bear", 0):
        score -= w * 0.5
        parts.append("ChoCH bearish")
    if row.get("liq_bull_sweep", 0):
        score += w * 0.6
        parts.append("Liquidity sweep bull")
    if row.get("liq_bear_sweep", 0):
        score -= w * 0.6
        parts.append("Liquidity sweep bear")

    return round(score, 3), (" | ".join(parts) if parts else "Tidak ada sinyal SMC")
