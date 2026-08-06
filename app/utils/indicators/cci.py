import numpy as np
import pandas as pd

DEFAULT_PERIOD = 20
CONSTANT = 0.015


def add_cci(df: pd.DataFrame, period: int = DEFAULT_PERIOD) -> pd.DataFrame:
    """Tambahkan kolom 'cci' (Commodity Channel Index)."""
    df = df.copy()
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    sma = typical_price.rolling(period).mean()
    mean_dev = typical_price.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean(), raw=True)

    df["cci"] = (typical_price - sma) / (CONSTANT * mean_dev.replace(0, 1e-10))
    return df
