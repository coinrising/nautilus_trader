import time
from decimal import Decimal

import msgspec

from nautilus_trader.adapters.mexc.common.symbol import MexcSymbol
from nautilus_trader.adapters.mexc.schemas.account.fee_rate import MexcFeeRate
from nautilus_trader.adapters.mexc.schemas.common import SpotLotSizeFilter
from nautilus_trader.adapters.mexc.schemas.common import SpotPriceFilter
from nautilus_trader.model.identifiers import Symbol
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.objects import Currency
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity


class MexcInstrumentSpot(msgspec.Struct):
    """MEXC Spot instrument schema."""
    symbol: str
    baseCoin: str
    quoteCoin: str
    status: str
    lotSizeFilter: SpotLotSizeFilter
    priceFilter: SpotPriceFilter

    def parse_to_instrument(
        self,
        base_currency: Currency,
        quote_currency: Currency,
        fee_rate: MexcFeeRate,
        ts_event: int,
        ts_init: int,
    ) -> CurrencyPair:
        """Parse MEXC instrument to Nautilus CurrencyPair."""
        assert base_currency.code == self.baseCoin
        assert quote_currency.code == self.quoteCoin
        mexc_symbol = MexcSymbol(self.symbol + "-SPOT")
        instrument_id = mexc_symbol.to_instrument_id()
        price_increment = Price.from_str(self.priceFilter.tickSize)
        size_increment = Quantity.from_str(self.lotSizeFilter.basePrecision)
        lot_size = Quantity.from_str(self.lotSizeFilter.basePrecision)
        max_quantity = Quantity.from_str(self.lotSizeFilter.maxOrderQty)
        min_quantity = Quantity.from_str(self.lotSizeFilter.minOrderQty)
        min_price = Price.from_str(self.priceFilter.minPrice) if self.priceFilter.minPrice else None
        max_price = Price.from_str(self.priceFilter.maxPrice) if self.priceFilter.maxPrice else None

        return CurrencyPair(
            instrument_id=instrument_id,
            raw_symbol=Symbol(mexc_symbol.raw_symbol),
            base_currency=base_currency,
            quote_currency=quote_currency,
            price_precision=price_increment.precision,
            size_precision=size_increment.precision,
            price_increment=price_increment,
            size_increment=size_increment,
            margin_init=Decimal("0.1"),
            margin_maint=Decimal("0.1"),
            maker_fee=Decimal(fee_rate.makerFeeRate),
            taker_fee=Decimal(fee_rate.takerFeeRate),
            ts_event=ts_event,
            ts_init=ts_init,
            lot_size=lot_size,
            max_quantity=max_quantity,
            min_quantity=min_quantity,
            min_price=min_price,
            max_price=max_price,
            info=msgspec.json.Decoder().decode(msgspec.json.Encoder().encode(self)),
        )


MexcInstrument = MexcInstrumentSpot
MexcInstrumentList = list[MexcInstrumentSpot]

