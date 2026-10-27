from __future__ import annotations

import pandas as pd
from typing import Optional, Union, Dict


def resolve_price_col(
    df: pd.DataFrame,
    price_col: Optional[str] = None,
    use_adjusted: bool = True
) -> str:
    """Resolve the target price column from a DataFrame."""
    if price_col is not None:
        if price_col not in df.columns:
            raise ValueError(
                f"Column '{price_col}' not found in DataFrame. Available: {list(df.columns)}"
            )
        return price_col

    if use_adjusted and "Adj Close" in df.columns and df["Adj Close"].notna().any():
        return "Adj Close"
    for candidate in ("Close", "close", "Adj Close", "adj_close"):
        if candidate in df.columns:
            return candidate
    raise ValueError(
        f"Could not automatically resolve a price column from {list(df.columns)}. "
        "Please specify `price_col` explicitly."
    )


def resolve_hlc_cols(
    df: pd.DataFrame,
    use_adjusted: bool = True
) -> tuple[str, str, str]:
    """Resolve High, Low, Close column names (adjusted or raw)."""
    if use_adjusted and {"Adj High", "Adj Low", "Adj Close"}.issubset(df.columns):
        if df["Adj High"].notna().any() and df["Adj Low"].notna().any():
            return "Adj High", "Adj Low", "Adj Close"

    if {"High", "Low", "Close"}.issubset(df.columns):
        return "High", "Low", "Close"
    if {"high", "low", "close"}.issubset(df.columns):
        return "high", "low", "close"

    raise ValueError(
        f"ATR / OHLC calculations require High, Low, Close columns. Got: {list(df.columns)}"
    )


def to_wide_prices(
    universe_data: Union[Dict[str, pd.DataFrame], pd.DataFrame],
    price_col: Optional[str] = None,
    use_adjusted: bool = True
) -> pd.DataFrame:
    """Convert Dict[str, DataFrame], long DataFrame, or wide DataFrame to a wide price matrix."""
    if isinstance(universe_data, dict):
        series_dict = {}
        for sym, df in universe_data.items():
            if df is None or df.empty:
                continue
            col = resolve_price_col(df, price_col=price_col, use_adjusted=use_adjusted)
            s = df[col].copy()
            if isinstance(s.index, pd.DatetimeIndex) and s.index.tz is not None:
                s.index = s.index.tz_localize(None)
            series_dict[sym] = s
        if not series_dict:
            return pd.DataFrame()
        return pd.DataFrame(series_dict)

    if isinstance(universe_data, pd.DataFrame):
        if universe_data.empty:
            return pd.DataFrame()

        cols_lower = {c.lower(): c for c in universe_data.columns}
        # Long-format DataFrame (e.g. symbol, date, close from SQLite)
        if "symbol" in cols_lower and (
            "date" in cols_lower or isinstance(universe_data.index, pd.DatetimeIndex)
        ):
            sym_col = cols_lower["symbol"]
            val_col = resolve_price_col(universe_data, price_col=price_col, use_adjusted=use_adjusted)
            df_long = universe_data.copy()
            if "date" in cols_lower:
                date_col = cols_lower["date"]
                df_long[date_col] = pd.to_datetime(df_long[date_col])
                wide = df_long.pivot_table(
                    index=date_col, columns=sym_col, values=val_col, aggfunc="last"
                )
            else:
                wide = df_long.pivot_table(
                    index=df_long.index, columns=sym_col, values=val_col, aggfunc="last"
                )
            if isinstance(wide.index, pd.DatetimeIndex) and wide.index.tz is not None:
                wide.index = wide.index.tz_localize(None)
            return wide

        # Already wide (index = Date, columns = symbols)
        wide = universe_data.copy()
        if not isinstance(wide.index, pd.DatetimeIndex):
            wide.index = pd.to_datetime(wide.index)
        if wide.index.tz is not None:
            wide.index = wide.index.tz_localize(None)
        return wide

    raise TypeError("universe_data must be a Dict[str, pd.DataFrame] or a pandas DataFrame.")
