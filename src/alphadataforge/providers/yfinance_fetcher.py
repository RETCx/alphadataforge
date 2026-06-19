import yfinance as yf
import pandas as pd
from typing import Optional, List, Dict
# Import the base class template
from ..core.base_fetcher import BaseDataFetcher

class YFinanceFetcher(BaseDataFetcher):
    """
    Data fetcher for Yahoo Finance API.
    Inherits from BaseDataFetcher.
    """
    
    def fetch_single(
        self, 
        symbol: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None, 
        interval: str = "1d",
        **kwargs
    ) -> pd.DataFrame:
        
        print(f"[YFinanceFetcher] Fetching data for {symbol}...")
        
        # Download data using yfinance
        df = yf.download(tickers=symbol, start=start_date, end=end_date, progress=False, interval=interval, **kwargs)
        
        # Return the DataFrame as defined in the contract
        return df

    def fetch_multiple(
        self, 
        symbols: List[str], 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None, 
        interval: str = "1d",
        **kwargs            
    ) -> Dict[str, pd.DataFrame]:
        print("Using yfinance Batch Download!")
        kwargs['group_by'] = 'ticker'
        df = yf.download(symbols, start=start_date, end=end_date, interval=interval, **kwargs)
        if len(symbols) == 1:
            return {symbols[0]: df}
        else:
            return {symbol: df[symbol] for symbol in symbols}