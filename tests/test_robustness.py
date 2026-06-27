import pytest
import pandas as pd
from unittest.mock import patch
from alphadataforge.data.price import Price
from alphadataforge.providers.yfinance_fetcher import YFinanceFetcher
from alphadataforge.providers.tiingo_fetcher import TiingoFetcher
from alphadataforge.config.settings import config
from alphadataforge.core.exceptions import ProviderConfigurationError

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

    def test_normalize_ohlcv_handles_multiindex_and_nans(self, yf_fetcher):
        import numpy as np
        # Create a df with MultiIndex and NaNs
        mi = pd.MultiIndex.from_tuples([('close', 'AAPL'), ('open', 'AAPL')])
        df = pd.DataFrame([[np.nan, np.nan], [np.nan, np.nan]], columns=mi)
        # All NaN should return empty
        norm = yf_fetcher._normalize_ohlcv(df)
        assert norm.empty
        
        # Now with some values
        df = pd.DataFrame([[150.0, 149.0]], columns=mi, index=["2023-01-01"])
        norm = yf_fetcher._normalize_ohlcv(df)
        assert not norm.empty
        assert 'Close' in norm.columns
        assert 'Open' in norm.columns

class TestValidation:
    """2. Validation Test: Ensuring bad inputs are caught early."""
    
    def test_empty_symbol_raises_error(self, yf_fetcher):
        with pytest.raises(ValueError, match="Symbol must be a non-empty string"):
            yf_fetcher.fetch_single("", start_date="2023-01-01")

    def test_invalid_date_order_raises_error(self, yf_fetcher):
        with pytest.raises(ValueError, match="start_date cannot be after end_date"):
            yf_fetcher.fetch_single("AAPL", start_date="2023-01-05", end_date="2023-01-01")
            
    def test_invalid_date_format_raises_error(self, yf_fetcher):
        with pytest.raises(ValueError, match="start_date format must be YYYY-MM-DD"):
            yf_fetcher.fetch_single("AAPL", start_date="01-01-2023")

    @patch('alphadataforge.providers.alphavantage_fetcher.config')
    def test_apikey_missing_raises_error(self, mock_config):
        from alphadataforge.providers.alphavantage_fetcher import AlphaVantageFetcher
        mock_config.ALPHAVANTAGE_API_KEY = None
        fetcher = AlphaVantageFetcher()
        with pytest.raises(ProviderConfigurationError, match="ALPHAVANTAGE_API_KEY is not set"):
            fetcher.fetch_single("AAPL")

    @patch('alphadataforge.providers.tiingo_fetcher.config')
    def test_tiingo_apikey_missing_raises_error(self, mock_config):
        from alphadataforge.providers.tiingo_fetcher import TiingoFetcher
        mock_config.TIINGO_API_KEY = None
        fetcher = TiingoFetcher()
        with pytest.raises(ProviderConfigurationError, match="TIINGO_API_KEY is not set"):
            fetcher.fetch_single("AAPL")

    @patch('alphadataforge.providers.fmp_fetcher.config')
    def test_fmp_apikey_missing_raises_error(self, mock_config):
        from alphadataforge.providers.fmp_fetcher import FMPFetcher
        mock_config.FMP_API_KEY = None
        fetcher = FMPFetcher()
        with pytest.raises(ProviderConfigurationError, match="FMP_API_KEY is not set"):
            fetcher.fetch_single("AAPL")

class TestErrorHandling:
    """3. Error Handling Test: Validate new fail-fast & skip-on-failure behavior."""
    
    def test_invalid_ticker_returns_empty_df(self, yf_fetcher):
        """yfinance returns empty DataFrame for unknown tickers (no exception raised)."""
        df = yf_fetcher.fetch_single("INVALID_TICKER_123")
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_batch_excludes_invalid_ticker(self, yf_fetcher):
        """fetch_multiple should exclude failed symbols and only return successful ones."""
        data = yf_fetcher.fetch_multiple(["AAPL", "INVALID_TICKER_123"])
        assert isinstance(data, dict)
        assert "AAPL" in data
        assert not data["AAPL"].empty
        # Invalid ticker should be excluded (not present in results)
        assert "INVALID_TICKER_123" not in data

    @patch('requests.get')
    def test_retry_on_rate_limit(self, mock_get):
        from alphadataforge.core.base_fetcher import BaseDataFetcher
        import requests
        
        class DummyFetcher(BaseDataFetcher):
            def fetch_single(self, *args, **kwargs): pass
            def fetch_info(self, *args, **kwargs): pass
            def fetch_financials(self, *args, **kwargs): pass
            
        fetcher = DummyFetcher()
        
        # Mock requests.get to return 429 then 200
        response_429 = requests.Response()
        response_429.status_code = 429
        
        response_200 = requests.Response()
        response_200.status_code = 200
        response_200._content = b'{"success": true}'
        
        mock_get.side_effect = [response_429, response_200]
        
        # This should succeed after 1 retry
        result = fetcher._make_http_request("http://dummy")
        assert result == {"success": True}
        assert mock_get.call_count == 2

    @patch('requests.get')
    def test_invalid_json_raises_value_error(self, mock_get):
        """_make_http_request should raise ValueError when response is not valid JSON."""
        from alphadataforge.core.base_fetcher import BaseDataFetcher
        import requests

        class DummyFetcher(BaseDataFetcher):
            def fetch_single(self, *args, **kwargs): pass
            def fetch_info(self, *args, **kwargs): pass
            def fetch_financials(self, *args, **kwargs): pass

        fetcher = DummyFetcher()

        response_ok = requests.Response()
        response_ok.status_code = 200
        response_ok._content = b'<html>Not JSON</html>'
        mock_get.return_value = response_ok

        with pytest.raises(ValueError, match="Invalid JSON response from API"):
            fetcher._make_http_request("http://dummy")

    def test_fetch_multiple_empty_list(self, yf_fetcher):
        """fetch_multiple([]) should return empty dict without raising."""
        result = yf_fetcher.fetch_multiple([])
        assert result == {}

    def test_fetch_news_empty_symbol_raises(self, yf_fetcher):
        """fetch_news with empty symbol should raise ValueError."""
        with pytest.raises(ValueError, match="Symbol must be a non-empty string"):
            yf_fetcher.fetch_news("")

    def test_fetch_news_invalid_count_raises(self, yf_fetcher):
        """fetch_news with non-positive count should raise ValueError."""
        with pytest.raises(ValueError, match="count must be a positive integer"):
            yf_fetcher.fetch_news("AAPL", count=0)

    def test_fetch_financials_invalid_statement_raises(self, yf_fetcher):
        """fetch_financials with unknown statement type should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown statement type"):
            yf_fetcher.fetch_financials("AAPL", statement="unknown")
        
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
