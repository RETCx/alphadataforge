from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional, List, Dict  # Remember to import List and Dict
import random as rd
import time

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