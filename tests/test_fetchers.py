import pytest
import pandas as pd
from alphadataforge.data_fetch.yfinance_fetcher import YFinanceFetcher

def test_yfinance_fetcher_returns_dataframe():
    """Test that the YFinance fetcher works according to the contract"""
    
    # 1. Simulate a call (fetch only 5 days to keep test fast)
    fetcher = YFinanceFetcher()
    df = fetcher.fetch_data("AAPL", start_date="2023-01-01", end_date="2023-01-05")
    
    # 2. Verify the results (will raise an error if condition is false)
    assert isinstance(df, pd.DataFrame), "Must return a DataFrame!"
    assert not df.empty, "Data must not be empty!"
    assert 'Close' in df.columns, "Must contain a Close price column"