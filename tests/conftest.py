import requests_cache
from vcr.stubs import VCRHTTPResponse
import pytest

# 1. Disable requests_cache globally for all tests to prevent VCR conflicts
requests_cache.uninstall_cache()

# 2. VCRHTTPResponse missing _request_url compatibility patch (User requested fix)
try:
    # Fix compatibility issue: VCRHTTPResponse has no attribute '_request_url'
    @property
    def _request_url_patch(self):
        request_url = getattr(self, "url", None)
        if request_url is None and hasattr(self, "request"):
            request_url = getattr(self.request, "url", None)
        return request_url
    VCRHTTPResponse._request_url = _request_url_patch
except ImportError:
    pass
import os
@pytest.fixture(scope="module")
def vcr_config():
    """
    Configuration for pytest-vcr to scrub sensitive information
    from cassettes before saving them to disk.
    """
    return {
        "record_mode": os.environ.get("VCR_RECORD_MODE", "once"),
        # Hide query parameters like ?apikey=YOUR_KEY
        "filter_query_parameters": ["apikey", "token", "api_key"],
        
        # Hide headers that might contain tokens
        "filter_headers": ["authorization", "x-api-key", "x-tiingo-token"],
        
        # Only record API calls if the cassette doesn't exist yet
        "record_mode": "once",
        
        # Save cassettes in a central directory
        "cassette_library_dir": "tests/cassettes",
    }
