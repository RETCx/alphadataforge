from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional, Union, List, Dict

from ._helpers import resolve_price_col, to_wide_prices


def compute_momentum(
    df: pd.DataFrame,
    windows: Union[int, List[int]] = (21, 63, 126, 252),
    include_12_1: bool = True,
    price_col: Optional[str] = None,
    use_adjusted: bool = True,
    inplace: bool = False
) -> pd.DataFrame:
    """
    Calculate Time-Series Momentum returns over multiple horizons for a single ticker.

    Args:
        df: OHLCV DataFrame.
        windows: Lookback periods in trading days (default: 21=1M, 63=3M, 126=6M, 252=12M).
        include_12_1: Also compute classic institutional 12-1 Month Momentum
                      (return from t-252 to t-21, skipping the most recent month's reversal).
        price_col: Specific price column to use.
        use_adjusted: Prefer 'Adj Close' over 'Close' if available.
        inplace: Modify DataFrame in place if True.
    """
    if df.empty:
        return df

    out = df if inplace else df.copy()
    target_col = resolve_price_col(out, price_col, use_adjusted)
    prices = out[target_col]

    win_list = [windows] if isinstance(windows, int) else list(windows)
    for w in win_list:
        if w < 1:
            raise ValueError("Momentum lookback window must be >= 1.")
        out[f"Mom_{w}d"] = prices.pct_change(periods=w)

    if include_12_1:
        out["Mom_12_1M"] = (prices.shift(21) / prices.shift(252)) - 1.0

    return out


def compute_cross_sectional_momentum(
    universe_data: Union[Dict[str, pd.DataFrame], pd.DataFrame],
    lookback: int = 252,
    skip_recent: int = 21,
    price_col: Optional[str] = None,
    use_adjusted: bool = True,
    risk_adjusted: bool = False,
    winsorize_limits: Optional[tuple[float, float]] = (0.01, 0.99)
) -> pd.DataFrame:
    """
    Calculate Cross-Sectional Momentum across a multi-asset universe at each date.

    Accepts:
      1. ``Dict[str, pd.DataFrame]`` — direct output from ``Price.get(["AAPL", "MSFT", ...])``
      2. Wide ``pd.DataFrame`` — index = Date, columns = Ticker symbols, values = Prices
      3. Long ``pd.DataFrame`` — columns containing ``['symbol', 'date', 'close']`` (e.g. SQLite table)

    Returns:
        Long-format DataFrame indexed by ``(Date, symbol)`` with columns:
        ``['Price', 'Momentum_Return', 'Realized_Vol', 'Risk_Adj_Momentum', 'CS_Rank_Pct', 'CS_ZScore', 'CS_Decile']``.
    """
    if lookback <= 0:
        raise ValueError("lookback must be > 0.")
    if skip_recent < 0 or skip_recent >= lookback:
        raise ValueError("skip_recent must satisfy 0 <= skip_recent < lookback.")

    wide_prices = to_wide_prices(
        universe_data, price_col=price_col, use_adjusted=use_adjusted
    )
    if wide_prices.empty:
        return pd.DataFrame()

    wide_prices = wide_prices.sort_index(ascending=True)

    if skip_recent > 0:
        mom_ret = (wide_prices.shift(skip_recent) / wide_prices.shift(lookback)) - 1.0
    else:
        mom_ret = wide_prices.pct_change(periods=lookback, fill_method=None)

    eff_window = lookback - skip_recent
    daily_ret = wide_prices.pct_change(fill_method=None)
    if skip_recent > 0:
        realized_vol = (
            daily_ret.shift(skip_recent)
            .rolling(window=eff_window, min_periods=max(5, eff_window // 2))
            .std()
            * np.sqrt(252)
        )
    else:
        realized_vol = (
            daily_ret.rolling(window=eff_window, min_periods=max(5, eff_window // 2)).std()
            * np.sqrt(252)
        )

    risk_adj_mom = mom_ret / realized_vol.replace(0.0, np.nan)
    target_signal = risk_adj_mom if risk_adjusted else mom_ret

    cs_rank_pct = target_signal.rank(axis=1, pct=True, ascending=True)

    sig_for_z = target_signal.copy()
    if winsorize_limits is not None:
        q_low, q_high = winsorize_limits
        lower_bound = sig_for_z.quantile(q_low, axis=1)
        upper_bound = sig_for_z.quantile(q_high, axis=1)
        sig_for_z = sig_for_z.clip(lower=lower_bound, upper=upper_bound, axis=0)

    row_mean = sig_for_z.mean(axis=1)
    row_std = sig_for_z.std(axis=1, ddof=0).replace(0.0, np.nan)
    cs_zscore = sig_for_z.sub(row_mean, axis=0).div(row_std, axis=0)

    cs_decile = np.ceil(cs_rank_pct * 10.0).clip(1.0, 10.0)

    wide_prices.index.name = "Date"
    wide_prices.columns.name = "symbol"

    result = pd.DataFrame({
        "Price": wide_prices.stack(),
        "Momentum_Return": mom_ret.stack(),
        "Realized_Vol": realized_vol.stack(),
        "Risk_Adj_Momentum": risk_adj_mom.stack(),
        "CS_Rank_Pct": cs_rank_pct.stack(),
        "CS_ZScore": cs_zscore.stack(),
        "CS_Decile": cs_decile.stack(),
    })
    result.index.names = ["Date", "symbol"]
    return result.dropna(subset=["Momentum_Return"])
