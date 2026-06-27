import yfinance as yf
import pandas as pd
from typing import Optional, List, Dict
from ..core.base_fetcher import BaseDataFetcher
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class YFinanceFetcher(BaseDataFetcher):
    """
    Data fetcher for Yahoo Finance API using the yfinance library.
    Inherits from BaseDataFetcher.

    Supports: stock/ETF/crypto/forex price, news, and fundamentals.
    All data is free with no API key required.
    """

    # ------------------------------------------------------------------
    # Required by BaseDataFetcher — fetches PRICE for 1 symbol
    # ------------------------------------------------------------------
    def fetch_single(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        interval: str = "1d",
        **kwargs
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV price data for a single symbol.

        Args:
            symbol:     Ticker, e.g. "AAPL", "BTC-USD", "EURUSD=X", "^VIX"
            start_date: "YYYY-MM-DD" (inclusive)
            end_date:   "YYYY-MM-DD" (exclusive)
            interval:   "1m","2m","5m","15m","30m","60m","90m","1h",
                        "1d","5d","1wk","1mo","3mo"
                        Note: intraday intervals only available for last 60 days
            **kwargs:   Any extra yf.download() params (e.g. auto_adjust=False)
        
        Raises:
            ValueError: If symbol or date inputs are invalid.
            Exception: If yfinance download fails (network, invalid ticker, etc.)
        """
        logger.info("Fetching price for %s (%s)...", symbol, interval)
        self._validate_inputs(symbol, start_date, end_date)
        
        # Pop adjusted if present, since yf.download doesn't accept it
        kwargs.pop("adjusted", None)
        
        # Force auto_adjust=False to get raw Close and Adj Close separately
        # This allows our backfill_adjusted_columns to generate full Adj OHLC
        download_kwargs = {
            "auto_adjust": False,
            "multi_level_index": False
        }
        download_kwargs.update(kwargs)
        
        df = yf.download(
            tickers=symbol,
            start=start_date,
            end=end_date,
            interval=interval,
            progress=False,
            **download_kwargs
        )
        
        if df.empty:
            logger.warning("yfinance returned empty DataFrame for %s. Check if the ticker is valid.", symbol)

        return self._normalize_ohlcv(df)

    # ------------------------------------------------------------------
    # Fetch price for multiple symbols at once (batch download)
    # ------------------------------------------------------------------
    def fetch_multiple(
        self,
        symbols: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        interval: str = "1d",
        **kwargs
    ) -> Dict[str, pd.DataFrame]:
        """
        Batch fetch OHLCV price data for multiple symbols in a single API call.
        More efficient than calling fetch_single() in a loop.
        
        Symbols that return empty or all-NaN data are logged and excluded.

        Returns: {symbol: DataFrame}  (only successfully fetched symbols)
        """
        logger.info("Batch downloading %d symbols...", len(symbols))
        # Add basic validation for empty list
        if not symbols:
            return {}
            
        kwargs['group_by'] = 'ticker'
        
        df = yf.download(
            symbols,
            start=start_date,
            end=end_date,
            interval=interval,
            progress=False,
            **kwargs
        )
            
        # Single symbol: yfinance doesn't create a MultiIndex, return directly
        if len(symbols) == 1:
            normalized = self._normalize_ohlcv(df)
            if normalized.empty:
                logger.warning("Batch download returned no data for %s — excluding.", symbols[0])
                return {}
            return {symbols[0]: normalized}
        
        results = {}
        for symbol in symbols:
            if symbol not in df.columns:
                logger.warning("Symbol %s not found in batch result — excluding.", symbol)
                continue
            normalized = self._normalize_ohlcv(df[symbol])
            if normalized.empty:
                logger.warning("Symbol %s returned empty data — excluding.", symbol)
                continue
            results[symbol] = normalized
        
        succeeded = len(results)
        failed = len(symbols) - succeeded
        if failed > 0:
            logger.warning(
                "Batch fetch finished: %d/%d succeeded, %d excluded.",
                succeeded, len(symbols), failed,
            )
        else:
            logger.info("Batch fetch finished: all %d symbols succeeded.", succeeded)

        return results

    # ------------------------------------------------------------------
    # News — recent news articles for a given ticker
    # ------------------------------------------------------------------
    def fetch_news(
        self,
        symbol: str,
        count: int = 10,
    ) -> pd.DataFrame:
        """
        Fetch recent news articles for a given ticker from Yahoo Finance.

        Args:
            symbol: Ticker symbol, e.g. "AAPL"
            count:  Max number of articles to return

        Returns:
            DataFrame with columns: title, publisher, link, providerPublishTime, type
        
        Raises:
            Exception: If yfinance ticker lookup fails.
        """
        logger.info("Fetching news for %s...", symbol)
        self._validate_inputs(symbol)
        if not isinstance(count, int) or count <= 0:
            raise ValueError(f"count must be a positive integer, got: {count!r}")
        ticker = yf.Ticker(symbol)
        articles = ticker.news
        if not articles:
            logger.warning("No news articles found for %s.", symbol)
            return pd.DataFrame()
        # Extract the 'content' dictionary which contains title, pubDate, etc.
        valid_articles = [a['content'] for a in articles[:count] if 'content' in a]
        df = pd.DataFrame(valid_articles)
        
        # Convert pubDate to datetime
        if 'pubDate' in df.columns:
            df['pubDate'] = pd.to_datetime(df['pubDate'])
            
        return df

    # ------------------------------------------------------------------
    # Fundamentals — summary info, financials, balance sheet, cash flow
    # ------------------------------------------------------------------
    def fetch_info(self, symbol: str) -> dict:
        """
        Fetch ticker metadata and key fundamental metrics (free-tier).
        Includes: sector, industry, marketCap, trailingPE, forwardPE,
                  dividendYield, 52-week high/low, beta, etc.

        Returns: dict (use pd.Series(result) to convert if needed)
        """
        logger.info("Fetching info for %s...", symbol)
        self._validate_inputs(symbol)
        return yf.Ticker(symbol).info

    def fetch_financials(
        self,
        symbol: str,
        statement: str = "income",
        period: str = "annual",
    ) -> pd.DataFrame:
        """
        Fetch financial statements for a ticker.

        Args:
            symbol:    Ticker symbol
            statement: "income" | "balance" | "cashflow"
            period:    "annual" | "quarterly".

        Returns: Normalized DataFrame with Dates as rows and metrics as columns
        
        Raises:
            ValueError: If statement type is not recognized.
        """
        logger.info(
            "Fetching %s statement for %s (%s)...",
            statement, symbol, period,
        )
        self._validate_inputs(symbol)
        ticker = yf.Ticker(symbol)
        
        quarterly = (period.lower() == "quarterly")

        if statement == "income":
            df = ticker.quarterly_income_stmt if quarterly else ticker.income_stmt
        elif statement == "balance":
            df = ticker.quarterly_balance_sheet if quarterly else ticker.balance_sheet
        elif statement == "cashflow":
            df = ticker.quarterly_cashflow if quarterly else ticker.cashflow
        else:
            raise ValueError(
                f"Unknown statement type: '{statement}'. "
                "Choose 'income', 'balance', or 'cashflow'."
            )
            
        # yfinance returns dates as columns and metrics as rows. Transpose it.
        df = df.T
        
        # Normalize columns (Net_Income, Total_Revenue, etc.)
        return self._normalize_financials(df)

    # ------------------------------------------------------------------
    # Crypto & Forex — yfinance supports these natively, no extra setup
    # ------------------------------------------------------------------
    def fetch_crypto(
        self,
        symbols: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        interval: str = "1d",
        **kwargs
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical OHLCV data for crypto pairs.
        Uses the same yfinance engine — just pass crypto symbols.

        Args:
            symbols: List of crypto pairs, e.g. ["BTC-USD", "ETH-USD", "SOL-USD"]

        Returns: {symbol: DataFrame}
        """
        logger.info("Fetching crypto: %s...", symbols)
        return self.fetch_multiple(symbols, start_date, end_date, interval, **kwargs)

    def fetch_forex(
        self,
        pairs: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        interval: str = "1d",
        **kwargs
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch historical FX rate data.
        Yahoo Finance forex symbol format: "EURUSD=X", "GBPUSD=X", "JPYUSD=X"

        Args:
            pairs: List of forex pair symbols, e.g. ["EURUSD=X", "GBPUSD=X"]

        Returns: {symbol: DataFrame}
        """
        logger.info("Fetching forex: %s...", pairs)
        return self.fetch_multiple(pairs, start_date, end_date, interval, **kwargs)