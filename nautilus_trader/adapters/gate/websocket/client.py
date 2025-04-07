from __future__ import annotations

import time
import json
import asyncio
import traceback
import websockets
import hmac, hashlib
from collections.abc import Callable
from typing import Any

from nautilus_trader.common.component import LiveClock
from nautilus_trader.common.component import Logger
from nautilus_trader.common.enums import LogColor
from nautilus_trader.adapters.gate.common.enums import GateOrderSide
from nautilus_trader.adapters.gate.common.enums import GateOrderType
from nautilus_trader.adapters.gate.common.enums import GateProductType
from nautilus_trader.adapters.gate.common.enums import GateTimeInForce
# from nautilus_trader.adapters.gate.http.client import GateHttpClient
# from nautilus_trader.adapters.gate.schemas.account.balance import GateWalletBalance, GateCoinBalance
# from nautilus_trader.adapters.gate.schemas.account.fee_rate import GateFeeRate
# from nautilus_trader.adapters.gate.schemas.order import GateOrder, GatePlaceOrder, GateAmendOrder, GateCancelOrder, GateCancelAllOrder
# from nautilus_trader.adapters.gate.schemas.trade import GateTrade
# from nautilus_trader.adapters.gate.schemas.position import GatePosition

class GateWebSocketClient:
    def __init__(
        self,
        clock: LiveClock,
        product_type: str,
        base_url: str,
        handler: Callable[[bytes], None],
        api_key: str,
        api_secret: str,
        loop: asyncio.AbstractEventLoop,
        is_private: bool | None = False,
        is_trade: bool | None = False,
    ) -> None:
        if is_private and is_trade:
            raise ValueError("`is_private` and `is_trade` cannot both be True")

        self._log: Logger = Logger(name=type(self).__name__)

        self._base_url: str = base_url
        self._handler: Callable[[bytes], None] = handler
        self._loop = loop

        self.api_key = api_key
        self.api_secret = api_secret
        self.running = False

        self._public_subscriptions: set[str] = set()
        self._private_subscriptions: set[str] = set()

    @property
    def subscriptions(self) -> set:
        return self._public_subscriptions | self._private_subscriptions

    async def connect(self) -> None:
        self._client = await websockets.connect(self._base_url)
        self._log.info(f"Connected to {self._base_url}", LogColor.BLUE)
        self.running = True

        self._loop.create_task(self._heartbeat())
        self._loop.create_task(self._keep_listening())

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
            self.running = False

    async def _keep_listening(self):
        while self.running:
            try:
                if self._client is None:
                    self._client = await websockets.connect(self._base_url)
                    self._log.info(f"Connected to {self._base_url}", LogColor.BLUE)
                    await self._subscribe_all()
                try:
                    raw = await asyncio.wait_for(self._client.recv(), timeout=5)
                except asyncio.TimeoutError:
                    continue
                msg = json.loads(raw)
                print(f"ws received {msg}")
                if msg['channel'] == 'spot.pong':
                    continue
                if msg.get('error'):
                    self._log.error(f"ws received error {msg['error']}")
                    continue
                await self._handler(msg)
            except:
                exception_text = traceback.format_exc()
                if 'ConnectionClosedError' not in exception_text:
                    self._log.error(exception_text)
                    if self._client is not None:
                        try:
                            await self._client.close()
                        except:
                            pass
                self._client = None

    async def _heartbeat(self):
        while self.running:
            try:
                if self._client is not None:
                    await self._send({'channel': 'spot.ping', 'time': int(time.time())})
                    await asyncio.sleep(30)
                else:
                    await asyncio.sleep(5)
            except:
                exception_text = traceback.format_exc()
                self._log.error(exception_text)

    async def _subscribe(self, req: dict, need_auth: bool=False) -> None:
        req_str = json.dumps(req)
        self._log.info(f"Subscribing to {req_str}")
        req.update({'time': int(time.time()), 'event':'subscribe'})
        if need_auth:
            self._private_subscriptions.add(req_str)
            req['auth'] = self._gen_sign(req['channel'], req['event'], req['time'])
        else:
            self._public_subscriptions.add(req_str)
        await self._send(req)

    async def _unsubscribe(self, req: dict, need_auth: bool=False) -> None:
        req_str = json.dumps(req)
        self._log.info(f"Unsubscribing to {req_str}")
        req.update({'time': int(time.time()), 'event':'unsubscribe'})
        if need_auth:
            self._private_subscriptions.remove(req_str)
            req['auth'] = self._gen_sign(req['channel'], req['event'], req['time'])
        else:
            self._public_subscriptions.remove(req_str)
        await self._send(req)

    async def _subscribe_all(self) -> None:
        if self._client is None:
            self._log.error("Cannot subscribe all: not connected")
            return
        for subscription in self._public_subscriptions:
            await self._subscribe(json.loads(subscription))
        for subscription in self._private_subscriptions:
            await self._subscribe(json.loads(subscription), need_auth=True)

    async def _send(self, request: dict[str, Any]) -> None:
        text = json.dumps(request)
        if self._client is None:
            self._log.error(f"Cannot send message {text!r}: not connected")
            return
        self._log.debug(f"SENDING: {text!r}")
        try:
            await self._client.send(text)
        except Exception as e:
            self._log.error(str(e))

    def _gen_sign(self, channel, event, timestamp):
        s = 'channel=%s&event=%s&time=%d' % (channel, event, timestamp)
        sign = hmac.new(self.api_secret.encode('utf-8'), s.encode('utf-8'), hashlib.sha512).hexdigest()
        return {'method': 'api_key', 'KEY': self.api_key, 'SIGN': sign}

    ################################################################################
    # Public
    ################################################################################

    async def subscribe_trades(self, symbol: str) -> None:
        subscription = {'channel': 'spot.trades', 'payload': [symbol]}
        await self._subscribe(subscription)

    async def unsubscribe_trades(self, symbol: str) -> None:
        subscription = {'channel': 'spot.trades', 'payload': [symbol]}
        await self._unsubscribe(subscription)

    async def subscribe_book_ticker(self, symbol: str) -> None:
        subscription = {'channel': 'spot.book_ticker', 'payload': [symbol]}
        await self._subscribe(subscription)

    async def unsubscribe_book_ticker(self, symbol: str) -> None:
        subscription = {'channel': 'spot.book_ticker', 'payload': [symbol]}
        await self._unsubscribe(subscription)

    ################################################################################
    # Private
    ################################################################################
    # status update
    async def subscribe_balances_update(self) -> None:
        subscription = {'channel': 'spot.balances'}
        await self._subscribe(subscription, True)

    async def subscribe_orders_update(self, symbol: str=None) -> None:
        subscription = {'channel': 'spot.orders', 'payload': [symbol or '!all']}
        await self._subscribe(subscription, True)

    async def subscribe_trades_update(self, symbol: str=None) -> None:
        subscription = {'channel': 'spot.usertrades', 'payload': [symbol or '!all']}
        await self._subscribe(subscription, True)

    # order action
    async def api_login(self) -> None:
        login_dict = {
            'time': int(time.time()),
            'channel': 'spot.login', 
            "event": "api",
            "payload": {
                "req_id": f"login_{int(time.time() * 1000)}",
                "api_key": self.api_key,
                "signature": self._gen_sign("spot.login", "api", int(time.time())),
                "timestamp": str(int(time.time())),
            }
        }
        await self._send(login_dict)

    async def place_order(self, product_type: GateProductType, symbol: str, side: GateOrderSide, order_type: GateOrderType, quantity: str,
                          price: str=None, time_in_force: GateTimeInForce=None, client_order_id: str=None, auto_borrow: bool=True) -> None:
        PlaceOrderDict = {
            'time': int(time.time()),
            'channel': 'spot.order_place', 
            "event": "api",
            "payload": {
                "req_id": str(time.time()),
                'req_param': {
                    'account': product_type.value,
                    'currency_pair': symbol,
                    'side': side.value,
                    'type': order_type.value,
                    'amount': quantity,
                    'price': price,
                    'time_in_force': time_in_force.value,
                    'text': client_order_id,
                    'auto_borrow': auto_borrow,
                    "auto_repay": False,
                }
            }
        }
        await self._send(PlaceOrderDict)

    async def cancel_order(self, product_type: GateProductType, symbol: str, venue_order_id: str=None, client_order_id: str=None) -> None:
        CancelOrderDict = {
            'time': int(time.time()),
            'channel': 'spot.order_cancel', 
            "event": "api",
            "payload": {
                "req_id": str(time.time()),
                'req_param': {
                    "currency_pair": symbol,
                    "order_id": venue_order_id if venue_order_id else client_order_id,
                }
            }
        }
        await self._send(CancelOrderDict)

    
