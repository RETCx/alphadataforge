import pytest
from unittest.mock import patch
import pandas as pd

from alphadataforge.providers.stockfit_fetcher import StockFitFetcher
from alphadataforge.data.fundamental import Fundamentals
from alphadataforge.data.price import Price
from alphadataforge.config import settings
from alphadataforge.core.exceptions import ProviderConfigurationError


@pytest.fixture
def stockfit_fetcher(monkeypatch):
    """Fixture with dummy API key for testing."""
    monkeypatch.setattr(settings.config, "STOCKFIT_API_KEY", "dummy_stockfit_key")
    return StockFitFetcher(api_key="dummy_stockfit_key")


def test_stockfit_missing_api_key(monkeypatch):
    """Ensure error is raised when API key is missing."""
    monkeypatch.setattr(settings.config, "STOCKFIT_API_KEY", None)
    fetcher = StockFitFetcher(api_key=None)
    with pytest.raises(ProviderConfigurationError, match="STOCKFIT_API_KEY is not set"):
        fetcher.fetch_scores("AAPL")


@patch("alphadataforge.providers.stockfit_fetcher.StockFitFetcher._make_http_request")
def test_stockfit_fetch_info(mock_http, stockfit_fetcher):
    """Test parsing company details."""
    mock_http.return_value = {
        "name": "Apple Inc.",
        "sector": "Information Technology",
        "industry": "Technology Hardware & Storage",
        "cik": 320193
    }
    info = stockfit_fetcher.fetch_info("AAPL")
    assert isinstance(info, dict)
    assert info.get("name") == "Apple Inc."
    assert info.get("sector") == "Information Technology"


@patch("alphadataforge.providers.stockfit_fetcher.StockFitFetcher._make_http_request")
def test_stockfit_fetch_financials_income(mock_http, stockfit_fetcher):
    """Test income statement parsing and column normalization."""
    mock_http.return_value = [
        {
            "period": "2025-09-26",
            "fiscalYear": 2025,
            "fiscalPeriod": "FY",
            "facts": {
                "revenue": 416161000000,
                "netIncome": 112010000000,
                "operatingIncome": 133050000000
            }
        }
    ]
    df = stockfit_fetcher.fetch_financials("AAPL", statement="income", period="annual", limit=5)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "Total_Revenue" in df.columns
    assert "Net_Income" in df.columns
    assert "Operating_Income" in df.columns
    assert df.loc["2025-09-26", "Total_Revenue"] == 416161000000


@patch("alphadataforge.providers.stockfit_fetcher.StockFitFetcher._make_http_request")
def test_stockfit_fetch_financials_balance(mock_http, stockfit_fetcher):
    """Test balance sheet parsing and column normalization."""
    mock_http.return_value = [
        {
            "period": "2025-09-26",
            "fiscalYear": 2025,
            "facts": {
                "assets": 359241000000,
                "liabilities": 285508000000,
                "totalEquity": 73733000000
            }
        }
    ]
    df = stockfit_fetcher.fetch_financials("AAPL", statement="balance", period="annual", limit=5)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "Total_Assets" in df.columns
    assert "Total_Liabilities" in df.columns
    assert "Total_Equity" in df.columns


@patch("alphadataforge.providers.stockfit_fetcher.StockFitFetcher._make_http_request")
def test_stockfit_fetch_financials_cashflow(mock_http, stockfit_fetcher):
    """Test cash flow statement parsing."""
    mock_http.return_value = [
        {
            "period": "2025-09-26",
            "fiscalYear": 2025,
            "facts": {
                "freeCashFlow": 98767000000,
                "operatingCashFlow": 118000000000
            }
        }
    ]
    df = stockfit_fetcher.fetch_financials("AAPL", statement="cashflow", period="annual", limit=5)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "Free_Cash_Flow" in df.columns


@patch("alphadataforge.providers.stockfit_fetcher.StockFitFetcher._make_http_request")
def test_stockfit_scores(mock_http, stockfit_fetcher):
    """Test Piotroski F-Score parsing."""
    mock_http.return_value = {
        "period": "2025-09-26",
        "piotroskiFScore": 8,
        "piotroskiDetails": {
            "positiveNetIncome": True,
            "positiveOperatingCashFlow": True
        }
    }
    scores = stockfit_fetcher.fetch_scores("AAPL")
    assert isinstance(scores, dict)
    assert scores.get("piotroskiFScore") == 8


@patch("alphadataforge.providers.stockfit_fetcher.StockFitFetcher._make_http_request")
def test_stockfit_fetch_single_price(mock_http, stockfit_fetcher):
    """Test historical price history parsing."""
    mock_http.return_value = {
        "symbol": "AAPL",
        "data": [
            [1704153600000, 183.4],
            [1704240000000, 182.0]
        ]
    }
    df = stockfit_fetcher.fetch_single("AAPL", start_date="2024-01-01", end_date="2024-01-03")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "Close" in df.columns
    assert "Adj Close" in df.columns


@patch("alphadataforge.providers.stockfit_fetcher.StockFitFetcher._make_http_request")
def test_fundamentals_facade_stockfit(mock_http, monkeypatch):
    """Test calling Fundamentals facade with stockfit provider."""
    monkeypatch.setattr(settings.config, "STOCKFIT_API_KEY", "dummy_stockfit_key")
    mock_http.return_value = [
        {
            "period": "2025-09-26",
            "fiscalYear": 2025,
            "facts": {
                "revenue": 245122000000,
                "netIncome": 88136000000
            }
        }
    ]
    df = Fundamentals.get_financials("MSFT", statement="income", period="annual", provider="stockfit", limit=3)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "Total_Revenue" in df.columns


@patch("alphadataforge.providers.stockfit_fetcher.StockFitFetcher._make_http_request")
def test_price_facade_stockfit(mock_http, monkeypatch):
    """Test calling Price facade with stockfit provider."""
    monkeypatch.setattr(settings.config, "STOCKFIT_API_KEY", "dummy_stockfit_key")
    mock_http.return_value = {
        "symbol": "MSFT",
        "data": [
            [1704153600000, 370.5]
        ]
    }
    df = Price.get("MSFT", provider="stockfit")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "Close" in df.columns
