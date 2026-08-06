import pandas as pd

DEFAULT_PERIOD = 14


def add_mfi(df: pd.DataFrame, period: int = DEFAULT_PERIOD) -> pd.DataFrame:
    """Tambahkan kolom 'mfi' (Money Flow Index — RSI berbasis volume)."""
    df = df.copy()
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    raw_money_flow = typical_price * df["volume"]

    price_up = typical_price.diff() > 0
    positive_flow = raw_money_flow.where(price_up, 0).rolling(period).sum()
    negative_flow = raw_money_flow.where(~price_up, 0).rolling(period).sum()

    money_ratio = positive_flow / negative_flow.replace(0, 1e-10)
    df["mfi"] = (100 - (100 / (1 + money_ratio))).fillna(50)
    return df
