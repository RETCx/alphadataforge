class Endpoints:
    """
    Centralized configuration for API provider endpoints.
    """
    class AlphaVantage:
        BASE_URL = "https://www.alphavantage.co/query"
        
        # Mappings for the `function` parameter in AlphaVantage
        FUNCTIONS = {
            "income": "INCOME_STATEMENT",
            "balance": "BALANCE_SHEET",
            "cashflow": "CASH_FLOW",
            "shares_outstanding": "SHARES_OUTSTANDING",
            "earnings": "EARNINGS",
            "overview": "OVERVIEW",
            "price_daily": "TIME_SERIES_DAILY",
            "dividends": "DIVIDENDS",
            "splits": "SPLITS"
        }

    class FMP:
        BASE_URL = "https://financialmodelingprep.com/stable"
        
        # Paths appended to the FMP BASE_URL
        PATHS = {
            "income": "income-statement",
            "balance": "balance-sheet-statement",
            "cashflow": "cash-flow-statement",
            "shares_float": "shares-float",
            "profile": "profile",
            "price_adjusted": "historical-price-eod/dividend-adjusted",
            "price_raw": "historical-price-eod/full"
        }

    class Tiingo:
        BASE_URL = "https://api.tiingo.com/tiingo/daily"
