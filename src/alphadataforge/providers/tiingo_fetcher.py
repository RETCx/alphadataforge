import pandas as pd
from typing import Optional, List, Dict, Any
from tiingo import TiingoClient
from ..core.base_fetcher import BaseDataFetcher


class TiingoFetcher(BaseDataFetcher):
    """
    Data fetcher for Tiingo API using the official tiingo-python client.
    Supports: stock price, news, fundamentals, and crypto.

    Requires TIINGO_API_KEY environment variable to be set.
    Free tier: 500 requests/hr, EOD prices + news headlines.
    """

    def __init__(self):
        # TiingoClient automatically reads TIINGO_API_KEY from environment
        self.client = TiingoClient({'session': True})

    # ------------------------------------------------------------------
    # [Contract] Required by BaseDataFetcher — fetches PRICE for 1 symbol
    # ------------------------------------------------------------------
    def fetch_single(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        frequency: str = "daily",
        **kwargs
    ) -> pd.DataFrame:
        """
        Fetch EOD price data for a single stock/ETF symbol.

        Args:
            symbol:     Ticker symbol, e.g. "AAPL"
            start_date: "YYYY-MM-DD" (inclusive)
            end_date:   "YYYY-MM-DD" (inclusive)
            frequency:  "daily" | "weekly" | "monthly" | "annually" | "1min" | "5min" etc.
            **kwargs:   Any extra params forwarded to TiingoClient.get_dataframe()
        """
        print(f"[TiingoFetcher] Fetching price for {symbol} ({frequency})...")
        df = self.client.get_dataframe(
            symbol,
            startDate=start_date,
            endDate=end_date,
            frequency=frequency,
            **kwargs
        )
        return df

    # ------------------------------------------------------------------
    # [Bonus] Fetch price for multiple symbols at once
    # ------------------------------------------------------------------
    def fetch_multiple(
        self,
        symbols: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        frequency: str = "daily",
        metric_name: str = "adjClose",
        **kwargs
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch price data for multiple symbols.
        Uses tiingo's built-in batch method when metric_name is specified,
        which is more efficient than looping.

        Returns: {symbol: DataFrame}
        """
        print(f"[TiingoFetcher] Batch fetching {len(symbols)} symbols...")
        combined: pd.DataFrame = self.client.get_dataframe(
            symbols,
            startDate=start_date,
            endDate=end_date,
            frequency=frequency,
            metric_name=metric_name,
            **kwargs
        )
        # When passing a list, tiingo returns a DataFrame with symbol columns
        return {sym: combined[[sym]].rename(columns={sym: metric_name})
                for sym in symbols if sym in combined.columns}

    # ------------------------------------------------------------------
    # [Extra] News — curated financial news with ticker + tag filtering
    # ------------------------------------------------------------------
    def fetch_news(
        self,
        tickers: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        sources: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 100,
    ) -> pd.DataFrame:
        """
        Fetch financial news articles from Tiingo.

        Args:
            tickers:    Filter by ticker symbols, e.g. ["AAPL", "GOOGL"]
            tags:       Filter by topic tags, e.g. ["Earnings"]
            sources:    Filter by news source domain, e.g. ["reuters.com"]
            start_date: "YYYY-MM-DD"
            end_date:   "YYYY-MM-DD"
            limit:      Max number of articles to return

        Returns:
            DataFrame with columns: publishedDate, title, description, url, tickers, tags
        """
        print(f"[TiingoFetcher] Fetching news (tickers={tickers}, tags={tags})...")
        articles = self.client.get_news(
            tickers=tickers,
            tags=tags,
            sources=sources,
            startDate=start_date,
            endDate=end_date,
            limit=limit,
        )
        return pd.DataFrame(articles)

    # ------------------------------------------------------------------
    # [Extra] Fundamentals — daily (marketCap etc.) and quarterly statements
    # ------------------------------------------------------------------
    def fetch_fundamentals_daily(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Fetch daily-updated fundamental metrics (e.g. marketCap, EV).
        NOTE: Requires Tiingo paid plan.
        """
        print(f"[TiingoFetcher] Fetching daily fundamentals for {symbol}...")
        data = self.client.get_fundamentals_daily(
            symbol, startDate=start_date, endDate=end_date
        )
        return pd.DataFrame(data)

    def fetch_fundamentals_statements(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        as_reported: bool = False,
    ) -> pd.DataFrame:
        """
        Fetch quarterly financial statements (income, balance sheet, cash flow).
        NOTE: Requires Tiingo paid plan.

        Args:
            as_reported: If True, returns raw SEC-reported data (no corrections).
        """
        print(f"[TiingoFetcher] Fetching quarterly statements for {symbol}...")
        data = self.client.get_fundamentals_statements(
            symbol,
            startDate=start_date,
            endDate=end_date,
            asReported=as_reported,
        )
        return pd.DataFrame(data)

    # ------------------------------------------------------------------
    # [Extra] Crypto — historical OHLCV for crypto pairs
    # ------------------------------------------------------------------
    def fetch_crypto(
        self,
        tickers: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        resample_freq: str = "1Day",
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical cryptocurrency price data.

        Args:
            tickers:       Crypto pairs as a list, e.g. ["BTCUSD", "ETHUSD"]
            start_date:    "YYYY-MM-DD"
            end_date:      "YYYY-MM-DD"
            resample_freq: e.g. "1Day", "1Hour", "30Min"

        Returns: {ticker: DataFrame}
        """
        print(f"[TiingoFetcher] Fetching crypto: {tickers}...")
        data = self.client.get_crypto_price_history(
            tickers=tickers,
            startDate=start_date,
            endDate=end_date,
            resampleFreq=resample_freq,
        )
        # Tiingo returns a list of dicts, each with 'ticker' and 'priceData'
        result = {}
        for item in data:
            ticker = item['ticker']
            result[ticker] = pd.DataFrame(item['priceData'])
        return result