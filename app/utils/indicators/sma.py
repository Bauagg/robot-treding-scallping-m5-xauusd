import pandas as pd

DEFAULT_PERIODS = (10, 20, 50, 200)


def add_sma(df: pd.DataFrame, periods: tuple[int, ...] = DEFAULT_PERIODS) -> pd.DataFrame:
    """Tambahkan kolom sma_<period> untuk tiap period (Simple Moving Average)."""
    df = df.copy()
    for period in periods:
        df[f"sma_{period}"] = df["close"].rolling(period).mean()
    return df
