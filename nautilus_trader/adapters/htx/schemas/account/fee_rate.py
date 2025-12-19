import msgspec


class HtxFeeRate(msgspec.Struct):
    """HTX fee rate schema."""
    symbol: str | None = None
    maker_fee_rate: str = "0.002"  # Default 0.2%
    taker_fee_rate: str = "0.002"  # Default 0.2%

