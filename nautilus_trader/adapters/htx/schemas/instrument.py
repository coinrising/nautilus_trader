from decimal import Decimal

import msgspec

from nautilus_trader.adapters.htx.common.symbol import HtxSymbol
from nautilus_trader.adapters.htx.schemas.account.fee_rate import HtxFeeRate
from nautilus_trader.adapters.htx.schemas.common import SpotLotSizeFilter, SpotPriceFilter
from nautilus_trader.model.identifiers import Symbol
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.objects import Currency
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity


class HtxInstrumentSpot(msgspec.Struct):
    """HTX Spot instrument schema."""
    symbol: str  # btcusdt
    base_currency: str  # btc
    quote_currency: str  # usdt
    price_precision: int
    amount_precision: int
    value_precision: int
    min_order_amt: str
    max_order_amt: str
    min_order_value: str
    state: str  # online, offline, suspend
    
    def parse_to_instrument(
        self,
        base_currency: Currency,
        quote_currency: Currency,
        fee_rate: HtxFeeRate,
        ts_event: int,
        ts_init: int,
    ) -> CurrencyPair:
        """Parse HTX instrument to Nautilus CurrencyPair."""
        htx_symbol = HtxSymbol(self.symbol + "-SPOT")
        instrument_id = htx_symbol.to_instrument_id()
        
        price_increment = Price(10 ** (-self.price_precision), self.price_precision)
        size_increment = Quantity(10 ** (-self.amount_precision), self.amount_precision)
        
        return CurrencyPair(
            instrument_id=instrument_id,
            raw_symbol=Symbol(htx_symbol.raw_symbol.upper()),
            base_currency=base_currency,
            quote_currency=quote_currency,
            price_precision=self.price_precision,
            size_precision=self.amount_precision,
            price_increment=price_increment,
            size_increment=size_increment,
            margin_init=Decimal("0.1"),
            margin_maint=Decimal("0.1"),
            maker_fee=Decimal(fee_rate.maker_fee_rate),
            taker_fee=Decimal(fee_rate.taker_fee_rate),
            ts_event=ts_event,
            ts_init=ts_init,
            lot_size=size_increment,
            max_quantity=Quantity.from_str(self.max_order_amt),
            min_quantity=Quantity.from_str(self.min_order_amt),
            min_price=None,
            max_price=None,
            info=msgspec.json.Decoder().decode(msgspec.json.Encoder().encode(self)),
        )


HtxInstrument = HtxInstrumentSpot
HtxInstrumentList = list[HtxInstrumentSpot]

