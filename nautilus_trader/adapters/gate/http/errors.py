from nautilus_trader.adapters.bybit.common.constants import BYBIT_RETRY_ERRORS_UTA


class GateError(Exception):

    def __init__(
        self,
        code: int | None,
        message: str | None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def __repr__(self) -> str:
        return f"{type(self).__name__}(code={self.code}, message='{self.message}')"


def should_retry(error: BaseException) -> bool:
    """
    Determine if a retry should be attempted based on the error code.

    Parameters
    ----------
    error : BaseException
        The error to check.

    Returns
    -------
    bool
        True if should retry, otherwise False.

    """
    if isinstance(error, GateError):
        return error.code in BYBIT_RETRY_ERRORS_UTA
    return False
