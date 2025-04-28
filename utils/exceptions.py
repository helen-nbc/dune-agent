"""Custom exceptions for the application."""

class DuneAnalyticsError(Exception):
    """Base exception for Dune Analytics related errors."""
    pass

class DuneAPIKeyError(DuneAnalyticsError):
    """Raised when the Dune API key is missing or invalid."""
    pass

class QueryExecutionError(DuneAnalyticsError):
    """Raised when there is an error executing a query."""
    pass

class QueryTimeoutError(DuneAnalyticsError):
    """Raised when a query execution times out."""
    pass

class NoDataError(DuneAnalyticsError):
    """Raised when no data is returned from a query."""
    pass

class SeleniumError(Exception):
    """Raised when there is an error with Selenium operations."""
    pass 