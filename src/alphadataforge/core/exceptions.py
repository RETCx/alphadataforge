class AlphaDataForgeError(Exception):
    """Base class for all exceptions raised by the alphadataforge library."""
    pass

class ProviderConfigurationError(AlphaDataForgeError):
    """Raised when a provider is improperly configured (e.g., missing API keys)."""
    pass

class RateLimitExceededError(AlphaDataForgeError):
    """Raised when an API rate limit is exceeded (HTTP 429 or API notice)."""
    pass

class InvalidTickerError(AlphaDataForgeError):
    """Raised when an API explicitly states the ticker is invalid or not found."""
    pass

class DataFetchError(AlphaDataForgeError):
    """Raised when a general error occurs while fetching data from the API."""
    pass
