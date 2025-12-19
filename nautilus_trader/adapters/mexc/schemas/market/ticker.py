import msgspec


class MexcTickerData(msgspec.Struct):
    """MEXC ticker data schema."""
    symbol: str
    priceChange: str | None = None
    priceChangePercent: str | None = None
    prevClosePrice: str | None = None
    lastPrice: str | None = None
    bidPrice: str | None = None
    bidQty: str | None = None
    askPrice: str | None = None
    askQty: str | None = None
    openPrice: str | None = None
    highPrice: str | None = None
    lowPrice: str | None = None
    volume: str | None = None
    quoteVolume: str | None = None
    openTime: int | None = None
    closeTime: int | None = None
    count: int | None = None

