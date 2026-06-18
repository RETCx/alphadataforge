import pytest
import pandas as pd
from alphadataforge.data_fetch.yfinance_fetcher import YFinanceFetcher

def test_yfinance_fetcher_returns_dataframe():
    """ทดสอบว่าตัวดึงข้อมูล YFinance ทำงานได้ถูกต้องตามสัญญาไหม"""
    
    # 1. จำลองการเรียกใช้งาน (ดึงแค่ 5 วันพอ เทสต์จะได้รันเร็วๆ)
    fetcher = YFinanceFetcher()
    df = fetcher.fetch_data("AAPL", start_date="2023-01-01", end_date="2023-01-05")
    
    # 2. ตรวจข้อสอบ (ถ้าไม่จริงมันจะฟ้อง Error สีแดงเลย)
    assert isinstance(df, pd.DataFrame), "ต้องคืนค่ามาเป็น DataFrame เท่านั้น!"
    assert not df.empty, "ข้อมูลต้องไม่ว่างเปล่า!"
    assert 'Close' in df.columns, "ต้องมีคอลัมน์ราคาปิด (Close)"