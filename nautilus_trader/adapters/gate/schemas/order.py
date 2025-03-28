from decimal import Decimal

import msgspec
import random
import time
from typing import Any

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
from nautilus_trader.adapters.gate.common.enums import GateEnumParser, GateOrderStatus, GateOrderType, GateOrderSide, GateTimeInForce, GateOrderEvent, GateOrderFinishAs


def gate_client_order_id() -> ClientOrderId:
    ts = int(time.time() * 1000)
    rand = '%04d' % random.randint(1, 9999)
    return ClientOrderId(f"t-{ts}-{rand}")

class GateOrder(msgspec.Struct, omit_defaults=True, kw_only=True):
    orderId: str  # id
    orderLinkId: str  # text
    createdTime: str  # create_time_ms
    updatedTime: str  # update_time_ms
    status: GateOrderStatus
    symbol: str  # currency_pair
    orderType: GateOrderType  # type
    price: str  # price
    qty: str  # amount
    side: GateOrderSide  # side
    timeInForce: GateTimeInForce
    finishAs: GateOrderFinishAs # open / cancelled / filled / ioc / poc / fok
    avgPrice: str | None = None  # avg_deal_price
    account: str  # spot / unified
    iceberg: str  # "iceberg": "0",

    leavesQty: str  # left
    # leavesValue: str
    cumExecQty: str  # filled_amount
    cumExecValue: str  # filled_total
    cumExecFee: str  # fee
    cumExecFeeCurrency: str  # fee_currency
    pointFee: str  # point_fee
    gtFee: str  # gt_fee": "0",
    gtMakerFee: str  # gt_maker_fee": "0",
    gtTakerFee: str  # gt_taker_fee": "0",
    gtDiscount: str  # gt_discount": false,
    rebatedFee: str  # rebated_fee": "0",
    rebatedFeeCurrency: str  # rebated_fee_currency": "USDT",

    @staticmethod
    def from_dict(order):
        return GateOrder(orderId=order['id'], orderLinkId=order['text'], createdTime=order['create_time_ms'], updatedTime=order['update_time_ms'],
                         status=GateOrderStatus(order['status']),
                         symbol=order['currency_pair'], orderType=GateOrderType(order['type']), price=order['price'], qty=order['amount'],
                         side=GateOrderSide(order['side']),
                         timeInForce=GateTimeInForce(order['time_in_force']),
                         finishAs=GateOrderFinishAs(order['finish_as']),
                         avgPrice=order.get('avg_deal_price'),
                         leavesQty=order['left'], cumExecQty=order['filled_amount'], cumExecValue=order['filled_total'],
                         cumExecFee=order['fee'], cumExecFeeCurrency=order['fee_currency'],
                         pointFee=order['point_fee'], gtFee=order['gt_fee'], gtMakerFee=order['gt_maker_fee'], gtTakerFee=order['gt_taker_fee'],
                         gtDiscount=order['gt_discount'],
                         rebatedFee=order['rebated_fee'], rebatedFeeCurrency=order['rebated_fee_currency'],
                         account=order['account'], iceberg=order.get('iceberg', '0'),
                         )

    @staticmethod
    def from_ws_dict(order):
        event = GateOrderEvent(order['event'])
        finish_as = GateOrderFinishAs(order['finish_as'])
        if event == GateOrderEvent.PUT:
            status = GateOrderStatus.OPEN
        elif event == GateOrderEvent.UPDATE:
            status = GateOrderStatus.OPEN
        elif event == GateOrderEvent.FINISH:
            if finish_as == GateOrderFinishAs.FILLED:
                status = GateOrderStatus.CLOSED
            else:
                status = GateOrderStatus.CANCELLED
        filled_amount = str(Decimal(order['amount']) - Decimal(order['left']))
        return GateOrder(orderId=order['id'], orderLinkId=order['text'], createdTime=order['create_time_ms'], updatedTime=order['update_time_ms'],
                         status=status,
                         symbol=order['currency_pair'], orderType=GateOrderType(order['type']), price=order['price'], qty=order['amount'],
                         side=GateOrderSide(order['side']), 
                         timeInForce=GateTimeInForce(order['time_in_force']),
                         finishAs=GateOrderFinishAs(order['finish_as']),
                         avgPrice=order.get('avg_deal_price'),
                         leavesQty=order['left'], cumExecQty=filled_amount, cumExecValue=order['filled_total'],
                         cumExecFee=order['fee'], cumExecFeeCurrency=order['fee_currency'],
                         pointFee=order['point_fee'], gtFee=order['gt_fee'], gtMakerFee=order.get('gt_maker_fee'), gtTakerFee=order.get('gt_taker_fee'),
                         gtDiscount=order.get('gt_discount'),
                         rebatedFee=order['rebated_fee'], rebatedFeeCurrency=order['rebated_fee_currency'],
                         account=order['account'], iceberg=order.get('iceberg', '0'),
                         )

    def parse_to_order_status_report(
        self,
        account_id: AccountId,
        instrument_id: InstrumentId,
        client_order_id: ClientOrderId,
        report_id: UUID4,
        enum_parser: GateEnumParser,
        ts_init: int,
    ) -> OrderStatusReport:
        order_list_id = None
        contingency_type = ContingencyType.NO_CONTINGENCY
        trailing_offset = None
        trailing_offset_type = TrailingOffsetType.NO_TRAILING_OFFSET
        avg_px = Decimal(self.avgPrice or 0)
        if self.status == GateOrderStatus.OPEN and Decimal(self.cumExecQty) > 0:  # 部分成交需要特判
            order_status = OrderStatus.PARTIALLY_FILLED
        else:
            order_status = enum_parser.parse_gate_order_status(self.status, self.finishAs)
        return OrderStatusReport(
            account_id=account_id,
            instrument_id=instrument_id,
            client_order_id=client_order_id,
            order_list_id=order_list_id,
            venue_order_id=VenueOrderId(str(self.orderId)),
            order_side=enum_parser.parse_gate_order_side(self.side),
            order_type=enum_parser.parse_gate_order_type(self.orderType),
            contingency_type=contingency_type,
            time_in_force=enum_parser.parse_gate_time_in_force(self.timeInForce),
            order_status=order_status,
            price=Price.from_str(self.price),
            trailing_offset=trailing_offset,
            trailing_offset_type=trailing_offset_type,
            quantity=Quantity.from_str(self.qty),
            filled_qty=Quantity.from_str(self.cumExecQty),
            avg_px=avg_px,
            post_only=self.timeInForce == GateTimeInForce.POST_ONLY,
            reduce_only=None,
            ts_accepted=millis_to_nanos(Decimal(self.createdTime)),
            ts_last=millis_to_nanos(Decimal(self.updatedTime)),
            report_id=report_id,
            ts_init=ts_init,
        )


################################################################################
# Place Order
################################################################################


class GatePlaceOrder(msgspec.Struct):
    orderId: str
    orderLinkId: str


################################################################################
# Cancel order
################################################################################
class GateCancelOrder(msgspec.Struct):
    orderId: str
    orderLinkId: str


################################################################################
# Amend order
################################################################################
class GateAmendOrder(msgspec.Struct):
    orderId: str
    orderLinkId: str

################################################################################
# Cancel all order
################################################################################
class GateCancelAllOrder(msgspec.Struct):
    cancelList: list[GateCancelOrder]

################################################################################
# Set trading stop
################################################################################
class GateSetTradingStopResponse(msgspec.Struct):
    retCode: int
    retMsg: str
    result: dict[str, Any]
    retExtInfo: dict[str, Any]
    time: int
