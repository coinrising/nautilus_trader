from __future__ import annotations
from typing import TYPE_CHECKING

from nautilus_trader.model.data import BarType
from nautilus_trader.model.data import BookOrder
from nautilus_trader.model.data import OrderBookDelta
from nautilus_trader.model.enums import AggressorSide
from nautilus_trader.model.enums import BarAggregation
from nautilus_trader.model.enums import BookAction
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import bar_aggregation_to_str
if TYPE_CHECKING:
    from nautilus_trader.model.identifiers import InstrumentId
    from nautilus_trader.model.objects import Price
    from nautilus_trader.model.objects import Quantity
    
def parse_aggressor_side(value: str) -> AggressorSide:
    match value:
        case "buy":
            return AggressorSide.BUYER
        case "sell":
            return AggressorSide.SELLER
        case _:
            raise ValueError(f"Invalid aggressor side value, was '{value}'")

def parse_gate_delta(    
    instrument_id: InstrumentId,
    values: tuple[Price, Quantity],
    side: OrderSide,
    update_id: int,
    flags: int,
    sequence: int,
    ts_event: int,
    ts_init: int,
    snapshot: bool,
) -> OrderBookDelta:
    price = values[0]
    size = values[1]
    if snapshot:
        action = BookAction.ADD
    else:
        action = BookAction.DELETE if size == 0 else BookAction.UPDATE

    return OrderBookDelta(
        instrument_id=instrument_id,
        action=action,
        order=BookOrder(
            side=side,
            price=price,
            size=size,
            order_id=update_id,
        ),
        flags=flags,
        sequence=sequence,
        ts_event=ts_event,
        ts_init=ts_init,
    )