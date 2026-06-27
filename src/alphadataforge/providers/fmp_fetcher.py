import pandas as pd
import requests
from typing import Optional, List, Dict, Any

from ..core.base_fetcher import BaseDataFetcher
from ..core.exceptions import ProviderConfigurationError
from ..config.settings import config
from ..config.endpoints import Endpoints
from ..utils.logger import setup_logger

logger = setup_logger(__name__)

class FMPFetcher(BaseDataFetcher):
    """
    Data fetcher for Financial Modeling Prep (FMP).
    Handles EOD prices, splits, and dividends.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.api_key = api_key or config.FMP_API_KEY
        self.base_url = Endpoints.FMP.BASE_URL

    def _require_api_key(self) -> None:
        if not self.api_key:
            raise ProviderConfigurationError(
                "FMP_API_KEY is not set. Please set it in your .env file or environment variables."
            )

    def _make_request(self, endpoint: str, **params) -> dict:
        """
        Executes HTTP GET request to FMP API.
        """
        self._require_api_key()
        params['apikey'] = self.api_key
        url = f"{self.base_url}/{endpoint}"
        return self._make_http_request(url, params=params)

    def fetch_single(
        self, 
        symbol: str, 
        start_date: Optional[str] = None, 
        end_date: Optional[str] = None, 
        outputsize: str = "full", 
        adjusted: bool = False,
        **kwargs
    ) -> pd.DataFrame:
        """
        Fetch EOD price data for a single symbol from FMP.
        FMP provides 'adjClose' by default, but if `adjusted=True`, this will fully calculate 
        Adj Open, Adj High, Adj Low, and Adj Volume via the finance_math utility.
        """
        logger.info("Fetching price for %s (adjusted=%s) via FMP...", symbol, adjusted)
        self._validate_inputs(symbol, start_date, end_date)
        
        # --- Step 1: Fetch raw price data ---
        # Note: We request 'from' and 'to' in the API to save bandwidth
        params = {'symbol': symbol}
        if start_date:
            params['from'] = start_date
        if end_date:
            params['to'] = end_date

        # Use the appropriate endpoint based on 'adjusted' flag
        # 'dividend-adjusted' = Fully adjusted (splits + dividends)
        # 'price_adjusted' = Fully adjusted (splits + dividends)
        # 'price_raw' = Standard price (split-adjusted only)
        if adjusted:
            endpoint = Endpoints.FMP.PATHS["price_adjusted"]
        else:
            endpoint = Endpoints.FMP.PATHS["price_raw"]
        
        raw_json = self._make_request(endpoint, **params)
            
        historical = raw_json if isinstance(raw_json, list) else raw_json.get("historical", [])
        if not historical:
            logger.warning("No historical data found for %s in FMP.", symbol)
            return pd.DataFrame()
            
        df = pd.DataFrame(historical)
        if 'date' in df.columns:
            df.index = pd.to_datetime(df['date'])
            df = df.drop(columns=['date'])

        # Since FMP's dividend-adjusted endpoint already provides adjusted OHLC, 
        # we don't need to manually fetch splits/dividends and calculate it.
        # We just normalize the columns and return.
        
        return self._normalize_ohlcv(df)

    def fetch_multiple(
        self,
        symbols: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        outputsize: str = "full",
        adjusted: bool = False,
        **kwargs
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch price data for multiple symbols.
        Passes outputsize and adjusted down to fetch_single.
        """
        return super().fetch_multiple(
            symbols,
            adjusted=adjusted,
            **kwargs
        )

    def fetch_info(self, symbol: str) -> dict:
        """
        Fetch company profile (fundamentals like sector, industry, mktCap).
        """
        logger.info("Fetching info for %s via FMP...", symbol)
        self._validate_inputs(symbol)
        
        # FMP profile API
        # using the v3 endpoint, but our base url is stable, wait, we need to adjust the base_url or override it
        # self.base_url is "https://financialmodelingprep.com/stable" but profile is usually "https://financialmodelingprep.com/api/v3/profile/AAPL"
        # Let's override the url completely here.
        url = f"{self.base_url}/{Endpoints.FMP.PATHS['profile']}"
        params = {'apikey': self.api_key, 'symbol': symbol}
        
        try:
            
            data = self._make_http_request(url, params=params)
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            return {}
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                raise RuntimeError("FMP Fundamentals data (like company profile) requires a premium API key.") from e
            raise

    def fetch_financials(self, symbol: str, statement: str = "income", period: str = "annual") -> pd.DataFrame:
        """
        Fetch financial statements from FMP.
        """
        logger.info("Fetching %s statement for %s (%s) via FMP...", statement, symbol, period)
        self._validate_inputs(symbol)
        
        # FMP expects period as 'annual' (default/omit) or 'quarter'
        fmp_period = "quarter" if period.lower() == "quarterly" else "annual"
        
        endpoint_map = Endpoints.FMP.PATHS
        valid_statements = {"income", "balance", "cashflow", "shares_float"}
        
        if statement not in valid_statements:
            raise ValueError(f"Unknown statement type: '{statement}'. Choose 'income', 'balance', 'cashflow', or 'shares_float'.")
            
        if statement == "shares_float":
            url = f"{self.base_url}/{Endpoints.FMP.PATHS['shares_float']}"
            params = {'apikey': self.api_key, 'symbol': symbol}
        else:
            url = f"{self.base_url}/{endpoint_map[statement]}"
            params = {'apikey': self.api_key, 'symbol': symbol, 'limit': 5} # limit 5 for free tier
            if fmp_period == "quarter":
                params['period'] = "quarter"

            
        try:
            data = self._make_http_request(url, params=params)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                raise RuntimeError(f"FMP Financial Statements data requires a premium API key.") from e
            raise
            
        if not data or not isinstance(data, list):
            logger.warning("No financial data found for %s in FMP.", symbol)
            return pd.DataFrame()
            
        df = pd.DataFrame(data)
        
        # FMP returns dates in the 'date' column.
        if 'date' in df.columns:
            df.index = pd.to_datetime(df['date'])
            df = df.drop(columns=['date'])
            
        # Normalize and return
        if statement == "shares_float":
            # Just return the DataFrame directly for shares_float
            return df
        return self._normalize_financials(df)
