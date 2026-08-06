import pandas as pd

from app.utils.indicators.rsi import add_rsi

DEFAULT_LOOKBACK = 15


def add_rsi_divergence(df: pd.DataFrame, lookback: int = DEFAULT_LOOKBACK) -> pd.DataFrame:
    """Tambahkan kolom rsi_bull_div, rsi_bear_div, rsi_hid_bull, rsi_hid_bear (RSI Divergence).

    Regular divergence = sinyal reversal (harga & RSI berlawanan arah di 2 pivot terakhir).
    Hidden divergence  = sinyal continuation (pullback dalam trend yang berlanjut).
    """
    df = add_rsi(df)
    n = len(df)
    bull_div = [0] * n
    bear_div = [0] * n
    hid_bull = [0] * n
    hid_bear = [0] * n

    low = df["low"].values
    high = df["high"].values
    rsi = df["rsi"].values

    for i in range(lookback, n):
        window_low = low[i - lookback : i + 1]
        window_high = high[i - lookback : i + 1]
        window_rsi = rsi[i - lookback : i + 1]

        prev_low_idx = window_low[:-1].argmin()
        prev_high_idx = window_high[:-1].argmax()

        curr_low, curr_rsi = low[i], rsi[i]
        curr_high = high[i]
        prev_low, prev_low_rsi = window_low[prev_low_idx], window_rsi[prev_low_idx]
        prev_high, prev_high_rsi = window_high[prev_high_idx], window_rsi[prev_high_idx]

        # Regular bullish: harga Lower Low, RSI Higher Low
        if curr_low < prev_low and curr_rsi > prev_low_rsi:
            bull_div[i] = 1
        # Regular bearish: harga Higher High, RSI Lower High
        if curr_high > prev_high and curr_rsi < prev_high_rsi:
            bear_div[i] = 1
        # Hidden bullish: harga Higher Low, RSI Lower Low (pullback uptrend)
        if curr_low > prev_low and curr_rsi < prev_low_rsi:
            hid_bull[i] = 1
        # Hidden bearish: harga Lower High, RSI Higher High (pullback downtrend)
        if curr_high < prev_high and curr_rsi > prev_high_rsi:
            hid_bear[i] = 1

    df["rsi_bull_div"] = bull_div
    df["rsi_bear_div"] = bear_div
    df["rsi_hid_bull"] = hid_bull
    df["rsi_hid_bear"] = hid_bear
    return df
