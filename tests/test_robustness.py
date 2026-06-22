import pytest
import pandas as pd
from alphadataforge.data.price import Price
from alphadataforge.providers.yfinance_fetcher import YFinanceFetcher
from alphadataforge.providers.tiingo_fetcher import TiingoFetcher
from alphadataforge.config.settings import config

@pytest.fixture
def yf_fetcher():
    return YFinanceFetcher()

@pytest.fixture
def tiingo_fetcher():
    if not config.TIINGO_API_KEY:
        pytest.skip("TIINGO_API_KEY not set. Skipping Tiingo tests.")
    return TiingoFetcher()

class TestNormalization:
    """1. Normalization Test: Ensuring consistent formatting across providers."""
    
    def test_yfinance_normalization(self, yf_fetcher):
        df = yf_fetcher.fetch_single("AAPL", start_date="2023-01-01", end_date="2023-01-05")
        assert not df.empty
        # Columns should be Title Case
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            assert col in df.columns
        # Index should be datetime
        assert isinstance(df.index, pd.DatetimeIndex)

    def test_tiingo_normalization(self, tiingo_fetcher):
        df = tiingo_fetcher.fetch_single("AAPL", start_date="2023-01-01", end_date="2023-01-05")
        assert not df.empty
        # Columns should be Title Case (normalized from tiingo's lowercase)
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            assert col in df.columns
        assert isinstance(df.index, pd.DatetimeIndex)

class TestValidation:
    """2. Validation Test: Ensuring bad inputs are caught early."""
    
    def test_empty_symbol_raises_error(self, yf_fetcher):
        with pytest.raises(ValueError, match="Symbol must be a non-empty string"):
            yf_fetcher.fetch_single("", start_date="2023-01-01")

    def test_invalid_date_order_raises_error(self, yf_fetcher):
        with pytest.raises(ValueError, match="start_date cannot be after end_date"):
            yf_fetcher.fetch_single("AAPL", start_date="2023-01-05", end_date="2023-01-01")
            
    def test_invalid_date_format_raises_error(self, yf_fetcher):
        with pytest.raises(ValueError, match="Date format must be YYYY-MM-DD"):
            yf_fetcher.fetch_single("AAPL", start_date="01-01-2023")

class TestErrorHandling:
    """3. Error Handling Test: Fetchers should return empty DataFrame on failure, not crash."""
    
    def test_invalid_ticker_returns_empty_df(self, yf_fetcher):
        df = yf_fetcher.fetch_single("INVALID_TICKER_123")
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_batch_invalid_ticker_returns_empty_df(self, yf_fetcher):
        data = yf_fetcher.fetch_multiple(["AAPL", "INVALID_TICKER_123"])
        assert isinstance(data, dict)
        assert not data["AAPL"].empty
        assert data["INVALID_TICKER_123"].empty
        
class TestProviderSelection:
    """4. Provider Selection Test: The Facade should route correctly."""
    
    def test_invalid_provider_raises_error(self):
        with pytest.raises(ValueError, match="Unsupported provider: 'invalid_provider'"):
            Price.get("AAPL", provider="invalid_provider")

    def test_valid_provider_routes_correctly(self):
        # We can test that it doesn't crash and returns a DataFrame
        df = Price.get("AAPL", provider="yfinance", start_date="2023-01-01", end_date="2023-01-05")
        assert not df.empty
        assert 'Close' in df.columns
