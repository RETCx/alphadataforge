import pytest
import pandas as pd
from alphadataforge.providers.alphavantage_fetcher import AlphaVantageFetcher

@pytest.fixture
def mock_fetcher():
    """Returns a fetcher but we override api_key so it doesn't need .env to run unit tests"""
    fetcher = AlphaVantageFetcher()
    fetcher.api_key = "demo"
    return fetcher

def test_alphavantage_parse_response_logic(mock_fetcher):
    """
    UNIT TEST (Layer 1): Test ONLY the parsing logic.
    We pass a fake JSON payload directly to _parse_response, bypassing _make_request.
    This takes 0.001 seconds and uses 0 API credits!
    """
    fake_raw_json = {
        "Meta Data": {
            "1. Information": "Daily Prices (open, high, low, close) and Volumes",
            "2. Symbol": "IBM",
        },
        "Time Series (Daily)": {
            "2023-03-24": {
                "1. open": "132.0000",
                "2. high": "133.5100",
                "3. low": "130.8700",
                "4. close": "132.3000",
                "5. adjusted close": "132.3000",
                "6. volume": "5142289"
            },
            "2023-03-23": {
                "1. open": "131.0000",
                "2. high": "132.0000",
                "3. low": "130.0000",
                "4. close": "131.5000",
                "5. adjusted close": "131.5000",
                "6. volume": "4000000"
            }
        }
    }
    
    # Call _parse_response directly
    df = mock_fetcher._parse_response(fake_raw_json, "Time Series (Daily)")
    
    # We must normalize it as fetch_single would do
    df = mock_fetcher._normalize_ohlcv(df)
    
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert len(df) == 2
    
    # Normalization should have capitalized the columns
    assert 'Open' in df.columns
    assert 'Close' in df.columns
    assert 'Volume' in df.columns
    assert 'Adj Close' in df.columns
    
    # Data should be numeric
    assert df.loc["2023-03-24", "Open"] == 132.0
    assert df.loc["2023-03-24", "Volume"] == 5142289
