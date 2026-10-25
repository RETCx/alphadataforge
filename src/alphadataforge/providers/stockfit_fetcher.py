import pandas as pd
from typing import Optional, List, Dict, Any, Union
import logging

from ..core.base_fetcher import BaseDataFetcher
from ..core.exceptions import ProviderConfigurationError
from ..config.settings import config
from ..config.endpoints import Endpoints
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class StockFitFetcher(BaseDataFetcher):
    """
    Data fetcher for StockFit API (https://stockfit.io).
    Extracts structured, point-in-time intelligence directly from official SEC EDGAR XBRL filings.
    
    Provides:
      - 15-20+ years of normalized financial statements (income, balance, cashflow)
      - SEC filing traceability (10-K, 10-Q accession numbers)
      - Financial health scores (Piotroski F-score, etc.)
      - Company profiles and price history
    """

    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.api_key = api_key or config.STOCKFIT_API_KEY
        self.base_url = Endpoints.StockFit.BASE_URL

    def _require_api_key(self) -> None:
        if not self.api_key:
            raise ProviderConfigurationError(
                "STOCKFIT_API_KEY is not set. Please set it in your .env file or pass it to StockFitFetcher(api_key=...)."
            )

    def _make_request(self, endpoint_path: str, **params) -> Any:
        """
        Executes HTTP GET request to StockFit API with Bearer token authentication.
        """
        self._require_api_key()
        url = f"{self.base_url}/{endpoint_path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json"
        }
        # Filter out None params
        filtered_params = {k: v for k, v in params.items() if v is not None}
        return self._make_http_request(url, params=filtered_params, headers=headers)

    # ------------------------------------------------------------------
    # Price
    # ------------------------------------------------------------------
    def fetch_single(
        self,
        symbol: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        adjusted: bool = True,
        resolution: str = "1d",
        **kwargs
    ) -> pd.DataFrame:
        """
        Fetch historical close prices from StockFit.
        
        Args:
            symbol: Ticker symbol (e.g. 'AAPL').
            start_date: 'YYYY-MM-DD' lower bound.
            end_date: 'YYYY-MM-DD' upper bound.
            adjusted: Split/dividend adjusted close (default True).
            resolution: Bar resolution ('1d', '1wk', '1mo').
        """
        logger.info("Fetching price history for %s via StockFit...", symbol)
        self._validate_inputs(symbol, start_date, end_date)

        params = {
            "symbol": symbol,
            "resolution": resolution,
            "adjusted": adjusted
        }
        if start_date:
            params["from"] = start_date
        if end_date:
            params["to"] = end_date

        try:
            data = self._make_request(Endpoints.StockFit.PATHS["price_history"], **params)
        except Exception as e:
            logger.error("Failed to fetch price history for %s via StockFit: %s", symbol, e)
            return pd.DataFrame()

        bars = data.get("data", [])
        if not bars:
            return pd.DataFrame()

        records = []
        for item in bars:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                ts_ms, val = item[0], item[1]
                records.append({
                    "Date": pd.to_datetime(ts_ms, unit="ms"),
                    "Close": val,
                    "Adj Close": val if adjusted else None
                })

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records).set_index("Date")
        df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
        df.index.name = "Date"

        # Backfill standard columns if needed
        return self._normalize_ohlcv(df)

    # ------------------------------------------------------------------
    # Company Profile / Info
    # ------------------------------------------------------------------
    def fetch_info(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch company profile and basic information from StockFit.
        """
        logger.info("Fetching company details for %s via StockFit...", symbol)
        self._validate_inputs(symbol)

        try:
            data = self._make_request(Endpoints.StockFit.PATHS["details"], symbol=symbol)
            if isinstance(data, dict):
                return data
            return {}
        except Exception as e:
            logger.error("Failed to fetch company details for %s via StockFit: %s", symbol, e)
            return {}

    # ------------------------------------------------------------------
    # Financial Statements
    # ------------------------------------------------------------------
    def fetch_financials(
        self,
        symbol: str,
        statement: str = "income",
        period: str = "annual",
        limit: int = 100,
        **kwargs
    ) -> pd.DataFrame:
        """
        Fetch historical SEC-reported financial statements from StockFit.
        
        Args:
            symbol: Ticker symbol (e.g., 'AAPL').
            statement: "income", "balance", "cashflow", "growth", "scores", or "key_metrics".
            period: "annual" (default) or "quarterly".
            limit: Number of historical periods to retrieve (default 100, up to 20 years).
        
        Returns:
            DataFrame with normalized financial metrics and DatetimeIndex.
        """
        logger.info("Fetching %s statement for %s (%s) via StockFit...", statement, symbol, period)
        self._validate_inputs(symbol)

        statement_clean = statement.lower().replace("-", "").replace("_", "")
        period_clean = "quarterly" if period.lower() in ("quarterly", "quarter", "q") else "annual"

        valid_statements = {
            "income": Endpoints.StockFit.PATHS["income"],
            "balance": Endpoints.StockFit.PATHS["balance"],
            "cashflow": Endpoints.StockFit.PATHS["cashflow"],
            "growth": Endpoints.StockFit.PATHS["growth"],
            "scores": Endpoints.StockFit.PATHS["scores"],
            "keymetrics": Endpoints.StockFit.PATHS["key_metrics"],
            "asreported": Endpoints.StockFit.PATHS["as_reported"],
        }

        if statement_clean not in valid_statements:
            raise ValueError(
                f"Unknown statement type: '{statement}'. Choose from {list(valid_statements.keys())}."
            )

        endpoint_path = valid_statements[statement_clean]
        params = {"symbol": symbol}

        # Statement and growth take period and limit
        if statement_clean in ("income", "balance", "cashflow", "growth", "asreported"):
            params["period"] = period_clean
            params["limit"] = limit
            if "splitAdjust" in kwargs:
                params["splitAdjust"] = kwargs["splitAdjust"]

        try:
            data = self._make_request(endpoint_path, **params)
        except Exception as e:
            logger.error("Failed to fetch %s for %s via StockFit: %s", statement, symbol, e)
            return pd.DataFrame()

        if not data:
            logger.warning("No %s financial data returned for %s in StockFit.", statement, symbol)
            return pd.DataFrame()

        # Handle score endpoints which return a single dict
        if statement_clean == "scores" and isinstance(data, dict):
            row = {k: v for k, v in data.items() if not isinstance(v, dict)}
            if "piotroskiDetails" in data and isinstance(data["piotroskiDetails"], dict):
                for k, v in data["piotroskiDetails"].items():
                    row[f"piotroski_{k}"] = v
            df = pd.DataFrame([row])
            if "period" in df.columns:
                df.index = pd.to_datetime(df["period"])
                df = df.drop(columns=["period"])
            df.index.name = "Date"
            return df

        # Handle growth or keymetrics
        if statement_clean == "growth" and isinstance(data, list):
            df = pd.DataFrame(data)
            if not df.empty and "period" in df.columns:
                df.index = pd.to_datetime(df["period"])
                df = df.drop(columns=["period"])
            df.index.name = "Date"
            return df

        # Standard financial statements: unpack 'facts' object
        if not isinstance(data, list):
            return pd.DataFrame()

        rows = []
        for item in data:
            if not isinstance(item, dict):
                continue
            facts = item.get("facts", {})
            row = facts.copy() if isinstance(facts, dict) else {}
            row["period"] = item.get("period")
            if "fiscalYear" in item:
                row["fiscalYear"] = item.get("fiscalYear")
            if "fiscalPeriod" in item:
                row["fiscalPeriod"] = item.get("fiscalPeriod")
            if "dateFiled" in item:
                row["dateFiled"] = item.get("dateFiled")
            rows.append(row)

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        if "period" in df.columns:
            df.index = pd.to_datetime(df["period"])
            df = df.drop(columns=["period"])
        df.index.name = "Date"

        # Apply standardized column normalization
        return self._normalize_financials(df)

    # ------------------------------------------------------------------
    # Additional Specialized Intelligence
    # ------------------------------------------------------------------
    def fetch_scores(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch Piotroski F-score and financial health metrics.
        """
        return self._make_request(Endpoints.StockFit.PATHS["scores"], symbol=symbol)

    def fetch_growth(self, symbol: str, period: str = "annual") -> pd.DataFrame:
        """
        Fetch historical growth rates (revenue, gross profit, net income, EPS).
        """
        return self.fetch_financials(symbol, statement="growth", period=period)
