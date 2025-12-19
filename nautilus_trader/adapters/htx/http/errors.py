"""HTX HTTP API error handling."""

from typing import Any


class HtxError(Exception):
    """Base exception for HTX API errors."""
    
    def __init__(
        self,
        status: str,
        err_code: str | None = None,
        err_msg: str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(err_msg or status)
        self.status = status
        self.err_code = err_code
        self.err_msg = err_msg
        self.headers = headers or {}


def should_retry(error: HtxError) -> bool:
    """
    Determine if an HTX error should be retried.
    
    Parameters
    ----------
    error : HtxError
        The error to check.
        
    Returns
    -------
    bool
        Whether the error should be retried.
        
    """
    from nautilus_trader.adapters.htx.common.constants import HTX_RETRY_ERRORS
    
    if error.err_code and error.err_code in HTX_RETRY_ERRORS:
        return True
    
    return False

