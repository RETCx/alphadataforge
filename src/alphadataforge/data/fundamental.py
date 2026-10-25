import pandas as pd
from typing import Optional, Dict, Any

from ..providers.yfinance_fetcher import YFinanceFetcher
from ..providers.fmp_fetcher import FMPFetcher
from ..providers.alphavantage_fetcher import AlphaVantageFetcher
from ..providers.stockfit_fetcher import StockFitFetcher
from ..utils.logger import setup_logger
from ..config.settings import config

logger = setup_logger(__name__)

class Fundamentals:
    """
    Facade for fetching fundamental data (company profile, financial statements)
    across multiple providers (YFinance, FMP, AlphaVantage, StockFit).
    """

    @staticmethod
    def _get_provider(provider_name: str):
        provider_name = provider_name.lower()
        if provider_name == "yfinance":
            return YFinanceFetcher()
        elif provider_name == "fmp":
            return FMPFetcher()
        elif provider_name == "alphavantage":
            return AlphaVantageFetcher()
        elif provider_name == "stockfit":
            return StockFitFetcher()
        else:
            raise ValueError(f"Unsupported provider: '{provider_name}'. Choose 'yfinance', 'stockfit', 'alphavantage', or 'fmp'.")

    @staticmethod
    def get_info(symbol: str, provider: str = "yfinance") -> Dict[str, Any]:
        """
        Fetch company profile and basic information.
        
        Args:
            symbol: Ticker symbol (e.g., "AAPL").
            provider: "yfinance" (default), "stockfit", "fmp", or "alphavantage".
            
        Returns:
            Dictionary containing company info (sector, industry, marketCap, etc.).
        """
        fetcher = Fundamentals._get_provider(provider)
        return fetcher.fetch_info(symbol)

    @staticmethod
    def get_financials(
        symbol: str, 
        statement: str = "income", 
        period: str = "annual", 
        provider: str = "yfinance",
        **kwargs
    ) -> pd.DataFrame:
        """
        Fetch financial statements (Income, Balance Sheet, Cash Flow).
        
        Args:
            symbol: Ticker symbol (e.g., "AAPL").
            statement: "income", "balance", "cashflow", "growth", "scores", "shares_outstanding", "earnings", or "shares_float".
            period: "annual" (default) or "quarterly".
            provider: "yfinance" (default), "stockfit", "fmp", or "alphavantage".
            **kwargs: Extra parameters passed to the provider (e.g. limit=100).
            
        Returns:
            DataFrame with normalized columns (e.g., Net_Income, Total_Revenue)
            and DatetimeIndex for the reporting periods.
        """
        fetcher = Fundamentals._get_provider(provider)
        return fetcher.fetch_financials(symbol, statement=statement, period=period, **kwargs)

    @staticmethod
    def get_scores(symbol: str, provider: str = "stockfit") -> Dict[str, Any]:
        """
        Fetch Piotroski F-Score and financial health scores.
        
        Args:
            symbol: Ticker symbol (e.g., "AAPL").
            provider: "stockfit" (default).
        """
        fetcher = Fundamentals._get_provider(provider)
        if hasattr(fetcher, "fetch_scores"):
            return fetcher.fetch_scores(symbol)
        raise NotImplementedError(f"Provider '{provider}' does not support get_scores.")

    @staticmethod
    def get_earnings_calendar(
        horizon: str = "3month", 
        symbol: Optional[str] = None,
        provider: str = "alphavantage"
    ) -> pd.DataFrame:
        """
        Fetch earnings calendar.
        
        Args:
            horizon: '3month' (default), '6month', or '12month'.
            symbol: Optional ticker symbol to fetch for specifically.
            provider: Defaults to "alphavantage" (currently the only supported provider for this).
            
        Returns:
            DataFrame containing the earnings calendar.
        """
        fetcher = Fundamentals._get_provider(provider)
        if not hasattr(fetcher, 'fetch_earnings_calendar'):
            raise NotImplementedError(f"Provider '{provider}' does not support get_earnings_calendar.")
        return fetcher.fetch_earnings_calendar(horizon=horizon, symbol=symbol)
