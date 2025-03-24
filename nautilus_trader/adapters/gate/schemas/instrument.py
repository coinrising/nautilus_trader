import time
from decimal import Decimal

import msgspec
import pandas as pd

from nautilus_trader.adapters.gate.common.symbol import GateSymbol
from nautilus_trader.adapters.gate.schemas.account.fee_rate import GateFeeRate
from nautilus_trader.adapters.gate.schemas.common import SpotLotSizeFilter
from nautilus_trader.adapters.gate.schemas.common import SpotPriceFilter
from nautilus_trader.model.identifiers import Symbol
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.objects import Currency
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity


class GateInstrumentSpot(msgspec.Struct):
    symbol: str
    baseCoin: str
    quoteCoin: str
    # innovation: str
    status: str
    marginTrading: str
    lotSizeFilter: SpotLotSizeFilter
    priceFilter: SpotPriceFilter

    def parse_to_instrument(
        self,
        base_currency: Currency,
        quote_currency: Currency,
        fee_rate: GateFeeRate,
        ts_event: int,
        ts_init: int,
    ) -> CurrencyPair:
        assert base_currency.code == self.baseCoin
        assert quote_currency.code == self.quoteCoin
        gate_symbol = GateSymbol(self.symbol + "-SPOT")
        instrument_id = gate_symbol.to_instrument_id()
        price_increment = Price.from_str(self.priceFilter.tickSize)
        size_increment = Quantity.from_str(self.lotSizeFilter.basePrecision)
        lot_size = Quantity.from_str(self.lotSizeFilter.basePrecision)
        max_quantity = Quantity.from_str(self.lotSizeFilter.maxOrderQty)
        min_quantity = Quantity.from_str(self.lotSizeFilter.minOrderQty)

        return CurrencyPair(
            instrument_id=instrument_id,
            raw_symbol=Symbol(gate_symbol.raw_symbol),
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
            min_price=None,
            max_price=None,
            info=msgspec.json.Decoder().decode(msgspec.json.Encoder().encode(self)),
        )


def get_strike_price_from_symbol(symbol: str) -> int:
    ## symbols are in the format of ETH-3JAN23-1250-P
    ## where the strike price is 1250
    return int(symbol.split("-")[2])


GateInstrument = (GateInstrumentSpot)

GateInstrumentList = (list[GateInstrumentSpot])