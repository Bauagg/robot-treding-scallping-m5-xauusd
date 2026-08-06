import pandas as pd

DEFAULT_PERIOD = 20


def add_vwap(df: pd.DataFrame, period: int = DEFAULT_PERIOD) -> pd.DataFrame:
    """Tambahkan kolom 'vwap' (Volume Weighted Average Price, rolling window)."""
    df = df.copy()
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    pv = typical_price * df["volume"]

    rolling_pv = pv.rolling(period).sum()
    rolling_vol = df["volume"].rolling(period).sum().replace(0, 1e-10)
    df["vwap"] = rolling_pv / rolling_vol
    return df
