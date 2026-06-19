import pytest
import pandas as pd
from alphadataforge.data_fetch.yfinance_fetcher import YFinanceFetcher

@pytest.fixture
def yf_fetcher():
    """Provides a YFinanceFetcher instance for tests."""
    return YFinanceFetcher()

def test_fetch_single_basic(yf_fetcher):
    """Test fetching a single symbol using default parameters."""
    df = yf_fetcher.fetch_single("AAPL", start_date="2023-01-01", end_date="2023-01-05")
    
    assert isinstance(df, pd.DataFrame), "Must return a DataFrame!"
    assert not df.empty, "Data must not be empty!"
    assert 'Close' in df.columns, "Must contain a Close price column"
    assert len(df) == 2  # 2023-01-01 is Sunday, Jan 2 is holiday observed, so Jan 3 and Jan 4 only

def test_fetch_single_intraday_with_kwargs(yf_fetcher):
    """Test fetching single symbol with intraday interval and extra kwargs."""
    # Note: intraday data is restricted to last 730 days for 1h, so using a recent date is better,
    # but since yf might ignore start/end if too old for intraday or return empty,
    # let's test with period='5d' using **kwargs to bypass start/end
    df = yf_fetcher.fetch_single("MSFT", interval="1h", period="5d", auto_adjust=False)
    
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert 'Close' in df.columns
    assert 'Adj Close' in df.columns  # because auto_adjust=False, we should see Adj Close

def test_fetch_multiple_basic(yf_fetcher):
    """Test fetching multiple symbols at once."""
    symbols = ["AAPL", "GOOGL"]
    data_dict = yf_fetcher.fetch_multiple(symbols, start_date="2023-01-01", end_date="2023-01-05")
    
    assert isinstance(data_dict, dict), "Must return a dictionary"
    assert set(data_dict.keys()) == set(symbols), "Dictionary must contain all requested symbols"
    
    for symbol, df in data_dict.items():
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert 'Close' in df.columns

def test_fetch_multiple_single_symbol_fallback(yf_fetcher):
    """Test fetch_multiple but with only one symbol in the list."""
    symbols = ["TSLA"]
    data_dict = yf_fetcher.fetch_multiple(symbols, start_date="2023-01-01", end_date="2023-01-05")
    
    assert isinstance(data_dict, dict)
    assert "TSLA" in data_dict
    assert not data_dict["TSLA"].empty

def test_fetch_multiple_index(yf_fetcher):
    """Test fetching multiple symbols with different index types (QQQ, ^VIX)"""
    symbols = ["QQQ", "^VIX"]
    data_dict = yf_fetcher.fetch_multiple(symbols, start_date="2023-01-01", end_date="2023-01-05")
    
    assert isinstance(data_dict, dict)
    for symbol in symbols:
        assert symbol in data_dict
        assert not data_dict[symbol].empty
        assert 'Close' in data_dict[symbol].columns