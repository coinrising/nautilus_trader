from decimal import Decimal
import msgspec
import random
import time

from nautilus_trader.core.datetime import millis_to_nanos
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.reports import OrderStatusReport
from nautilus_trader.model.enums import ContingencyType, TrailingOffsetType
from nautilus_trader.model.identifiers import AccountId, ClientOrderId, InstrumentId, VenueOrderId
from nautilus_trader.model.objects import Price, Quantity

from nautilus_trader.adapters.htx.common.enums import HtxEnumParser, HtxOrderState, HtxOrderType, HtxOrderSide


def htx_client_order_id() -> ClientOrderId:
    """Generate an HTX-compatible client order ID."""
    ts = int(time.time() * 1000)
    rand = '%04d' % random.randint(1, 9999)
    return ClientOrderId(f"t-{ts}-{rand}")


class HtxOrder(msgspec.Struct, omit_defaults=True, kw_only=True):
    """HTX order schema."""
    id: int  # Order ID
    symbol: str  # Trading pair
    account_id: int  # Account ID
    client_order_id: str | None = None  # Client order ID
    price: str  # Order price
    created_at: int  # Order creation time (ms)
    type: HtxOrderType  # Order type
    filled_amount: str  # Filled amount
    filled_cash_amount: str  # Filled cash amount
    filled_fees: str  # Transaction fees
    source: str  # Order source
    state: HtxOrderState  # Order state
    
    @staticmethod
    def from_dict(data: dict) -> 'HtxOrder':
        """Create HtxOrder from API response dictionary."""
        return HtxOrder(
            id=data['id'],
            symbol=data['symbol'],
            account_id=data['account-id'],
            client_order_id=data.get('client-order-id'),
            price=str(data.get('price', '0')),
            created_at=data['created-at'],
            type=HtxOrderType(data['type']),
            filled_amount=str(data.get('filled-amount', '0')),
            filled_cash_amount=str(data.get('filled-cash-amount', '0')),
            filled_fees=str(data.get('filled-fees', '0')),
            source=data['source'],
            state=HtxOrderState(data['state']),
        )
    
    def parse_to_order_status_report(
        self,
        account_id: AccountId,
        instrument_id: InstrumentId,
        client_order_id: ClientOrderId,
        report_id: UUID4,
        enum_parser: HtxEnumParser,
        ts_init: int,
    ) -> OrderStatusReport:
        """Parse to Nautilus OrderStatusReport."""
        # Calculate average price
        avg_px = Decimal(0)
        if Decimal(self.filled_amount) > 0 and Decimal(self.filled_cash_amount) > 0:
            avg_px = Decimal(self.filled_cash_amount) / Decimal(self.filled_amount)
        
        # Parse order side from type
        if 'buy' in self.type.value:
            order_side = enum_parser.parse_htx_order_side(HtxOrderSide.BUY)
        else:
            order_side = enum_parser.parse_htx_order_side(HtxOrderSide.SELL)
        
        # Determine order type
        from nautilus_trader.model.enums import OrderType as NautilusOrderType
        if 'market' in self.type.value:
            order_type = NautilusOrderType.MARKET
        else:
            order_type = NautilusOrderType.LIMIT
        
        # Parse time in force
        from nautilus_trader.model.enums import TimeInForce
        if 'ioc' in self.type.value:
            time_in_force = TimeInForce.IOC
        else:
            time_in_force = TimeInForce.GTC
        
        return OrderStatusReport(
            account_id=account_id,
            instrument_id=instrument_id,
            client_order_id=client_order_id,
            order_list_id=None,
            venue_order_id=VenueOrderId(str(self.id)),
            order_side=order_side,
            order_type=order_type,
            contingency_type=ContingencyType.NO_CONTINGENCY,
            time_in_force=time_in_force,
            order_status=enum_parser.parse_htx_order_status(self.state),
            price=Price.from_str(self.price) if self.price != '0' else None,
            trailing_offset=None,
            trailing_offset_type=TrailingOffsetType.NO_TRAILING_OFFSET,
            quantity=Quantity.from_str(self.filled_amount) if self.filled_amount != '0' else Quantity.from_str('0'),
            filled_qty=Quantity.from_str(self.filled_amount),
            avg_px=avg_px,
            post_only='maker' in self.type.value,
            reduce_only=None,
            ts_accepted=millis_to_nanos(self.created_at),
            ts_last=millis_to_nanos(self.created_at),
            report_id=report_id,
            ts_init=ts_init,
        )


class HtxPlaceOrderResponse(msgspec.Struct):
    """HTX place order response."""
    status: str
    data: str  # order-id


class HtxCancelOrderResponse(msgspec.Struct):
    """HTX cancel order response."""
    status: str
    data: str  # order-id

