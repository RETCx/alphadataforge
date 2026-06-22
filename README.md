# AlphaDataForge

AlphaDataForge is a modular data fetching and feature engineering pipeline designed for quantitative trading and financial analysis. It provides a unified, clean, and extensible interface to fetch financial data (Price, News, Fundamentals, Crypto, Forex) from various providers like Yahoo Finance, Tiingo, Alpha Vantage, and Financial Modeling Prep (FMP).

## Table of Contents
- [Architecture Overview](#architecture-overview)
- [Key Features](#key-features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Areas for Improvement](#areas-for-improvement)

## Architecture Overview

The system is built with a **Facade Pattern** on top of a **Strategy Pattern**, ensuring high maintainability and ease of use:

1. **Facade Layer (`src/alphadataforge/data/price.py`)**:
   - Exposes a unified API (e.g., `Price.get()`) to users. The user doesn't need to know the underlying provider mechanics.
2. **Abstract Interface (`src/alphadataforge/core/base_fetcher.py`)**:
   - `BaseDataFetcher` acts as the contract ensuring all providers implement `fetch_single()` and `fetch_multiple()`. It handles standard inputs, index normalization, and robust HTTP request retries using `tenacity`.
3. **Provider Layer (`src/alphadataforge/providers/`)**:
   - Concrete implementations (e.g., `YFinanceFetcher`, `TiingoFetcher`) that adapt specific API responses to the standardized format required by the core.

## Key Features

- **Unified API**: Switch between providers (e.g., `yfinance` to `tiingo`) with a single parameter change.
- **Data Normalization**: Automatically standardizes columns to `[Open, High, Low, Close, Volume, Adj Close]` and ensures a DatetimeIndex.
- **Robustness**: Built-in HTTP retries with exponential backoff for transient errors.
- **Multi-Asset Support**: Fetches Equities, Cryptocurrencies, and Forex pairs.
- **Rich Data**: Not just prices—also fetches news, fundamentals (income statements, balance sheets, cash flows), and metadata.

## Installation

```bash
# Clone the repository
git clone https://github.com/RETCx/alphadataforge.git
cd alphadataforge

# Install dependencies (requires Python 3.8+)
pip install -e .
```

## Configuration

For free-tier providers like `yfinance`, no configuration is needed.
For providers that require API keys (Tiingo, Alpha Vantage, FMP), copy the environment template and add your keys:

```bash
cp .env.example .env
```

Edit the `.env` file to include your keys:
```
TIINGO_API_KEY="your_tiingo_api_key"
ALPHAVANTAGE_API_KEY="your_alphavantage_api_key"
FMP_API_KEY="your_fmp_api_key"
```

## Usage Examples

### 1. Using the Unified Facade (Recommended)

```python
from alphadataforge.data.price import Price

# Fetch AAPL from default provider (yfinance)
df_aapl = Price.get("AAPL", start_date="2023-01-01", end_date="2023-01-10")
print(df_aapl.head())

# Fetch from a different provider (e.g., FMP)
df_msft = Price.get("MSFT", provider="fmp", provider_params={"adjusted": True})

# Batch fetching
data_dict = Price.get(["AAPL", "GOOGL"], start_date="2023-01-01")
print(data_dict["GOOGL"].tail())
```

### 2. Using Specific Fetchers Directly

If you need provider-specific features like News or Crypto, you can instantiate the fetcher directly:

```python
from alphadataforge.providers.yfinance_fetcher import YFinanceFetcher

yf = YFinanceFetcher()

# Fetch News
news_df = yf.fetch_news("AAPL", count=5)

# Fetch Fundamentals
income_stmt = yf.fetch_financials("AAPL", statement="income")

# Fetch Crypto
crypto_data = yf.fetch_crypto(["BTC-USD", "ETH-USD"])
```

## Areas for Improvement (Future Roadmap)

1. **Caching Layer**: Implement local caching (e.g., using `sqlite`, `redis`, or file-based caching) to prevent redundant network calls and avoid API rate limits.
2. **Asynchronous Fetching**: The current `fetch_multiple` implementations use sequential looping in some providers. Integrating `asyncio` and `aiohttp` could drastically improve batch fetching performance.
3. **Data Quality Checks**: Implement automated anomaly detection (e.g., handling missing data, identifying extreme price spikes) before returning data to the user.
4. **Feature Engineering Module**: The `features/` directory is currently empty. Expanding this to calculate standard technical indicators (RSI, MACD) automatically would add immense value to quantitative workflows.
5. **Standardized Exceptions**: Create custom exception classes (e.g., `DataFetchError`, `InvalidTickerError`) to make error handling more predictable for the end user.