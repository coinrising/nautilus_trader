from __future__ import annotations

from enum import Enum
from enum import unique
from typing import TYPE_CHECKING

from nautilus_trader.core.nautilus_pyo3 import PositionSide
from nautilus_trader.model.enums import BarAggregation
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import OrderStatus
from nautilus_trader.model.enums import OrderType
from nautilus_trader.model.enums import TimeInForce
from nautilus_trader.model.enums import time_in_force_to_str


if TYPE_CHECKING:
    from nautilus_trader.model.data import BarType


def raise_error(error):
    raise error

@unique
class GateProductType(Enum):
    SPOT = "spot"
    LINEAR = "linear"
    INVERSE = "inverse"
    OPTION = "option"

    @property
    def is_spot(self) -> bool:
        return self == GateProductType.SPOT

    @property
    def is_linear(self) -> bool:
        return self == GateProductType.LINEAR

    @property
    def is_inverse(self) -> bool:
        return self == GateProductType.INVERSE

    @property
    def is_option(self) -> bool:
        return self == GateProductType.OPTION

@unique
class GatePositionIdx(Enum):
    # One-way mode position
    ONE_WAY = 0
    # Buy side of hedge-mode position
    BUY_HEDGE = 1
    # Sell side of hedge-mode position
    SELL_HEDGE = 2

@unique
class GatePositionSide(Enum):
    FLAT = ""
    BUY = "Buy"
    SELL = "Sell"

    def parse_to_position_side(self) -> PositionSide:
        if self == GatePositionSide.FLAT:
            return PositionSide.FLAT
        elif self == GatePositionSide.BUY:
            return PositionSide.LONG
        elif self == GatePositionSide.SELL:
            return PositionSide.SHORT
        raise RuntimeError(f"invalid position side, was {self}")


@unique
class GateWsOrderRequestMsgOP(Enum):
    CREATE = "order.create"
    AMEND = "order.amend"
    CANCEL = "order.cancel"


@unique
class GateKlineInterval(Enum):
    MINUTE_1 = "1"
    MINUTE_3 = "3"
    MINUTE_5 = "5"
    MINUTE_15 = "15"
    MINUTE_30 = "30"
    HOUR_1 = "60"
    HOUR_2 = "120"
    HOUR_4 = "240"
    HOUR_6 = "360"
    HOUR_12 = "720"
    DAY_1 = "D"
    WEEK_1 = "W"
    MONTH_1 = "M"


@unique
class GateOrderStatus(Enum):
    OPEN = "open"
    CLOSED = "closed"
    CANCELLED = "cancelled"


@unique
class GateOrderSide(Enum):
    UNKNOWN = ""  # It will be an empty string in some cases
    BUY = "buy"
    SELL = "sell"


@unique
class GateOrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    LIMIT_BORROW = "limit_borrow"


@unique
class GateOrderEvent(Enum):
    PUT = "put"
    UPDATE = "update"
    FINISH = "finish"


@unique
class GateOrderFinishAs(Enum):
    UNKNOWN = "-"  # Default
    OPEN = 'open'
    FILLED = 'filled'
    CANCELLED = 'cancelled'
    IOC = 'ioc'
    FOK = 'fok'
    POC = 'poc'
    SMALL = 'small'
    TRADER_NOT_ENOUGH = 'trader_not_enough'
    DEPTH_NOT_ENOUGH = 'depth_not_enough'


@unique
class GateTimeInForce(Enum):
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    POST_ONLY = "poc"


def check_dict_keys(key, data):
    try:
        return data[key]
    except KeyError as e:
        raise RuntimeError(
            f"Unrecognized Gate {key} not found in {data}",
        ) from e


class GateEnumParser:
    def __init__(self) -> None:
        self.gate_to_nautilus_order_side = {
            GateOrderSide.BUY: OrderSide.BUY,
            GateOrderSide.SELL: OrderSide.SELL,
        }
        self.nautilus_to_gate_order_side = {
            b: a for a, b in self.gate_to_nautilus_order_side.items()
        }
        self.gate_to_nautilus_order_type = {
            (GateOrderType.LIMIT): OrderType.LIMIT,
            (GateOrderType.LIMIT_BORROW): OrderType.LIMIT,
            (GateOrderType.MARKET): OrderType.MARKET,
        }

        # TODO check time in force mapping
        self.gate_to_nautilus_time_in_force = {
            GateTimeInForce.GTC: TimeInForce.GTC,
            GateTimeInForce.IOC: TimeInForce.IOC,
            GateTimeInForce.FOK: TimeInForce.FOK,
            GateTimeInForce.POST_ONLY: TimeInForce.GTC,
        }
        self.nautilus_to_gate_time_in_force = {
            TimeInForce.GTC: GateTimeInForce.GTC,
            TimeInForce.IOC: GateTimeInForce.IOC,
            TimeInForce.FOK: GateTimeInForce.FOK,
        }

        # fmt: off
        self.gate_to_nautilus_order_status = {
            (GateOrderStatus.OPEN, GateOrderFinishAs.OPEN): OrderStatus.ACCEPTED,
            (GateOrderStatus.CLOSED, GateOrderFinishAs.FILLED): OrderStatus.FILLED,
            (GateOrderStatus.CANCELLED, GateOrderFinishAs.CANCELLED): OrderStatus.CANCELED,
            (GateOrderStatus.CANCELLED, GateOrderFinishAs.IOC): OrderStatus.REJECTED,
            (GateOrderStatus.CANCELLED, GateOrderFinishAs.POC): OrderStatus.REJECTED,
            (GateOrderStatus.CANCELLED, GateOrderFinishAs.FOK): OrderStatus.REJECTED,
            (GateOrderStatus.CANCELLED, GateOrderFinishAs.SMALL): OrderStatus.REJECTED,
            (GateOrderStatus.CANCELLED, GateOrderFinishAs.TRADER_NOT_ENOUGH): OrderStatus.REJECTED,
            (GateOrderStatus.CANCELLED, GateOrderFinishAs.DEPTH_NOT_ENOUGH): OrderStatus.REJECTED,
        }

        # klines
        self.minute_klines_interval = [1, 3, 5, 15, 30]
        self.hour_klines_interval = [1, 2, 4, 6, 12]
        self.aggregation_kline_mapping = {
            BarAggregation.MINUTE: lambda x: GateKlineInterval(f"{x}"),
            BarAggregation.HOUR: lambda x: GateKlineInterval(f"{x * 60}"),
            BarAggregation.DAY: lambda x: (
                GateKlineInterval("D")
                if x == 1
                else raise_error(ValueError(f"Gate incorrect day kline interval {x}"))
            ),
            BarAggregation.WEEK: lambda x: (
                GateKlineInterval("W")
                if x == 1
                else raise_error(ValueError(f"Gate incorrect week kline interval {x}"))
            ),
            BarAggregation.MONTH: lambda x: (
                GateKlineInterval("M")
                if x == 1
                else raise_error(ValueError(f"Gate incorrect month kline interval {x}"))
            ),
        }
        self.valid_time_in_force = {
            TimeInForce.GTC,
            TimeInForce.IOC,
            TimeInForce.FOK,
        }

    def parse_gate_time_in_force(self, time_in_force: GateTimeInForce) -> TimeInForce:
        return check_dict_keys(time_in_force, self.gate_to_nautilus_time_in_force)

    def parse_gate_order_side(self, order_side: GateOrderSide) -> OrderSide:
        return check_dict_keys(order_side, self.gate_to_nautilus_order_side)

    def parse_nautilus_order_side(self, order_side: OrderSide) -> GateOrderSide:
        return check_dict_keys(order_side, self.nautilus_to_gate_order_side)

    def parse_gate_order_status(self, order_status: GateOrderStatus, order_finish_as: GateOrderFinishAs) -> OrderStatus:
        return check_dict_keys(
            (order_status, order_finish_as),
            self.gate_to_nautilus_order_status,
        )

    def parse_gate_order_type(
        self,
        order_type: GateOrderType,
    ) -> OrderType:
        return check_dict_keys(
            (order_type),
            self.gate_to_nautilus_order_type,
        )

    def parse_nautilus_time_in_force(self, time_in_force: TimeInForce) -> GateTimeInForce:
        try:
            return self.nautilus_to_gate_time_in_force[time_in_force]
        except KeyError as e:
            raise RuntimeError(
                f"unrecognized Gate time in force, was {time_in_force_to_str(time_in_force)}",  # pragma: no cover
            ) from e