import pandas as pd
from typing import Optional
from ..core.base_fetcher import BaseDataFetcher
import os

class TiingoFetcher(BaseDataFetcher):
    def __init__(self):
        self.api_key = os.environ.get("TIINGO_API_KEY")
        if not self.api_key:
            raise ValueError("TIINGO_API_KEY environment variable not set")

    def fetch_single(
        self, 
        symbol: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None,
        interval: str = "daily",
        **kwargs
    ) -> pd.DataFrame:
        print(f"[TiingoFetcher] Fetching data for {symbol}...")
        
        # Build the URL
        url = f"https://api.tiingo.com/tiingo/{interval}/{symbol}/prices"
        
        # Set parameters
        params = {
            'startDate': start_date,
            'endDate': end_date,
            'token': self.api_key
        }
        
        # Add any extra parameters from kwargs
        params.update(kwargs)
        
        # Fetch the data
        response = requests.get(url, params=params)
        response.raise_for_status()
        
        # Parse the JSON response
        data = response.json()
        
        # Convert to DataFrame
        df = pd.DataFrame(data)
        
        # Set the index to the date
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            
        return df
        