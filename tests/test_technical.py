import pytest
import numpy as np
import pandas as pd
from alphadataforge.features import TechnicalIndicators


@pytest.fixture
def sample_ohlcv() -> pd.DataFrame:
    """Generate 300 trading days of synthetic OHLCV data."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2024-01-01", periods=300)
    returns = rng.normal(loc=0.0008, scale=0.015, size=300)
    close = 100.0 * np.exp(np.cumsum(returns))
    open_px = close * (1.0 + rng.normal(0, 0.004, size=300))
    high = np.maximum(open_px, close) * (1.0 + np.abs(rng.normal(0.005, 0.003, size=300)))
    low = np.minimum(open_px, close) * (1.0 - np.abs(rng.normal(0.005, 0.003, size=300)))
    vol = rng.integers(1_000_000, 10_000_000, size=300).astype(float)

    df = pd.DataFrame(
        {
            "Open": open_px,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": vol,
            "Adj Open": open_px,
            "Adj High": high,
            "Adj Low": low,
            "Adj Close": close,
            "Adj Volume": vol,
        },
        index=dates,
    )
    df.index.name = "Date"
    return df


def test_rsi_calculations(sample_ohlcv):
    df = TechnicalIndicators.rsi(sample_ohlcv, window=14, method="wilder")
    assert "RSI_14" in df.columns
    valid = df["RSI_14"].dropna()
    assert len(valid) > 250
    assert (valid >= 0.0).all() and (valid <= 100.0).all()

    # Monotonically increasing prices should produce RSI = 100
    up_df = pd.DataFrame(
        {"Close": np.arange(1.0, 50.0)},
        index=pd.bdate_range("2025-01-01", periods=49),
    )
    up_res = TechnicalIndicators.rsi(up_df, window=14, method="sma")
    assert np.isclose(up_res["RSI_14"].iloc[-1], 100.0)

    # EMA method
    df_ema = TechnicalIndicators.rsi(sample_ohlcv, window=10, method="ema")
    assert "RSI_10" in df_ema.columns


def test_macd_calculations(sample_ohlcv):
    df = TechnicalIndicators.macd(sample_ohlcv, fast=12, slow=26, signal=9)
    assert {"MACD", "MACD_Signal", "MACD_Hist"}.issubset(df.columns)
    valid = df.dropna(subset=["MACD", "MACD_Signal", "MACD_Hist"])
    assert np.allclose(valid["MACD"] - valid["MACD_Signal"], valid["MACD_Hist"])

    with pytest.raises(ValueError, match="fast period"):
        TechnicalIndicators.macd(sample_ohlcv, fast=26, slow=12)


def test_bollinger_bands_calculations(sample_ohlcv):
    df = TechnicalIndicators.bollinger_bands(sample_ohlcv, window=20, num_std=2.0)
    expected_cols = {"BB_Middle", "BB_Upper", "BB_Lower", "BB_Bandwidth", "BB_PercentB"}
    assert expected_cols.issubset(df.columns)

    valid = df.dropna(subset=list(expected_cols))
    assert (valid["BB_Upper"] >= valid["BB_Middle"]).all()
    assert (valid["BB_Middle"] >= valid["BB_Lower"]).all()
    # When price equals middle band, PercentB is 0.5
    mid_check = (valid["Adj Close"] - valid["BB_Lower"]) / (valid["BB_Upper"] - valid["BB_Lower"])
    assert np.allclose(valid["BB_PercentB"], mid_check)


def test_atr_calculations(sample_ohlcv):
    df = TechnicalIndicators.atr(sample_ohlcv, window=14, include_natr=True)
    assert "ATR_14" in df.columns
    assert "NATR_14" in df.columns
    valid = df.dropna(subset=["ATR_14", "NATR_14"])
    assert (valid["ATR_14"] > 0).all()
    assert np.allclose(valid["NATR_14"], (valid["ATR_14"] / valid["Adj Close"]) * 100.0)

    # Test gap-up True Range: Day 1 Close=100, Day 2 High=120, Low=115 -> TR should be 120 - 100 = 20
    gap_df = pd.DataFrame(
        {
            "High": [105.0, 120.0, 125.0],
            "Low": [95.0, 115.0, 118.0],
            "Close": [100.0, 118.0, 122.0],
        },
        index=pd.bdate_range("2025-01-01", periods=3),
    )
    res_atr = TechnicalIndicators.atr(gap_df, window=2, method="sma", use_adjusted=False)
    # Day 1 TR = 10, Day 2 TR = max(5, |120-100|=20, |115-100|=15) = 20 -> 2-day SMA = 15.0
    assert np.isclose(res_atr["ATR_2"].iloc[1], 15.0)


def test_rolling_volatility_estimators(sample_ohlcv):
    df_close = TechnicalIndicators.rolling_volatility(sample_ohlcv, windows=[20, 60], estimator="close")
    assert {"Volatility_20d", "Volatility_60d"}.issubset(df_close.columns)
    assert (df_close["Volatility_20d"].dropna() > 0).all()

    df_park = TechnicalIndicators.rolling_volatility(sample_ohlcv, windows=20, estimator="parkinson")
    assert "Volatility_Parkinson_20d" in df_park.columns
    assert (df_park["Volatility_Parkinson_20d"].dropna() > 0).all()

    df_gk = TechnicalIndicators.rolling_volatility(sample_ohlcv, windows=20, estimator="garman_klass")
    assert "Volatility_GK_20d" in df_gk.columns
    assert (df_gk["Volatility_GK_20d"].dropna() > 0).all()


def test_time_series_momentum(sample_ohlcv):
    df = TechnicalIndicators.momentum(sample_ohlcv, windows=[21, 63, 126, 252], include_12_1=True)
    assert {"Mom_21d", "Mom_63d", "Mom_126d", "Mom_252d", "Mom_12_1M"}.issubset(df.columns)

    # Verify 12-1M formula: P_{t-21} / P_{t-252} - 1
    expected_12_1 = (sample_ohlcv["Adj Close"].shift(21) / sample_ohlcv["Adj Close"].shift(252)) - 1.0
    assert np.allclose(df["Mom_12_1M"].dropna(), expected_12_1.dropna())


def test_cross_sectional_momentum_dict_and_long(sample_ohlcv):
    dates = sample_ohlcv.index
    # Create a 5-stock universe with distinct deterministic drift rates
    universe_dict = {}
    drifts = {"WINNER": 0.003, "STRONG": 0.0015, "NEUTRAL": 0.0005, "WEAK": -0.0005, "LOSER": -0.002}
    for sym, drift in drifts.items():
        px = 100.0 * np.exp(np.cumsum(np.full(len(dates), drift)))
        universe_dict[sym] = pd.DataFrame({"Close": px, "Adj Close": px}, index=dates)

    cs_df = TechnicalIndicators.cross_sectional_momentum(
        universe_dict, lookback=126, skip_recent=21, risk_adjusted=False
    )
    assert not cs_df.empty
    expected_cols = {
        "Price",
        "Momentum_Return",
        "Realized_Vol",
        "Risk_Adj_Momentum",
        "CS_Rank_Pct",
        "CS_ZScore",
        "CS_Decile",
    }
    assert expected_cols.issubset(cs_df.columns)

    # Check last date rankings: WINNER must have rank 1.0 (Decile 10) and LOSER rank 0.2 (Decile 2)
    last_date = cs_df.index.get_level_values("Date").max()
    snap = cs_df.loc[last_date]
    assert np.isclose(snap.loc["WINNER", "CS_Rank_Pct"], 1.0)
    assert snap.loc["WINNER", "CS_Decile"] == 10.0
    assert np.isclose(snap.loc["LOSER", "CS_Rank_Pct"], 0.2)
    assert snap.loc["WINNER", "CS_ZScore"] > snap.loc["LOSER", "CS_ZScore"]

    # Also test long-format DataFrame input (matching SQLite price_history_daily schema)
    long_rows = []
    for sym, df_sym in universe_dict.items():
        tmp = pd.DataFrame({"symbol": sym, "date": df_sym.index, "close": df_sym["Close"].values})
        long_rows.append(tmp)
    long_df = pd.concat(long_rows, ignore_index=True)

    cs_from_long = TechnicalIndicators.cross_sectional_momentum(long_df, lookback=126, skip_recent=21)
    pd.testing.assert_series_equal(
        cs_from_long.loc[last_date, "Momentum_Return"],
        snap["Momentum_Return"],
    )


def test_add_all_single_and_dict(sample_ohlcv):
    enriched = TechnicalIndicators.add_all(sample_ohlcv)
    for col in [
        "RSI_14",
        "MACD",
        "MACD_Signal",
        "MACD_Hist",
        "BB_Upper",
        "BB_Lower",
        "ATR_14",
        "NATR_14",
        "Volatility_20d",
        "Volatility_60d",
        "Mom_21d",
        "Mom_12_1M",
    ]:
        assert col in enriched.columns

    multi = {"AAPL": sample_ohlcv, "MSFT": sample_ohlcv.copy()}
    multi_enriched = TechnicalIndicators.add_all(multi)
    assert isinstance(multi_enriched, dict)
    assert "RSI_14" in multi_enriched["AAPL"].columns
    assert "MACD" in multi_enriched["MSFT"].columns
