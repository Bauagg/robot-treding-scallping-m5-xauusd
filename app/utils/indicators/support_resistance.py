import numpy as np
import pandas as pd

DEFAULT_PIVOT_LOOKBACK = 5  # candle di kiri & kanan yang harus lebih rendah/tinggi supaya jadi pivot
DEFAULT_MAX_LEVELS = 5  # berapa pivot terakhir (per sisi) yang masih dianggap "relevan"


def add_swing_pivots(df: pd.DataFrame, lookback: int = DEFAULT_PIVOT_LOOKBACK) -> pd.DataFrame:
    """Tambahkan kolom pivot_high, pivot_low (level harga di titik pivot, NaN kalau bukan pivot).

    Beda dari rolling max/min (bos_choch.py/fibonacci.py) -- pivot sejati butuh konfirmasi dari
    KEDUA sisi (candle sebelum DAN sesudah harus lebih rendah/tinggi), bukan cuma lihat ke
    belakang. Ini artinya pivot candle ke-i baru "terkonfirmasi" `lookback` candle SETELAHNYA --
    dipakai di caller dgn shift yang sesuai supaya tidak lookahead saat live (lihat
    build_sr_levels()).
    """
    df = df.copy()
    high = df["high"].to_numpy()
    low = df["low"].to_numpy()
    n = len(df)

    pivot_high = np.full(n, np.nan)
    pivot_low = np.full(n, np.nan)

    for i in range(lookback, n - lookback):
        window_high = high[i - lookback : i + lookback + 1]
        window_low = low[i - lookback : i + lookback + 1]
        if high[i] == window_high.max() and (window_high == high[i]).sum() == 1:
            pivot_high[i] = high[i]
        if low[i] == window_low.min() and (window_low == low[i]).sum() == 1:
            pivot_low[i] = low[i]

    df["pivot_high"] = pivot_high
    df["pivot_low"] = pivot_low
    return df


def build_sr_levels(df: pd.DataFrame, lookback: int = DEFAULT_PIVOT_LOOKBACK, max_levels: int = DEFAULT_MAX_LEVELS) -> pd.DataFrame:
    """Tambahkan kolom sr_resistance, sr_support -- level pivot TERDEKAT di atas/bawah close
    candle saat ini, dari pivot yang sudah TERKONFIRMASI (candle ke-i cuma boleh pakai pivot
    yang confirm-nya sudah lewat, yaitu i - lookback, supaya tidak lookahead saat dipakai live).

    max_levels: dari seluruh pivot yang confirmed s/d saat ini, cuma `max_levels` pivot
    TERAKHIR di tiap sisi (atas & bawah) yang dianggap masih relevan -- level pivot yang jauh di
    masa lalu (misal ratusan candle lalu) biasanya sudah tidak relevan lagi.
    """
    df = add_swing_pivots(df, lookback=lookback)
    n = len(df)
    close = df["close"].to_numpy()
    pivot_high = df["pivot_high"].to_numpy()
    pivot_low = df["pivot_low"].to_numpy()

    resistance = np.full(n, np.nan)
    support = np.full(n, np.nan)

    recent_highs: list[float] = []
    recent_lows: list[float] = []
    confirmed_upto = -1

    for i in range(n):
        # Pivot candle j confirmed begitu kita sampai di candle j + lookback (kanan-nya lengkap)
        newly_confirmed = i - lookback
        if newly_confirmed > confirmed_upto and 0 <= newly_confirmed < n:
            confirmed_upto = newly_confirmed
            if not np.isnan(pivot_high[newly_confirmed]):
                recent_highs.append(pivot_high[newly_confirmed])
                recent_highs = recent_highs[-max_levels:]
            if not np.isnan(pivot_low[newly_confirmed]):
                recent_lows.append(pivot_low[newly_confirmed])
                recent_lows = recent_lows[-max_levels:]

        c = close[i]
        above = [h for h in recent_highs if h > c]
        below = [lo for lo in recent_lows if lo < c]
        resistance[i] = min(above) if above else np.nan
        support[i] = max(below) if below else np.nan

    df["sr_resistance"] = resistance
    df["sr_support"] = support
    return df
