import pandas as pd
import numpy as np
from alphadataforge.utils.finance_math import calculate_adjusted_prices

def test_calculate_adjusted_prices_split_only():
    """Test backward adjustment for a simple 2:1 stock split."""
    raw = pd.DataFrame({
        'Date': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03']),
        'Open': [100.0, 100.0, 50.0],
        'High': [110.0, 110.0, 55.0],
        'Low': [90.0, 90.0, 45.0],
        'Close': [105.0, 100.0, 52.0],
        'Volume': [1000, 1000, 2000]
    }).set_index('Date')
    
    splits = pd.DataFrame({
        'Date': pd.to_datetime(['2023-01-03']),
        'SplitFactor': [2.0]
    }).set_index('Date')
    
    divs = pd.DataFrame() # Empty dividends
    
    adj = calculate_adjusted_prices(raw, divs, splits)
    
    # Assert Day 1 and 2 prices are halved
    assert adj.loc['2023-01-01', 'Adj Close'] == 105.0 / 2.0
    assert adj.loc['2023-01-02', 'Adj Close'] == 100.0 / 2.0
    
    # Assert Day 3 prices are unchanged (split is effective on Day 3 open)
    assert adj.loc['2023-01-03', 'Adj Close'] == 52.0
    
    # Assert Volume is doubled for Day 1 and 2
    assert adj.loc['2023-01-01', 'Adj Volume'] == 2000
    assert adj.loc['2023-01-02', 'Adj Volume'] == 2000
    assert adj.loc['2023-01-03', 'Adj Volume'] == 2000

def test_calculate_adjusted_prices_dividend_only():
    """Test backward adjustment for a cash dividend."""
    raw = pd.DataFrame({
        'Date': pd.to_datetime(['2023-01-01', '2023-01-02']),
        'Open': [100.0, 90.0],
        'High': [110.0, 95.0],
        'Low': [90.0, 85.0],
        'Close': [100.0, 90.0],
        'Volume': [1000, 1000]
    }).set_index('Date')
    
    splits = pd.DataFrame()
    
    # 10$ dividend on day 2. Previous close was 100. Factor = (100-10)/100 = 0.9
    divs = pd.DataFrame({
        'Date': pd.to_datetime(['2023-01-02']),
        'Dividend': [10.0]
    }).set_index('Date')
    
    adj = calculate_adjusted_prices(raw, divs, splits)
    
    # Assert Day 1 price is adjusted by 0.9
    assert adj.loc['2023-01-01', 'Adj Close'] == 100.0 * 0.9
    
    # Assert Day 2 price is unchanged
    assert adj.loc['2023-01-02', 'Adj Close'] == 90.0
    
    # Assert Volume is unchanged by dividends
    assert adj.loc['2023-01-01', 'Adj Volume'] == 1000
    
def test_calculate_adjusted_prices_missing_columns():
    """Test robustness with missing/different column names."""
    raw = pd.DataFrame({
        'Date': pd.to_datetime(['2023-01-01', '2023-01-02']),
        'Open': [100.0, 90.0],
        'High': [110.0, 95.0],
        'Low': [90.0, 85.0],
        'Close': [100.0, 90.0],
        'Volume': [1000, 1000]
    }).set_index('Date')
    
    # Missing 'Dividend' column, using 'divCash' instead
    divs = pd.DataFrame({
        'Date': pd.to_datetime(['2023-01-02']),
        'divCash': [10.0]
    }).set_index('Date')
    
    # Missing 'SplitFactor' column, using 'splitFactor' instead
    splits = pd.DataFrame({
        'Date': pd.to_datetime(['2023-01-02']),
        'splitFactor': [1.0]
    }).set_index('Date')
    
    adj = calculate_adjusted_prices(raw, divs, splits)
    
    assert adj.loc['2023-01-01', 'Adj Close'] == 100.0 * 0.9
