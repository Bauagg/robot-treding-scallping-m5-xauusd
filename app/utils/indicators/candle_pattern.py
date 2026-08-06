import pandas as pd


def add_candle_pattern(df: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan kolom 'candle_pat' — pola candle dasar: 1=bullish, -1=bearish, 0=none.

    Deteksi: bullish/bearish engulfing, hammer, shooting star.
    """
    df = df.copy()
    open_, close = df["open"], df["close"]
    high, low = df["high"], df["low"]

    body = (close - open_).abs()
    full_range = (high - low).replace(0, 1e-10)
    wick_up = high - pd.concat([open_, close], axis=1).max(axis=1)
    wick_down = pd.concat([open_, close], axis=1).min(axis=1) - low

    prev_open = open_.shift(1)
    prev_close = close.shift(1)

    bullish_engulf = (
        (prev_close < prev_open) & (close > open_) & (close > prev_open) & (open_ < prev_close)
    )
    bearish_engulf = (
        (prev_close > prev_open) & (close < open_) & (close < prev_open) & (open_ > prev_close)
    )
    hammer = (wick_down / full_range >= 0.6) & (body / full_range <= 0.3) & (close > open_)
    shooting_star = (wick_up / full_range >= 0.6) & (body / full_range <= 0.3) & (close < open_)

    pattern = pd.Series(0, index=df.index)
    pattern[bullish_engulf | hammer] = 1
    pattern[bearish_engulf | shooting_star] = -1

    df["candle_pat"] = pattern
    return df


def add_extra_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan kolom 'candle_ex' — pola candle multi-bar: 2=Three White Soldiers,
    1=Morning Star/Bullish Harami, -1=Evening Star/Bearish Harami, -2=Three Black Crows, 0=none.
    """
    df = df.copy()
    open_, close = df["open"], df["close"]
    is_bull = close > open_
    is_bear = close < open_

    three_soldiers = is_bull & is_bull.shift(1, fill_value=False) & is_bull.shift(2, fill_value=False)
    three_crows = is_bear & is_bear.shift(1, fill_value=False) & is_bear.shift(2, fill_value=False)

    prev_body = (close.shift(1) - open_.shift(1)).abs()
    curr_body = (close - open_).abs()
    harami_bull = (
        is_bear.shift(1, fill_value=False)
        & is_bull
        & (open_ > close.shift(1))
        & (close < open_.shift(1))
        & (curr_body < prev_body)
    )
    harami_bear = (
        is_bull.shift(1, fill_value=False)
        & is_bear
        & (open_ < close.shift(1))
        & (close > open_.shift(1))
        & (curr_body < prev_body)
    )

    pattern = pd.Series(0, index=df.index)
    pattern[harami_bull] = 1
    pattern[three_soldiers] = 2
    pattern[harami_bear] = -1
    pattern[three_crows] = -2

    df["candle_ex"] = pattern
    return df
