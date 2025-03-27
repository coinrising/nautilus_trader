from __future__ import annotations

import time
import json
import asyncio
import traceback
import websockets
from collections.abc import Callable
from typing import Any
from websockets.legacy.client import WebSocketClientProtocol

from nautilus_trader.common.component import LiveClock
from nautilus_trader.common.component import Logger
from nautilus_trader.common.enums import LogColor
from nautilus_trader.core.nautilus_pyo3 import WebSocketClientError


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
        ws_trade_timeout_secs: float | None = 5.0,
    ) -> None:
        if is_private and is_trade:
            raise ValueError("`is_private` and `is_trade` cannot both be True")

        self._clock = clock
        self._log: Logger = Logger(name=type(self).__name__)

        self._base_url: str = base_url
        self._handler: Callable[[bytes], None] = handler
        self._loop = loop
        self._ws_trade_timeout_secs = ws_trade_timeout_secs

        self._client: WebSocketClientProtocol = None
        self._api_key = api_key
        self._api_secret = api_secret
        self.running = False

        self._subscriptions: set[str] = set()

    @property
    def subscriptions(self) -> set:
        return self._subscriptions

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
                self._log.debug(f"ws received {msg['channel']}")
                if msg['channel'] == 'spot.pong':
                    continue
                await self._handler(msg)
            except:
                exception_text = traceback.format_exc()
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

    async def _subscribe(self, subscription: dict) -> None:
        sub_str = json.dumps(subscription)
        if sub_str not in self._subscriptions:
            self._log.info(f"Subscribing to {sub_str}")
            self._subscriptions.add(sub_str)
            subscription.update({'time': int(time.time()), 'event':'subscribe'})
            await self._send(subscription)

    async def _unsubscribe(self, subscription: dict) -> None:
        sub_str = json.dumps(subscription)
        if sub_str in self._subscriptions:
            self._log.info(f"Unsubscribing to {sub_str}")
            self._subscriptions.remove(sub_str)
            subscription.update({'time': int(time.time()), 'event':'unsubscribe'})
            await self._send(subscription)

    async def _subscribe_all(self) -> None:
        if self._client is None:
            self._log.error("Cannot subscribe all: not connected")
            return
        for subscription in self._subscriptions:
            await self._subscribe(json.loads(subscription))

    async def _send(self, msg: dict[str, Any]) -> None:
        await self._send_text(json.dumps(msg))

    async def _send_text(self, msg: bytes) -> None:
        if self._client is None:
            self._log.error(f"Cannot send message {msg!r}: not connected")
            return
        self._log.debug(f"SENDING: {msg!r}")
        try:
            await self._client.send(msg)
        except WebSocketClientError as e:
            self._log.error(str(e))

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

    async def subscribe_balances_update(self) -> None:
        subscription = {'channel': 'spot.balances'}
        await self._subscribe(subscription)

    async def subscribe_orders_update(self, symbol: str) -> None:
        subscription = {'channel': 'spot.orders', 'payload': [symbol]}
        await self._subscribe(subscription)

    # async def subscribe_executions_update(self) -> None:
    #     subscription = "execution"
    #     await self._subscribe(subscription)

    # async def subscribe_executions_fast_update(self) -> None:
    #     subscription = "execution.fast"
    #     await self._subscribe(subscription)

    # async def subscribe_wallet_update(self) -> None:
    #     subscription = "wallet"
    #     await self._subscribe(subscription)
