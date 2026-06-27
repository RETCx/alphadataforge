from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional, List, Dict
import random as rd
import time
from datetime import datetime
import gzip
import json

import requests
import requests_cache
from requests.exceptions import RequestException, HTTPError, Timeout, ConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
import concurrent.futures
import tempfile
import os

from .exceptions import RateLimitExceededError

# Globally patch requests to use sqlite cache (expires after 24 hours)
# Store cache in the OS's temp directory to avoid cluttering the user's workspace
cache_path = os.path.join(tempfile.gettempdir(), 'alphadataforge_cache')
def _filter_responses(response):
    # Don't cache AlphaVantage rate limit messages (which return HTTP 200)
    if "Thank you for using Alpha Vantage!" in response.text:
        return False
    return True

import sys
if "pytest" not in sys.modules and os.environ.get("DISABLE_REQUESTS_CACHE") != "1":
    requests_cache.install_cache(
        cache_name=cache_path, 
        backend='sqlite', 
        expire_after=86400,
        filter_fn=_filter_responses
    )

from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class BaseDataFetcher(ABC):
    """
    Abstract Base Class for all data fetchers.
    Acts as a contract ensuring all fetchers implement the fetch_single method.
    """
    
    @abstractmethod
    def fetch_single(
        self, 
        symbol: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None, 
        **kwargs
    ) -> pd.DataFrame:
        """
        Fetch data for a single symbol.
        Every provider must implement this method.
        """
        pass

    @abstractmethod
    def fetch_info(self, symbol: str) -> dict:
        """
        Fetch company profile and basic information.
        Must return a dictionary.
        """
        pass

    @abstractmethod
    def fetch_financials(self, symbol: str, statement: str = "income", period: str = "annual") -> pd.DataFrame:
        """
        Fetch financial statements (income, balance, cashflow).
        period: "annual" or "quarterly".
        Must return a DataFrame with dates as the index.
        """
        pass
    
    def _validate_inputs(self, symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
        """Validates standard inputs before fetching."""
        if not symbol or not isinstance(symbol, str) or symbol.strip() == "":
            raise ValueError("Symbol must be a non-empty string.")
        
        def validate_date(date_str, name):
            if date_str:
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    raise ValueError(f"{name} format must be YYYY-MM-DD, got: '{date_str}'")
            return None
            
        start = validate_date(start_date, "start_date")
        end = validate_date(end_date, "end_date")
        
        if start and end and start > end:
            raise ValueError("start_date cannot be after end_date.")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((RequestException, Timeout, ConnectionError, RateLimitExceededError)),
        before_sleep=before_sleep_log(logger, log_level=20),  # 20 = INFO
        reraise=True,
    )
    def _make_http_request(self, url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> dict:
        """
        Generic HTTP GET request helper with automatic retry.
        Retries up to 3 times with exponential backoff for transient network errors.
        Raises HTTPError for non-retryable server errors (4xx).
        """
        logger.debug("GET %s params=%s", url, list((params or {}).keys()))
        response = requests.get(url, params=params, headers=headers, timeout=30)

        # Raise specific error for rate-limiting so tenacity can retry it
        if response.status_code == 429:
            logger.warning("Rate limited (HTTP 429). Retrying after backoff...")
            raise RateLimitExceededError(f"Rate limited by server (HTTP 429) for URL: {url}")

        response.raise_for_status()
        try:
            # Handle gzip-compressed responses
            if response.content[:2] == b'\x1f\x8b':  # gzip magic bytes
                content = gzip.decompress(response.content)
                return json.loads(content)
            return response.json()
        except (ValueError, gzip.BadGzipFile) as e:
            logger.error("Failed to parse JSON response from %s. Snippet: %s", url, response.text[:200])
            raise ValueError(f"Invalid JSON response from API: {e}")
    
    def _normalize_ohlcv(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Standardizes the DataFrame columns to Title Case (Open, High, Low, Close, Volume, Adj Close)
        and ensures the index is a DatetimeIndex.
        """
        if df.empty:
            return pd.DataFrame()
            
        # If all values are NaN (e.g. yfinance returning NaNs for invalid tickers in batch), return empty
        if df.isna().all().all():
            logger.warning("All values are NaN after fetch — returning empty DataFrame.")
            return pd.DataFrame()

        # Flatten MultiIndex columns (e.g., from new yfinance versions returning Price/Ticker)
        if isinstance(df.columns, pd.MultiIndex):
            # We assume level 0 is the metric (Close, High, etc.) and level 1 is the ticker
            df.columns = df.columns.get_level_values(0)

        # Title case mapping for common variants
        col_mapping = {
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume',
            'adjclose': 'Adj Close',
            'adj_close': 'Adj Close',
            'adjClose': 'Adj Close',
            'adjOpen': 'Adj Open',
            'adjHigh': 'Adj High',
            'adjLow': 'Adj Low',
            'adjVolume': 'Adj Volume',
        }
        df = df.rename(columns=col_mapping)
        
        # Ensure index is datetime and named 'Date'
        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception as e:
                logger.warning(
                    "Could not convert index to DatetimeIndex: %s. "
                    "Falling back to pd.to_datetime with errors='coerce'.", e
                )
                df.index = pd.to_datetime(df.index, errors='coerce')
        df.index.name = "Date"
                
        return df

    def _normalize_financials(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Standardizes financial statement column names across different providers.
        Targets: Net_Income, Total_Equity, Shares_Outstanding, Total_Revenue,
                 Operating_Income, Free_Cash_Flow, Total_Assets, Total_Liabilities.
        """
        if df.empty:
            return df
            
        # Common variations for fundamental metrics
        col_mapping = {
            # Net Income
            'netIncome': 'Net_Income',
            'Net Income': 'Net_Income',
            'netIncomeLoss': 'Net_Income',
            'net_income': 'Net_Income',
            
            # Total Equity
            'totalStockholdersEquity': 'Total_Equity',
            'Total Stockholder Equity': 'Total_Equity',
            'Stockholders Equity': 'Total_Equity',
            'totalEquity': 'Total_Equity',
            'total_equity': 'Total_Equity',
            'totalShareholderEquity': 'Total_Equity',
            
            # Shares Outstanding
            'sharesOutstanding': 'Shares_Outstanding',
            'commonStockSharesOutstanding': 'Shares_Outstanding',
            'Basic Average Shares': 'Shares_Outstanding',
            'shares_outstanding': 'Shares_Outstanding',
            'shares_outstanding_basic': 'Shares_Outstanding',
            
            # Total Revenue
            'totalRevenue': 'Total_Revenue',
            'Total Revenue': 'Total_Revenue',
            'revenue': 'Total_Revenue',
            
            # Operating Income
            'operatingIncome': 'Operating_Income',
            'Operating Income': 'Operating_Income',
            'operating_income': 'Operating_Income',
            'ebit': 'Operating_Income',
            'EBIT': 'Operating_Income',
            
            # Free Cash Flow
            'freeCashFlow': 'Free_Cash_Flow',
            'Free Cash Flow': 'Free_Cash_Flow',
            'free_cash_flow': 'Free_Cash_Flow',
            
            # Total Assets
            'totalAssets': 'Total_Assets',
            'Total Assets': 'Total_Assets',
            'total_assets': 'Total_Assets',
            
            # Total Liabilities
            'totalLiabilities': 'Total_Liabilities',
            'Total Liabilities': 'Total_Liabilities',
            'Total Liabilities Net Minority Interest': 'Total_Liabilities',
            'total_liabilities': 'Total_Liabilities'
        }
        
        # Rename columns if they exist in mapping
        df = df.rename(columns=col_mapping)
        
        # Ensure index is datetime and named 'Date'
        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                # Some APIs return dates in index, some as a column. Assume index here.
                df.index = pd.to_datetime(df.index)
            except Exception:
                pass
        df.index.name = "Date"
                
        return df
    
    def fetch_multiple(
        self, 
        symbols: List[str], 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None,
        max_workers: int = 5,
        **kwargs
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple tickers, returning a dictionary of DataFrames.
        Symbols that fail are logged and excluded from the result.
        Uses ThreadPoolExecutor for concurrent fetching to improve performance.
        """
        if not symbols:
            return {}

        results = {}

        def _fetch_one(symbol):
            try:
                # Add random delay to prevent instantly hitting rate limits
                time.sleep(rd.uniform(0.1, 0.5))
                df = self.fetch_single(symbol, start_date, end_date, **kwargs)
                return symbol, df, None
            except Exception as e:
                return symbol, None, e

        logger.info(
            "Batch fetching %d symbols concurrently (max_workers=%d)...", 
            len(symbols), max_workers
        )

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_fetch_one, sym): sym for sym in symbols}
            for future in concurrent.futures.as_completed(futures):
                sym, df, err = future.result()
                if err:
                    logger.error("Failed to fetch %s — skipping. Error: %s", sym, err)
                else:
                    results[sym] = df

        succeeded = len(results)
        failed = len(symbols) - succeeded
        if failed > 0:
            logger.warning(
                "fetch_multiple finished: %d/%d succeeded, %d failed.",
                succeeded, len(symbols), failed,
            )
        else:
            logger.info("fetch_multiple finished: all %d symbols succeeded.", succeeded)

        return results