import numpy as np
import pandas as pd


def add_order_block(df: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan kolom ob_bull, ob_bear (Order Block) + level harga rentangnya.

    Bullish OB: candle bearish diikuti minimal 2 dari 3 candle berikutnya bullish (impulse naik).
    Bearish OB: candle bullish diikuti minimal 2 dari 3 candle berikutnya bearish (impulse turun).

    ob_bull_high/ob_bull_low/ob_bear_high/ob_bear_low: rentang harga (high/low) candle order
    block itu sendiri saat pertama terbentuk (NaN kalau ob_bull/ob_bear == 0) -- dibutuhkan utk
    cek overlap level harga antar timeframe (mis. apakah order block M5 berada di dalam rentang
    order block H4/D1 yang levelnya lebih besar/kuat), bukan cuma flag ada/tidaknya.
    """
    df = df.copy()
    is_bearish = df["close"] < df["open"]
    is_bullish = df["close"] > df["open"]

    next_bullish_count = (
        is_bullish.shift(-1, fill_value=False).astype(int)
        + is_bullish.shift(-2, fill_value=False).astype(int)
        + is_bullish.shift(-3, fill_value=False).astype(int)
    )
    next_bearish_count = (
        is_bearish.shift(-1, fill_value=False).astype(int)
        + is_bearish.shift(-2, fill_value=False).astype(int)
        + is_bearish.shift(-3, fill_value=False).astype(int)
    )

    ob_bull = is_bearish & (next_bullish_count >= 2)
    ob_bear = is_bullish & (next_bearish_count >= 2)

    df["ob_bull"] = ob_bull.astype(int)
    df["ob_bear"] = ob_bear.astype(int)
    df["ob_bull_high"] = np.where(ob_bull, df["high"], np.nan)
    df["ob_bull_low"] = np.where(ob_bull, df["low"], np.nan)
    df["ob_bear_high"] = np.where(ob_bear, df["high"], np.nan)
    df["ob_bear_low"] = np.where(ob_bear, df["low"], np.nan)
    return df
