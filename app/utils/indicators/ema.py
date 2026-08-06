import pandas as pd

DEFAULT_PERIODS = (9, 20, 50, 200)


def add_ema(df: pd.DataFrame, periods: tuple[int, ...] = DEFAULT_PERIODS) -> pd.DataFrame:
    """Tambahkan kolom ema_<period> untuk tiap period (Exponential Moving Average)."""
    df = df.copy()
    for period in periods:
        df[f"ema_{period}"] = df["close"].ewm(span=period, adjust=False).mean()
    return df
