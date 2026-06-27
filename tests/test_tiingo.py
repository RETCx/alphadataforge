import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
from alphadataforge.providers.tiingo_fetcher import TiingoFetcher
from alphadataforge.config import settings
from alphadataforge.core.exceptions import ProviderConfigurationError

# Test initialization
def test_tiingo_fetcher_no_key(monkeypatch):
    monkeypatch.setattr(settings.config, "TIINGO_API_KEY", "")
    fetcher = TiingoFetcher()
    with pytest.raises(ProviderConfigurationError, match="TIINGO_API_KEY is not set"):
        fetcher.fetch_single("AAPL")

@pytest.fixture
def tiingo_fetcher(monkeypatch):
    monkeypatch.setattr(settings.config, "TIINGO_API_KEY", "dummy_key")
    return TiingoFetcher()

@patch('tiingo.TiingoClient.get_dataframe')
def test_tiingo_fetch_single_empty(mock_get_df, tiingo_fetcher):
    mock_get_df.return_value = pd.DataFrame()
    df = tiingo_fetcher.fetch_single("INVALID")
    assert df.empty

def test_tiingo_fetch_multiple_empty_symbols(tiingo_fetcher):
    assert tiingo_fetcher.fetch_multiple([]) == {}

@patch('tiingo.TiingoClient.get_dataframe')
@patch('alphadataforge.providers.tiingo_fetcher.TiingoFetcher.fetch_single') # Mock fallback
def test_tiingo_fetch_multiple_exception_fallback(mock_single, mock_get_df, tiingo_fetcher):
    mock_get_df.side_effect = Exception("Batch error")
    mock_single.return_value = pd.DataFrame({'close': [100]}, index=pd.DatetimeIndex(["2023-01-01"]))
    
    res = tiingo_fetcher.fetch_multiple(["AAPL"])
    assert "AAPL" in res
    assert not res["AAPL"].empty
    mock_single.assert_called_once()

@patch('tiingo.TiingoClient.get_dataframe')
def test_tiingo_fetch_multiple_batch_edge_cases(mock_get_df, tiingo_fetcher):
    # Mock return DataFrame with symbol columns
    mock_df = pd.DataFrame({
        "AAPL": [150.0],
        "EMPTY_SYM": [None] # Will drop to empty
    }, index=pd.DatetimeIndex(["2023-01-01"]))
    mock_get_df.return_value = mock_df
    
    res = tiingo_fetcher.fetch_multiple(["AAPL", "MISSING_SYM", "EMPTY_SYM"])
    assert "AAPL" in res
    assert "MISSING_SYM" not in res
    assert "EMPTY_SYM" not in res

@patch('tiingo.TiingoClient.get_news')
def test_tiingo_fetch_news(mock_get_news, tiingo_fetcher):
    mock_get_news.return_value = [{"title": "News 1", "url": "http"}]
    df = tiingo_fetcher.fetch_news(tickers=["AAPL"])
    assert not df.empty
    assert df.iloc[0]["title"] == "News 1"

@patch('tiingo.TiingoClient.get_news')
def test_tiingo_fetch_news_empty(mock_get_news, tiingo_fetcher):
    mock_get_news.return_value = []
    df = tiingo_fetcher.fetch_news(tickers=["AAPL"])
    assert df.empty

def test_tiingo_fetch_crypto_empty_symbols(tiingo_fetcher):
    assert tiingo_fetcher.fetch_crypto([]) == {}

@patch('tiingo.TiingoClient.get_crypto_price_history')
def test_tiingo_fetch_crypto_edge_cases(mock_get_crypto, tiingo_fetcher):
    mock_get_crypto.return_value = [
        {"ticker": "BTCUSD", "priceData": [{"date": "2023-01-01", "close": 50000}]},
        {"ticker": "NOPRICE", "priceData": []},
        {"ticker": "EMPTYDF", "priceData": [{"bad_col": 1}]} # Normalization might fail or make it empty
    ]
    
    with patch('alphadataforge.providers.tiingo_fetcher.TiingoFetcher._normalize_ohlcv') as mock_norm:
        mock_norm.side_effect = lambda df: pd.DataFrame() if "bad_col" in df.columns else df
        res = tiingo_fetcher.fetch_crypto(["BTCUSD", "NOPRICE", "EMPTYDF"])
        
        assert "BTCUSD" in res
        assert "NOPRICE" not in res
        assert "EMPTYDF" not in res

@patch('tiingo.TiingoClient.get_crypto_price_history')
def test_tiingo_fetch_crypto_exception(mock_get_crypto, tiingo_fetcher):
    mock_get_crypto.return_value = [{"ticker": "ERR", "priceData": [{"date": "2023-01-01"}]}]
    
    with patch('alphadataforge.providers.tiingo_fetcher.TiingoFetcher._normalize_ohlcv') as mock_norm:
        mock_norm.side_effect = Exception("Normalize error")
        res = tiingo_fetcher.fetch_crypto(["ERR"])
        assert res == {}

@patch('tiingo.TiingoClient.get_ticker_metadata')
def test_tiingo_fetch_info(mock_meta, tiingo_fetcher):
    mock_meta.return_value = {"ticker": "AAPL", "description": "Apple"}
    info = tiingo_fetcher.fetch_info("AAPL")
    assert info["ticker"] == "AAPL"

@patch('tiingo.TiingoClient.get_ticker_metadata')
def test_tiingo_fetch_info_exception(mock_meta, tiingo_fetcher):
    mock_meta.side_effect = Exception("API Error")
    info = tiingo_fetcher.fetch_info("AAPL")
    assert info == {}

def test_tiingo_fetch_financials(tiingo_fetcher):
    df = tiingo_fetcher.fetch_financials("AAPL")
    assert df.empty
