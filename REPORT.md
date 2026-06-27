# AlphaDataForge Review Report

Below is a comprehensive review of the `alphadataforge` codebase, focusing on architecture, data pipeline consistency, and specific bugs or edge cases (รายละเอียดย่อยๆ).

## 1. Data Pipeline Consistency (Column Issues)
Currently, if a user fetches data from multiple providers and tries to compare or combine them, they will encounter schema mismatches and missing column errors.
* **Strict Schema Enforcement:** The `_normalize_ohlcv` method renames common columns to standard names (`Open`, `High`, etc.), but it **does not drop provider-specific extra columns**. For example, Tiingo returns `divCash` and `splitFactor`, while YFinance might not. If a user tries to concatenate YFinance and Tiingo DataFrames, they will have disjointed schemas.
* **Missing `Adj Close`:** If a provider does not support `Adj Close` natively (or if a user requests unadjusted data), the resulting DataFrame will simply lack the `Adj Close` column. The pipeline should guarantee the presence of a strict set of core columns: `['Open', 'High', 'Low', 'Close', 'Volume', 'Adj Close']`. If `Adj Close` is unavailable, it should be explicitly set to `NaN` (or fall back to `Close`) so the schema is identical.
* **Case Sensitivity:** `_normalize_financials` standardizes many columns, but relies on a predefined map. Any new financial metric introduced by an API change will pass through with its raw, provider-specific name, leading to inconsistency across providers.

## 2. Architecture Feedback
The use of the Facade (`Price`, `Fundamentals`) and Strategy (`BaseDataFetcher` subclasses) patterns is excellent and makes the library easy to use. However, there are significant architectural improvements to consider:

* **Caching Mechanism (Global State Mutation):**
  In `base_fetcher.py`, `requests_cache.install_cache` is called globally. This monkey-patches the `requests` library for the **entire Python process**. If a user imports `alphadataforge` into a larger trading system that also uses `requests` for internal microservices or other APIs, those requests will unintentionally be cached in `alphadataforge_cache`.
  * *Suggestion:* Use an explicit `requests_cache.CachedSession()` and pass it to the fetchers instead of installing it globally.
* **Concurrency vs. Rate Limiting (Thread Safety):**
  `BaseDataFetcher.fetch_multiple` uses a `ThreadPoolExecutor` to fetch symbols concurrently. However, `AlphaVantageFetcher` enforces its 1 request/second limit using `time.sleep(1.2)` *inside* the fetch method. Because threads run concurrently, 5 threads will all sleep for 1.2 seconds simultaneously, and then all 5 will fire requests at the exact same moment, triggering Alpha Vantage's rate limit immediately.
  * *Suggestion:* Implement a thread-safe token bucket, a central Semaphore, or migrate to asynchronous fetching using `asyncio` and `aiohttp`.
* **Retry Logic on Client Errors:**
  The `@retry` decorator on `_make_http_request` retries on `RequestException`. Because `HTTPError` is a subclass of `RequestException`, this means it will blindly retry **HTTP 401 (Unauthorized)**, **HTTP 403 (Forbidden)**, and **HTTP 404 (Not Found)** errors up to 3 times with exponential backoff. This wastes time and API calls for deterministic errors. It should only retry `HTTP 429` (Rate Limit) and `5xx` (Server Errors).

## 3. Edge Cases and Minor Bugs (รายละเอียดย่อยๆ)

1. **YFinance MultiIndex Bug:**
   In `_normalize_ohlcv`, there is a check:
   ```python
   if isinstance(df.columns, pd.MultiIndex):
       df.columns = df.columns.get_level_values(0)
   ```
   If YFinance changes its output format or if batch fetching groups by `Ticker` (putting `Ticker` at level 0 and `Price` at level 1), `get_level_values(0)` will accidentally rename all columns to the Ticker symbol (e.g., `'AAPL', 'AAPL', 'AAPL'`) instead of `Open, High, Low`, completely breaking the data pipeline.
2. **Datetime Index parsing failure:**
   In `_normalize_financials`, the code converts the index to a datetime object inside a generic `try/except: pass` block. If parsing fails, the index silently remains strings (or integers). This will silently break time-series alignments (e.g., `df_income.join(df_balance)`) downstream. It should force datetime conversion with `errors='coerce'` like in `_normalize_ohlcv` and drop `NaT` values.
3. **AlphaVantage `fetch_multiple` exhaustion:**
   The free tier for AlphaVantage is strictly 25 requests per day. Since `fetch_multiple` runs concurrently and fetches splits, dividends, and prices (3 calls per symbol if `adjusted=True`), batch fetching just 10 symbols will consume 30 credits and silently fail or exhaust the API key quota without warning the user before execution.
4. **FMP Fundamentals URL Construction:**
   Depending on the exact value of `Endpoints.FMP.PATHS['profile']`, passing the symbol in the `params={'symbol': symbol}` dictionary might not work if FMP's v3 API expects the symbol in the path (e.g., `/api/v3/profile/AAPL`). If it strictly requires a path parameter, the current request will return a 404 or a 400 error.
