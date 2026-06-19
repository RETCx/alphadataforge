from typing import Optional, Dict, Any
import pandas as pd

# ดึงผู้ปฏิบัติงาน (Providers) ที่อยู่หลังบ้านมาเตรียมไว้
from ..providers.yfinance_fetcher import YFinanceFetcher
from ..providers.tiingo_fetcher import TiingoFetcher

class Price:
    """
    Unified Facade API for fetching price data.
    Hides provider-specific complexity from the caller.
    """
    
    @staticmethod
    def get(
        symbol: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None,
        provider: str = "yfinance",    # Which provider to use (default: yfinance)
        provider_params: Optional[Dict[str, Any]] = None  # Extra provider-specific params
    ) -> pd.DataFrame:
        
        # Prevent error if no params are passed
        provider_params = provider_params or {}
        
        # 1. Route to the correct provider
        if provider == "yfinance":
            fetcher = YFinanceFetcher()
        elif provider == "tiingo":
            fetcher = TiingoFetcher()
        else:
            raise ValueError(f"Unsupported provider: '{provider}'. Choose 'yfinance' or 'tiingo'.")
            
        # 2. Fetch the data, forwarding any extra params through **provider_params
        df = fetcher.fetch_single(symbol, start_date, end_date, **provider_params)
        
        # 3. Return to caller
        return df