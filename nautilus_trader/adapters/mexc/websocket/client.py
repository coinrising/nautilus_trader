"""MEXC WebSocket client implementation."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import time
import traceback
from collections.abc import Callable
from typing import Any

import websockets

from nautilus_trader.common.component import LiveClock
from nautilus_trader.common.component import Logger
from nautilus_trader.common.enums import LogColor


class MexcWebSocketClient:
    """
    WebSocket client for MEXC.
    
    Parameters
    ----------
    clock : LiveClock
        The clock instance.
    product_type : str
        The product type.
    base_url : str
        The WebSocket base URL.
    handler : Callable[[dict], None]
        The message handler.
    api_key : str
        The API key.
    api_secret : str
        The API secret.
    loop : asyncio.AbstractEventLoop
        The event loop.
    is_private : bool, optional
        Whether this is a private connection.
    is_trade : bool, optional
        Whether this is a trade connection.
        
    """

    def __init__(
        self,
        clock: LiveClock,
        product_type: str,
        base_url: str,
        handler: Callable[[dict], None],
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
        self._handler: Callable[[dict], None] = handler
        self._loop = loop

        self.api_key = api_key
        self.api_secret = api_secret
        self.running = False
        self._client = None

        self._public_subscriptions: set[str] = set()
        self._private_subscriptions: set[str] = set()

    @property
    def subscriptions(self) -> set:
        """Get all subscriptions."""
        return self._public_subscriptions | self._private_subscriptions

    async def connect(self) -> None:
        """Connect to WebSocket."""
        self._client = await websockets.connect(self._base_url)
        self._log.info(f"Connected to {self._base_url}", LogColor.BLUE)
        self.running = True

        self._loop.create_task(self._heartbeat())
        self._loop.create_task(self._keep_listening())

    async def disconnect(self) -> None:
        """Disconnect from WebSocket."""
        if self._client is not None:
            await self._client.close()
            self._client = None
            self.running = False

    async def _keep_listening(self):
        """Keep listening for messages."""
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
                self._log.debug(f"ws received {msg}")
                
                # Handle pong messages
                if msg.get('msg') == 'pong':
                    continue
                
                # Handle error messages
                if 'code' in msg and msg['code'] != 0:
                    self._log.error(f"ws received error {msg}")
                    continue
                
                await self._handler(msg)
            except Exception:
                exception_text = traceback.format_exc()
                self._log.error(exception_text)
                if self._client is not None:
                    try:
                        await self._client.close()
                    except Exception:
                        pass
                self._client = None

    async def _heartbeat(self):
        """Send periodic heartbeat messages."""
        while self.running:
            try:
                if self._client is not None:
                    await self._send({'method': 'PING'})
                    await asyncio.sleep(20)
                else:
                    await asyncio.sleep(5)
            except Exception:
                exception_text = traceback.format_exc()
                self._log.error(exception_text)

    async def _subscribe(self, req: dict, need_auth: bool = False) -> None:
        """Subscribe to a channel."""
        req_str = json.dumps(req)
        self._log.info(f"Subscribing to {req_str}")
        
        if need_auth:
            self._private_subscriptions.add(req_str)
            # Add authentication for private channels
            req = self._add_auth(req)
        else:
            self._public_subscriptions.add(req_str)
        
        await self._send(req)

    async def _unsubscribe(self, req: dict, need_auth: bool = False) -> None:
        """Unsubscribe from a channel."""
        req_str = json.dumps(req)
        self._log.info(f"Unsubscribing from {req_str}")
        
        req['method'] = 'UNSUBSCRIPTION'
        
        if need_auth:
            self._private_subscriptions.remove(req_str)
            req = self._add_auth(req)
        else:
            self._public_subscriptions.remove(req_str)
        
        await self._send(req)

    async def _subscribe_all(self) -> None:
        """Resubscribe to all channels after reconnection."""
        if self._client is None:
            self._log.error("Cannot subscribe all: not connected")
            return
        
        for subscription in self._public_subscriptions:
            await self._subscribe(json.loads(subscription))
        for subscription in self._private_subscriptions:
            await self._subscribe(json.loads(subscription), need_auth=True)

    async def _send(self, request: dict[str, Any]) -> None:
        """Send a message."""
        text = json.dumps(request)
        if self._client is None:
            self._log.error(f"Cannot send message {text!r}: not connected")
            return
        self._log.debug(f"SENDING: {text!r}")
        try:
            await self._client.send(text)
        except Exception as e:
            self._log.error(str(e))

    def _add_auth(self, request: dict) -> dict:
        """Add authentication to request."""
        timestamp = int(time.time() * 1000)
        request['timestamp'] = timestamp
        request['apiKey'] = self.api_key
        
        # MEXC uses different auth mechanism
        # Create signature
        params_str = f"{self.api_key}{timestamp}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            params_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        request['signature'] = signature
        
        return request

    ################################################################################
    # Public
    ################################################################################

    async def subscribe_trades(self, symbol: str) -> None:
        """Subscribe to trade updates."""
        subscription = {
            'method': 'SUBSCRIPTION',
            'params': [f'spot@public.deals.v3.api@{symbol}']
        }
        await self._subscribe(subscription)

    async def unsubscribe_trades(self, symbol: str) -> None:
        """Unsubscribe from trade updates."""
        subscription = {
            'method': 'SUBSCRIPTION',
            'params': [f'spot@public.deals.v3.api@{symbol}']
        }
        await self._unsubscribe(subscription)

    async def subscribe_book_ticker(self, symbol: str) -> None:
        """Subscribe to best bid/ask updates."""
        subscription = {
            'method': 'SUBSCRIPTION',
            'params': [f'spot@public.bookTicker.v3.api@{symbol}']
        }
        await self._subscribe(subscription)

    async def unsubscribe_book_ticker(self, symbol: str) -> None:
        """Unsubscribe from best bid/ask updates."""
        subscription = {
            'method': 'SUBSCRIPTION',
            'params': [f'spot@public.bookTicker.v3.api@{symbol}']
        }
        await self._unsubscribe(subscription)

    ################################################################################
    # Private
    ################################################################################

    async def subscribe_balances_update(self) -> None:
        """Subscribe to balance updates."""
        subscription = {
            'method': 'SUBSCRIPTION',
            'params': ['spot@private.account.v3.api']
        }
        await self._subscribe(subscription, True)

    async def subscribe_orders_update(self, symbol: str | None = None) -> None:
        """Subscribe to order updates."""
        if symbol:
            subscription = {
                'method': 'SUBSCRIPTION',
                'params': [f'spot@private.orders.v3.api@{symbol}']
            }
        else:
            subscription = {
                'method': 'SUBSCRIPTION',
                'params': ['spot@private.orders.v3.api']
            }
        await self._subscribe(subscription, True)

