from typing import Optional, Dict, Any, Union, List, Literal
import pandas as pd

from ..providers.yfinance_fetcher import YFinanceFetcher
from ..providers.tiingo_fetcher import TiingoFetcher
from ..providers.alphavantage_fetcher import AlphaVantageFetcher
from ..providers.fmp_fetcher import FMPFetcher

class Price:
    """
    Unified Facade API for fetching price data.
    Hides provider-specific complexity from the caller.
    """
    
    @staticmethod
    def get(
        symbols: Union[str, List[str]], 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None,
        provider: Literal["yfinance", "tiingo", "alphavantage", "fmp"] = "yfinance",
        provider_params: Optional[Dict[str, Any]] = None
    ) -> Union[pd.DataFrame, Dict[str, pd.DataFrame]]:
        """
        Fetch historical end-of-day (EOD) price data for one or more symbols.

        Args:
            symbols (Union[str, List[str]]): 
                A single ticker symbol (e.g., 'AAPL') or a list of symbols (e.g., ['AAPL', 'MSFT']).
            start_date (Optional[str], optional): 
                Start date in 'YYYY-MM-DD' format. Defaults to None.
            end_date (Optional[str], optional): 
                End date in 'YYYY-MM-DD' format. Defaults to None.
            provider (Literal["yfinance", "tiingo", "alphavantage", "fmp"], optional): 
                The data provider to use. Defaults to "yfinance".
            provider_params (Optional[Dict[str, Any]], optional): 
                Additional parameters passed directly to the specific provider's fetcher.
                
                **Supported `provider_params` by provider:**
                
                *   **All Providers:**
                    *   `adjusted` (bool): If True, returns fully adjusted prices (Splits & Dividends). Default is False.
                    
                *   **yfinance:**
                    *   `interval` (str): Data interval (e.g., "1d", "1wk", "1mo").
                    *   `prepost` (bool): Include Pre and Post market data.
                    
                *   **tiingo:**
                    *   `resampleFreq` (str): Resample frequency (e.g., "daily", "weekly", "monthly").
                    
                *   **alphavantage:**
                    *   `outputsize` (str): "compact" (last 100 data points) or "full" (20+ years). Default is "compact".

                *   **fmp:**
                    *   `outputsize` (str): "full" (all history).
                
        Returns:
            Union[pd.DataFrame, Dict[str, pd.DataFrame]]: 
                - If `symbols` is a single string, returns a pandas DataFrame.
                - If `symbols` is a list, returns a dictionary mapping symbols to DataFrames.
                
        Examples:
            >>> from alphadataforge.data.price import Price
            >>> # 1. Default (yfinance)
            >>> df = Price.get("AAPL", start_date="2023-01-01")
            >>> 
            >>> # 2. Using FMP with adjusted prices
            >>> df_fmp = Price.get("MSFT", provider="fmp", provider_params={"adjusted": True})
        """
        
        # Prevent error if no params are passed
        provider_params = provider_params or {}
        
        # 1. Route to the correct provider
        if provider == "yfinance":
            fetcher = YFinanceFetcher()
        elif provider == "tiingo":
            fetcher = TiingoFetcher()
        elif provider == "alphavantage":
            fetcher = AlphaVantageFetcher()
        elif provider == "fmp":
            fetcher = FMPFetcher()
        else:
            raise ValueError(f"Unsupported provider: '{provider}'. Choose 'yfinance', 'tiingo', 'alphavantage', or 'fmp'.")
            
        # 2. fetch price data (check whether list or string)
        if isinstance(symbols, list):
            result = fetcher.fetch_multiple(symbols, start_date, end_date, **provider_params)
        else:
            result = fetcher.fetch_single(symbols, start_date, end_date, **provider_params)
        
        # 3. Return to caller
        return result