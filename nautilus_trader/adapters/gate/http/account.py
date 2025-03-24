from __future__ import annotations

from typing import Any

from nautilus_trader.adapters.gate.common.enums import GateOrderSide
from nautilus_trader.adapters.gate.common.enums import GateOrderStatus
from nautilus_trader.adapters.gate.common.enums import GateOrderType
from nautilus_trader.adapters.gate.common.enums import GateProductType
from nautilus_trader.adapters.gate.common.enums import GateTimeInForce
from nautilus_trader.adapters.gate.schemas.order import GateOrder
from nautilus_trader.adapters.gate.schemas.order import GatePlaceOrder
from nautilus_trader.adapters.gate.schemas.order import GateAmendOrder
from nautilus_trader.adapters.gate.schemas.order import GateCancelOrder
from nautilus_trader.adapters.gate.schemas.order import GateCancelAllOrder
from nautilus_trader.adapters.gate.schemas.trade import GateExecution
from nautilus_trader.adapters.gate.schemas.account.fee_rate import GateFeeRate
from nautilus_trader.adapters.gate.http.client import GateHttpClient
from nautilus_trader.adapters.gate.schemas.position import GatePosition
from nautilus_trader.adapters.gate.schemas.account.balance import GateWalletBalance, GateCoinBalance
from nautilus_trader.common.component import LiveClock
from nautilus_trader.core.correctness import PyCondition


class GateAccountHttpAPI:
    client: GateHttpClient
    _clock: LiveClock
    def __init__(
        self,
        client: GateHttpClient,
        clock: LiveClock,
    ) -> None:
        PyCondition.not_none(client, "client")
        self.client = client
        self._clock = clock
        self.default_settle_coin = "USDT"

    async def query_open_orders(
        self,
        product_type: GateProductType,
        symbol: str | None = None,
    ) -> list[GateOrder]:
        open_orders = await self.client.fetch_open_orders(product_type, symbol)
        orders = []
        for order in open_orders:
            orders.append(GateOrder(orderId=order['id'], orderLinkId=order['text'], createdTime=order['create_time_ms'], updatedTime=order['update_time_ms'],
                                    symbol=order['currency_pair'], orderType=GateOrderType(order['type']), price=order['price'], qty=order['amount'],
                                    side=GateOrderSide(order['side']), orderStatus=GateOrderStatus(order['status']),
                                    timeInForce=GateTimeInForce(order['time_in_force']),
                                    cancelType=order['cancel_type'],
                                    avgPrice=order['avg_deal_price'],
                                    leavesQty=order['left'], cumExecQty=order['filled_amount'], cumExecValue=order['filled_total'],
                                    cumExecFee=order['fee'], cumExecFeeCurrency=order['fee_currency'],
                                    pointFee=order['point_fee'], gtFee=order['gt_fee'], gtMakerFee=order['gt_maker_fee'], gtTakerFee=order['gt_taker_fee'],
                                    gtDiscount=order['gt_discount'],
                                    rebatedFee=order['rebated_fee'], rebatedFeeCurrency=order['rebated_fee_currency'],
                                    account='spot', iceberg='0'))
        return orders

    async def query_order_history(
        self,
        product_type: GateProductType,
        symbol: str | None = None,
        open_only: bool | None = None,
        start_milli: int = None,
    ) -> list[GateOrder]:
        order_history = await self.client.fetch_order_history(product_type, symbol)
        orders = []
        for order in order_history:
            orders.append(GateOrder(orderId=order['id'], orderLinkId=order['text'], createdTime=order['create_time_ms'], updatedTime=order['update_time_ms'],
                                    symbol=order['currency_pair'], orderType=GateOrderType(order['type']), price=order['price'], qty=order['amount'],
                                    side=GateOrderSide(order['side']), orderStatus=GateOrderStatus(order['status']),
                                    timeInForce=GateTimeInForce(order['time_in_force']),
                                    cancelType=order['cancel_type'],
                                    avgPrice=order['avg_deal_price'],
                                    leavesQty=order['left'], cumExecQty=order['filled_amount'], cumExecValue=order['filled_total'],
                                    cumExecFee=order['fee'], cumExecFeeCurrency=order['fee_currency'],
                                    pointFee=order['point_fee'], gtFee=order['gt_fee'], gtMakerFee=order['gt_maker_fee'], gtTakerFee=order['gt_taker_fee'],
                                    gtDiscount=order['gt_discount'],
                                    rebatedFee=order['rebated_fee'], rebatedFeeCurrency=order['rebated_fee_currency'],
                                    account='spot', iceberg='0',
                                    ))
        return orders

    async def query_order(
        self,
        product_type: GateProductType,
        symbol: str | None,
        client_order_id: str | None,
        order_id: str | None,
    ) -> GateOrder:
        order = await self.client.fetch_order(product_type, symbol, order_id)
        return GateOrder(orderId=order['id'], orderLinkId=order['text'], createdTime=order['create_time_ms'], updatedTime=order['update_time_ms'],
                         symbol=order['currency_pair'], orderType=GateOrderType(order['type']), price=order['price'], qty=order['amount'],
                         side=GateOrderSide(order['side']), orderStatus=GateOrderStatus(order['status']),
                         timeInForce=GateTimeInForce(order['time_in_force']),
                         cancelType=order['cancel_type'],
                         avgPrice=order['avg_deal_price'],
                         leavesQty=order['left'], cumExecQty=order['filled_amount'], cumExecValue=order['filled_total'],
                         cumExecFee=order['fee'], cumExecFeeCurrency=order['fee_currency'],
                         pointFee=order['point_fee'], gtFee=order['gt_fee'], gtMakerFee=order['gt_maker_fee'], gtTakerFee=order['gt_taker_fee'],
                         gtDiscount=order['gt_discount'],
                         rebatedFee=order['rebated_fee'], rebatedFeeCurrency=order['rebated_fee_currency'],
                         account='spot', iceberg='0',
                         )

    async def query_trade_history(
        self,
        product_type: GateProductType,
        symbol: str | None = None,
    ) -> list[GateExecution]:
        trade_history = await self.client.fetch_trade_history(product_type, symbol)
        trades = []
        for trade in trade_history:
            trades.append(GateExecution(execId=trade['id'], orderId=trade['order_id'], side=GateOrderSide(trade['side']), execPrice=trade['price'], execQty=trade['amount'],
                                        execFee=trade['fee'], execFeeCurrency=trade['fee_currency'], execTime=trade['create_time_ms'],
                                        isMaker=(trade['role'] == 'maker'), seq=trade['seq']
                                        ))
        return trades


    async def place_order(self, product_type: GateProductType, symbol: str, side: GateOrderSide, order_type: GateOrderType, quantity: str,
                          price: str | None = None, time_in_force: GateTimeInForce | None = None, client_order_id: str | None = None) -> GatePlaceOrder:
        resp = await self.client.place_order(product_type.value, symbol, side.value, order_type.value, quantity, price, time_in_force.value, client_order_id)
        return GatePlaceOrder(orderId=resp['id'], orderLinkId=resp['text'])

    async def amend_order(self, product_type: GateProductType, symbol: str, venue_order_id: str | None = None, client_order_id: str | None = None,
                          quantity: str | None = None, price: str | None = None) -> GateAmendOrder:
        resp = await self.client.amend_order(product_type.value, symbol, venue_order_id, client_order_id, quantity, price)
        return GateAmendOrder(orderId=resp['id'], orderLinkId=resp['text'])

    async def cancel_order(self, product_type: GateProductType, symbol: str, venue_order_id: str | None = None, client_order_id: str | None = None) -> GateCancelOrder:
        resp = await self.client.cancel_order(product_type.value, symbol, venue_order_id, client_order_id)
        return GateCancelOrder(orderId=resp['id'], orderLinkId=resp['text'])

    async def cancel_all_orders(self, product_type: GateProductType, symbol: str) -> list[Any]:
        resp = await self.client.cancel_all_orders(product_type.value, symbol)
        return GateCancelAllOrder(orderId=resp['id'], orderLinkId=resp['text'])

    async def fetch_fee_rate(self, product_type: GateProductType):
        return GateFeeRate(symbol='', makerFeeRate='-0.00015', takerFeeRate='0.0002')
        resp = await self.client.fetch_fee_rate(product_type)
        return GateFeeRate(symbol='', makerFee=resp['maker_fee'], takerFee=resp['taker_fee'])

    async def fetch_position_info(self, product_type: GateProductType=None, symbol: str=None) -> list[GatePosition]:
        resp = await self.client.fetch_position_info(product_type, symbol)
        print('fetch position info:', resp)
        positions = []
        for r in resp:
            positions.append(GatePosition(symbol=r['currency'], side=r['buy'], size=r['available'], lock=r['locked']))
        return positions

    async def fetch_wallet_balance(self) -> GateWalletBalance:
        # resp = await self.client.fetch_wallet_balance()
        # print('fetch wallet balance:', resp)
        resp = await self.client.fetch_position_info()
        print('fetch position info:', resp)
        coins = []
        for r in resp:
            coins.append(GateCoinBalance(currency=r['currency'], available=r['available'], locked=r['locked'])
            )
        return GateWalletBalance(coins=coins)