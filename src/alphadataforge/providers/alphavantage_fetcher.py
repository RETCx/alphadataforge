import pandas as pd
from typing import Optional, List, Dict

from requests.exceptions import RequestException
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type

from ..core.base_fetcher import BaseDataFetcher
from ..config.settings import config
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class AlphaVantageFetcher(BaseDataFetcher):
    """
    Data fetcher for Alpha Vantage using direct HTTP requests.
    Supports: EOD stock price.
    
    Requires ALPHAVANTAGE_API_KEY environment variable.
    Free tier limit: 25 requests per day.
    """

    def __init__(self):
        self.api_key = config.ALPHAVANTAGE_API_KEY
        self.base_url = "https://www.alphavantage.co/query"

        if not self.api_key:
            raise ValueError(
                "ALPHAVANTAGE_API_KEY is not set. "
                "Please set it in your .env file or environment variables."
            )

    def _make_request(self, **params) -> dict:
        """
        Executes HTTP GET request to Alpha Vantage API.
        Raises ValueError for API-level errors (bad symbol, etc.).
        Raises RuntimeError for rate-limit / information notices.
        """
        params['apikey'] = self.api_key
        data = self._make_http_request(self.base_url, params=params)
        
        # Alpha Vantage returns an error message in the JSON payload instead of HTTP status sometimes
        if "Error Message" in data:
            raise ValueError(f"AlphaVantage API Error: {data['Error Message']}")
        if "Information" in data:
            raise RuntimeError(
                f"AlphaVantage rate limit or notice: {data['Information']}"
            )
        return data

    def _parse_response(self, raw_json: dict, time_series_key: str) -> pd.DataFrame:
        """
        Parses Alpha Vantage JSON response into a Pandas DataFrame.
        Raises KeyError if the expected time series key is missing from the response.
        """
        if time_series_key not in raw_json:
            logger.warning(
                "Expected key '%s' not found in API response. "
                "Available keys: %s", time_series_key, list(raw_json.keys())
            )
            return pd.DataFrame()
            
        time_series_data = raw_json[time_series_key]
        
        # Convert dictionary to DataFrame
        df = pd.DataFrame.from_dict(time_series_data, orient='index')
        
        # Alpha Vantage returns columns like "1. open", "2. high", etc.
        # We clean them to match standard mappings ("open", "high", etc.)
        # so that _normalize_ohlcv can capitalize them.
        rename_map = {
            '1. open': 'open',
            '2. high': 'high',
            '3. low': 'low',
            '4. close': 'close',
            '5. volume': 'volume',
            '5. adjusted close': 'adjClose',
            '6. volume': 'volume',  # Adjusted daily uses 6 for volume
        }
        df.rename(columns=rename_map, inplace=True)
        
        # Convert types from string to float
        for col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        return df

    # ------------------------------------------------------------------
    # Required by BaseDataFetcher — fetches PRICE for 1 symbol
    # ------------------------------------------------------------------
    def fetch_single(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        outputsize: str = "compact",  # "compact" (100 days) or "full" (20 years)
        adjusted: bool = False,
        **kwargs
    ) -> pd.DataFrame:
        """
        Fetch EOD price data for a single stock/ETF symbol from Alpha Vantage.
        
        Raises:
            ValueError: If symbol is invalid or API returns an error.
            RuntimeError: If rate limit is exceeded.
            RequestException: If network request fails after retries.
        """
        logger.info("Fetching price for %s (size=%s, adjusted=%s)...", symbol, outputsize, adjusted)
        self._validate_inputs(symbol, start_date, end_date)
        
        function = "TIME_SERIES_DAILY_ADJUSTED" if adjusted else "TIME_SERIES_DAILY"
        time_series_key = "Time Series (Daily)"
        
        # --- Step 1: Fetch price data (will raise on failure) ---
        raw_json = self._make_request(
            function=function,
            symbol=symbol,
            outputsize=outputsize
        )
        df = self._parse_response(raw_json, time_series_key)
        
        # Alpha Vantage doesn't let us filter by date in the API call directly
        # We must filter it locally in pandas
        if not df.empty:
            df.index = pd.to_datetime(df.index)
            if start_date:
                df = df[df.index >= pd.to_datetime(start_date)]
            if end_date:
                df = df[df.index <= pd.to_datetime(end_date)]

        # --- Step 2: Fetch Dividends & Splits (separate try/except) ---
        if adjusted and not df.empty:
            import time

            div_df = pd.DataFrame(columns=['Dividend'])
            split_df = pd.DataFrame(columns=['SplitFactor'])

            # --- 2a: Dividends ---
            try:
                logger.info("Fetching DIVIDENDS for %s...", symbol)
                time.sleep(1.2)  # Avoid 1 req/sec limit
                div_json = self._make_request(function="DIVIDENDS", symbol=symbol)
                div_data = div_json.get("data", [])
                if div_data:
                    div_df = pd.DataFrame(div_data)
                    div_df['Dividend'] = pd.to_numeric(div_df['amount'], errors='coerce')
                    div_df.index = pd.to_datetime(div_df['ex_dividend_date'])
            except Exception as e:
                logger.warning(
                    "Could not fetch dividends for %s: %s. "
                    "Proceeding without dividend adjustment.", symbol, e
                )

            # --- 2b: Splits ---
            try:
                logger.info("Fetching SPLITS for %s...", symbol)
                time.sleep(1.2)  # Avoid 1 req/sec limit
                split_json = self._make_request(function="SPLITS", symbol=symbol)
                split_data = split_json.get("data", [])
                if split_data:
                    split_df = pd.DataFrame(split_data)
                    split_df['SplitFactor'] = pd.to_numeric(split_df['split_factor'], errors='coerce')
                    split_df.index = pd.to_datetime(split_df['effective_date'])
            except Exception as e:
                logger.warning(
                    "Could not fetch splits for %s: %s. "
                    "Proceeding without split adjustment.", symbol, e
                )

            # --- 2c: Apply adjustment ---
            from ..utils.finance_math import calculate_adjusted_prices
            df = self._normalize_ohlcv(df)
            df = calculate_adjusted_prices(df, div_df, split_df)
                    
        return self._normalize_ohlcv(df)

    # ------------------------------------------------------------------
    # Fetch price for multiple symbols at once
    # ------------------------------------------------------------------
    def fetch_multiple(
        self,
        symbols: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        outputsize: str = "compact",
        adjusted: bool = False,
        **kwargs
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch price data for multiple symbols.
        Alpha Vantage does not have a batch endpoint for free tier, so we must loop.
        WARNING: This easily consumes the 25 req/day limit.
        Symbols that fail are logged and excluded from the result.
        """
        logger.warning(
            "Batch fetching %d symbols from AlphaVantage. "
            "WARNING: This uses ~%d API credits!",
            len(symbols), len(symbols)
        )
        
        # Delegate to BaseDataFetcher.fetch_multiple which handles per-symbol
        # error isolation and logging automatically.
        return super().fetch_multiple(
            symbols,
            start_date=start_date,
            end_date=end_date,
            outputsize=outputsize,
            adjusted=adjusted,
            **kwargs
        )

    # ------------------------------------------------------------------
    # Fetch fundamental data
    # ------------------------------------------------------------------
    def fetch_fundamental(self, symbol: str, function: str = "OVERVIEW") -> dict:
        """
        Fetch fundamental data from Alpha Vantage.
        Supported functions: OVERVIEW, INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW, EARNINGS, etc.
        
        Raises:
            ValueError: If symbol is invalid or API returns an error.
            RuntimeError: If rate limit is exceeded.
        """
        logger.info("Fetching %s for %s...", function, symbol)
        self._validate_inputs(symbol)
        
        raw_json = self._make_request(
            function=function,
            symbol=symbol
        )
        return raw_json
