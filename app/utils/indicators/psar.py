import numpy as np
import pandas as pd

DEFAULT_AF_START = 0.02
DEFAULT_AF_STEP = 0.02
DEFAULT_AF_MAX = 0.20


def add_psar(
    df: pd.DataFrame,
    af_start: float = DEFAULT_AF_START,
    af_step: float = DEFAULT_AF_STEP,
    af_max: float = DEFAULT_AF_MAX,
) -> pd.DataFrame:
    """Tambahkan kolom 'psar', 'psar_dir' (1=BUY/-1=SELL) — Parabolic SAR."""
    df = df.copy()
    high = df["high"].values
    low = df["low"].values

    psar = np.zeros(len(df))
    direction = np.ones(len(df), dtype=int)
    af = af_start
    ep = high[0]
    psar[0] = low[0]

    for i in range(1, len(df)):
        prev_psar = psar[i - 1]
        prev_dir = direction[i - 1]

        if prev_dir == 1:
            psar[i] = prev_psar + af * (ep - prev_psar)
            psar[i] = min(psar[i], low[i - 1], low[i - 2] if i >= 2 else low[i - 1])
            if low[i] < psar[i]:
                direction[i] = -1
                psar[i] = ep
                ep = low[i]
                af = af_start
            else:
                direction[i] = 1
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + af_step, af_max)
        else:
            psar[i] = prev_psar + af * (ep - prev_psar)
            psar[i] = max(psar[i], high[i - 1], high[i - 2] if i >= 2 else high[i - 1])
            if high[i] > psar[i]:
                direction[i] = 1
                psar[i] = ep
                ep = high[i]
                af = af_start
            else:
                direction[i] = -1
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + af_step, af_max)

    df["psar"] = psar
    df["psar_dir"] = direction
    return df
