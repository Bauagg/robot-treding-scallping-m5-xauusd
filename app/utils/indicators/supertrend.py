import numpy as np
import pandas as pd

from app.utils.indicators.atr import add_atr

DEFAULT_PERIOD = 10
DEFAULT_MULTIPLIER = 3.0


def add_supertrend(
    df: pd.DataFrame, period: int = DEFAULT_PERIOD, multiplier: float = DEFAULT_MULTIPLIER
) -> pd.DataFrame:
    """Tambahkan kolom 'supertrend', 'supertrend_dir' (1=uptrend/-1=downtrend), 'supertrend_flip'."""
    df = add_atr(df, period=period)

    hl2 = (df["high"] + df["low"]) / 2
    upper_band = hl2 + multiplier * df["atr"]
    lower_band = hl2 - multiplier * df["atr"]

    supertrend = pd.Series(np.nan, index=df.index)
    direction = pd.Series(1, index=df.index)

    for i in range(len(df)):
        if i == 0:
            supertrend.iloc[i] = upper_band.iloc[i]
            direction.iloc[i] = 1
            continue

        prev_st = supertrend.iloc[i - 1]
        prev_dir = direction.iloc[i - 1]
        close = df["close"].iloc[i]

        curr_upper = upper_band.iloc[i]
        curr_lower = lower_band.iloc[i]
        if prev_dir == 1:
            curr_lower = max(curr_lower, prev_st) if prev_st == prev_st else curr_lower
        else:
            curr_upper = min(curr_upper, prev_st) if prev_st == prev_st else curr_upper

        if prev_dir == 1 and close < curr_lower:
            direction.iloc[i] = -1
            supertrend.iloc[i] = curr_upper
        elif prev_dir == -1 and close > curr_upper:
            direction.iloc[i] = 1
            supertrend.iloc[i] = curr_lower
        else:
            direction.iloc[i] = prev_dir
            supertrend.iloc[i] = curr_lower if prev_dir == 1 else curr_upper

    df["supertrend"] = supertrend
    df["supertrend_dir"] = direction
    df["supertrend_flip"] = direction.diff().fillna(0).apply(
        lambda x: 1 if x == 2 else (-1 if x == -2 else 0)
    )
    return df
