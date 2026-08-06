import pandas as pd

DEFAULT_PERIOD = 20
DEFAULT_STD = 2.0


def add_bollinger_bands(df: pd.DataFrame, period: int = DEFAULT_PERIOD, std: float = DEFAULT_STD) -> pd.DataFrame:
    """Tambahkan kolom 'bb_upper', 'bb_mid', 'bb_lower', 'bb_pct' (Bollinger Bands)."""
    df = df.copy()
    mid = df["close"].rolling(period).mean()
    dev = df["close"].rolling(period).std()

    df["bb_mid"] = mid
    df["bb_upper"] = mid + std * dev
    df["bb_lower"] = mid - std * dev
    rng = (df["bb_upper"] - df["bb_lower"]).replace(0, 1e-10)
    df["bb_pct"] = (df["close"] - df["bb_lower"]) / rng
    return df
