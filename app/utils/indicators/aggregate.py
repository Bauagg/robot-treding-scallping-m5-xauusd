import pandas as pd

from app.utils.indicators.adx import add_adx
from app.utils.indicators.atr import add_atr
from app.utils.indicators.bollinger_bands import add_bollinger_bands
from app.utils.indicators.bos_choch import add_bos_choch
from app.utils.indicators.candle_pattern import add_candle_pattern, add_extra_patterns
from app.utils.indicators.cci import add_cci
from app.utils.indicators.ema import add_ema
from app.utils.indicators.fair_value_gap import add_fair_value_gap
from app.utils.indicators.fibonacci import add_fibonacci_levels
from app.utils.indicators.ichimoku import add_ichimoku
from app.utils.indicators.liquidity_sweep import add_liquidity_sweep
from app.utils.indicators.macd import add_macd
from app.utils.indicators.mfi import add_mfi
from app.utils.indicators.momentum_chain import add_momentum_chain
from app.utils.indicators.obv import add_obv
from app.utils.indicators.order_block import add_order_block
from app.utils.indicators.psar import add_psar
from app.utils.indicators.rsi import add_rsi
from app.utils.indicators.rsi_divergence import add_rsi_divergence
from app.utils.indicators.sma import add_sma
from app.utils.indicators.stochastic import add_stochastic
from app.utils.indicators.supertrend import add_supertrend
from app.utils.indicators.vwap import add_vwap
from app.utils.indicators.williams_r import add_williams_r


def add_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Hitung dan tambahkan seluruh indikator ke DataFrame OHLCV sekaligus.

    Input df wajib punya kolom: open, high, low, close, volume.
    Urutan pemanggilan mengikuti dependency (mis. ADX/Supertrend butuh ATR).
    """
    df = df.copy()

    # Trend
    df = add_ema(df)
    df = add_sma(df)
    df = add_macd(df)
    df = add_adx(df)
    df = add_supertrend(df)
    df = add_psar(df)
    df = add_ichimoku(df)

    # Momentum
    df = add_rsi(df)
    df = add_stochastic(df)
    df = add_cci(df)
    df = add_williams_r(df)
    df = add_mfi(df)

    # Volatility
    df = add_atr(df)
    df = add_bollinger_bands(df)

    # Volume
    df = add_obv(df)
    df = add_vwap(df)

    # Struktur & pola tambahan
    df = add_fibonacci_levels(df)
    df = add_rsi_divergence(df)
    df = add_momentum_chain(df)

    # Smart Money Concepts
    df = add_fair_value_gap(df)
    df = add_order_block(df)
    df = add_bos_choch(df)
    df = add_liquidity_sweep(df)

    # Candle patterns
    df = add_candle_pattern(df)
    df = add_extra_patterns(df)

    return df
