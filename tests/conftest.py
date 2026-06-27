import pytest

@pytest.fixture(scope="module")
def vcr_config():
    """
    Configuration for pytest-vcr to scrub sensitive information
    from cassettes before saving them to disk.
    """
    return {
        # Hide query parameters like ?apikey=YOUR_KEY
        "filter_query_parameters": ["apikey", "token", "api_key"],
        
        # Hide headers that might contain tokens
        "filter_headers": ["authorization", "x-api-key", "x-tiingo-token"],
        
        # Only record API calls if the cassette doesn't exist yet
        "record_mode": "once",
        
        # Save cassettes in a central directory
        "cassette_library_dir": "tests/cassettes",
    }
