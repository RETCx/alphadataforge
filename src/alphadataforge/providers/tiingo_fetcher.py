import pandas as pd
import os
from typing import Optional, List, Dict, Any
from tiingo import TiingoClient
from ..core.base_fetcher import BaseDataFetcher
from ..core.exceptions import ProviderConfigurationError
from ..config.settings import config
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class TiingoFetcher(BaseDataFetcher):
    """
    Data fetcher for Tiingo API using the official tiingo-python client.
    Supports: stock price, news, fundamentals, and crypto.

    Requires TIINGO_API_KEY environment variable to be set.
    Free tier: 500 requests/hr, EOD prices + news headlines.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or config.TIINGO_API_KEY
        self._client = None

    @property
    def client(self) -> TiingoClient:
        if not self._client:
            if not self.api_key:
                raise ProviderConfigurationError(
                    "TIINGO_API_KEY is not set. Please set it in your .env file or environment variables."
                )
            # Temporarily inject key to OS env for TiingoClient
            os.environ['TIINGO_API_KEY'] = self.api_key
            self._client = TiingoClient({'session': True})
        return self._client
        

    # ------------------------------------------------------------------
    # Required by BaseDataFetcher — fetches PRICE for 1 symbol
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
        
        Raises:
            ValueError: If symbol or date inputs are invalid.
            Exception: If Tiingo API call fails (network, auth, etc.)
        """
        logger.info("Fetching price for %s (%s)...", symbol, frequency)
        self._validate_inputs(symbol, start_date, end_date)
        
        df = self.client.get_dataframe(
            tickers=symbol,
            startDate=start_date,
            endDate=end_date,
            frequency=frequency,
            **kwargs
        )
        
        if df.empty:
            logger.warning("Tiingo returned empty DataFrame for %s. Check if the ticker is valid.", symbol)

        return self._normalize_ohlcv(df)

    # ------------------------------------------------------------------
    # Fetch price for multiple symbols at once
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
        
        Symbols that fail or return empty data are logged and excluded.

        Returns: {symbol: DataFrame}  (only successfully fetched symbols)
        """
        logger.info("Batch fetching %d symbols...", len(symbols))
        if not symbols:
            return {}

        try:
            combined: pd.DataFrame = self.client.get_dataframe(
                symbols,
                startDate=start_date,
                endDate=end_date,
                frequency=frequency,
                metric_name=metric_name,
                **kwargs
            )
        except Exception as e:
            logger.error(
                "Tiingo batch fetch failed entirely for %s symbols: %s. "
                "Falling back to per-symbol fetch.", len(symbols), e
            )
            # Fallback: use base class loop so partial results are still returned
            return super().fetch_multiple(
                symbols, start_date=start_date, end_date=end_date,
                frequency=frequency, **kwargs
            )

        # When passing a list, tiingo returns a DataFrame with symbol columns
        results = {}
        for sym in symbols:
            if sym not in combined.columns:
                logger.warning("Symbol %s not found in Tiingo batch result — excluding.", sym)
                continue
            normalized = self._normalize_ohlcv(combined[[sym]].rename(columns={sym: metric_name}))
            if normalized.empty:
                logger.warning("Symbol %s returned empty data — excluding.", sym)
                continue
            results[sym] = normalized

        succeeded = len(results)
        failed = len(symbols) - succeeded
        if failed > 0:
            logger.warning(
                "Tiingo batch fetch finished: %d/%d succeeded, %d excluded.",
                succeeded, len(symbols), failed,
            )
        else:
            logger.info("Tiingo batch fetch finished: all %d symbols succeeded.", succeeded)

        return results

    # ------------------------------------------------------------------
    #   News — curated financial news with ticker + tag filtering
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
        
        Raises:
            Exception: If Tiingo news API call fails.
        """
        logger.info("Fetching news (tickers=%s, tags=%s)...", tickers, tags)
        articles = self.client.get_news(
            tickers=tickers,
            tags=tags,
            sources=sources,
            startDate=start_date,
            endDate=end_date,
            limit=limit,
        )

        if not articles:
            logger.warning("No news articles found for tickers=%s.", tickers)

        return pd.DataFrame(articles)

    # # ------------------------------------------------------------------
    # # Fundamentals — daily (marketCap etc.) and quarterly statements
    # # ------------------------------------------------------------------
    # def fetch_fundamentals_daily(
    #     self,
    #     symbol: str,
    #     start_date: Optional[str] = None,
    #     end_date: Optional[str] = None,
    # ) -> pd.DataFrame:
    #     """
    #     Fetch daily-updated fundamental metrics (e.g. marketCap, EV).
    #     NOTE: Requires Tiingo paid plan.
    #     """
    #     logger.info("Fetching daily fundamentals for %s...", symbol)
    #     data = self.client.get_fundamentals_daily(
    #         symbol, startDate=start_date, endDate=end_date
    #     )
    #     return pd.DataFrame(data)

    # def fetch_fundamentals_statements(
    #     self,
    #     symbol: str,
    #     start_date: Optional[str] = None,
    #     end_date: Optional[str] = None,
    #     as_reported: bool = False,
    # ) -> pd.DataFrame:
    #     """
    #     Fetch quarterly financial statements (income, balance sheet, cash flow).
    #     NOTE: Requires Tiingo paid plan.

    #     Args:
    #         as_reported: If True, returns raw SEC-reported data (no corrections).
    #     """
    #     logger.info("Fetching quarterly statements for %s...", symbol)
    #     data = self.client.get_fundamentals_statements(
    #         symbol,
    #         startDate=start_date,
    #         endDate=end_date,
    #         asReported=as_reported,
    #     )
    #     return pd.DataFrame(data)

    # ------------------------------------------------------------------
    #   Crypto — historical OHLCV for crypto pairs
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

        Returns: {ticker: DataFrame}  (only successfully fetched tickers)
        
        Raises:
            Exception: If Tiingo crypto API call fails.
        """
        logger.info("Fetching crypto: %s...", tickers)
        if not tickers:
            return {}
            
        data = self.client.get_crypto_price_history(
            tickers=tickers,
            startDate=start_date,
            endDate=end_date,
            resampleFreq=resample_freq,
        )

        # Tiingo returns a list of dicts, each with 'ticker' and 'priceData'
        result = {}
        for item in data:
            ticker = item.get('ticker', '<unknown>')
            price_data = item.get('priceData', [])
            if not price_data:
                logger.warning("Crypto ticker '%s' has no priceData — skipping.", ticker)
                continue
            try:
                df = pd.DataFrame(price_data)
                normalized = self._normalize_ohlcv(df)
                if normalized.empty:
                    logger.warning("Crypto ticker '%s' normalized to empty — skipping.", ticker)
                    continue
                result[ticker] = normalized
            except Exception as e:
                logger.error("Failed to process crypto ticker '%s': %s — skipping.", ticker, e)

        return result

    def fetch_info(self, symbol: str) -> dict:
        """
        Fetch company profile via Tiingo.
        """
        logger.info("Fetching info for %s via Tiingo...", symbol)
        self._validate_inputs(symbol)
        try:
            return self.client.get_ticker_metadata(symbol)
        except Exception as e:
            logger.warning("Failed to fetch info for %s from Tiingo: %s", symbol, e)
            return {}

    def fetch_financials(self, symbol: str, statement: str = "income", period: str = "annual") -> pd.DataFrame:
        """
        Tiingo does not provide full standardized financial statements in the free tier
        (only basic daily fundamentals). Returning empty DataFrame.
        """
        logger.warning("Tiingo free tier does not support full %s statements. Returning empty.", statement)
        return pd.DataFrame()