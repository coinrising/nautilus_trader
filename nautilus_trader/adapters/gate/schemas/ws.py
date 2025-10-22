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
                sequence=0,
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
                sequence=0,
                ts_event=ts_event,
                ts_init=ts_init,
                snapshot=snapshot,
            )
            deltas.append(delta)
        if not deltas:
            return None

        return OrderBookDeltas(instrument_id=instrument_id, deltas=deltas)



class GateWsOrderbookDepthMsg(msgspec.Struct):
    event: str
    channel: str
    time_ms: int
    result: GateWsOrderbookDepth


def decoder_ws_orderbook():
    return msgspec.json.Decoder(GateWsOrderbookDepthMsg)