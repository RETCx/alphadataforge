import pandas as pd
from alphadataforge.data.price import Price
import warnings
warnings.filterwarnings('ignore')

symbol = 'AAPL'
start = '2026-05-01'
end = '2026-05-31'
target_date = '2026-05-05'

providers = ['yfinance', 'tiingo', 'fmp', 'alphavantage', 'hybrid_av_tiingo']
dfs = {}

print('Fetching data for detailed comparison (May 2026)...')
for p in providers:
    try:
        df = Price.get(symbol, start_date=start, end_date=end, provider=p, provider_params={'adjusted': True})
        dfs[p] = df
    except Exception as e:
        print(f'{p.upper()} Failed:', type(e).__name__, e)

core_columns = [
    'Open', 'High', 'Low', 'Close', 'Volume', 
    'Adj Open', 'Adj High', 'Adj Low', 'Adj Close', 'Adj Volume'
]

print(f'\nDetailed Core Column Comparison for AAPL on {target_date}:\n')

# We'll build a DataFrame to show it nicely
comparison_data = {}
for p in providers:
    if p in dfs and not dfs[p].empty and target_date in dfs[p].index:
        row = dfs[p].loc[target_date]
        comparison_data[p] = {col: (row[col] if col in row else None) for col in core_columns}
    else:
        comparison_data[p] = {col: None for col in core_columns}

comp_df = pd.DataFrame(comparison_data)
# Reorder rows to match core_columns
comp_df = comp_df.loc[core_columns]

print(comp_df.to_string())

# We can also check if the values are within 1% of each other (excluding Volume which might have different scales)
