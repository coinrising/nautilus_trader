from collections.abc import Sequence
from decimal import Decimal
from typing import TYPE_CHECKING

import msgspec
from nautilus_trader.adapters.gate.common.parsing import parse_gate_delta

from nautilus_trader.core.datetime import millis_to_nanos
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.reports import OrderStatusReport
from nautilus_trader.model.data import Bar
from nautilus_trader.model.data import BarType
from nautilus_trader.model.data import OrderBookDelta
from nautilus_trader.model.data import OrderBookDeltas
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.data import TradeTick
from nautilus_trader.model.enums import AggressorSide
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import OrderType
from nautilus_trader.model.enums import RecordFlag
from nautilus_trader.model.enums import TrailingOffsetType
from nautilus_trader.model.identifiers import AccountId
from nautilus_trader.model.identifiers import ClientOrderId
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import TradeId
from nautilus_trader.model.identifiers import VenueOrderId
from nautilus_trader.model.objects import AccountBalance
from nautilus_trader.model.objects import Currency
from nautilus_trader.model.objects import MarginBalance
from nautilus_trader.model.objects import Money
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity

class GateWsOrderbookDepth(msgspec.Struct):
    # symbol
    s: str
    u: int
    # bids
    b: list[list[str]]
    # asks
    a: list[list[str]]
    t: int


    def parse_to_deltas(
        self,
        instrument_id: InstrumentId,
        price_precision: int | None,
        size_precision: int | None,
        ts_event: int,
        ts_init: int,
        snapshot: bool = False,
    ) -> OrderBookDeltas:
        bids_raw = [
            (
                Price(float(d[0]), price_precision),
                Quantity(float(d[1]), size_precision),
            )
            for d in self.b
        ]
        asks_raw = [
            (
                Price(float(d[0]), price_precision),
                Quantity(float(d[1]), size_precision),
            )
            for d in self.a
        ]

        deltas: list[OrderBookDelta] = []

        if snapshot:
            deltas.append(OrderBookDelta.clear(instrument_id, 0, ts_event, ts_init))

        bids_len = len(bids_raw)
        asks_len = len(asks_raw)

        for idx, bid in enumerate(bids_raw):
            flags = 0
            if idx == bids_len - 1 and asks_len == 0:
                # F_LAST, 1 << 7
                # Last message in the book event or packet from the venue for a given `instrument_id`
                flags = RecordFlag.F_LAST

            delta = parse_gate_delta(
                instrument_id=instrument_id,
                values=bid,
                side=OrderSide.BUY,
                update_id=self.u,
                flags=flags,
                sequence=self.seq,
                ts_event=ts_event,
                ts_init=ts_init,
                snapshot=snapshot,
            )
            deltas.append(delta)

        for idx, ask in enumerate(asks_raw):
            flags = 0
            if idx == asks_len - 1:
                # F_LAST, 1 << 7
                # Last message in the book event or packet from the venue for a given `instrument_id`
                flags = RecordFlag.F_LAST

            delta = parse_gate_delta(
                instrument_id=instrument_id,
                values=ask,
                side=OrderSide.SELL,
                update_id=self.u,
                flags=flags,
                sequence=self.seq,
                ts_event=ts_event,
                ts_init=ts_init,
                snapshot=snapshot,
            )
            deltas.append(delta)

        return OrderBookDeltas(instrument_id=instrument_id, deltas=deltas)

    def parse_to_quote_tick(
        self,
        instrument_id: InstrumentId,
        last_quote: QuoteTick,
        price_precision: int,
        size_precision: int,
        ts_event: int,
        ts_init: int,
    ) -> QuoteTick:
        top_bid = self.b[0] if self.b else None
        top_ask = self.a[0] if self.a else None
        top_bid_price = top_bid[0] if top_bid else None
        top_ask_price = top_ask[0] if top_ask else None
        top_bid_size = top_bid[1] if top_bid else None
        top_ask_size = top_ask[1] if top_ask else None

        if top_bid_size == "0":
            top_bid_size = None
        if top_ask_size == "0":
            top_ask_size = None

        # Convert the previous quote to new price and sizes to ensure that the precision
        # of the new Quote is consistent with the instrument definition even after
        # updates of the instrument.
        return QuoteTick(
            instrument_id=instrument_id,
            bid_price=(
                Price(float(top_bid_price), price_precision)
                if top_bid_price
                else Price(last_quote.bid_price.as_double(), price_precision)
            ),
            ask_price=(
                Price(float(top_ask_price), price_precision)
                if top_ask_price
                else Price(last_quote.ask_price.as_double(), price_precision)
            ),
            bid_size=(
                Quantity(float(top_bid_size), size_precision)
                if top_bid_size
                else Quantity(last_quote.bid_size.as_double(), size_precision)
            ),
            ask_size=(
                Quantity(float(top_ask_size), size_precision)
                if top_ask_size
                else Quantity(last_quote.ask_size.as_double(), size_precision)
            ),
            ts_event=ts_event,
            ts_init=ts_init,
        )


class GateWsOrderbookDepthMsg(msgspec.Struct):
    event: str
    channel: str
    time_ms: int
    result: GateWsOrderbookDepth


def decoder_ws_orderbook():
    return msgspec.json.Decoder(GateWsOrderbookDepthMsg)