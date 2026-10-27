from __future__ import annotations

import pandas as pd
from typing import Optional, Union, List, Dict, Literal

from ._helpers import resolve_hlc_cols
from .oscillators import compute_rsi, compute_macd
from .volatility import compute_bollinger_bands, compute_atr, compute_rolling_volatility
from .momentum import compute_momentum, compute_cross_sectional_momentum


class TechnicalIndicators:
    """
    Unified Frontend Facade for Technical Indicators & Quantitative Momentum Factors.

    Delegates calculations to modular backend implementations:
      - ``oscillators.py``: RSI, MACD
      - ``volatility.py``: Bollinger Bands, ATR/NATR, Rolling Volatility (Close, Parkinson, Garman-Klass)
      - ``momentum.py``: Time-Series Momentum & Cross-Sectional Momentum
    """

    rsi = staticmethod(compute_rsi)
    macd = staticmethod(compute_macd)
    bollinger_bands = staticmethod(compute_bollinger_bands)
    atr = staticmethod(compute_atr)
    rolling_volatility = staticmethod(compute_rolling_volatility)
    momentum = staticmethod(compute_momentum)
    cross_sectional_momentum = staticmethod(compute_cross_sectional_momentum)

    @staticmethod
    def add_all(
        data: Union[pd.DataFrame, Dict[str, pd.DataFrame]],
        use_adjusted: bool = True,
        rsi_window: int = 14,
        macd_params: tuple[int, int, int] = (12, 26, 9),
        bb_window: int = 20,
        bb_std: float = 2.0,
        atr_window: int = 14,
        vol_windows: Union[int, List[int]] = (20, 60),
        mom_windows: Union[int, List[int]] = (21, 63, 126, 252),
        inplace: bool = False
    ) -> Union[pd.DataFrame, Dict[str, pd.DataFrame]]:
        """
        Compute all core technical indicators (RSI, MACD, Bollinger Bands, ATR,
        Rolling Volatility, and Time-Series Momentum) on a DataFrame or Dict of DataFrames.
        """
        if isinstance(data, dict):
            return {
                sym: TechnicalIndicators.add_all(
                    df,
                    use_adjusted=use_adjusted,
                    rsi_window=rsi_window,
                    macd_params=macd_params,
                    bb_window=bb_window,
                    bb_std=bb_std,
                    atr_window=atr_window,
                    vol_windows=vol_windows,
                    mom_windows=mom_windows,
                    inplace=False,
                )
                for sym, df in data.items()
            }

        if data.empty:
            return data

        out = data if inplace else data.copy()
        compute_rsi(out, window=rsi_window, use_adjusted=use_adjusted, inplace=True)
        compute_macd(
            out,
            fast=macd_params[0],
            slow=macd_params[1],
            signal=macd_params[2],
            use_adjusted=use_adjusted,
            inplace=True,
        )
        compute_bollinger_bands(
            out, window=bb_window, num_std=bb_std, use_adjusted=use_adjusted, inplace=True
        )
        try:
            resolve_hlc_cols(out, use_adjusted=use_adjusted)
            compute_atr(out, window=atr_window, use_adjusted=use_adjusted, inplace=True)
        except ValueError:
            pass

        compute_rolling_volatility(
            out, windows=vol_windows, use_adjusted=use_adjusted, inplace=True
        )
        compute_momentum(
            out, windows=mom_windows, use_adjusted=use_adjusted, inplace=True
        )
        return out


# Alias for top-level unified feature access
Features = TechnicalIndicators
