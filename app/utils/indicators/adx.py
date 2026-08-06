import pandas as pd

from app.utils.indicators.atr import add_atr

DEFAULT_PERIOD = 14


def add_adx(df: pd.DataFrame, period: int = DEFAULT_PERIOD) -> pd.DataFrame:
    """Tambahkan kolom 'adx', 'di_pos', 'di_neg' (Average Directional Index + Directional Indicators)."""
    df = add_atr(df, period=period)

    up_move = df["high"].diff()
    down_move = -df["low"].diff()

    plus_dm = pd.Series(0.0, index=df.index)
    minus_dm = pd.Series(0.0, index=df.index)
    plus_dm[(up_move > down_move) & (up_move > 0)] = up_move[(up_move > down_move) & (up_move > 0)]
    minus_dm[(down_move > up_move) & (down_move > 0)] = down_move[(down_move > up_move) & (down_move > 0)]

    atr_smooth = df["atr"].replace(0, 1e-10)
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_smooth
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_smooth

    dx = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, 1e-10))

    df["di_pos"] = plus_di
    df["di_neg"] = minus_di
    df["adx"] = dx.ewm(alpha=1 / period, adjust=False).mean()
    return df
