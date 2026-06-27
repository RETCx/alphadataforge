import pandas as pd
from typing import Optional, List, Dict

from ..core.base_fetcher import BaseDataFetcher
from .alphavantage_fetcher import AlphaVantageFetcher
from .tiingo_fetcher import TiingoFetcher
from ..utils.finance_math import calculate_adjusted_prices
from ..utils.logger import setup_logger

logger = setup_logger(__name__)

class HybridFetcher(BaseDataFetcher):
    """
    Hybrid Data Fetcher that combines multiple providers for optimal rate limit usage.
    Primary use case:
    - Fetches long-history raw prices from Alpha Vantage.
    - Fetches dividend and split events from Tiingo.
    - Computes full adjusted prices locally.
    Saves 2 API calls per symbol on Alpha Vantage compared to using AV's native adjusted fetch.
    """

    def __init__(self):
        super().__init__()
        self.av_fetcher = AlphaVantageFetcher()
        self.tiingo_fetcher = TiingoFetcher()

    def fetch_single(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        **kwargs
    ) -> pd.DataFrame:
        """
        Fetch hybrid data for a single symbol.
        """
        logger.info("Fetching hybrid price data for %s (AlphaVantage + Tiingo)...", symbol)
        
        # Pop adjusted if present to avoid multiple values conflict
        kwargs.pop("adjusted", None)
        
        # 1. Fetch raw prices from Alpha Vantage
        # Force adjusted=False to save API calls, we just need raw OHLCV
        df_raw = self.av_fetcher.fetch_single(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            adjusted=False,
            **kwargs
        )
        
        if df_raw.empty:
            return df_raw
            
        # 2. Fetch splits and dividends from Tiingo
        try:
            df_tiingo = self.tiingo_fetcher.fetch_single(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                frequency="daily"
            )
        except Exception as e:
            logger.warning("Failed to fetch Tiingo data for %s: %s. Returning raw AV data.", symbol, e)
            return df_raw
            
        if df_tiingo.empty:
            # No Tiingo data, return raw AV data
            return df_raw
            
        # Extract dividends and splits
        dividends_df = df_tiingo[['divCash']].rename(columns={'divCash': 'Dividend'})
        dividends_df = dividends_df[dividends_df['Dividend'] > 0]
        
        splits_df = df_tiingo[['splitFactor']].rename(columns={'splitFactor': 'SplitFactor'})
        splits_df = splits_df[splits_df['SplitFactor'] != 1.0]
        
        # 3. Calculate adjusted prices using our math utility
        df_adj = calculate_adjusted_prices(df_raw, dividends_df, splits_df)
        
        return df_adj

    def fetch_info(self, symbol: str, **kwargs) -> dict:
        raise NotImplementedError("HybridFetcher only supports price fetching.")

    def fetch_financials(self, symbol: str, statement: str = "income", **kwargs) -> pd.DataFrame:
        raise NotImplementedError("HybridFetcher only supports price fetching.")
