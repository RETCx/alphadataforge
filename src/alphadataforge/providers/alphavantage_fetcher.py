import pandas as pd
from typing import Optional, List, Dict

import time
from ..utils.finance_math import calculate_adjusted_prices

from ..core.base_fetcher import BaseDataFetcher
from ..core.exceptions import ProviderConfigurationError, RateLimitExceededError, InvalidTickerError
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
            raise ProviderConfigurationError(
                "ALPHAVANTAGE_API_KEY is not set. "
                "Please set it in your .env file or environment variables."
            )

    def _make_request(self, **params) -> dict:
        """
        Executes HTTP GET request to Alpha Vantage API.
        Raises ValueError for API-level errors (bad symbol, etc.).
        Raises RuntimeError for rate-limit / information notices.
        """
        # AlphaVantage Free Tier allows max 1 request/second. 
        # Add automatic delay to prevent immediate rate limit hits when users chain calls.
        time.sleep(1.2)
        
        params['apikey'] = self.api_key
        data = self._make_http_request(self.base_url, params=params)
        
        # Alpha Vantage returns an error message in the JSON payload instead of HTTP status sometimes
        if "Error Message" in data:
            raise InvalidTickerError(f"AlphaVantage API Error: {data['Error Message']}")
        if "Information" in data:
            raise RateLimitExceededError(
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
        
        # TIME_SERIES_DAILY_ADJUSTED is a premium endpoint now.
        # We always use TIME_SERIES_DAILY and manually adjust it using DIVIDENDS/SPLITS.
        function = "TIME_SERIES_DAILY"
        time_series_key = "Time Series (Daily)"
        
        # --- Step 1: Fetch price data (will raise on failure) ---
        raw_json = self._make_request(
            function=function,
            symbol=symbol,
            outputsize=outputsize
        )
        df = self._parse_response(raw_json, time_series_key)
        if df.empty:
            logger.warning("_parse_response returned empty for %s (key='%s').", symbol, time_series_key)
        
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

            div_df = pd.DataFrame(columns=['Dividend'])
            split_df = pd.DataFrame(columns=['SplitFactor'])

            # --- 2a: Dividends ---
            try:
                logger.info("Fetching DIVIDENDS for %s...", symbol)
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
            InvalidTickerError: If symbol is invalid or API returns an error.
            RateLimitExceededError: If rate limit is exceeded.
        """
        logger.info("Fetching %s for %s...", function, symbol)
        self._validate_inputs(symbol)
        
        raw_json = self._make_request(
            function=function,
            symbol=symbol
        )
        return raw_json

    def fetch_info(self, symbol: str) -> dict:
        """
        Fetch company profile (fundamentals like sector, industry, mktCap).
        """
        logger.info("Fetching info for %s via AlphaVantage...", symbol)
        return self.fetch_fundamental(symbol, function="OVERVIEW")

    def fetch_financials(self, symbol: str, statement: str = "income", period: str = "annual") -> pd.DataFrame:
        """
        Fetch financial statements from AlphaVantage.
        """
        logger.info("Fetching %s statement for %s (%s) via AlphaVantage...", statement, symbol, period)
        
        endpoint_map = {
            "income": "INCOME_STATEMENT",
            "balance": "BALANCE_SHEET",
            "cashflow": "CASH_FLOW",
            "shares_outstanding": "SHARES_OUTSTANDING",
            "earnings": "EARNINGS"
        }
        
        if statement not in endpoint_map:
            raise ValueError(f"Unknown statement type: '{statement}'. Choose 'income', 'balance', 'cashflow', 'shares_outstanding', or 'earnings'.")
            
        function = endpoint_map[statement]
        raw_json = self.fetch_fundamental(symbol, function=function)
        
        # AlphaVantage uses different keys for different endpoints
        if statement == "shares_outstanding":
            # SHARES_OUTSTANDING uses a flat "data" list
            reports = raw_json.get("data", [])
        else:
            if statement == "earnings":
                report_key = "quarterlyEarnings" if period.lower() == "quarterly" else "annualEarnings"
            else:
                report_key = "quarterlyReports" if period.lower() == "quarterly" else "annualReports"
            reports = raw_json.get(report_key, [])
            
        if not reports:
            logger.warning("No %s financial data found for %s in AlphaVantage.", period, symbol)
            return pd.DataFrame()
            
        df = pd.DataFrame(reports)
        
        # fiscalDateEnding or date is the index
        if 'fiscalDateEnding' in df.columns:
            df.index = pd.to_datetime(df['fiscalDateEnding'])
            df = df.drop(columns=['fiscalDateEnding'])
        elif 'date' in df.columns:
            df.index = pd.to_datetime(df['date'])
            df = df.drop(columns=['date'])
            
        return self._normalize_financials(df)

    def fetch_earnings_calendar(self, horizon: str = "3month", symbol: Optional[str] = None) -> pd.DataFrame:
        """
        Fetch earnings calendar.
        horizon: '3month', '6month', or '12month'
        symbol: Optional specific symbol to fetch for.
        """
        logger.info("Fetching earnings calendar (horizon=%s) via AlphaVantage...", horizon)
        
        # AlphaVantage Free Tier allows max 1 request/second.
        time.sleep(1.2)
        
        # This endpoint returns CSV directly, so we use pandas read_csv instead of _make_request
        url = f"{self.base_url}?function=EARNINGS_CALENDAR&horizon={horizon}&apikey={self.api_key}"
        if symbol:
            url += f"&symbol={symbol}"
            
        try:
            df = pd.read_csv(url)
            # Check for API rate limit (AlphaVantage returns JSON error if rate limited, which breaks read_csv, or returns a 1-row DataFrame with the error)
            if not df.empty and len(df.columns) == 1 and "Thank you for using Alpha Vantage!" in str(df.iloc[0, 0]):
                raise RateLimitExceededError(f"AlphaVantage rate limit or notice: {df.iloc[0, 0]}")
            
            # The CSV columns are: symbol, name, reportDate, fiscalDateEnding, estimate, currency
            if 'reportDate' in df.columns:
                df['reportDate'] = pd.to_datetime(df['reportDate'], errors='coerce')
            if 'fiscalDateEnding' in df.columns:
                df['fiscalDateEnding'] = pd.to_datetime(df['fiscalDateEnding'], errors='coerce')
                
            return df
        except Exception as e:
            if isinstance(e, RateLimitExceededError):
                raise
            logger.error("Failed to fetch earnings calendar: %s", e)
            return pd.DataFrame()
