import pandas as pd

DEFAULT_EMA_PERIOD = 20


def add_obv(df: pd.DataFrame, ema_period: int = DEFAULT_EMA_PERIOD) -> pd.DataFrame:
    """Tambahkan kolom 'obv', 'obv_ema' (On-Balance Volume)."""
    df = df.copy()
    direction = df["close"].diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    df["obv"] = (direction * df["volume"]).cumsum()
    df["obv_ema"] = df["obv"].ewm(span=ema_period, adjust=False).mean()
    return df
