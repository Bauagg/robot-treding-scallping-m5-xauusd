import pandas as pd

DEFAULT_TENKAN = 9
DEFAULT_KIJUN = 26
DEFAULT_SENKOU_B = 52
DEFAULT_SHIFT = 26


def add_ichimoku(
    df: pd.DataFrame,
    tenkan_period: int = DEFAULT_TENKAN,
    kijun_period: int = DEFAULT_KIJUN,
    senkou_b_period: int = DEFAULT_SENKOU_B,
    shift: int = DEFAULT_SHIFT,
) -> pd.DataFrame:
    """Tambahkan kolom Ichimoku Cloud: ichi_tenkan, ichi_kijun, ichi_span_a, ichi_span_b,
    ichi_cloud_top, ichi_cloud_bot, ichi_cloud_bull, ichi_tk_bull, ichi_tk_bear."""
    df = df.copy()

    def _midpoint(period: int) -> pd.Series:
        return (df["high"].rolling(period).max() + df["low"].rolling(period).min()) / 2

    tenkan = _midpoint(tenkan_period)
    kijun = _midpoint(kijun_period)
    span_a = ((tenkan + kijun) / 2).shift(shift)
    span_b = _midpoint(senkou_b_period).shift(shift)

    df["ichi_tenkan"] = tenkan
    df["ichi_kijun"] = kijun
    df["ichi_span_a"] = span_a
    df["ichi_span_b"] = span_b
    df["ichi_cloud_top"] = pd.concat([span_a, span_b], axis=1).max(axis=1)
    df["ichi_cloud_bot"] = pd.concat([span_a, span_b], axis=1).min(axis=1)
    df["ichi_cloud_bull"] = (span_a > span_b).astype(int)

    tk_cross = (tenkan > kijun).astype(int).diff().fillna(0)
    df["ichi_tk_bull"] = (tk_cross == 1).astype(int)
    df["ichi_tk_bear"] = (tk_cross == -1).astype(int)
    return df
