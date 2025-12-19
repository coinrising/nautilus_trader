import msgspec


class MexcFeeRate(msgspec.Struct):
    """MEXC fee rate schema."""
    symbol: str | None = None
    makerFeeRate: str = "0.002"  # Default 0.2%
    takerFeeRate: str = "0.002"  # Default 0.2%

