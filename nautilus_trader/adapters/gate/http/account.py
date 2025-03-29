from __future__ import annotations

from typing import Any
import traceback

from nautilus_trader.common.component import LiveClock
from nautilus_trader.core.correctness import PyCondition

from nautilus_trader.adapters.gate.common.enums import GateOrderSide
from nautilus_trader.adapters.gate.common.enums import GateOrderType
from nautilus_trader.adapters.gate.common.enums import GateProductType
from nautilus_trader.adapters.gate.common.enums import GateTimeInForce
from nautilus_trader.adapters.gate.http.client import GateHttpClient
from nautilus_trader.adapters.gate.schemas.account.balance import GateWalletBalance, GateCoinBalance
from nautilus_trader.adapters.gate.schemas.account.fee_rate import GateFeeRate
from nautilus_trader.adapters.gate.schemas.order import GateOrder, GatePlaceOrder, GateAmendOrder, GateCancelOrder, GateCancelAllOrder
from nautilus_trader.adapters.gate.schemas.trade import GateExecution
from nautilus_trader.adapters.gate.schemas.position import GatePosition


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
        symbol: str=None,
    ) -> list[GateOrder]:
        open_orders = await self.client.fetch_open_orders(product_type, symbol)
        orders = []
        for order in open_orders:
            orders.append(GateOrder.from_dict(order))
        return orders

    async def query_order_history(
        self,
        product_type: GateProductType,
        symbol: str=None,
        open_only: bool=None,
        start_milli: int = None,
    ) -> list[GateOrder]:
        order_history = await self.client.fetch_order_history(product_type, symbol)
        orders = []
        for order in order_history:
            orders.append(GateOrder.from_dict(order))
        return orders

    async def query_order(
        self,
        product_type: GateProductType,
        symbol: str | None,
        client_order_id: str | None,
        order_id: str | None,
    ) -> GateOrder:
        print('query order: ', client_order_id, order_id, symbol)
        order = await self.client.fetch_order(product_type, symbol, client_order_id, order_id)
        return GateOrder.from_dict(order)

    async def query_trade_history(
        self,
        product_type: GateProductType,
        symbol: str=None,
    ) -> list[GateExecution]:
        trade_history = await self.client.fetch_trade_history(product_type, symbol)
        trades = []
        for trade in trade_history:
            trades.append(GateExecution(execId=trade['id'], orderId=trade['order_id'], clientOrderId=trade['text'],
                                        side=GateOrderSide(trade['side']), execPrice=trade['price'], execQty=trade['amount'],
                                        execFee=trade['fee'], feeCurrency=trade['fee_currency'], execTime=trade['create_time_ms'],
                                        isMaker=(trade['role'] == 'maker'), seq=trade['sequence_id']
                                        ))
        return trades


    async def place_order(self, product_type: GateProductType, symbol: str, side: GateOrderSide, order_type: GateOrderType, quantity: str,
                          price: str=None, time_in_force: GateTimeInForce=None, client_order_id: str=None, auto_borrow: bool=True) -> GatePlaceOrder:
        try:
            resp = await self.client.place_order(product_type.value, symbol, side.value, order_type.value, quantity, price, time_in_force.value, client_order_id, auto_borrow)
            return GatePlaceOrder(orderId=resp['id'], orderLinkId=resp['text'])
        except:
            exception_text = traceback.format_exc()
            if 'POC' in exception_text:
                print(f"Failed to submit [{side}-{symbol} {quantity} on {price}] due to POC: {exception_text}")
            else:
                raise

    async def amend_order(self, product_type: GateProductType, symbol: str, venue_order_id: str=None, client_order_id: str=None,
                          quantity: str=None, price: str=None) -> GateAmendOrder:
        resp = await self.client.amend_order(product_type.value, symbol, venue_order_id, client_order_id, quantity, price)
        return GateAmendOrder(orderId=resp['id'], orderLinkId=resp['text'])

    async def cancel_order(self, product_type: GateProductType, symbol: str, venue_order_id: str=None, client_order_id: str=None) -> GateCancelOrder:
        try:
            resp = await self.client.cancel_order(product_type.value, symbol, venue_order_id, client_order_id)
            return GateCancelOrder(orderId=resp['id'], orderLinkId=resp['text'])
        except Exception as e:
            exception_text = traceback.format_exc()
            if 'not found' in exception_text:
                print(f"Failed to cancel {client_order_id}({venue_order_id}) due to : {repr(e)}")
            else:
                raise


    async def cancel_all_orders(self, product_type: GateProductType, symbol: str) -> list[Any]:
        resp = await self.client.cancel_all_orders(product_type.value, symbol)
        cancel_list = []
        for c in resp:
            cancel_list.append(GateCancelOrder(orderId=c['id'], orderLinkId=c['text']))
        return GateCancelAllOrder(cancel_list)

    async def fetch_fee_rate(self, product_type: GateProductType):
        return GateFeeRate(symbol='', makerFeeRate='-0.00015', takerFeeRate='0.0002')
        resp = await self.client.fetch_fee_rate(product_type)
        return GateFeeRate(symbol='', makerFee=resp['maker_fee'], takerFee=resp['taker_fee'])

    async def fetch_position_info(self, product_type: GateProductType=None, symbol: str=None) -> list[GatePosition]:
        resp = await self.client.fetch_position_info(product_type, symbol)
        positions = []
        for r in resp:
            positions.append(GatePosition(symbol=r['currency'], side=r['buy'], size=r['available'], lock=r['locked']))
        return positions

    async def fetch_wallet_balance(self) -> GateWalletBalance:
        resp = await self.client.fetch_position_info()
        coins = []
        for r in resp:
            coins.append(GateCoinBalance(coin=r['currency'], available=r['available'], locked=r['locked'])
            )
        return GateWalletBalance(coins=coins)