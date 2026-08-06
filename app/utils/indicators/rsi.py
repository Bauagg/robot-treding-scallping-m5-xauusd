import pandas as pd

DEFAULT_PERIOD = 14


def add_rsi(df: pd.DataFrame, period: int = DEFAULT_PERIOD) -> pd.DataFrame:
    """Tambahkan kolom 'rsi' (Relative Strength Index)."""
    df = df.copy()
    delta = df["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, 1e-10)
    df["rsi"] = (100 - (100 / (1 + rs))).fillna(50)
    return df
