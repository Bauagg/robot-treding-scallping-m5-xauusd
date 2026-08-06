import pandas as pd

DEFAULT_K_PERIOD = 14
DEFAULT_D_PERIOD = 3


def add_stochastic(
    df: pd.DataFrame, k_period: int = DEFAULT_K_PERIOD, d_period: int = DEFAULT_D_PERIOD
) -> pd.DataFrame:
    """Tambahkan kolom 'stoch_k', 'stoch_d' (Stochastic Oscillator)."""
    df = df.copy()
    lowest_low = df["low"].rolling(k_period).min()
    highest_high = df["high"].rolling(k_period).max()
    rng = (highest_high - lowest_low).replace(0, 1e-10)

    df["stoch_k"] = 100 * (df["close"] - lowest_low) / rng
    df["stoch_d"] = df["stoch_k"].rolling(d_period).mean()
    return df
