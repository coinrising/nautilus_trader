"""MEXC HTTP API error handling."""

from typing import Any


class MexcError(Exception):
    """Base exception for MEXC API errors."""

    def __init__(
        self,
        status: int,
        message: str,
        headers: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.headers = headers or {}


def should_retry(error: MexcError) -> bool:
    """
    Determine if a MEXC error should be retried.
    
    Parameters
    ----------
    error : MexcError
        The error to check.
        
    Returns
    -------
    bool
        Whether the error should be retried.
        
    """
    from nautilus_trader.adapters.mexc.common.constants import MEXC_RETRY_ERRORS
    
    # Check HTTP status codes
    if error.status in {429, 500, 503, 504}:
        return True
    
    # Check MEXC error codes if available
    # MEXC typically returns errors in the response body
    return False

