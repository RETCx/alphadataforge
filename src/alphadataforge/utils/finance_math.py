import pandas as pd
import numpy as np

def calculate_adjusted_prices(
    raw_df: pd.DataFrame, 
    dividends_df: pd.DataFrame, 
    splits_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Calculates backward-adjusted OHLCV prices using raw daily data, dividends, and splits.
    
    Expected inputs:
    - raw_df: DataFrame with DatetimeIndex and columns ['Open', 'High', 'Low', 'Close', 'Volume']
    - dividends_df: DataFrame with DatetimeIndex (ex-dividend date) and column 'Dividend'
    - splits_df: DataFrame with DatetimeIndex (effective date) and column 'SplitFactor'
      (SplitFactor > 1 means a forward split, e.g., 4.0 for a 4-for-1 split)
    
    Returns:
    - DataFrame with same index and columns ['Open', 'High', 'Low', 'Close', 'Volume', 'Adj Close', ...]
    """
    if raw_df.empty:
        return raw_df

    required_cols = {'Open', 'High', 'Low', 'Close', 'Volume'}
    missing = required_cols - set(raw_df.columns)
    if missing:
        raise ValueError(
            f"calculate_adjusted_prices requires columns {required_cols}. "
            f"Missing: {missing}. Got: {list(raw_df.columns)}"
        )

    df = raw_df.copy()
    
    # Ensure index is sorted ascending (oldest to newest)
    df = df.sort_index(ascending=True)
    
    # 1. Join Dividends and Splits onto the main DataFrame
    # Ensure df index is tz-naive
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    df['Dividend'] = 0.0
    if dividends_df is not None and not dividends_df.empty:
        if dividends_df.index.tz is not None:
            dividends_df.index = dividends_df.index.tz_localize(None)
        # Align dividends by date
        div_series = dividends_df['Dividend'] if 'Dividend' in dividends_df.columns else dividends_df.iloc[:, 0]
        divs = div_series.groupby(dividends_df.index).sum()
        df['Dividend'] = df.index.map(divs).fillna(0.0)
        
    df['SplitFactor'] = 1.0
    if splits_df is not None and not splits_df.empty:
        if splits_df.index.tz is not None:
            splits_df.index = splits_df.index.tz_localize(None)
        # Align splits by date (if multiple splits on same day, multiply them)
        split_series = splits_df['SplitFactor'] if 'SplitFactor' in splits_df.columns else splits_df.iloc[:, 0]
        splits = split_series.groupby(splits_df.index).prod()
        df['SplitFactor'] = df.index.map(splits).fillna(1.0)
        
    # 2. Calculate Cumulative Split Multiplier (Backward)
    # If a split is effective ON day t, prices on day t are ALREADY split.
    # Prices on day t-1 must be divided by SplitFactor to be comparable.
    # So CumSplit on day t-1 should multiply SplitFactor from day t.
    df['CumSplit'] = df['SplitFactor'].iloc[::-1].cumprod().shift(1).fillna(1.0).iloc[::-1]
    
    # 3. Calculate Split-Adjusted Close (needed for dividend adjustment)
    df['SplitAdjClose'] = df['Close'] / df['CumSplit']
    
    # 4. Calculate Dividend Adjustment Factor
    # DivFactor_t = (PrevClose - Dividend) / PrevClose
    # This factor calculated on ex-date applies to all days BEFORE ex-date.
    prev_close = df['SplitAdjClose'].shift(1)
    
    # Avoid division by zero
    div_factor = np.where(
        (df['Dividend'] > 0) & (prev_close > 0),
        (prev_close - df['Dividend']) / prev_close,
        1.0
    )
    df['DivFactor'] = div_factor
    
    # 5. Calculate Cumulative Dividend Multiplier (Backward)
    df['CumDiv'] = df['DivFactor'].iloc[::-1].cumprod().shift(1).fillna(1.0).iloc[::-1]
    
    # 6. Apply Total Adjustment Factor
    df['AdjFactor'] = df['CumDiv'] / df['CumSplit']
    
    # We create standard adjusted columns
    df['Adj Close'] = df['Close'] * df['AdjFactor']
    df['Adj Open'] = df['Open'] * df['AdjFactor']
    df['Adj High'] = df['High'] * df['AdjFactor']
    df['Adj Low'] = df['Low'] * df['AdjFactor']
    
    # Volume is adjusted by splits only, not dividends
    df['Adj Volume'] = df['Volume'] * df['CumSplit']
    
    # Drop temporary calculation columns
    drop_cols = ['Dividend', 'SplitFactor', 'CumSplit', 'SplitAdjClose', 'DivFactor', 'CumDiv', 'AdjFactor']
    df = df.drop(columns=drop_cols)
    
    return df

def backfill_adjusted_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Backfills 'Adj Open', 'Adj High', 'Adj Low' by calculating the ratio of 'Adj Close' / 'Close'.
    This ensures a consistent Full Adjusted OHLC schema across providers like YFinance or FMP 
    that only natively return 'Adj Close'.
    """
    if df.empty:
        return df
        
    df = df.copy()
    
    if 'Close' in df.columns and 'Adj Close' in df.columns:
        # Calculate ratio, defaulting to 1.0 where Close is 0 or NaN
        ratio = np.where(df['Close'] != 0, df['Adj Close'] / df['Close'], 1.0)
        
        if 'Open' in df.columns and 'Adj Open' not in df.columns:
            df['Adj Open'] = df['Open'] * ratio
        if 'High' in df.columns and 'Adj High' not in df.columns:
            df['Adj High'] = df['High'] * ratio
        if 'Low' in df.columns and 'Adj Low' not in df.columns:
            df['Adj Low'] = df['Low'] * ratio
            
    return df
