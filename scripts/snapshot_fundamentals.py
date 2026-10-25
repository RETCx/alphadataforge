"""
AlphaDataForge - Historical Fundamentals Snapshot Tool
Captures 20-year financial statement history (Annual & Quarterly) from StockFit SEC XBRL
and stores it locally in Parquet and SQLite before trial evaluation ends.
"""

import os
import sys
import time
import sqlite3
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd

# Reconfigure stdout for UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add src to sys.path so the package can be imported directly
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "src"))

from alphadataforge.providers.stockfit_fetcher import StockFitFetcher
from alphadataforge.data.fundamental import Fundamentals
from alphadataforge.utils.logger import setup_logger

logger = setup_logger(__name__)

# Presets
MAG7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]

TOP25 = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
    "BRK-B", "JPM", "JNJ", "V", "PG", "XOM", "UNH", "HD",
    "WMT", "LLY", "AVGO", "COST", "MA", "ABBV", "BAC", "KO", "PEP", "MRK"
]


def setup_storage(base_dir: Path):
    """Ensure storage directories exist."""
    parquet_dir = base_dir / "parquet"
    parquet_dir.mkdir(parents=True, exist_ok=True)
    db_path = base_dir / "fundamentals.db"
    return parquet_dir, db_path


def save_to_sqlite(df: pd.DataFrame, db_path: Path, table_name: str, symbol: Optional[str] = None):
    """Save or append a DataFrame to SQLite table with dynamic column evolution."""
    if df.empty:
        return
    df_copy = df.copy()
    if symbol:
        df_copy["symbol"] = symbol
    if df_copy.index.name or not isinstance(df_copy.index, pd.RangeIndex):
        df_copy = df_copy.reset_index()

    # Convert complex objects or lists to JSON string if any
    for col in df_copy.columns:
        if df_copy[col].dtype == "object":
            df_copy[col] = df_copy[col].apply(lambda x: str(x) if isinstance(x, (dict, list)) else x)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
        if cursor.fetchone() is None:
            df_copy.to_sql(table_name, conn, if_exists="replace", index=False)
        else:
            cursor.execute(f"PRAGMA table_info('{table_name}');")
            existing_cols = {row[1] for row in cursor.fetchall()}
            for col in df_copy.columns:
                if col not in existing_cols:
                    cursor.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{col}" TEXT;')
            df_copy.to_sql(table_name, conn, if_exists="append", index=False)


def save_to_parquet(df: pd.DataFrame, parquet_path: Path, symbol: str):
    """Save DataFrame to Parquet file."""
    if df.empty:
        return
    df_copy = df.copy()
    df_copy["symbol"] = symbol
    
    # Clean object types for parquet compatibility
    for col in df_copy.columns:
        if df_copy[col].dtype == "object":
            df_copy[col] = df_copy[col].apply(lambda x: str(x) if isinstance(x, (dict, list)) else x)

    df_copy.to_parquet(parquet_path, engine="auto", compression="snappy")


def run_snapshot(symbols: List[str], base_dir: Path, include_quarterly: bool = True):
    print("=" * 70)
    print("=== ALPHADATAFORGE - STOCKFIT SEC XBRL SNAPSHOT UTILITY ===")
    print("=" * 70)
    print(f"Target Symbols  : {len(symbols)} tickers -> {symbols}")
    print(f"Destination Dir : {base_dir}")
    print(f"Include Quarter : {include_quarterly}")
    print("-" * 70)

    parquet_dir, db_path = setup_storage(base_dir)
    fetcher = StockFitFetcher()

    statements = ["income", "balance", "cashflow"]
    periods = ["annual"]
    if include_quarterly:
        periods.append("quarterly")

    total_files = 0
    total_records = 0
    start_time = time.time()

    for idx, sym in enumerate(symbols, 1):
        print(f"\n[{idx}/{len(symbols)}] Processing {sym}...")
        
        # 1. Company Profile / Info
        try:
            info = fetcher.fetch_info(sym)
            if info:
                df_info = pd.DataFrame([info])
                save_to_sqlite(df_info, db_path, "company_profiles", symbol=sym)
                print(f"  [+] Profile saved ({info.get('name')}, Sector: {info.get('sector')})")
        except Exception as e:
            print(f"  [-] Failed profile for {sym}: {e}")

        # 2. Health Scores
        try:
            scores = fetcher.fetch_scores(sym)
            if scores and isinstance(scores, dict):
                row = {k: v for k, v in scores.items() if not isinstance(v, dict)}
                df_scores = pd.DataFrame([row])
                save_to_sqlite(df_scores, db_path, "financial_scores", symbol=sym)
                print(f"  [+] Scores saved (Piotroski F-Score: {scores.get('piotroskiFScore')})")
        except Exception as e:
            print(f"  [-] Failed scores for {sym}: {e}")

        # 3. Financial Statements (Annual & Quarterly)
        for stmt in statements:
            for per in periods:
                try:
                    df = fetcher.fetch_financials(sym, statement=stmt, period=per, limit=100)
                    if not df.empty:
                        # Save Parquet
                        pq_file = parquet_dir / f"{sym}_{stmt}_{per}.parquet"
                        save_to_parquet(df, pq_file, sym)
                        
                        # Save SQLite table
                        table_name = f"{stmt}_{per}"
                        save_to_sqlite(df, db_path, table_name, symbol=sym)

                        records_count = len(df)
                        total_records += records_count
                        total_files += 1
                        oldest = df.index.min().strftime("%Y-%m-%d")
                        newest = df.index.max().strftime("%Y-%m-%d")
                        print(f"  [+] {stmt:10} ({per:9}) -> {records_count:2} periods ({oldest} to {newest})")
                    else:
                        print(f"  [-] {stmt:10} ({per:9}) -> Empty")
                except Exception as e:
                    print(f"  [!] Failed {stmt} {per} for {sym}: {e}")
                
                # Polite delay
                time.sleep(0.05)

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("=== SNAPSHOT COMPLETED SUCCESSFULLY! ===")
    print(f"Total Symbols Processed : {len(symbols)}")
    print(f"Total Statements Saved  : {total_files} Parquet files")
    print(f"Total Data Points/Rows  : {total_records}")
    print(f"SQLite Database File    : {db_path} ({os.path.getsize(db_path) / 1024:.1f} KB)")
    print(f"Time Elapsed            : {elapsed:.2f} seconds")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Snapshot Historical Fundamental Data from StockFit")
    parser.add_argument(
        "--preset", 
        type=str, 
        choices=["mag7", "top25"], 
        default="mag7", 
        help="Predefined ticker basket (default: mag7)"
    )
    parser.add_argument(
        "--symbols", 
        type=str, 
        help="Comma-separated ticker list, e.g. AAPL,MSFT,NVDA"
    )
    parser.add_argument(
        "--outdir", 
        type=str, 
        default="data_store/stockfit_snapshots", 
        help="Directory to store parquet and sqlite db"
    )
    parser.add_argument(
        "--annual-only", 
        action="store_true", 
        help="Capture only annual statements (skip quarterly)"
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Clean old database before running snapshot"
    )

    args = parser.parse_args()

    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    elif args.preset == "top25":
        symbols = TOP25
    else:
        symbols = MAG7

    base_dir = root_dir / args.outdir
    if args.clean:
        db_file = base_dir / "fundamentals.db"
        if db_file.exists():
            db_file.unlink()
            print(f"Removed previous database: {db_file}")

    run_snapshot(symbols, base_dir, include_quarterly=not args.annual_only)


if __name__ == "__main__":
    main()
