import msgspec


class SpotLotSizeFilter(msgspec.Struct):
    """HTX Spot lot size filter."""
    min_order_amt: str  # Minimum order amount (base currency)
    max_order_amt: str  # Maximum order amount (base currency)
    min_order_value: str  # Minimum order value (quote currency)
    limit_order_min_order_amt: str | None = None
    limit_order_max_order_amt: str | None = None
    sell_market_min_order_amt: str | None = None
    sell_market_max_order_amt: str | None = None
    buy_market_max_order_value: str | None = None


class SpotPriceFilter(msgspec.Struct):
    """HTX Spot price filter."""
    price_precision: int
    amount_precision: int
    value_precision: int

