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
class MexcProductType(Enum):
    SPOT = "spot"
    LINEAR = "linear"
    INVERSE = "inverse"

    @property
    def is_spot(self) -> bool:
        return self == MexcProductType.SPOT

    @property
    def is_linear(self) -> bool:
        return self == MexcProductType.LINEAR

    @property
    def is_inverse(self) -> bool:
        return self == MexcProductType.INVERSE

@unique
class MexcPositionSide(Enum):
    FLAT = ""
    BUY = "BUY"
    SELL = "SELL"

    def parse_to_position_side(self) -> PositionSide:
        if self == MexcPositionSide.FLAT:
            return PositionSide.FLAT
        elif self == MexcPositionSide.BUY:
            return PositionSide.LONG
        elif self == MexcPositionSide.SELL:
            return PositionSide.SHORT
        raise RuntimeError(f"invalid position side, was {self}")


@unique
class MexcKlineInterval(Enum):
    MINUTE_1 = "1m"
    MINUTE_3 = "3m"
    MINUTE_5 = "5m"
    MINUTE_15 = "15m"
    MINUTE_30 = "30m"
    HOUR_1 = "1h"
    HOUR_2 = "2h"
    HOUR_4 = "4h"
    HOUR_6 = "6h"
    HOUR_12 = "12h"
    DAY_1 = "1d"
    WEEK_1 = "1w"
    MONTH_1 = "1M"


@unique
class MexcOrderStatus(Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    PARTIALLY_CANCELED = "PARTIALLY_CANCELED"


@unique
class MexcOrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


@unique
class MexcOrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    LIMIT_MAKER = "LIMIT_MAKER"


@unique
class MexcTimeInForce(Enum):
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


def check_dict_keys(key, data):
    try:
        return data[key]
    except KeyError as e:
        raise RuntimeError(
            f"Unrecognized MEXC {key} not found in {data}",
        ) from e


class MexcEnumParser:
    def __init__(self) -> None:
        self.mexc_to_nautilus_order_side = {
            MexcOrderSide.BUY: OrderSide.BUY,
            MexcOrderSide.SELL: OrderSide.SELL,
        }
        self.nautilus_to_mexc_order_side = {
            b: a for a, b in self.mexc_to_nautilus_order_side.items()
        }
        self.mexc_to_nautilus_order_type = {
            MexcOrderType.LIMIT: OrderType.LIMIT,
            MexcOrderType.MARKET: OrderType.MARKET,
            MexcOrderType.LIMIT_MAKER: OrderType.LIMIT,
        }

        self.mexc_to_nautilus_time_in_force = {
            MexcTimeInForce.GTC: TimeInForce.GTC,
            MexcTimeInForce.IOC: TimeInForce.IOC,
            MexcTimeInForce.FOK: TimeInForce.FOK,
        }
        self.nautilus_to_mexc_time_in_force = {
            TimeInForce.GTC: MexcTimeInForce.GTC,
            TimeInForce.IOC: MexcTimeInForce.IOC,
            TimeInForce.FOK: MexcTimeInForce.FOK,
        }

        # fmt: off
        self.mexc_to_nautilus_order_status = {
            MexcOrderStatus.NEW: OrderStatus.ACCEPTED,
            MexcOrderStatus.PARTIALLY_FILLED: OrderStatus.PARTIALLY_FILLED,
            MexcOrderStatus.FILLED: OrderStatus.FILLED,
            MexcOrderStatus.CANCELED: OrderStatus.CANCELED,
            MexcOrderStatus.PARTIALLY_CANCELED: OrderStatus.CANCELED,
        }

        # klines
        self.minute_klines_interval = [1, 3, 5, 15, 30]
        self.hour_klines_interval = [1, 2, 4, 6, 12]
        self.aggregation_kline_mapping = {
            BarAggregation.MINUTE: lambda x: MexcKlineInterval(f"{x}m"),
            BarAggregation.HOUR: lambda x: MexcKlineInterval(f"{x}h"),
            BarAggregation.DAY: lambda x: (
                MexcKlineInterval("1d")
                if x == 1
                else raise_error(ValueError(f"MEXC incorrect day kline interval {x}"))
            ),
            BarAggregation.WEEK: lambda x: (
                MexcKlineInterval("1w")
                if x == 1
                else raise_error(ValueError(f"MEXC incorrect week kline interval {x}"))
            ),
            BarAggregation.MONTH: lambda x: (
                MexcKlineInterval("1M")
                if x == 1
                else raise_error(ValueError(f"MEXC incorrect month kline interval {x}"))
            ),
        }
        self.valid_time_in_force = {
            TimeInForce.GTC,
            TimeInForce.IOC,
            TimeInForce.FOK,
        }

    def parse_mexc_time_in_force(self, time_in_force: MexcTimeInForce) -> TimeInForce:
        return check_dict_keys(time_in_force, self.mexc_to_nautilus_time_in_force)

    def parse_mexc_order_side(self, order_side: MexcOrderSide) -> OrderSide:
        return check_dict_keys(order_side, self.mexc_to_nautilus_order_side)

    def parse_nautilus_order_side(self, order_side: OrderSide) -> MexcOrderSide:
        return check_dict_keys(order_side, self.nautilus_to_mexc_order_side)

    def parse_mexc_order_status(self, order_status: MexcOrderStatus) -> OrderStatus:
        return check_dict_keys(order_status, self.mexc_to_nautilus_order_status)

    def parse_mexc_order_type(self, order_type: MexcOrderType) -> OrderType:
        return check_dict_keys(order_type, self.mexc_to_nautilus_order_type)

    def parse_nautilus_time_in_force(self, time_in_force: TimeInForce) -> MexcTimeInForce:
        try:
            return self.nautilus_to_mexc_time_in_force[time_in_force]
        except KeyError as e:
            raise RuntimeError(
                f"unrecognized MEXC time in force, was {time_in_force_to_str(time_in_force)}",  # pragma: no cover
            ) from e

