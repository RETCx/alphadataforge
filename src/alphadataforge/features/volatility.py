from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional, Union, List, Literal

from ._helpers import resolve_price_col, resolve_hlc_cols


def compute_bollinger_bands(
    df: pd.DataFrame,
    window: int = 20,
    num_std: float = 2.0,
    price_col: Optional[str] = None,
    use_adjusted: bool = True,
    prefix: str = "BB",
    inplace: bool = False
) -> pd.DataFrame:
    """
    Calculate Bollinger Bands, Bandwidth, and %B.

    Adds columns:
      - ``{prefix}_Middle``: Rolling SMA
      - ``{prefix}_Upper``: Middle + num_std * std
      - ``{prefix}_Lower``: Middle - num_std * std
      - ``{prefix}_Bandwidth``: (Upper - Lower) / Middle
      - ``{prefix}_PercentB``: (Price - Lower) / (Upper - Lower)
    """
    if df.empty:
        return df
    if window < 2:
        raise ValueError("window must be >= 2 for Bollinger Bands.")

    out = df if inplace else df.copy()
    target_col = resolve_price_col(out, price_col, use_adjusted)
    price = out[target_col]

    middle = price.rolling(window=window, min_periods=window).mean()
    std = price.rolling(window=window, min_periods=window).std(ddof=0)

    upper = middle + (num_std * std)
    lower = middle - (num_std * std)
    band_range = (upper - lower).replace(0.0, np.nan)

    out[f"{prefix}_Middle"] = middle
    out[f"{prefix}_Upper"] = upper
    out[f"{prefix}_Lower"] = lower
    out[f"{prefix}_Bandwidth"] = (upper - lower) / middle.replace(0.0, np.nan)
    out[f"{prefix}_PercentB"] = (price - lower) / band_range
    return out


def compute_atr(
    df: pd.DataFrame,
    window: int = 14,
    use_adjusted: bool = True,
    method: Literal["wilder", "ema", "sma"] = "wilder",
    include_natr: bool = True,
    col_name: Optional[str] = None,
    inplace: bool = False
) -> pd.DataFrame:
    """
    Calculate Average True Range (ATR) and optionally Normalized ATR (NATR %).

    True Range = max(High - Low, |High - PrevClose|, |Low - PrevClose|).
    """
    if df.empty:
        return df
    if window < 1:
        raise ValueError("window must be >= 1")

    out = df if inplace else df.copy()
    high_col, low_col, close_col = resolve_hlc_cols(out, use_adjusted=use_adjusted)

    high = out[high_col]
    low = out[low_col]
    close = out[close_col]
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    true_range[high.isna() | low.isna() | close.isna()] = np.nan

    if method == "wilder":
        atr_val = true_range.ewm(alpha=1.0 / window, min_periods=window, adjust=False).mean()
    elif method == "ema":
        atr_val = true_range.ewm(span=window, min_periods=window, adjust=False).mean()
    elif method == "sma":
        atr_val = true_range.rolling(window=window, min_periods=window).mean()
    else:
        raise ValueError(f"Unsupported method '{method}'. Choose 'wilder', 'ema', or 'sma'.")

    atr_col = col_name or f"ATR_{window}"
    out[atr_col] = atr_val
    if include_natr:
        out[f"NATR_{window}"] = (atr_val / close.replace(0.0, np.nan)) * 100.0

    return out


def compute_rolling_volatility(
    df: pd.DataFrame,
    windows: Union[int, List[int]] = 20,
    price_col: Optional[str] = None,
    use_adjusted: bool = True,
    annualize: bool = True,
    trading_days: int = 252,
    log_returns: bool = True,
    estimator: Literal["close", "parkinson", "garman_klass"] = "close",
    inplace: bool = False
) -> pd.DataFrame:
    """
    Calculate Rolling Realized Volatility across one or multiple lookback windows.

    Supports 'close' (standard close-to-close), 'parkinson' (High-Low), and 'garman_klass' (OHLC).
    """
    if df.empty:
        return df

    out = df if inplace else df.copy()
    win_list = [windows] if isinstance(windows, int) else list(windows)
    scale = np.sqrt(trading_days) if annualize else 1.0

    if estimator == "close":
        target_col = resolve_price_col(out, price_col, use_adjusted)
        prices = out[target_col]
        if log_returns:
            ret = np.log(prices / prices.shift(1))
        else:
            ret = prices.pct_change()

        for w in win_list:
            if w < 2:
                raise ValueError("Volatility window must be >= 2.")
            col_label = f"Volatility_{w}d"
            out[col_label] = ret.rolling(window=w, min_periods=w).std(ddof=1) * scale

    elif estimator == "parkinson":
        high_col, low_col, _ = resolve_hlc_cols(out, use_adjusted=use_adjusted)
        hl_log_sq = (np.log(out[high_col] / out[low_col])) ** 2
        factor = 1.0 / (4.0 * np.log(2.0))
        for w in win_list:
            if w < 2:
                raise ValueError("Volatility window must be >= 2.")
            var = factor * hl_log_sq.rolling(window=w, min_periods=w).mean()
            out[f"Volatility_Parkinson_{w}d"] = np.sqrt(var) * scale

    elif estimator == "garman_klass":
        high_col, low_col, close_col = resolve_hlc_cols(out, use_adjusted=use_adjusted)
        open_col = "Adj Open" if (use_adjusted and "Adj Open" in out.columns) else (
            "Open" if "Open" in out.columns else "open"
        )
        if open_col not in out.columns:
            raise ValueError("Garman-Klass estimator requires an Open column.")
        log_hl = np.log(out[high_col] / out[low_col]) ** 2
        log_co = np.log(out[close_col] / out[open_col]) ** 2
        gk_daily = 0.5 * log_hl - (2.0 * np.log(2.0) - 1.0) * log_co
        for w in win_list:
            if w < 2:
                raise ValueError("Volatility window must be >= 2.")
            var = gk_daily.rolling(window=w, min_periods=w).mean().clip(lower=0.0)
            out[f"Volatility_GK_{w}d"] = np.sqrt(var) * scale
    else:
        raise ValueError(
            f"Unsupported estimator '{estimator}'. Choose 'close', 'parkinson', or 'garman_klass'."
        )

    return out
