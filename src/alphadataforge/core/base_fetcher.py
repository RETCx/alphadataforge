from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional, List, Dict
import random as rd
import time
from datetime import datetime

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
    
    def _validate_inputs(self, symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
        """Validates standard inputs before fetching."""
        if not symbol or not isinstance(symbol, str) or symbol.strip() == "":
            raise ValueError("Symbol must be a non-empty string.")
        
        def validate_date(date_str, name):
            if date_str:
                try:
                    return datetime.strptime(date_str, "%Y-%m-%d")
                except ValueError:
                    raise ValueError("Date format must be YYYY-MM-DD.")
            return None
            
        start = validate_date(start_date, "start_date")
        end = validate_date(end_date, "end_date")
        
        if start and end and start > end:
            raise ValueError("start_date cannot be after end_date.")
    
    def _normalize_ohlcv(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Standardizes the DataFrame columns to Title Case (Open, High, Low, Close, Volume, Adj Close)
        and ensures the index is a DatetimeIndex.
        """
        if df.empty:
            return pd.DataFrame()
            
        # If all values are NaN (e.g. yfinance returning NaNs for invalid tickers in batch), return empty
        if df.isna().all().all():
            return pd.DataFrame()

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
        
        # Ensure index is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            try:
                df.index = pd.to_datetime(df.index)
            except Exception:
                pass
                
        return df
    
    def fetch_multiple(
        self, 
        symbols: List[str], 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None,
        **kwargs
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple tickers simultaneously, returning a dictionary of DataFrames
        """
        results = {}
        for symbol in symbols:
            print(f"Fetching {symbol}...")
            # It calls the child class's fetch_single (e.g., yfinance) for each ticker
            results[symbol] = self.fetch_single(symbol, start_date, end_date, **kwargs)
            
            # add random delay to avoid API rate limits
            time.sleep(rd.uniform(0.5,1))
            
        return results