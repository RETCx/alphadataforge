import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    """
    Settings of the package
    """
    TIINGO_API_KEY = os.getenv("TIINGO_API_KEY")
    ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY")

config = Settings()