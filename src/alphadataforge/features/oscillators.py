from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional, Literal

from ._helpers import resolve_price_col


def compute_rsi(
    df: pd.DataFrame,
    window: int = 14,
    price_col: Optional[str] = None,
    use_adjusted: bool = True,
    method: Literal["wilder", "ema", "sma"] = "wilder",
    col_name: Optional[str] = None,
    inplace: bool = False
) -> pd.DataFrame:
    """
    Calculate Relative Strength Index (RSI).

    Args:
        df: OHLCV DataFrame with DatetimeIndex.
        window: Lookback period (default 14).
        price_col: Specific column to use. If None, uses 'Adj Close' (when use_adjusted=True) or 'Close'.
        use_adjusted: Prefer 'Adj Close' over 'Close' if available.
        method: Smoothing method: 'wilder' (standard RMA, alpha=1/window), 'ema', or 'sma'.
        col_name: Output column name (defaults to f"RSI_{window}").
        inplace: Modify DataFrame in place if True.

    Returns:
        DataFrame with the RSI column added.
    """
    if df.empty:
        return df
    if window < 1:
        raise ValueError("window must be >= 1")

    out = df if inplace else df.copy()
    target_col = resolve_price_col(out, price_col, use_adjusted)
    out_col = col_name or f"RSI_{window}"

    delta = out[target_col].diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    if method == "wilder":
        avg_gain = gain.ewm(alpha=1.0 / window, min_periods=window, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1.0 / window, min_periods=window, adjust=False).mean()
    elif method == "ema":
        avg_gain = gain.ewm(span=window, min_periods=window, adjust=False).mean()
        avg_loss = loss.ewm(span=window, min_periods=window, adjust=False).mean()
    elif method == "sma":
        avg_gain = gain.rolling(window=window, min_periods=window).mean()
        avg_loss = loss.rolling(window=window, min_periods=window).mean()
    else:
        raise ValueError(f"Unsupported method '{method}'. Choose 'wilder', 'ema', or 'sma'.")

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi_val = 100.0 - (100.0 / (1.0 + rs))
    rsi_val = np.where((avg_loss == 0) & (avg_gain > 0), 100.0, rsi_val)
    rsi_val = np.where((avg_loss == 0) & (avg_gain == 0), 50.0, rsi_val)
    rsi_series = pd.Series(rsi_val, index=out.index)
    rsi_series[avg_gain.isna() & avg_loss.isna()] = np.nan

    out[out_col] = rsi_series
    return out


def compute_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    price_col: Optional[str] = None,
    use_adjusted: bool = True,
    prefix: str = "MACD",
    inplace: bool = False
) -> pd.DataFrame:
    """
    Calculate MACD line, Signal line, and MACD Histogram.

    Adds columns:
      - ``{prefix}`` (fast EMA - slow EMA)
      - ``{prefix}_Signal`` (EMA of MACD line)
      - ``{prefix}_Hist`` (MACD - Signal)
    """
    if df.empty:
        return df
    if fast <= 0 or slow <= 0 or signal <= 0:
        raise ValueError("fast, slow, and signal periods must be positive integers.")
    if fast >= slow:
        raise ValueError(f"fast period ({fast}) must be less than slow period ({slow}).")

    out = df if inplace else df.copy()
    target_col = resolve_price_col(out, price_col, use_adjusted)

    ema_fast = out[target_col].ewm(span=fast, min_periods=fast, adjust=False).mean()
    ema_slow = out[target_col].ewm(span=slow, min_periods=slow, adjust=False).mean()

    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, min_periods=signal, adjust=False).mean()
    hist_line = macd_line - signal_line

    out[prefix] = macd_line
    out[f"{prefix}_Signal"] = signal_line
    out[f"{prefix}_Hist"] = hist_line
    return out
