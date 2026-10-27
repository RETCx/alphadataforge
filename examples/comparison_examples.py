"""
AlphaDataForge - Price Comparison & Consensus Examples
This script demonstrates the power of the Price API, including:
1. Basic Cross-Provider Comparison
2. Detailed Core Column Validation
3. Importing, Normalizing, Adjusting, and comparing a Custom CSV
"""

import pandas as pd
import warnings
from alphadataforge.data.price import Price
from alphadataforge.providers.tiingo_fetcher import TiingoFetcher
from alphadataforge.utils.finance_math import calculate_adjusted_prices

warnings.filterwarnings('ignore')

SYMBOL = 'AAPL'
START_DATE = '2026-05-01'
END_DATE = '2026-05-31'
TARGET_DATE = '2026-05-05'

def run_basic_comparison():
    print("\n" + "="*50)
    print("1. BASIC CROSS-PROVIDER COMPARISON")
    print("="*50)
    
    print(f"Fetching adjusted data for {SYMBOL} from multiple providers...")
    multi_df = Price.compare(
        SYMBOL, 
        start_date=START_DATE, 
        end_date=END_DATE, 
        provider_params={'adjusted': True}
    )
    
    print("\nConsensus (Median) Prices:")
    consensus_df = Price.consensus(
        SYMBOL, 
        start_date=START_DATE, 
        end_date=END_DATE, 
        provider_params={'adjusted': True}, 
        method='median'
    )
    print(consensus_df[['Adj Open', 'Adj High', 'Adj Low', 'Adj Close']].head())


def run_detailed_validation():
    print("\n" + "="*50)
    print(f"2. DETAILED CORE COLUMN VALIDATION ({TARGET_DATE})")
    print("="*50)
    
    multi_df = Price.compare(
        SYMBOL, 
        start_date=START_DATE, 
        end_date=END_DATE, 
        provider_params={'adjusted': True}
    )
    
    if TARGET_DATE in multi_df.index:
        target_row = multi_df.loc[TARGET_DATE]
        # target_row is a Series with MultiIndex (Provider, Column)
        # We unstack it to make it a DataFrame where Columns=Providers, Rows=OHLCV
        df_display = target_row.unstack(level=0)
        
        core_columns = ['Open', 'High', 'Low', 'Close', 'Volume', 'Adj Open', 'Adj High', 'Adj Low', 'Adj Close', 'Adj Volume']
        existing_cols = [c for c in core_columns if c in df_display.index]
        df_display = df_display.loc[existing_cols]
        print(df_display.to_string())
    else:
        print(f"No data available for {TARGET_DATE}")


def run_custom_csv_workflow():
    print("\n" + "="*50)
    print("3. CUSTOM CSV WORKFLOW (Normalize -> Adjust -> Consensus)")
    print("="*50)
    
    # 1. Load Custom Data
    df_custom = pd.read_csv('test_data/Apple Stock Price History.csv')
    
    # --- THIS IS HOW YOU NORMALIZE CUSTOM DATA ---
    # We map the non-standard column names to AlphaDataForge standards
    column_mapping = {
        'Price': 'Close',
        'Vol.': 'Volume'
    }
    df_custom.rename(columns=column_mapping, inplace=True)
    
    # Set standard index
    df_custom['Date'] = pd.to_datetime(df_custom['Date'])
    df_custom.set_index('Date', inplace=True)
    df_custom = df_custom.sort_index()

    # Clean data (convert string formats like "261.78M" to float)
    def parse_volume(vol_str):
        if isinstance(vol_str, str):
            if 'M' in vol_str: return float(vol_str.replace('M', '')) * 1_000_000
            elif 'K' in vol_str: return float(vol_str.replace('K', '')) * 1_000
            elif 'B' in vol_str: return float(vol_str.replace('B', '')) * 1_000_000_000
        return float(vol_str)
    df_custom['Volume'] = df_custom['Volume'].apply(parse_volume)
    
    for col in ['Open', 'High', 'Low', 'Close']:
        if df_custom[col].dtype == object:
            df_custom[col] = df_custom[col].str.replace(',', '').astype(float)
            
    print("Normalized Custom Data (Raw Prices):")
    print(df_custom[['Open', 'High', 'Low', 'Close', 'Volume']].head(2).to_string())

    # 2. Back-Adjust the Custom Data using Tiingo Dividends/Splits
    start_str = df_custom.index.min().strftime('%Y-%m-%d')
    end_str = df_custom.index.max().strftime('%Y-%m-%d')
    
    tf = TiingoFetcher()
    df_tiingo = tf.fetch_single(SYMBOL, start_date=start_str, end_date=end_str)
    dividends_df = df_tiingo[['divCash']].rename(columns={'divCash': 'Dividend'})
    dividends_df = dividends_df[dividends_df['Dividend'] > 0]
    splits_df = df_tiingo[['splitFactor']].rename(columns={'splitFactor': 'SplitFactor'})
    splits_df = splits_df[splits_df['SplitFactor'] != 1.0]

    df_custom_adjusted = calculate_adjusted_prices(df_custom, dividends_df, splits_df)
    print("\nBack-Adjusted Custom Data (using Tiingo events):")
    print(df_custom_adjusted[['Adj Open', 'Adj High', 'Adj Low', 'Adj Close']].head(2).to_string())

    # 3. Feed the Custom Data into Price.consensus()!
    print("\nMerging Custom CSV into Consensus engine (along with YFinance & AlphaVantage)...")
    consensus_df = Price.consensus(
        SYMBOL, 
        start_date="2026-06-01", 
        end_date="2026-06-05", 
        providers=["yfinance", "alphavantage"], 
        provider_params={"adjusted": True},
        custom_data={"my_local_csv": df_custom_adjusted},
        method="median"
    )
    
    print("\nFinal Consensus Output:")
    print(consensus_df[['Adj Open', 'Adj High', 'Adj Low', 'Adj Close']].to_string())


if __name__ == "__main__":
    run_basic_comparison()
    run_detailed_validation()
    run_custom_csv_workflow()
