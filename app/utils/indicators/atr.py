import pandas as pd

DEFAULT_PERIOD = 14


def add_atr(df: pd.DataFrame, period: int = DEFAULT_PERIOD) -> pd.DataFrame:
    """Tambahkan kolom 'atr' (Average True Range)."""
    df = df.copy()
    prev_close = df["close"].shift(1)
    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    df["atr"] = true_range.ewm(alpha=1 / period, adjust=False).mean()
    return df
