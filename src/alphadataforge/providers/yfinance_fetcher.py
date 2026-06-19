import yfinance as yf
import pandas as pd
from typing import Optional, List, Dict
from ..core.base_fetcher import BaseDataFetcher


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
        """
        print(f"[YFinanceFetcher] Fetching price for {symbol} ({interval})...")
        df = yf.download(
            tickers=symbol,
            start=start_date,
            end=end_date,
            interval=interval,
            progress=False,
            **kwargs
        )
        return df

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

        Returns: {symbol: DataFrame}
        """
        print(f"[YFinanceFetcher] Batch downloading {len(symbols)} symbols...")
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
            return {symbols[0]: df}
        return {symbol: df[symbol] for symbol in symbols}

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
        """
        print(f"[YFinanceFetcher] Fetching news for {symbol}...")
        ticker = yf.Ticker(symbol)
        articles = ticker.news
        if not articles:
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
        print(f"[YFinanceFetcher] Fetching info for {symbol}...")
        return yf.Ticker(symbol).info

    def fetch_financials(
        self,
        symbol: str,
        statement: str = "income",
        quarterly: bool = False,
    ) -> pd.DataFrame:
        """
        Fetch financial statements for a ticker.

        Args:
            symbol:    Ticker symbol
            statement: "income" | "balance" | "cashflow"
            quarterly: If True, return quarterly data. Default is annual.

        Returns: DataFrame with financial line items as rows, periods as columns
        """
        print(f"[YFinanceFetcher] Fetching {statement} statement for {symbol} "
              f"({'quarterly' if quarterly else 'annual'})...")
        ticker = yf.Ticker(symbol)

        if statement == "income":
            return ticker.quarterly_income_stmt if quarterly else ticker.income_stmt
        elif statement == "balance":
            return ticker.quarterly_balance_sheet if quarterly else ticker.balance_sheet
        elif statement == "cashflow":
            return ticker.quarterly_cashflow if quarterly else ticker.cashflow
        else:
            raise ValueError(
                f"Unknown statement type: '{statement}'. "
                "Choose 'income', 'balance', or 'cashflow'."
            )

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
        print(f"[YFinanceFetcher] Fetching crypto: {symbols}...")
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
        print(f"[YFinanceFetcher] Fetching forex: {pairs}...")
        return self.fetch_multiple(pairs, start_date, end_date, interval, **kwargs)