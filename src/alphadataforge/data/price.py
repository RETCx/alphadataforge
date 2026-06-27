from typing import Optional, Dict, Any, Union, List, Literal
import pandas as pd
import concurrent.futures
import logging

logger = logging.getLogger(__name__)

from ..providers.yfinance_fetcher import YFinanceFetcher
from ..providers.tiingo_fetcher import TiingoFetcher
from ..providers.alphavantage_fetcher import AlphaVantageFetcher
from ..providers.fmp_fetcher import FMPFetcher
from ..providers.hybrid_fetcher import HybridFetcher

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
        provider: Literal["yfinance", "tiingo", "alphavantage", "fmp", "hybrid_av_tiingo"] = "yfinance",
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
        elif provider == "hybrid_av_tiingo":
            fetcher = HybridFetcher()
        else:
            raise ValueError(f"Unsupported provider: '{provider}'. Choose 'yfinance', 'tiingo', 'alphavantage', 'fmp', or 'hybrid_av_tiingo'.")
            
        # 2. fetch price data (check whether list or string)
        if isinstance(symbols, list):
            result = fetcher.fetch_multiple(symbols, start_date, end_date, **provider_params)
        else:
            result = fetcher.fetch_single(symbols, start_date, end_date, **provider_params)
        
        # 3. Return to caller
        return result

    @staticmethod
    def compare(
        symbol: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None,
        providers: Optional[List[str]] = None,
        provider_params: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Fetch historical price data from multiple providers concurrently and combine them 
        into a single MultiIndex DataFrame for easy comparison.
        """
        if providers is None:
            providers = ["yfinance", "tiingo", "alphavantage", "fmp", "hybrid_av_tiingo"]
            
        provider_params = provider_params or {}
        
        def fetch_for_provider(p):
            try:
                return p, Price.get(
                    symbols=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    provider=p,
                    provider_params=provider_params
                )
            except Exception as e:
                logger.error(f"Failed to fetch from {p} for comparison: {type(e).__name__} {e}")
                return p, pd.DataFrame()

        results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(providers)) as executor:
            futures = [executor.submit(fetch_for_provider, p) for p in providers]
            for future in concurrent.futures.as_completed(futures):
                p, df = future.result()
                if not df.empty:
                    if df.index.tz is not None:
                        df.index = df.index.tz_localize(None)
                    results[p] = df

        if not results:
            return pd.DataFrame()

        # Combine into MultiIndex DataFrame
        # pd.concat(results, axis=1) creates MultiIndex where level 0 is the dictionary key (provider)
        multi_df = pd.concat(results, axis=1)
        return multi_df

    @staticmethod
    def consensus(
        symbol: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None,
        providers: Optional[List[str]] = None,
        provider_params: Optional[Dict[str, Any]] = None,
        method: Literal["mean", "median"] = "median"
    ) -> pd.DataFrame:
        """
        Fetch from multiple providers and return a single consensus DataFrame 
        by calculating the mean or median across all available providers.
        """
        multi_df = Price.compare(symbol, start_date, end_date, providers, provider_params)
        
        if multi_df.empty:
            return pd.DataFrame()
            
        # Filter out non-numeric columns (like 'symbol' strings)
        numeric_df = multi_df.select_dtypes(include='number')
        
        # Group by level 1 (the column names like 'Close', 'Adj Close') and aggregate
        # Using .T.groupby() to avoid deprecated axis=1
        if method == "mean":
            consensus_df = numeric_df.T.groupby(level=1).mean().T
        elif method == "median":
            consensus_df = numeric_df.T.groupby(level=1).median().T
        else:
            raise ValueError("Method must be 'mean' or 'median'")
            
        # Sort columns to maintain standard OHLCV order
        standard_cols = ['Open', 'High', 'Low', 'Close', 'Volume', 'Adj Open', 'Adj High', 'Adj Low', 'Adj Close', 'Adj Volume']
        existing_cols = [c for c in standard_cols if c in consensus_df.columns]
        other_cols = [c for c in consensus_df.columns if c not in standard_cols]
        consensus_df = consensus_df[existing_cols + other_cols]
        
        return consensus_df