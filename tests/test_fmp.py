import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

from alphadataforge.providers.fmp_fetcher import FMPFetcher

@pytest.fixture
def mock_fmp_response():
    return {
        "symbol": "AAPL",
        "historical": [
            {
                "date": "2023-08-25",
                "open": 177.38,
                "high": 179.15,
                "low": 175.82,
                "close": 178.61,
                "adjClose": 178.61,
                "volume": 51449600,
                "unadjustedVolume": 51449600,
                "change": 1.23,
                "changePercent": 0.693,
                "vwap": 177.86,
                "label": "August 25, 23",
                "changeOverTime": 0.00693
            },
            {
                "date": "2023-08-24",
                "open": 170.0,
                "high": 175.0,
                "low": 169.0,
                "close": 174.0,
                "adjClose": 174.0,
                "volume": 50000000,
                "unadjustedVolume": 50000000,
                "change": 4.0,
                "changePercent": 2.35,
                "vwap": 173.0,
                "label": "August 24, 23",
                "changeOverTime": 0.0235
            }
        ]
    }

@patch('alphadataforge.providers.fmp_fetcher.config')
@patch('alphadataforge.providers.fmp_fetcher.FMPFetcher._make_http_request')
def test_fmp_fetcher_single_unadjusted(mock_http, mock_config, mock_fmp_response):
    mock_config.FMP_API_KEY = "test_key"
    mock_http.return_value = mock_fmp_response
    
    fetcher = FMPFetcher()
    df = fetcher.fetch_single("AAPL", adjusted=False)
    
    assert not df.empty
    assert 'Close' in df.columns
    assert 'Adj Close' in df.columns
    
    # Assert proper sorting/index
    assert isinstance(df.index, pd.DatetimeIndex)
    assert len(df) == 2
    
    # Check that data matches mock
    assert df.loc['2023-08-25', 'Close'] == 178.61
    assert df.loc['2023-08-24', 'Open'] == 170.0

    mock_http.assert_called_with(
        "https://financialmodelingprep.com/stable/historical-price-eod/non-split-adjusted", 
        params={'symbol': 'AAPL', 'apikey': 'test_key'}
    )

@patch('alphadataforge.providers.fmp_fetcher.config')
@patch('alphadataforge.providers.fmp_fetcher.FMPFetcher._make_http_request')
def test_fmp_fetcher_single_adjusted(mock_http, mock_config, mock_fmp_response):
    # Test adjusted=True uses dividend-adjusted endpoint
    mock_config.FMP_API_KEY = "test_key"
    mock_http.return_value = mock_fmp_response
    
    fetcher = FMPFetcher()
    df = fetcher.fetch_single("AAPL", adjusted=True)
    
    assert not df.empty
    mock_http.assert_called_with(
        "https://financialmodelingprep.com/stable/historical-price-eod/dividend-adjusted", 
        params={'symbol': 'AAPL', 'apikey': 'test_key'}
    )
