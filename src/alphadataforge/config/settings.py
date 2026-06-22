import os
from typing import Optional
from dotenv import load_dotenv

# Use override=True so that if the user updates .env while the Jupyter kernel is running,
# and autoreload triggers, it will actually load the new API keys instead of keeping the old ones in os.environ.
load_dotenv(override=True)

class Settings:
    """
    Settings of the package
    """
    TIINGO_API_KEY: Optional[str] = os.getenv("TIINGO_API_KEY")
    ALPHAVANTAGE_API_KEY: Optional[str] = os.getenv("ALPHAVANTAGE_API_KEY")

config = Settings()