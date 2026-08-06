import pandas as pd


def add_fair_value_gap(df: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan kolom fvg_bull, fvg_bear (Fair Value Gap — gap 3-candle yang belum terisi).

    Bullish FVG: high candle[t-2] < low candle[t] (gap naik).
    Bearish FVG: low candle[t-2]  > high candle[t] (gap turun).
    """
    df = df.copy()
    high_2 = df["high"].shift(2)
    low_2 = df["low"].shift(2)

    df["fvg_bull"] = (high_2 < df["low"]).astype(int)
    df["fvg_bear"] = (low_2 > df["high"]).astype(int)
    return df
