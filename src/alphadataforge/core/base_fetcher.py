from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional, List, Dict  # Remember to import List and Dict
import random as rd

class BaseDataFetcher(ABC):
    """
    Abstract Base Class for all data fetchers.
    Acts as a contract ensuring all fetchers implement the fetch_data method.
    """
    
    @abstractmethod
    def fetch_data(
        self, 
        symbol: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None, 
        **kwargs
    ) -> pd.DataFrame:
        """
        Fetch data for a single symbol
        (Every fetcher must implement its own data retrieval method in this function)
        """
        pass
    
    def fetch_multiple(
        self, 
        tickers: List[str], 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None,
        **kwargs
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple tickers simultaneously, returning a dictionary of DataFrames
        """
        results = {}
        for ticker in tickers:
            print(f"Fetching {ticker}...")
            # It calls the child class's fetch_data (e.g., yfinance) for each ticker
            results[ticker] = self.fetch_data(ticker, start_date, end_date, **kwargs)
            
            # add random delay to avoid API rate limits
            time.sleep(rd.uniform(0.5,1))
            
        return results