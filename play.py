from alphadataforge.providers.yfinance_fetcher import YFinanceFetcher
from alphadataforge.data.price import Price
import pandas as pd
import time
import requests_cache

def play_with_fetchers():
    print("=" * 60)
    print("start yfinance_fetcher (and Facade API)")
    print("=" * 60)

    # 1. Test fetching price data using Price Facade
    print("\n[1] test fetching AAPL through Price Facade (Level 1)")
    df_normal = Price.get("AAPL", start_date="2023-01-01", end_date="2023-01-10")
    print(df_normal.head())

    print("\n[2] test fetching multiple stocks through Price Facade (Level 1 Batch)")
    data_dict = Price.get(["AAPL", "GOOGL"], start_date="2023-01-01", end_date="2023-01-05")
    for sym, df in data_dict.items():
        print(f"--- {sym} ---")
        print(df.head(2))

    print("\n[3] test fetching MSFT through Price Facade with params (Level 3)")
    df_advanced = Price.get("MSFT", provider="yfinance", provider_params={"interval": "1wk", "period": "1mo", "auto_adjust": False})
    print(df_advanced.head())

    # Create an instance of YFinanceFetcher to test other features
    yf_fetcher = YFinanceFetcher()

    # 2. Test fetching price data using fetch_single and fetch_multiple
    print("\n[3] test fetch_single for AAPL (1d)")
    df_single = yf_fetcher.fetch_single("AAPL", start_date="2023-01-01", end_date="2023-01-05")
    print(df_single)

    print("\n[4] test fetch_single with interval=1h and kwargs (auto_adjust=False)")
    df_intraday = yf_fetcher.fetch_single("MSFT", interval="1h", period="5d", auto_adjust=False)
    print(df_intraday.head())

    print("\n[5] test fetch_multiple stocks (AAPL, GOOGL)")
    data_dict = yf_fetcher.fetch_multiple(["AAPL", "GOOGL"], start_date="2023-01-01", end_date="2023-01-05")
    for symbol, df in data_dict.items():
        print(f"\n--- {symbol} ---")
        print(df.head())

    # 3. Test fetching news (News)
    print("\n[6] test fetch_news (fetch news of AAPL 2 latest news)")
    df_news = yf_fetcher.fetch_news("AAPL", count=2)
    if not df_news.empty:
        print(df_news.head())
    else:
        print(" No news found or failed to fetch news")

    # 4. Test fetching fundamental data (Fundamentals / Info)
    print("\n[7] test fetch_info (fetch basic info of AAPL)")
    info = yf_fetcher.fetch_info("AAPL")
    # Print only some important keys because info of yfinance has many keys
    keys_to_show = ['sector', 'industry', 'marketCap', 'trailingPE', 'dividendYield']
    for k in keys_to_show:
        print(f"  - {k}: {info.get(k, 'N/A')}")

    print("\n[8] test fetch_financials (fetch income statement of AAPL)")
    df_income = yf_fetcher.fetch_financials("AAPL", statement="income")
    # yfinance income statement has years as columns
    print(df_income.iloc[:5, :3]) # show first 5 rows and first 3 years

    # 5. Test fetching crypto and Forex
    print("\n[9] test fetch_crypto (fetch Bitcoin price)")
    crypto_data = yf_fetcher.fetch_crypto(["BTC-USD"], start_date="2023-01-01", end_date="2023-01-05")
    print(crypto_data["BTC-USD"].head())

    print("\n[10] test fetch_forex (fetch EUR/USD price)")
    forex_data = yf_fetcher.fetch_forex(["EURUSD=X"], start_date="2023-01-01", end_date="2023-01-05")
    print(forex_data["EURUSD=X"].head())

    print("\n" + "=" * 60)
    print("Start testing TiingoFetcher")
    print("=" * 60)

    from alphadataforge.config.settings import config
    if config.TIINGO_API_KEY:
        from alphadataforge.providers.tiingo_fetcher import TiingoFetcher
        tiingo = TiingoFetcher()
        
        print("\n[11] test Tiingo fetch_single (AAPL)")
        df_tiingo = tiingo.fetch_single("AAPL", start_date="2023-01-01", end_date="2023-01-05")
        print(df_tiingo.head())

        print("\n[12] test Tiingo fetch_news (AAPL)")
        try:
            df_tiingo_news = tiingo.fetch_news(tickers=["AAPL"], limit=2)
            if not df_tiingo_news.empty:
                print(df_tiingo_news[['title', 'source']].head())
        except Exception as e:
            print(f"  No news found (Limit or API Key): {e}")
            
        print("\n[13] test Tiingo fetch_crypto (BTCUSD)")
        try:
            df_tiingo_crypto = tiingo.fetch_crypto(["BTCUSD"], start_date="2023-01-01", end_date="2023-01-05")
            print(df_tiingo_crypto["btcusd"].head())
        except Exception as e:
            print(f"  Can't fetch crypto: {e}")
    else:
        print("\nSkip Tiingo test because TIINGO_API_KEY not found")

    print("\n" + "=" * 60)
    print("Test completed")
    print("=" * 60)

def test_performance():
    print("\n" + "=" * 60)
    print("Performance Test: Caching & Asynchronous Fetching")
    print("=" * 60)
    
    # We clear the cache to ensure the first run hits the network
    print("\n[0] Clearing cache to simulate first run...")
    requests_cache.clear()
    
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "NFLX", "JPM", "V"]
    yf_fetcher = YFinanceFetcher()
    
    print(f"\n[1] Run 1: Network Fetch + ThreadPool (Downloading {len(symbols)} symbols...)")
    start_time = time.time()
    _ = yf_fetcher.fetch_multiple(symbols, start_date="2023-01-01", end_date="2023-06-01")
    run1_time = time.time() - start_time
    print(f"  -> Finished in: {run1_time:.2f} seconds")
    
    print(f"\n[2] Run 2: Cached Fetch (Downloading SAME {len(symbols)} symbols...)")
    start_time = time.time()
    _ = yf_fetcher.fetch_multiple(symbols, start_date="2023-01-01", end_date="2023-06-01")
    run2_time = time.time() - start_time
    print(f"  -> Finished in: {run2_time:.2f} seconds")
    
    print("\n[3] Conclusion:")
    if run1_time > 0 and run2_time > 0:
        print(f"  - Caching made it {run1_time / run2_time:.1f}x faster!")
    print(f"  - Async fetching (ThreadPool) allowed {len(symbols)} network requests in just {run1_time:.2f}s!")

if __name__ == "__main__":
    # play_with_fetchers()
    test_performance()