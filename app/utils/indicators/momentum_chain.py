import pandas as pd

DEFAULT_N = 4


def add_momentum_chain(df: pd.DataFrame, n: int = DEFAULT_N) -> pd.DataFrame:
    """Tambahkan kolom bull_chain, bear_chain, close_slope.

    bull_chain/bear_chain: jumlah kondisi Higher-High + Higher-Low (atau LL+LH) terpenuhi
    dalam n candle terakhir, skala 0..(n*2) — merepresentasikan kekuatan struktur trend.
    """
    df = df.copy()
    higher_high = (df["high"] > df["high"].shift(1)).astype(int)
    higher_low = (df["low"] > df["low"].shift(1)).astype(int)
    lower_high = (df["high"] < df["high"].shift(1)).astype(int)
    lower_low = (df["low"] < df["low"].shift(1)).astype(int)

    bull_signal = higher_high + higher_low
    bear_signal = lower_low + lower_high

    df["bull_chain"] = bull_signal.rolling(n).sum()
    df["bear_chain"] = bear_signal.rolling(n).sum()
    df["close_slope"] = df["close"].diff(n)
    return df
