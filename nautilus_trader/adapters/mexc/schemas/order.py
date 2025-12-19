from decimal import Decimal

import msgspec
import random
import time

from nautilus_trader.core.datetime import millis_to_nanos
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.reports import OrderStatusReport
from nautilus_trader.model.enums import ContingencyType
from nautilus_trader.model.enums import TrailingOffsetType
from nautilus_trader.model.identifiers import AccountId
from nautilus_trader.model.identifiers import ClientOrderId
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import VenueOrderId
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity

from nautilus_trader.model.enums import OrderStatus
from nautilus_trader.adapters.mexc.common.enums import (
    MexcEnumParser,
    MexcOrderStatus,
    MexcOrderType,
    MexcOrderSide,
    MexcTimeInForce,
)


def mexc_client_order_id() -> ClientOrderId:
    """Generate a MEXC-compatible client order ID."""
    ts = int(time.time() * 1000)
    rand = '%04d' % random.randint(1, 9999)
    return ClientOrderId(f"t-{ts}-{rand}")


class MexcOrder(msgspec.Struct, omit_defaults=True, kw_only=True):
    """MEXC order schema."""
    orderId: str
    orderListId: str | None = None
    clientOrderId: str | None = None
    price: str
    origQty: str
    executedQty: str
    cummulativeQuoteQty: str
    status: MexcOrderStatus
    timeInForce: MexcTimeInForce
    type: MexcOrderType
    side: MexcOrderSide
    symbol: str
    transactTime: int | None = None
    time: int | None = None
    updateTime: int | None = None

    @staticmethod
    def from_dict(data: dict) -> 'MexcOrder':
        """Create MexcOrder from API response dictionary."""
        return MexcOrder(
            orderId=str(data['orderId']),
            orderListId=str(data.get('orderListId')) if data.get('orderListId') else None,
            clientOrderId=data.get('clientOrderId'),
            price=str(data['price']),
            origQty=str(data['origQty']),
            executedQty=str(data['executedQty']),
            cummulativeQuoteQty=str(data.get('cummulativeQuoteQty', '0')),
            status=MexcOrderStatus(data['status']),
            timeInForce=MexcTimeInForce(data['timeInForce']),
            type=MexcOrderType(data['type']),
            side=MexcOrderSide(data['side']),
            symbol=data['symbol'],
            transactTime=data.get('transactTime'),
            time=data.get('time'),
            updateTime=data.get('updateTime'),
        )

    def parse_to_order_status_report(
        self,
        account_id: AccountId,
        instrument_id: InstrumentId,
        client_order_id: ClientOrderId,
        report_id: UUID4,
        enum_parser: MexcEnumParser,
        ts_init: int,
    ) -> OrderStatusReport:
        """Parse to Nautilus OrderStatusReport."""
        order_list_id = None
        contingency_type = ContingencyType.NO_CONTINGENCY
        trailing_offset = None
        trailing_offset_type = TrailingOffsetType.NO_TRAILING_OFFSET
        
        avg_px = Decimal(0)
        if Decimal(self.executedQty) > 0 and Decimal(self.cummulativeQuoteQty) > 0:
            avg_px = Decimal(self.cummulativeQuoteQty) / Decimal(self.executedQty)
        
        order_status = enum_parser.parse_mexc_order_status(self.status)
        
        ts_last = self.updateTime or self.time or self.transactTime
        if ts_last is None:
            ts_last = int(time.time() * 1000)
        
        ts_accepted = self.time or self.transactTime or ts_last
        
        return OrderStatusReport(
            account_id=account_id,
            instrument_id=instrument_id,
            client_order_id=client_order_id,
            order_list_id=order_list_id,
            venue_order_id=VenueOrderId(str(self.orderId)),
            order_side=enum_parser.parse_mexc_order_side(self.side),
            order_type=enum_parser.parse_mexc_order_type(self.type),
            contingency_type=contingency_type,
            time_in_force=enum_parser.parse_mexc_time_in_force(self.timeInForce),
            order_status=order_status,
            price=Price.from_str(self.price),
            trailing_offset=trailing_offset,
            trailing_offset_type=trailing_offset_type,
            quantity=Quantity.from_str(self.origQty),
            filled_qty=Quantity.from_str(self.executedQty),
            avg_px=avg_px,
            post_only=self.type == MexcOrderType.LIMIT_MAKER,
            reduce_only=None,
            ts_accepted=millis_to_nanos(ts_accepted),
            ts_last=millis_to_nanos(ts_last),
            report_id=report_id,
            ts_init=ts_init,
        )


################################################################################
# Place Order Response
################################################################################

class MexcPlaceOrderResponse(msgspec.Struct):
    """MEXC place order response."""
    symbol: str
    orderId: str
    orderListId: int | None = None
    clientOrderId: str | None = None
    transactTime: int | None = None


################################################################################
# Cancel Order Response
################################################################################

class MexcCancelOrderResponse(msgspec.Struct):
    """MEXC cancel order response."""
    symbol: str
    orderId: str
    clientOrderId: str | None = None
    status: str | None = None

