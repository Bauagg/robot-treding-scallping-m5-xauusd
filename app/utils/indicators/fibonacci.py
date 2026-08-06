import pandas as pd

DEFAULT_LOOKBACK = 50
LEVELS = {
    "fib_236": 0.236,
    "fib_382": 0.382,
    "fib_500": 0.500,
    "fib_618": 0.618,
    "fib_786": 0.786,
}


def add_fibonacci_levels(df: pd.DataFrame, lookback: int = DEFAULT_LOOKBACK) -> pd.DataFrame:
    """Tambahkan kolom fib_swing_high, fib_swing_low, dan fib_<level> (retracement dari swing rolling)."""
    df = df.copy()
    swing_high = df["high"].rolling(lookback).max()
    swing_low = df["low"].rolling(lookback).min()
    rng = swing_high - swing_low

    df["fib_swing_high"] = swing_high
    df["fib_swing_low"] = swing_low
    for col, level in LEVELS.items():
        df[col] = swing_high - rng * level
    return df
