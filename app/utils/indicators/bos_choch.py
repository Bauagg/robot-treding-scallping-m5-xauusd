import pandas as pd

from app.utils.indicators.ema import add_ema

DEFAULT_LOOKBACK = 20
TREND_EMA_PERIOD = 50


def add_bos_choch(df: pd.DataFrame, lookback: int = DEFAULT_LOOKBACK) -> pd.DataFrame:
    """Tambahkan kolom bos_bull, bos_bear, choch_bull, choch_bear.

    BOS (Break of Structure): close menembus swing high/low lookback candle sebelumnya
    (konfirmasi kelanjutan trend).
    ChoCH (Change of Character): BOS yang terjadi berlawanan dengan trend EMA50
    (indikasi kemungkinan reversal).
    """
    df = add_ema(df, periods=(TREND_EMA_PERIOD,))
    swing_high = df["high"].shift(1).rolling(lookback).max()
    swing_low = df["low"].shift(1).rolling(lookback).min()

    bos_bull = (df["close"] > swing_high).astype(int)
    bos_bear = (df["close"] < swing_low).astype(int)

    ema_trend = df[f"ema_{TREND_EMA_PERIOD}"]
    downtrend_context = df["close"] < ema_trend
    uptrend_context = df["close"] > ema_trend

    df["bos_bull"] = bos_bull
    df["bos_bear"] = bos_bear
    df["choch_bull"] = (bos_bull & downtrend_context).astype(int)
    df["choch_bear"] = (bos_bear & uptrend_context).astype(int)
    return df
