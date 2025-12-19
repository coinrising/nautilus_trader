from __future__ import annotations

from enum import Enum
from enum import unique

from nautilus_trader.core.nautilus_pyo3 import PositionSide
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import OrderStatus
from nautilus_trader.model.enums import OrderType
from nautilus_trader.model.enums import TimeInForce
from nautilus_trader.model.enums import time_in_force_to_str


@unique
class HtxProductType(Enum):
    """HTX product types."""
    SPOT = "spot"
    LINEAR = "linear"
    INVERSE = "inverse"
    
    @property
    def is_spot(self) -> bool:
        return self == HtxProductType.SPOT
    
    @property
    def is_linear(self) -> bool:
        return self == HtxProductType.LINEAR
    
    @property
    def is_inverse(self) -> bool:
        return self == HtxProductType.INVERSE


@unique
class HtxOrderType(Enum):
    """HTX order types."""
    BUY_MARKET = "buy-market"
    SELL_MARKET = "sell-market"
    BUY_LIMIT = "buy-limit"
    SELL_LIMIT = "sell-limit"
    BUY_LIMIT_MAKER = "buy-limit-maker"
    SELL_LIMIT_MAKER = "sell-limit-maker"
    BUY_IOC = "buy-ioc"
    SELL_IOC = "sell-ioc"


@unique
class HtxOrderState(Enum):
    """HTX order states."""
    PRE_SUBMITTED = "pre-submitted"
    SUBMITTED = "submitted"
    PARTIAL_FILLED = "partial-filled"
    FILLED = "filled"
    PARTIAL_CANCELED = "partial-canceled"
    CANCELED = "canceled"


@unique
class HtxOrderSide(Enum):
    """HTX order sides."""
    BUY = "buy"
    SELL = "sell"


@unique
class HtxPositionSide(Enum):
    """HTX position sides."""
    FLAT = ""
    LONG = "long"
    SHORT = "short"
    
    def parse_to_position_side(self) -> PositionSide:
        if self == HtxPositionSide.FLAT:
            return PositionSide.FLAT
        elif self == HtxPositionSide.LONG:
            return PositionSide.LONG
        elif self == HtxPositionSide.SHORT:
            return PositionSide.SHORT
        raise RuntimeError(f"invalid position side, was {self}")


def check_dict_keys(key, data):
    try:
        return data[key]
    except KeyError as e:
        raise RuntimeError(
            f"Unrecognized HTX {key} not found in {data}",
        ) from e


class HtxEnumParser:
    """HTX enum parser for converting between HTX and Nautilus enums."""
    
    def __init__(self) -> None:
        # Order side mappings
        self.htx_to_nautilus_order_side = {
            HtxOrderSide.BUY: OrderSide.BUY,
            HtxOrderSide.SELL: OrderSide.SELL,
        }
        self.nautilus_to_htx_order_side = {
            b: a for a, b in self.htx_to_nautilus_order_side.items()
        }
        
        # Order status mappings
        self.htx_to_nautilus_order_status = {
            HtxOrderState.PRE_SUBMITTED: OrderStatus.SUBMITTED,
            HtxOrderState.SUBMITTED: OrderStatus.ACCEPTED,
            HtxOrderState.PARTIAL_FILLED: OrderStatus.PARTIALLY_FILLED,
            HtxOrderState.FILLED: OrderStatus.FILLED,
            HtxOrderState.PARTIAL_CANCELED: OrderStatus.CANCELED,
            HtxOrderState.CANCELED: OrderStatus.CANCELED,
        }
        
        # Order type mappings (simplified)
        self.nautilus_to_htx_order_type_side = {
            (OrderType.MARKET, OrderSide.BUY): HtxOrderType.BUY_MARKET,
            (OrderType.MARKET, OrderSide.SELL): HtxOrderType.SELL_MARKET,
            (OrderType.LIMIT, OrderSide.BUY): HtxOrderType.BUY_LIMIT,
            (OrderType.LIMIT, OrderSide.SELL): HtxOrderType.SELL_LIMIT,
        }
        
        # Time in force (HTX doesn't use standard TIF, embedded in order type)
        self.valid_time_in_force = {
            TimeInForce.GTC,
            TimeInForce.IOC,
            TimeInForce.FOK,
        }
    
    def parse_htx_order_side(self, order_side: HtxOrderSide) -> OrderSide:
        return check_dict_keys(order_side, self.htx_to_nautilus_order_side)
    
    def parse_nautilus_order_side(self, order_side: OrderSide) -> HtxOrderSide:
        return check_dict_keys(order_side, self.nautilus_to_htx_order_side)
    
    def parse_htx_order_status(self, order_state: HtxOrderState) -> OrderStatus:
        return check_dict_keys(order_state, self.htx_to_nautilus_order_status)
    
    def parse_nautilus_order_type_side(
        self,
        order_type: OrderType,
        order_side: OrderSide,
        post_only: bool = False,
        time_in_force: TimeInForce = TimeInForce.GTC,
    ) -> HtxOrderType:
        """Parse Nautilus order type and side to HTX order type."""
        if post_only and order_type == OrderType.LIMIT:
            return HtxOrderType.BUY_LIMIT_MAKER if order_side == OrderSide.BUY else HtxOrderType.SELL_LIMIT_MAKER
        
        if time_in_force == TimeInForce.IOC and order_type == OrderType.LIMIT:
            return HtxOrderType.BUY_IOC if order_side == OrderSide.BUY else HtxOrderType.SELL_IOC
        
        key = (order_type, order_side)
        try:
            return self.nautilus_to_htx_order_type_side[key]
        except KeyError as e:
            raise RuntimeError(
                f"Unrecognized order type/side combination: {order_type}/{order_side}",
            ) from e

