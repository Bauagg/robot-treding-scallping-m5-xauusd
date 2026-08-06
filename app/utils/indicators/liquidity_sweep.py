import pandas as pd

DEFAULT_LOOKBACK = 20


def add_liquidity_sweep(df: pd.DataFrame, lookback: int = DEFAULT_LOOKBACK) -> pd.DataFrame:
    """Tambahkan kolom liq_bull_sweep, liq_bear_sweep (Liquidity Sweep / stop hunt).

    Bull sweep: low menembus swing low sebelumnya tapi close kembali di atasnya (stop hunt selesai, reversal naik).
    Bear sweep: high menembus swing high sebelumnya tapi close kembali di bawahnya (stop hunt selesai, reversal turun).
    """
    df = df.copy()
    swing_high = df["high"].shift(1).rolling(lookback).max()
    swing_low = df["low"].shift(1).rolling(lookback).min()

    df["liq_bull_sweep"] = ((df["low"] < swing_low) & (df["close"] > swing_low)).astype(int)
    df["liq_bear_sweep"] = ((df["high"] > swing_high) & (df["close"] < swing_high)).astype(int)
    return df
