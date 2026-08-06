import pandas as pd


def add_order_block(df: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan kolom ob_bull, ob_bear (Order Block).

    Bullish OB: candle bearish diikuti minimal 2 dari 3 candle berikutnya bullish (impulse naik).
    Bearish OB: candle bullish diikuti minimal 2 dari 3 candle berikutnya bearish (impulse turun).
    """
    df = df.copy()
    is_bearish = df["close"] < df["open"]
    is_bullish = df["close"] > df["open"]

    next_bullish_count = (
        is_bullish.shift(-1, fill_value=False).astype(int)
        + is_bullish.shift(-2, fill_value=False).astype(int)
        + is_bullish.shift(-3, fill_value=False).astype(int)
    )
    next_bearish_count = (
        is_bearish.shift(-1, fill_value=False).astype(int)
        + is_bearish.shift(-2, fill_value=False).astype(int)
        + is_bearish.shift(-3, fill_value=False).astype(int)
    )

    df["ob_bull"] = (is_bearish & (next_bullish_count >= 2)).astype(int)
    df["ob_bear"] = (is_bullish & (next_bearish_count >= 2)).astype(int)
    return df
