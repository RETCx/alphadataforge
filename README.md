# AlphaDataForge

AlphaDataForge is a modular data fetching pipeline for quantitative trading and financial analysis. It provides a unified interface to fetch **Price** and **Fundamental** data across multiple providers with automatic caching, rate limit protection, and standardized output formats.

---

## Quick Start

```bash
git clone https://github.com/RETCx/alphadataforge.git
cd alphadataforge
pip install -e .
```

Copy the environment template and add your API keys:
```bash
cp .env.example .env
```

```
# .env
TIINGO_API_KEY="your_tiingo_key"
ALPHAVANTAGE_API_KEY="your_alphavantage_key"
FMP_API_KEY="your_fmp_key"
```

*YFinance does not require an API key.*

---

## Architecture

```
alphadataforge/
├── data/
│   ├── price.py          ← Unified Price Facade (Price.get())
│   └── fundamental.py    ← Unified Fundamental Facade (Fundamentals.get_info(), etc.)
│
├── providers/
│   ├── yfinance_fetcher.py
│   ├── alphavantage_fetcher.py
│   ├── tiingo_fetcher.py
│   └── fmp_fetcher.py
│
└── core/
    ├── base_fetcher.py   ← BaseDataFetcher (caching, retry, normalization)
    └── exceptions.py     ← AlphaDataForgeError, RateLimitExceededError, etc.
```

**Built-in features (all providers)**:
- **SQLite Caching** (24h TTL) — auto-stored in OS temp folder, no setup needed.
- **Auto-Retry** with exponential backoff for network errors (via `tenacity`).
- **Normalized Output** — all prices return `[Open, High, Low, Close, Volume, Adj Close]` with a `DatetimeIndex`. All financials return standardized columns (`Net_Income`, `Total_Revenue`, etc.).

---

## Module 1: Price

**Entry point:** `from alphadataforge.data.price import Price`

```python
from alphadataforge.data.price import Price

# Single symbol
df = Price.get("AAPL", start_date="2023-01-01", end_date="2023-12-31")

# Multiple symbols (returns dict)
data = Price.get(["AAPL", "GOOGL", "MSFT"], provider="yfinance")

# Specific provider
df = Price.get("TSLA", provider="tiingo", start_date="2022-01-01")
```

### `Price.get()` — All Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbol` | `str` or `List[str]` | *required* | Ticker(s) e.g. `"AAPL"` or `["AAPL", "MSFT"]` |
| `provider` | `str` | `"yfinance"` | `"yfinance"`, `"alphavantage"`, `"tiingo"`, `"fmp"`, `"hybrid_av_tiingo"` |
| `start_date` | `str` | `None` | `"YYYY-MM-DD"` |
| `end_date` | `str` | `None` | `"YYYY-MM-DD"` |
| `**provider_params` | `dict` | `{}` | Extra params passed to the underlying provider (see per-provider sections below) |

**Returns:** `pd.DataFrame` (single symbol) or `Dict[str, pd.DataFrame]` (multiple symbols)

**Output Columns:**

| Column | Type | Description |
|---|---|---|
| `Open` | float | Opening price |
| `High` | float | Daily high |
| `Low` | float | Daily low |
| `Close` | float | Closing price |
| `Volume` | float | Trading volume |
| `Adj Open` | float | Adjusted opening price (if `adjusted=True`) |
| `Adj High` | float | Adjusted daily high (if `adjusted=True`) |
| `Adj Low` | float | Adjusted daily low (if `adjusted=True`) |
| `Adj Close` | float | Dividend & split adjusted close (if available or `adjusted=True`) |
| `Adj Volume` | float | Split-adjusted volume (if `adjusted=True`) |

> **Note on Adjusted Prices:** If `adjusted=True` is passed (or if the provider returns it natively), AlphaDataForge guarantees the presence of full Adjusted OHLC columns (`Adj Open`, `Adj High`, `Adj Low`, `Adj Close`). For providers like YFinance that only natively return `Adj Close`, our pipeline automatically backfills the remaining adjusted columns using the ratio of `Adj Close` / `Close`.

### Hybrid Provider (`hybrid_av_tiingo`)
AlphaDataForge offers a special `hybrid_av_tiingo` provider for optimal data quality and API usage:
- **Raw Prices:** Fetched from Alpha Vantage (deepest historical data, 20+ years).
- **Dividends & Splits:** Fetched from Tiingo (highly accurate, saves Alpha Vantage premium limits).
- **Processing:** Fully adjusted prices are calculated locally via our `finance_math` engine.

### Cross-Provider Adjusted Price Comparison
To ensure data consistency across all platforms, we tested the fully adjusted prices for `AAPL` on `2026-05-05` across all available providers and the hybrid engine. The results perfectly align:

**Adjusted Close:**
- `yfinance`: 283.9184
- `tiingo`: 283.9181
- `fmp`: 283.9200
- `alphavantage`: 283.9184
- `hybrid_av_tiingo`: 283.9184

**Adjusted Open:**
- `yfinance`: 276.6751
- `tiingo`: 276.6698
- `fmp`: 276.6800
- `alphavantage`: 276.6701
- `hybrid_av_tiingo`: 276.6701

### Multi-Provider Consensus & Comparison

AlphaDataForge provides built-in tools to fetch from multiple providers concurrently and either compare them side-by-side or calculate a consensus (mean/median) to automatically filter out bad data.

```python
# 1. Compare across all providers (Returns a MultiIndex DataFrame)
multi_df = Price.compare("AAPL", start_date="2023-01-01", provider_params={"adjusted": True})

# Access specific provider
yfinance_close = multi_df["yfinance"]["Close"]

# 2. Consensus Price (Calculates the median across all providers)
consensus_df = Price.consensus("AAPL", start_date="2023-01-01", method="median")
print(consensus_df.head())
```

#### Integrating Custom External Data (`custom_data`)
You can inject your own external DataFrames (from a CSV, database, etc.) directly into the Consensus engine! 
*Note: You must normalize your DataFrame's columns to the AlphaDataForge standard (`Open`, `High`, `Low`, `Close`, `Volume`) before passing it in.*

```python
import pandas as pd

# Load and Normalize your data
df_custom = pd.read_csv('my_database.csv')
df_custom = df_custom.rename(columns={'Price': 'Close', 'Vol.': 'Volume'})
df_custom['Date'] = pd.to_datetime(df_custom['Date'])
df_custom.set_index('Date', inplace=True)

# Inject custom data into compare or consensus!
consensus_df = Price.consensus(
    "AAPL", 
    start_date="2026-06-01", 
    providers=["yfinance", "alphavantage"], 
    custom_data={"my_local_db": df_custom},
    method="median"
)
```

---

## Module 2: Fundamentals

**Entry point:** `from alphadataforge.data.fundamental import Fundamentals`

### `Fundamentals.get_info()` — Company Profile

```python
info = Fundamentals.get_info("AAPL", provider="yfinance")
print(info["sector"], info["marketCap"])
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbol` | `str` | *required* | Ticker e.g. `"AAPL"` |
| `provider` | `str` | `"yfinance"` | `"yfinance"`, `"alphavantage"`, `"fmp"` |

**Returns:** `dict`

---

### `Fundamentals.get_financials()` — Financial Statements

```python
df = Fundamentals.get_financials("AAPL", statement="income", period="annual", provider="yfinance")
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `symbol` | `str` | *required* | Ticker e.g. `"AAPL"` |
| `statement` | `str` | `"income"` | See table below for per-provider support |
| `period` | `str` | `"annual"` | `"annual"` or `"quarterly"` |
| `provider` | `str` | `"yfinance"` | `"yfinance"`, `"alphavantage"`, `"fmp"` |

**Returns:** `pd.DataFrame` with `DatetimeIndex` and normalized columns

**Normalized Columns (Standardized Across All Providers):**

| Column | Description |
|---|---|
| `Net_Income` | Net profit/loss after tax |
| `Total_Revenue` | Total revenue |
| `Operating_Income` | EBIT / Operating profit |
| `Free_Cash_Flow` | Free cash flow |
| `Total_Assets` | Total assets |
| `Total_Liabilities` | Total liabilities |
| `Total_Equity` | Shareholders' equity |
| `Shares_Outstanding` | Basic shares outstanding |

---

### `Fundamentals.get_earnings_calendar()` — Earnings Calendar

```python
df = Fundamentals.get_earnings_calendar(horizon="3month", symbol="AAPL", provider="alphavantage")
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `horizon` | `str` | `"3month"` | `"3month"`, `"6month"`, or `"12month"` |
| `symbol` | `str` | `None` | Filter for specific ticker (optional) |
| `provider` | `str` | `"alphavantage"` | Only `"alphavantage"` supported |

**Returns:** `pd.DataFrame` with columns: `symbol`, `name`, `reportDate`, `fiscalDateEnding`, `estimate`, `currency`

---

## Provider Reference

---

### Provider 1: YFinance (`provider="yfinance"`)

| | |
|---|---|
| **API Key** | No Not required |
| **Rate Limit** | Practically unlimited |
| **Best For** | Development, batch fetching, comprehensive fundamentals |

#### Price

```python
from alphadataforge.data.price import Price

# Basic fetch
df = Price.get("AAPL", start_date="2023-01-01")

# With intraday interval (available last 60 days only)
df = Price.get("AAPL", provider_params={"interval": "1h"})

# Crypto & Forex (use yfinance ticker format)
df = Price.get("BTC-USD")           # Bitcoin
df = Price.get("ETH-USD")           # Ethereum
df = Price.get("EURUSD=X")          # EUR/USD Forex
df = Price.get("^VIX")              # VIX Index
```

**Extra `provider_params` for YFinance Price:**

| Param | Type | Default | Description |
|---|---|---|---|
| `interval` | `str` | `"1d"` | `"1m"`, `"5m"`, `"15m"`, `"30m"`, `"1h"`, `"1d"`, `"1wk"`, `"1mo"`, `"3mo"`. Intraday (< 1d) only for last 60 days. |
| `auto_adjust` | `bool` | `False` | Pass `True` if you want yfinance to overwrite the Open/High/Low columns with adjusted prices. |

**Under the hood (YFinance):**
- **API Calls:** 1 call per fetch.
- **Adjusted Prices:** Natively returns `Adj Close`. If you want `Adj Open/High/Low`, you must pass `provider_params={"auto_adjust": True}`.

#### Fundamentals (YFinance)

| Method | `statement=` value | Notes |
|---|---|---|
| `get_info()` | — | Returns 80+ fields: `sector`, `industry`, `marketCap`, `trailingPE`, `forwardPE`, `dividendYield`, `beta`, `52WeekHigh`, `52WeekLow`, etc. |
| `get_financials()` | `"income"` | Up to 4 years annual / 8 quarters quarterly |
| `get_financials()` | `"balance"` | Up to 4 years annual / 8 quarters quarterly |
| `get_financials()` | `"cashflow"` | Up to 4 years annual / 8 quarters quarterly |

```python
from alphadataforge.data.fundamental import Fundamentals

# Company overview
info = Fundamentals.get_info("AAPL", provider="yfinance")
print(info["sector"])        # "Technology"
print(info["marketCap"])     # 3_000_000_000_000
print(info["trailingPE"])    # 33.2

# Financial Statements
df_income   = Fundamentals.get_financials("AAPL", statement="income",   period="annual",    provider="yfinance")
df_balance  = Fundamentals.get_financials("AAPL", statement="balance",  period="quarterly", provider="yfinance")
df_cashflow = Fundamentals.get_financials("AAPL", statement="cashflow", period="annual",    provider="yfinance")

# Merge all three by date index
df_all = df_income.join(df_balance, how="outer", rsuffix="_bal").join(df_cashflow, how="outer", rsuffix="_cf")
```

---

### Provider 2: Alpha Vantage (`provider="alphavantage"`)

| | |
|---|---|
| **API Key** | Yes Required (`ALPHAVANTAGE_API_KEY`) |
| **Rate Limit (Free)** | 25 requests / day, 1 request / second |
| **Auto-Sleep** | Yes Built-in 1.2s delay between each request (no manual sleep needed) |
| **Data Depth** | Up to 20 years of price history, full SEC-normalized financials |
| **Best For** | Deep historical financial statements, Earnings Calendar |

> Warning **25 requests/day** is the hard ceiling on the free plan. Each call to `get_financials()` or `get_info()` costs 1 request. Plan accordingly.

#### Price

```python
from alphadataforge.data.price import Price

# Basic EOD price (compact = last 100 days)
df = Price.get("AAPL", provider="alphavantage")

# Full history (~20 years)
df = Price.get("AAPL", provider="alphavantage", provider_params={"outputsize": "full"})

# Adjusted prices (costs 3 API calls: Price + Dividends + Splits)
df = Price.get("AAPL", provider="alphavantage", provider_params={"adjusted": True, "outputsize": "full"})
```

**Extra `provider_params` for AlphaVantage Price:**

| Param | Type | Default | Description |
|---|---|---|---|
| `outputsize` | `str` | `"compact"` | `"compact"` (last 100 days) or `"full"` (full ~20yr history). |
| `adjusted` | `bool` | `False` | Fetches dividends/splits and back-adjusts all OHLCV. |

**Under the hood (Alpha Vantage):**
- **API Calls (`adjusted=False`):** 1 call (`TIME_SERIES_DAILY`).
- **API Calls (`adjusted=True`):** **3 calls** (`TIME_SERIES_DAILY`, `DIVIDENDS`, `SPLITS`).
- **Adjusted Prices:** Since Alpha Vantage made their adjusted endpoint premium, we built a custom math engine. When `adjusted=True`, we fetch raw prices, dividends, and splits on the free endpoints and calculate `Adj Open`, `Adj High`, `Adj Low`, `Adj Close`, `Adj Volume` entirely locally. You get premium-grade adjusted data for free!

#### Fundamentals (AlphaVantage)

| Method | `statement=` value | Notes |
|---|---|---|
| `get_info()` | — | Maps to `OVERVIEW` endpoint. Returns company ratios, P/E, EPS, dividends, 52-week data etc. |
| `get_financials()` | `"income"` | SEC-normalized annual or quarterly income statement |
| `get_financials()` | `"balance"` | SEC-normalized annual or quarterly balance sheet |
| `get_financials()` | `"cashflow"` | SEC-normalized annual or quarterly cash flow |
| `get_financials()` | `"shares_outstanding"` | Historical quarterly shares (basic + diluted). Note: `period` param ignored — always quarterly. |
| `get_financials()` | `"earnings"` | Annual/quarterly EPS history with analyst estimates and surprise % |
| `get_earnings_calendar()` | — | Upcoming earnings dates for next 3/6/12 months |

```python
from alphadataforge.data.fundamental import Fundamentals

# Company overview (maps to OVERVIEW endpoint)
info = Fundamentals.get_info("IBM", provider="alphavantage")

# Income Statement (annual, goes back 5+ years)
df_income = Fundamentals.get_financials("IBM", statement="income", period="annual", provider="alphavantage")

# Balance Sheet (quarterly)
df_balance = Fundamentals.get_financials("IBM", statement="balance", period="quarterly", provider="alphavantage")

# Cash Flow
df_cf = Fundamentals.get_financials("IBM", statement="cashflow", period="annual", provider="alphavantage")

# Historical Shares Outstanding (quarterly, to track buybacks/dilution)
df_shares = Fundamentals.get_financials("IBM", statement="shares_outstanding", provider="alphavantage")
# Returns: Shares_Outstanding (basic), shares_outstanding_diluted

# Earnings History with analyst surprise
df_earnings = Fundamentals.get_financials("IBM", statement="earnings", period="quarterly", provider="alphavantage")
# Returns: reportedEPS, estimatedEPS, surprise, surprisePercentage, reportTime

# Earnings Calendar (upcoming earnings dates)
df_cal = Fundamentals.get_earnings_calendar(horizon="3month", provider="alphavantage")             # all upcoming
df_cal = Fundamentals.get_earnings_calendar(horizon="12month", symbol="AAPL", provider="alphavantage")  # specific ticker
```

---

### Provider 3: Tiingo (`provider="tiingo"`)

| | |
|---|---|
| **API Key** | Yes Required (`TIINGO_API_KEY`) |
| **Rate Limit (Free)** | 500 requests / hour (very generous) |
| **Best For** | Clean institutional-grade EOD prices, News API with tag filtering |

#### Price

```python
from alphadataforge.data.price import Price

# Basic EOD price
df = Price.get("AAPL", provider="tiingo", start_date="2020-01-01")

# With weekly frequency
df = Price.get("AAPL", provider="tiingo", provider_params={"frequency": "weekly"})
```

**Extra `provider_params` for Tiingo Price:**

| Param | Type | Default | Description |
|---|---|---|---|
| `frequency` | `str` | `"daily"` | `"daily"`, `"weekly"`, `"monthly"`, `"annually"`. Intraday (`"1min"`, `"5min"`, etc.) requires paid plan. |

**Under the hood (Tiingo):**
- **API Calls:** 1 call per fetch.
- **Adjusted Prices:** The Tiingo API natively sends a full suite of adjusted prices. The resulting DataFrame will always contain `Adj Open`, `Adj High`, `Adj Low`, `Adj Close`, and `Adj Volume`. No manual calculation needed.

#### Crypto (Tiingo)

```python
# Tiingo crypto uses different ticker format (no dash): BTCUSD, ETHUSD
from alphadataforge.providers.tiingo_fetcher import TiingoFetcher

tiingo = TiingoFetcher()
crypto_data = tiingo.fetch_crypto(
    tickers=["BTCUSD", "ETHUSD"],
    start_date="2023-01-01",
    resample_freq="1Day"   # "1Day", "1Hour", "30Min"
)
```

#### News (Tiingo)

Tiingo has the most powerful news filtering of all providers.

```python
from alphadataforge.providers.tiingo_fetcher import TiingoFetcher

tiingo = TiingoFetcher()
news_df = tiingo.fetch_news(
    tickers=["AAPL", "MSFT"],         # Filter by ticker (optional)
    tags=["Earnings"],                 # Filter by tag (optional)
    sources=["reuters.com"],           # Filter by source domain (optional)
    start_date="2024-01-01",
    end_date="2024-06-01",
    limit=50
)
# Returns columns: publishedDate, title, description, url, tickers, tags
```

#### Fundamentals (Tiingo)

| Method | Support | Notes |
|---|---|---|
| `get_info()` | Yes Supported | Returns basic ticker metadata (name, description, exchange, startDate) |
| `get_financials()` | No Not Supported | Returns empty DataFrame. Full financial statements require Tiingo's paid `fundamentals` plan. |

---

### Provider 4: FMP — Financial Modeling Prep (`provider="fmp"`)

| | |
|---|---|
| **API Key** | Yes Required (`FMP_API_KEY`) |
| **Rate Limit (Free)** | 250 requests / day |
| **Best For** | EOD Price data (free), Deep fundamental history (paid) |

> Warning **Important:** Financial statements (`get_financials`) are **locked behind FMP's paid plan** and will return a `403 Forbidden` error with a free API key. `get_info()` and `Price.get()` work on the free tier.

#### Price

```python
from alphadataforge.data.price import Price

# Basic EOD price
df = Price.get("AAPL", provider="fmp", start_date="2023-01-01")

# Dividend & split adjusted
df = Price.get("AAPL", provider="fmp", provider_params={"adjusted": True})
```

**Extra `provider_params` for FMP Price:**

| Param | Type | Default | Description |
|---|---|---|---|
| `adjusted` | `bool` | `False` | `False` = raw non-split-adjusted prices. `True` = fully dividend & split adjusted. |

**Under the hood (FMP):**
- **API Calls:** 1 call per fetch (regardless of `adjusted` flag).
- **Adjusted Prices:** If `adjusted=True`, we hit FMP's `dividend-adjusted` endpoint, which natively returns adjusted values for Open, High, Low, and Close. The resulting DataFrame will contain `Adj Open`, `Adj High`, `Adj Low`, and `Adj Close`.

#### Fundamentals (FMP)

| Method | `statement=` value | Free Tier | Notes |
|---|---|---|---|
| `get_info()` | — | ✅ Free | Returns company profile: `sector`, `industry`, `mktCap`, `beta`, `description`, `ceo`, etc. |
| `get_financials()` | `"income"` | ✅ Free | 5 periods returned on free tier |
| `get_financials()` | `"balance"` | ✅ Free | 5 periods returned on free tier |
| `get_financials()` | `"cashflow"` | ✅ Free | 5 periods returned on free tier |
| `get_financials()` | `"shares_float"` | ✅ Free | Returns `freeFloat`, `floatShares`, and `outstandingShares` snapshot |

```python
from alphadataforge.data.fundamental import Fundamentals

# Company profile (works on free tier)
info = Fundamentals.get_info("AAPL", provider="fmp")
print(info["sector"])       # "Technology"
print(info["ceo"])          # "Timothy D. Cook"

# Financial statements (PAID ONLY — will raise error on free key)
# df = Fundamentals.get_financials("AAPL", statement="income", provider="fmp")
```

---

## Provider Comparison Table

### Price

| Feature | YFinance | AlphaVantage | Tiingo | FMP |
|---|---|---|---|---|
| API Key Required | No | Yes | Yes | Yes |
| Rate Limit | Unlimited | 25/day | 500/hr | 250/day |
| Adjusted Prices | Yes | Yes (costs 3 calls) | Yes | Yes |
| Intraday | Yes (last 60d) | No | Paid only | No |
| Crypto | Yes (`BTC-USD`) | No | Yes (`BTCUSD`) | No |
| Forex | Yes (`EURUSD=X`) | No | No | No |
| Historical Depth | ~20yr | ~20yr | ~30yr | ~30yr |
| Batch Fetching | Yes (1 API call) | Warning (1 call/symbol) | Yes (1 API call) | Warning (1 call/symbol) |

### Fundamentals

| Feature | YFinance | AlphaVantage | Tiingo | FMP |
|---|---|---|---|---|
| `get_info()` | Yes Rich (80+ fields) | Yes Good | Yes Basic | Yes Good |
| `statement="income"` | Yes (4yr) | Yes (5yr+) | No | No Paid |
| `statement="balance"` | Yes (4yr) | Yes (5yr+) | No | No Paid |
| `statement="cashflow"` | Yes (4yr) | Yes (5yr+) | No | No Paid |
| `statement="shares_outstanding"` | Warning (in balance sheet) | Yes Historical | No | No Paid |
| `statement="earnings"` | Warning (basic) | Yes + Analyst Est. | No | No Paid |
| `get_earnings_calendar()` | No | Yes | No | No |
| News | Yes | No | Yes (Best) | No |

---

## Roadmap

- [x] SQLite Caching (24h TTL, OS temp folder)
- [x] Concurrent batch fetching (ThreadPoolExecutor)
- [x] Auto Rate Limit protection (AlphaVantage)
- [x] Custom Exception hierarchy
- [x] Fundamentals Facade (Income, Balance, Cashflow, Earnings, Shares Outstanding)
- [ ] Data Quality Checks (anomaly detection, missing data handling)
- [ ] Technical Indicators Module (RSI, MACD, Bollinger Bands)

---

## Testing

This project utilizes `pytest-vcr` and `unittest.mock` to ensure robust and comprehensive test coverage without consuming actual API rate limits. 

### VCR Cassettes (`pytest-vcr`)
VCR records real HTTP interactions and saves them as `.yaml` files (cassettes) within the `tests/cassettes/` directory.

- **Rate Limit Protection**: By replaying recorded responses, our test suite can execute reliably in CI/CD environments (e.g., GitHub Actions) without exhausting API provider quotas.
- **Security**: Sensitive query parameters, such as API keys, are automatically sanitized and replaced with placeholder strings (`DUMMY`) before being persisted to the cassettes.
- **Version Control**: The `.yaml` cassette files **must be committed** to version control. They act as the definitive mock data for automated CI pipelines.

### Generating New Cassettes
When adding new tests or modifying existing API requests, you will need to generate new cassettes:
1. Ensure your valid API keys are configured in the `.env` file.
2. Execute `pytest` locally. If a cassette for a specific test does not exist, VCR will automatically perform a real HTTP request and record the sanitized response.
3. Commit the newly generated `.yaml` files to Git.

### Running Tests & Checking Coverage
To run the test suite and see a detailed coverage report for all fetchers:
```bash
pytest --cov=src/alphadataforge --cov-report=term-missing
```