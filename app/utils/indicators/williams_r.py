import pandas as pd

DEFAULT_PERIOD = 14


def add_williams_r(df: pd.DataFrame, period: int = DEFAULT_PERIOD) -> pd.DataFrame:
    """Tambahkan kolom 'williams_r' (Williams %R)."""
    df = df.copy()
    highest_high = df["high"].rolling(period).max()
    lowest_low = df["low"].rolling(period).min()
    rng = (highest_high - lowest_low).replace(0, 1e-10)

    df["williams_r"] = (-100 * (highest_high - df["close"]) / rng).fillna(-50)
    return df
