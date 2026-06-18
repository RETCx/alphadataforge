import yfinance as yf
import pandas as pd
from typing import Optional

# Import the base class template
from ..core.base_fetcher import BaseDataFetcher

class YFinanceFetcher(BaseDataFetcher):
    """
    Data fetcher for Yahoo Finance API.
    Inherits from BaseDataFetcher.
    """
    
    def fetch_data(
        self, 
        symbol: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None, 
        **kwargs
    ) -> pd.DataFrame:
        
        print(f"[YFinanceFetcher] Fetching data for {symbol}...")
        
        # Download data using yfinance
        df = yf.download(tickers=symbol, start=start_date, end=end_date, progress=False, **kwargs)
        
        # Return the DataFrame as defined in the contract
        return df