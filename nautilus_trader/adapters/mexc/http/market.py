"""MEXC market data HTTP API."""

from __future__ import annotations

from nautilus_trader.common.component import LiveClock
from nautilus_trader.core.correctness import PyCondition

from nautilus_trader.adapters.mexc.common.enums import MexcProductType
from nautilus_trader.adapters.mexc.http.client import MexcHttpClient
from nautilus_trader.adapters.mexc.schemas.instrument import MexcInstrument
from nautilus_trader.adapters.mexc.schemas.common import SpotLotSizeFilter, SpotPriceFilter


class MexcMarketHttpAPI:
    """MEXC market data HTTP API handler."""

    def __init__(
        self,
        client: MexcHttpClient,
        clock: LiveClock,
    ) -> None:
        PyCondition.not_none(client, "client")
        self.client = client
        self._clock = clock

    async def fetch_all_instruments(
        self,
        product_type: MexcProductType,
    ) -> list[MexcInstrument]:
        """Fetch all instruments for a product type."""
        symbols = await self.client.fetch_symbols()
        instruments = []
        
        for symbol_info in symbols:
            if symbol_info['status'] != 'ENABLED':
                continue
            
            # Extract lot size filter
            lot_size_filter = self._extract_lot_size_filter(symbol_info)
            
            # Extract price filter
            price_filter = self._extract_price_filter(symbol_info)
            
            instrument = MexcInstrument(
                symbol=symbol_info['symbol'],
                baseCoin=symbol_info['baseAsset'],
                quoteCoin=symbol_info['quoteAsset'],
                status=symbol_info['status'],
                lotSizeFilter=lot_size_filter,
                priceFilter=price_filter,
            )
            instruments.append(instrument)
        
        return instruments

    def _extract_lot_size_filter(self, symbol_info: dict) -> SpotLotSizeFilter:
        """Extract lot size filter from symbol info."""
        # Find LOT_SIZE filter
        for filter_info in symbol_info.get('filters', []):
            if filter_info['filterType'] == 'LOT_SIZE':
                return SpotLotSizeFilter(
                    basePrecision=str(symbol_info.get('baseAssetPrecision', 8)),
                    quotePrecision=str(symbol_info.get('quoteAssetPrecision', 8)),
                    minOrderQty=filter_info['minQty'],
                    maxOrderQty=filter_info['maxQty'],
                    minOrderValue='0',  # Will be updated from MIN_NOTIONAL
                )
        
        # Default if not found
        return SpotLotSizeFilter(
            basePrecision=str(symbol_info.get('baseAssetPrecision', 8)),
            quotePrecision=str(symbol_info.get('quoteAssetPrecision', 8)),
            minOrderQty='0.00000001',
            maxOrderQty='9000000000',
            minOrderValue='0',
        )

    def _extract_price_filter(self, symbol_info: dict) -> SpotPriceFilter:
        """Extract price filter from symbol info."""
        # Find PRICE_FILTER
        for filter_info in symbol_info.get('filters', []):
            if filter_info['filterType'] == 'PRICE_FILTER':
                return SpotPriceFilter(
                    tickSize=filter_info['tickSize'],
                    minPrice=filter_info.get('minPrice'),
                    maxPrice=filter_info.get('maxPrice'),
                )
        
        # Default if not found
        return SpotPriceFilter(
            tickSize='0.00000001',
            minPrice=None,
            maxPrice=None,
        )

