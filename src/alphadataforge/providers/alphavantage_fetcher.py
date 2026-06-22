import requests
import pandas as pd
from typing import Optional, List, Dict
from ..core.base_fetcher import BaseDataFetcher
from ..config.settings import config

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

    def _make_request(self, **params) -> dict:
        """
        Executes HTTP GET request to Alpha Vantage API.
        """
        if not self.api_key:
            raise ValueError("ALPHAVANTAGE_API_KEY is not set.")
            
        params['apikey'] = self.api_key
        data = self._make_http_request(self.base_url, params=params)
        
        # Alpha Vantage returns an error message in the JSON payload instead of HTTP status sometimes
        if "Error Message" in data:
            raise ValueError(f"AlphaVantage API Error: {data['Error Message']}")
        if "Information" in data:
            info = data["Information"].lower()
            raise Exception (info)
        return data

    def _parse_response(self, raw_json: dict, time_series_key: str) -> pd.DataFrame:
        """
        Parses Alpha Vantage JSON response into a Pandas DataFrame.
        """
        if time_series_key not in raw_json:
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
        """
        print(f"[AlphaVantageFetcher] Fetching price for {symbol} (size={outputsize})...")
        self._validate_inputs(symbol, start_date, end_date)
        
        function = "TIME_SERIES_DAILY_ADJUSTED" if adjusted else "TIME_SERIES_DAILY"
        time_series_key = "Time Series (Daily)"
        
        try:
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
                    
            if adjusted and not df.empty:
                import time
                print(f"[AlphaVantageFetcher] Fetching DIVIDENDS and SPLITS for {symbol} to calculate adjusted price...")
                # Fetch Dividends
                time.sleep(1.2)  # Avoid 1 req/sec limit
                div_json = self._make_request(function="DIVIDENDS", symbol=symbol)
                div_data = div_json.get("data", [])
                if div_data:
                    div_df = pd.DataFrame(div_data)
                    div_df['Dividend'] = pd.to_numeric(div_df['amount'], errors='coerce')
                    div_df.index = pd.to_datetime(div_df['ex_dividend_date'])
                else:
                    div_df = pd.DataFrame(columns=['Dividend'])
                    
                # Fetch Splits
                time.sleep(1.2)  # Avoid 1 req/sec limit
                split_json = self._make_request(function="SPLITS", symbol=symbol)
                split_data = split_json.get("data", [])
                if split_data:
                    split_df = pd.DataFrame(split_data)
                    split_df['SplitFactor'] = pd.to_numeric(split_df['split_factor'], errors='coerce')
                    split_df.index = pd.to_datetime(split_df['effective_date'])
                else:
                    split_df = pd.DataFrame(columns=['SplitFactor'])
                
                from ..utils.finance_math import calculate_adjusted_prices
                df = self._normalize_ohlcv(df)
                df = calculate_adjusted_prices(df, div_df, split_df)
                    
        except Exception as e:
            print(f"[AlphaVantageFetcher] Error fetching {symbol}: {e}")
            df = pd.DataFrame()
            
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
        """
        print(f"[AlphaVantageFetcher] Batch fetching {len(symbols)} symbols. (WARNING: This uses {len(symbols)} API credits!)")
        
        results = {}
        for symbol in symbols:
            results[symbol] = self.fetch_single(
                symbol, 
                start_date=start_date, 
                end_date=end_date, 
                outputsize=outputsize, 
                adjusted=adjusted, 
                **kwargs
            )
        return results

    # ------------------------------------------------------------------
    # Fetch fundamental data
    # ------------------------------------------------------------------
    def fetch_fundamental(self, symbol: str, function: str = "OVERVIEW") -> dict:
        """
        Fetch fundamental data from Alpha Vantage.
        Supported functions: OVERVIEW, INCOME_STATEMENT, BALANCE_SHEET, CASH_FLOW, EARNINGS, etc.
        Returns the raw JSON dictionary.
        """
        print(f"[AlphaVantageFetcher] Fetching {function} for {symbol}...")
        self._validate_inputs(symbol)
        
        try:
            raw_json = self._make_request(
                function=function,
                symbol=symbol
            )
            return raw_json
        except Exception as e:
            print(f"[AlphaVantageFetcher] Error fetching {function} for {symbol}: {e}")
            return {}
