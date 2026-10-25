import pytest
import pandas as pd
from alphadataforge.providers.stockfit_fetcher import StockFitFetcher
from alphadataforge.data.fundamental import Fundamentals


@pytest.fixture
def stockfit_fetcher():
    return StockFitFetcher()


def test_stockfit_fetch_info(stockfit_fetcher):
    info = stockfit_fetcher.fetch_info("AAPL")
    assert isinstance(info, dict)
    assert info.get("name") == "Apple Inc."
    assert info.get("sector") == "Information Technology"


def test_stockfit_fetch_financials_income(stockfit_fetcher):
    df = stockfit_fetcher.fetch_financials("AAPL", statement="income", period="annual", limit=5)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "Total_Revenue" in df.columns
    assert "Net_Income" in df.columns
    assert "Operating_Income" in df.columns


def test_stockfit_fetch_financials_balance(stockfit_fetcher):
    df = stockfit_fetcher.fetch_financials("AAPL", statement="balance", period="annual", limit=5)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "Total_Assets" in df.columns
    assert "Total_Liabilities" in df.columns
    assert "Total_Equity" in df.columns


def test_stockfit_fetch_financials_cashflow(stockfit_fetcher):
    df = stockfit_fetcher.fetch_financials("AAPL", statement="cashflow", period="annual", limit=5)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "Free_Cash_Flow" in df.columns


def test_stockfit_scores(stockfit_fetcher):
    scores = stockfit_fetcher.fetch_scores("AAPL")
    assert isinstance(scores, dict)
    assert "piotroskiFScore" in scores


def test_fundamentals_facade_stockfit():
    df = Fundamentals.get_financials("MSFT", statement="income", period="annual", provider="stockfit", limit=3)
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "Total_Revenue" in df.columns
