import pytest
import pandas as pd
import requests
from unittest.mock import patch

from alphadataforge.providers.fmp_fetcher import FMPFetcher

@patch('alphadataforge.providers.fmp_fetcher.FMPFetcher._make_http_request')
def test_fmp_fetcher_single_unadjusted(mock_http):
    mock_http.return_value = {"historical": [{"date": "2023-01-01", "close": 150.0, "volume": 1000}]}
    fetcher = FMPFetcher()
    df = fetcher.fetch_single("AAPL", adjusted=False)
    
    assert not df.empty
    assert 'Close' in df.columns
    
    # Assert proper sorting/index
    assert isinstance(df.index, pd.DatetimeIndex)

@patch('alphadataforge.providers.fmp_fetcher.FMPFetcher._make_http_request')
def test_fmp_fetcher_single_adjusted(mock_http):
    mock_http.return_value = {"historical": [{"date": "2023-01-01", "adjClose": 150.0}]}
    fetcher = FMPFetcher()
    df = fetcher.fetch_single("AAPL", adjusted=True)
    
    assert not df.empty
    assert 'Adj Close' in df.columns

@patch('alphadataforge.providers.fmp_fetcher.FMPFetcher._make_http_request')
def test_fmp_fetcher_single_error(mock_http):
    mock_http.side_effect = ValueError("API Error")
    
    fetcher = FMPFetcher()
    with pytest.raises(ValueError, match="API Error"):
        fetcher.fetch_single("AAPL")

@patch('alphadataforge.providers.fmp_fetcher.FMPFetcher._make_http_request')
def test_fmp_fetcher_single_empty(mock_http):
    mock_http.return_value = {"symbol": "INVALID", "historical": []}
    
    fetcher = FMPFetcher()
    df = fetcher.fetch_single("INVALID")
    assert df.empty

@patch('alphadataforge.providers.fmp_fetcher.FMPFetcher._make_http_request')
def test_fmp_fetcher_info(mock_http):
    mock_http.return_value = [{"symbol": "AAPL", "companyName": "Apple Inc."}]
    fetcher = FMPFetcher()
    info = fetcher.fetch_info("AAPL")
    assert isinstance(info, dict)
    assert info.get("symbol") == "AAPL"

@patch('alphadataforge.providers.fmp_fetcher.FMPFetcher._make_http_request')
def test_fmp_fetcher_financials(mock_http):
    mock_http.return_value = [{"date": "2023-01-01", "netIncome": 10000}]
    fetcher = FMPFetcher()
    df = fetcher.fetch_financials("AAPL", statement="income", period="annual")
    assert not df.empty
    assert "Net_Income" in df.columns

@patch('alphadataforge.providers.fmp_fetcher.FMPFetcher._make_http_request')
def test_fmp_fetcher_info_empty(mock_http):
    mock_http.return_value = [] # Empty list from API
    
    fetcher = FMPFetcher()
    info = fetcher.fetch_info("AAPL")
    assert info == {}

@patch('alphadataforge.providers.fmp_fetcher.FMPFetcher._make_http_request')
def test_fmp_fetcher_info_forbidden(mock_http):
    import requests
    response = requests.Response()
    response.status_code = 403
    mock_http.side_effect = requests.exceptions.HTTPError("Forbidden", response=response)
    
    fetcher = FMPFetcher()
    with pytest.raises(RuntimeError, match="FMP Fundamentals data.*requires a premium API key"):
        fetcher.fetch_info("AAPL")

def test_fmp_fetcher_financials_invalid_statement():
    fetcher = FMPFetcher()
    with pytest.raises(ValueError, match="Unknown statement type"):
        fetcher.fetch_financials("AAPL", statement="invalid_type")

@patch('alphadataforge.providers.fmp_fetcher.FMPFetcher._make_http_request')
def test_fmp_fetcher_financials_shares_float(mock_http):
    mock_http.return_value = [{"date": "2023-01-01", "freeFloat": 100}]
    
    fetcher = FMPFetcher()
    df = fetcher.fetch_financials("AAPL", statement="shares_float")
    assert not df.empty
    assert "freeFloat" in df.columns

@patch('alphadataforge.providers.fmp_fetcher.FMPFetcher._make_http_request')
def test_fmp_fetcher_financials_quarterly(mock_http):
    mock_http.return_value = [{"date": "2023-01-01", "netIncome": 500}]
    
    fetcher = FMPFetcher()
    df = fetcher.fetch_financials("AAPL", statement="income", period="quarterly")
    assert not df.empty

@patch('alphadataforge.providers.fmp_fetcher.FMPFetcher._make_http_request')
def test_fmp_fetcher_financials_empty(mock_http):
    mock_http.return_value = []
    
    fetcher = FMPFetcher()
    df = fetcher.fetch_financials("AAPL")
    assert df.empty

@patch('alphadataforge.providers.fmp_fetcher.FMPFetcher._make_http_request')
def test_fmp_fetcher_financials_forbidden(mock_http):
    import requests
    response = requests.Response()
    response.status_code = 403
    mock_http.side_effect = requests.exceptions.HTTPError("Forbidden", response=response)
    
    fetcher = FMPFetcher()
    with pytest.raises(RuntimeError, match="FMP Financial Statements data requires a premium API key"):
        fetcher.fetch_financials("AAPL")

