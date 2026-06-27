import pandas as pd
from alphadataforge.data.price import Price
import warnings
warnings.filterwarnings('ignore')

symbol = 'AAPL'
start = '2026-05-01'
end = '2026-05-31'

providers = ['yfinance', 'tiingo', 'fmp', 'alphavantage', 'hybrid_av_tiingo']
dfs = {}

print('Fetching data for comparison (May 2026)...')
for p in providers:
    try:
        df = Price.get(symbol, start_date=start, end_date=end, provider=p, provider_params={'adjusted': True})
        dfs[p] = df
        print(f'{p.upper()} Columns:', df.columns.tolist())
    except Exception as e:
        print(f'{p.upper()} Failed:', type(e).__name__, e)

print('\nComparing Adj Close for 2026-05-05:')
for p, df in dfs.items():
    try:
        val = df.loc['2026-05-05', 'Adj Close']
        print(f'{p.rjust(16)}: {val:.4f}')
    except:
        print(f'{p.rjust(16)}: N/A')
        
print('\nComparing Adj Open for 2026-05-05:')
for p, df in dfs.items():
    try:
        val = df.loc['2026-05-05', 'Adj Open']
        print(f'{p.rjust(16)}: {val:.4f}')
    except:
        print(f'{p.rjust(16)}: N/A')
