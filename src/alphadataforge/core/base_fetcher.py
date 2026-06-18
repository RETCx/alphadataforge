from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional

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
        Fetches data and returns a pandas DataFrame.
        
        Parameters:
        - symbol: Ticker or asset symbol (e.g., 'AAPL', 'BTC-USD')
        - start_date: Start date (YYYY-MM-DD)
        - end_date: End date (YYYY-MM-DD)
        - kwargs: Additional parameters for specific APIs
        
        Returns:
        - pd.DataFrame containing the historical data
        """
        pass