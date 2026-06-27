import pytest
import pandas as pd
import os
from alphadataforge.providers.yfinance_fetcher import YFinanceFetcher
from alphadataforge.providers.tiingo_fetcher import TiingoFetcher
from alphadataforge.data.price import Price
from alphadataforge.data.fundamental import Fundamentals
from alphadataforge.config.settings import config

@pytest.fixture
def yf_fetcher():
    """Provides a YFinanceFetcher instance for tests."""
    return YFinanceFetcher()

@pytest.fixture
def tiingo_fetcher():
    """Provides a TiingoFetcher instance for tests. Skips if no API key."""
    if not config.TIINGO_API_KEY:
        pytest.skip("TIINGO_API_KEY not set. Skipping Tiingo tests.")
    return TiingoFetcher()

def test_fetch_single_basic(yf_fetcher):
    """Test fetching a single symbol using default parameters."""
    df = yf_fetcher.fetch_single("AAPL", start_date="2023-01-01", end_date="2023-01-05")
    
    assert isinstance(df, pd.DataFrame), "Must return a DataFrame!"
    assert not df.empty, "Data must not be empty!"
    assert 'Close' in df.columns, "Must contain a Close price column"
    assert len(df) == 2  # 2023-01-01 is Sunday, Jan 2 is holiday observed, so Jan 3 and Jan 4 only

def test_fetch_single_intraday_with_kwargs(yf_fetcher):
    """Test fetching single symbol with intraday interval and extra kwargs."""
    df = yf_fetcher.fetch_single("MSFT", interval="1h", period="5d", auto_adjust=False)
    
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert 'Close' in df.columns
    assert 'Adj Close' in df.columns  # auto_adjust=False means Adj Close should be present

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

def test_price_unified_api_normal():
    """Test unified Facade API with default provider (yfinance)."""
    df_normal = Price.get("AAPL", start_date="2023-01-01", end_date="2023-01-05")
    assert isinstance(df_normal, pd.DataFrame)
    assert not df_normal.empty
    assert 'Close' in df_normal.columns

def test_price_unified_api_multiple():
    """Test unified Facade API fetching multiple symbols at once."""
    symbols = ["AAPL", "GOOGL"]
    data_dict = Price.get(symbols, start_date="2023-01-01", end_date="2023-01-05")
    
    assert isinstance(data_dict, dict), "Must return a dictionary when passing a list of symbols"
    assert set(data_dict.keys()) == set(symbols), "Dictionary must contain all requested symbols"
    
    for symbol, df in data_dict.items():
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert 'Close' in df.columns

def test_price_unified_api_advanced():
    """Test Facade API with advanced provider_params (weekly interval)."""
    df_advanced = Price.get("AAPL", provider="yfinance", provider_params={"interval": "1wk", "period": "1mo"})
    assert isinstance(df_advanced, pd.DataFrame)
    assert not df_advanced.empty
    assert 'Close' in df_advanced.columns

def test_fetch_news(yf_fetcher):
    """Test fetching news articles for a ticker."""
    df = yf_fetcher.fetch_news("AAPL", count=5)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert 'title' in df.columns

def test_fetch_info(yf_fetcher):
    """Test fetching ticker metadata and fundamental info dict."""
    info = yf_fetcher.fetch_info("AAPL")
    assert isinstance(info, dict)
    assert 'marketCap' in info
    assert 'sector' in info

def test_fetch_financials_income(yf_fetcher):
    """Test fetching annual income statement."""
    df = yf_fetcher.fetch_financials("AAPL", statement="income")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    # Check if normalization happened
    assert 'Net_Income' in df.columns or 'Total_Revenue' in df.columns

def test_fundamentals_facade():
    """Test the unified Fundamentals Facade API."""
    info = Fundamentals.get_info("AAPL", provider="yfinance")
    assert isinstance(info, dict)
    assert 'sector' in info
    
    df = Fundamentals.get_financials("AAPL", statement="balance", period="annual", provider="yfinance")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert df.index.name == "Date"

def test_fetch_crypto(yf_fetcher):
    """Test fetching crypto price via yfinance (BTC-USD)."""
    data = yf_fetcher.fetch_crypto(["BTC-USD"], start_date="2023-01-01", end_date="2023-01-05")
    assert isinstance(data, dict)
    assert "BTC-USD" in data
    assert not data["BTC-USD"].empty

def test_fetch_forex(yf_fetcher):
    """Test fetching forex rate data (EUR/USD)."""
    data = yf_fetcher.fetch_forex(["EURUSD=X"], start_date="2023-01-01", end_date="2023-01-05")
    assert isinstance(data, dict)
    assert "EURUSD=X" in data
    assert not data["EURUSD=X"].empty

# -------------------------------------------------------------------
# TiingoFetcher Tests
# -------------------------------------------------------------------

def test_tiingo_fetch_single(tiingo_fetcher):
    """Test fetching a single symbol using Tiingo."""
    df = tiingo_fetcher.fetch_single("AAPL", start_date="2023-01-01", end_date="2023-01-05")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert 'Close' in df.columns or 'Adj Close' in df.columns

def test_tiingo_fetch_multiple(tiingo_fetcher):
    """Test fetching multiple symbols at once using Tiingo."""
    symbols = ["AAPL", "GOOGL"]
    data_dict = tiingo_fetcher.fetch_multiple(symbols, start_date="2023-01-01", end_date="2023-01-05")
    assert isinstance(data_dict, dict)
    assert set(data_dict.keys()) == set(symbols)
    
    for symbol, df in data_dict.items():
        assert isinstance(df, pd.DataFrame)
        assert not df.empty

def test_tiingo_fetch_crypto(tiingo_fetcher):
    """Test fetching crypto price via Tiingo (BTCUSD)."""
    data = tiingo_fetcher.fetch_crypto(["BTCUSD"], start_date="2023-01-01", end_date="2023-01-05")
    assert isinstance(data, dict)
    # Tiingo API returns crypto tickers in lowercase
    assert "btcusd" in data
    assert not data["btcusd"].empty

def test_price_tiingo_provider():
    """Test Facade API with tiingo provider."""
    if not config.TIINGO_API_KEY:
        pytest.skip("TIINGO_API_KEY not set. Skipping Tiingo Facade test.")
    
    df = Price.get("AAPL", provider="tiingo", start_date="2023-01-01", end_date="2023-01-05")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty