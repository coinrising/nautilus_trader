import msgspec


class SpotLotSizeFilter(msgspec.Struct):
    """MEXC Spot lot size filter."""
    basePrecision: str
    quotePrecision: str
    minOrderQty: str
    maxOrderQty: str
    minOrderValue: str  # minNotional in MEXC


class SpotPriceFilter(msgspec.Struct):
    """MEXC Spot price filter."""
    tickSize: str
    minPrice: str | None = None
    maxPrice: str | None = None

