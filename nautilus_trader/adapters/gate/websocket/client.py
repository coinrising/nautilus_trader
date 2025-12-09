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
    req_header = {'X-Gate-Channel-Id': 'zerodivision'}

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
        self.enable_login = False
        self.running = False

        self._public_subscriptions: set[str] = set()
        self._private_subscriptions: set[str] = set()
        
        # Authentication state management
        self._is_authenticated: bool = False
        self._auth_lock: asyncio.Lock = asyncio.Lock()
        self._last_login_time: float = 0.0
        self._login_retry_count: int = 0
        self._max_login_retries: int = 3
        
        # Task management
        self._tasks: set[asyncio.Task] = set()


    @property
    def subscriptions(self) -> set:
        return self._public_subscriptions | self._private_subscriptions

    async def connect(self) -> None:
        self._client = await websockets.connect(self._base_url)
        self._log.info(f"Connected to {self._base_url}", LogColor.BLUE)
        self.running = True

        # Create and track tasks
        heartbeat_task = self._loop.create_task(self._heartbeat())
        listening_task = self._loop.create_task(self._keep_listening())
        login_task = self._loop.create_task(self._keep_login())
        
        self._tasks.update([heartbeat_task, listening_task, login_task])

    async def disconnect(self) -> None:
        self.running = False
        
        # Cancel all running tasks
        if self._tasks:
            for task in self._tasks:
                if not task.done():
                    task.cancel()
            # Wait for tasks to complete cancellation
            await asyncio.gather(*self._tasks, return_exceptions=True)
            self._tasks.clear()
        
        if self._client is not None:
            await self._client.close()
            self._client = None
        self._log.info(f"Disconnected from {self._base_url}", LogColor.BLUE)

    async def _keep_listening(self):
        while self.running:
            try:
                if self._client is None:
                    self._client = await websockets.connect(self._base_url)
                    self._log.info(f"Connected to {self._base_url}", LogColor.BLUE)
                    # Reset auth state on reconnect
                    self._is_authenticated = False
                    await self._subscribe_all()
                try:
                    # self._log.info("Waiting for message...")
                    raw = await asyncio.wait_for(self._client.recv(), timeout=5)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    # Task cancelled during recv/wait_for: exit loop quietly
                    break
                msg = json.loads(raw)
                # print(f"ws received {msg}")
                if msg.get('channel') == 'spot.pong':
                    continue
                if msg.get('error'):
                    self._log.error(f"ws received error {msg['error']}")
                    continue
                
                # Check for authentication errors in any message
                if self._check_auth_error(msg):
                    await self._handle_auth_failure()
                
                await self._handler(msg)
            except asyncio.CancelledError:
                # Task cancelled while running outer try-block: exit quietly
                break
            except:
                exception_text = traceback.format_exc()
                if not ('ConnectionClosedError' in exception_text or 'ConnectionClosedOK' in exception_text):
                    self._log.error(exception_text)
                    if self._client is not None:
                        try:
                            await self._client.close()
                        except:
                            pass
                self._client = None
                # Reset auth state on connection loss
                self._is_authenticated = False

    async def _heartbeat(self):
        while self.running:
            try:
                if self._client is not None:
                    await self._send({'channel': 'spot.ping', 'time': int(time.time())})
                    await asyncio.sleep(30)
                else:
                    await asyncio.sleep(5)
            except GeneratorExit:
                # Task is being cancelled, exit gracefully
                break
            except Exception as e:
                exception_text = traceback.format_exc()
                self._log.error(exception_text)

    async def _keep_login(self):
        next_login_time = 0
        while self.running:
            try:
                if not self.enable_login:
                    await asyncio.sleep(10)
                    continue
                if self._client is not None:
                    current_time = time.time()
                    # Login if not authenticated or if it's time for periodic refresh
                    if not self._is_authenticated or current_time > next_login_time:
                        async with self._auth_lock:
                            # Double-check after acquiring lock
                            if not self._is_authenticated or current_time > next_login_time:
                                success = await self._perform_login_with_retry()
                                if success:
                                    next_login_time = current_time + 300  # Refresh every 5 minutes
                                    self._login_retry_count = 0
                                else:
                                    # If login failed, retry more frequently
                                    next_login_time = current_time + 30
                else:
                    next_login_time = 0
                    self._is_authenticated = False
                await asyncio.sleep(60)    
            except GeneratorExit:
                # Task is being cancelled, exit gracefully
                break
            except Exception as e:
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
        # Subscribe to public channels first
        for subscription in self._public_subscriptions:
            await self._subscribe(json.loads(subscription))
        # For private channels, ensure we're authenticated first
        if self._private_subscriptions and self.enable_login:
            if not self._is_authenticated:
                self._log.warning("Not authenticated, attempting login before subscribing to private channels")
                success = await self._perform_login_with_retry()
                if not success:
                    self._log.error("Failed to authenticate, private subscriptions may fail")
        # Subscribe to private channels
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
    
    def _gen_sign_ws(self, channel, event, timestamp, req_param=""):
        # s = 'channel=%s&event=%s&time=%d' % (channel, event, timestamp)
        s = f'{event}\n{channel}\n{req_param}\n{timestamp}'
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

    async def subscribe_order_book_deltas(self, symbol: str) -> None:
        subscription = {'channel': 'spot.order_book_update', 'payload': [symbol, "20ms"]}
        await self._subscribe(subscription, True)
    
    async def unsubscribe_order_book_deltas(self, symbol: str) -> None:
        subscription = {'channel': 'spot.order_book_update', 'payload': [symbol, "20ms"]}
        await self._unsubscribe(subscription, True)

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

    async def subscribe_priceorders_update(self, symbol: str=None) -> None:
        subscription = {'channel': 'spot.priceorders', 'payload': [symbol or '!all']}
        await self._subscribe(subscription, True)


    ################################################################################
    # Authentication Management
    ################################################################################
    
    def _check_auth_error(self, msg: dict) -> bool:
        """Check if message indicates authentication failure."""
        # Check for "Not login" error in various message formats
        if isinstance(msg, dict):
            # Check in data.errs.message
            if "data" in msg and isinstance(msg["data"], dict):
                if "errs" in msg["data"]:
                    errs = msg["data"]["errs"]
                    if isinstance(errs, dict) and "message" in errs:
                        message = str(errs["message"]).lower()
                        if "not login" in message or "unauthorized" in message or "authentication" in message:
                            return True
            # Check in error field
            if "error" in msg:
                error = str(msg["error"]).lower()
                if "not login" in error or "unauthorized" in error or "authentication" in error:
                    return True
        return False
    
    async def _handle_auth_failure(self) -> None:
        """Handle authentication failure by re-authenticating and re-subscribing."""
        async with self._auth_lock:
            # Check if we're already handling auth failure (lock prevents concurrent calls)
            # If already not authenticated and recently tried, skip to avoid spam
            current_time = time.time()
            if not self._is_authenticated and (current_time - self._last_login_time) < 10:
                # Recently tried to login, skip
                return
            
            self._log.warning("Authentication failure detected, re-authenticating...")
            self._is_authenticated = False
            
            # Perform login with retry
            success = await self._perform_login_with_retry()
            if success:
                # Re-subscribe to all private channels
                self._log.info("Re-authentication successful, re-subscribing to private channels...")
                await self._resubscribe_private_channels()
            else:
                self._log.error("Failed to re-authenticate after failure")
    
    async def _perform_login_with_retry(self) -> bool:
        """Perform login with retry logic."""
        for attempt in range(self._max_login_retries):
            try:
                await self.api_login()
                # Wait a bit for login response
                await asyncio.sleep(1)
                # Note: Actual success is determined by login response handler
                # For now, we assume success if no exception is raised
                # The handler will set _is_authenticated based on response
                self._last_login_time = time.time()
                return True
            except Exception as e:
                self._login_retry_count += 1
                self._log.warning(f"Login attempt {attempt + 1}/{self._max_login_retries} failed: {e}")
                if attempt < self._max_login_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
        return False
    
    async def _resubscribe_private_channels(self) -> None:
        """Re-subscribe to all private channels after re-authentication."""
        if not self._private_subscriptions:
            return
        
        self._log.info(f"Re-subscribing to {len(self._private_subscriptions)} private channels...")
        for subscription_str in list(self._private_subscriptions):
            try:
                subscription = json.loads(subscription_str)
                await self._subscribe(subscription, need_auth=True)
                # Small delay to avoid overwhelming the server
                await asyncio.sleep(0.1)
            except Exception as e:
                self._log.error(f"Failed to re-subscribe to {subscription_str}: {e}")
    
    def set_authenticated(self, authenticated: bool) -> None:
        """Set authentication state (called by message handler)."""
        if authenticated != self._is_authenticated:
            self._is_authenticated = authenticated
            if authenticated:
                self._log.info("WebSocket authentication successful", LogColor.GREEN)
                self._login_retry_count = 0
            else:
                self._log.warning("WebSocket authentication state set to False", LogColor.YELLOW)
    
    @property
    def is_authenticated(self) -> bool:
        """Check if currently authenticated."""
        return self._is_authenticated

    # order action
    async def api_login(self) -> None:
        signature = self._gen_sign_ws("spot.login", "api", int(time.time()))
        self._log.info(f"Performing WebSocket login...", LogColor.BLUE)
        login_dict = {
            'time': int(time.time()),
            'channel': 'spot.login', 
            "event": "api",
            "payload": {
                "req_header": self.req_header,
                "req_id": f"login_{int(time.time() * 1000)}",
                "api_key": self.api_key,
                "signature": signature["SIGN"],
                "timestamp": str(int(time.time())),
            }
        }
        await self._send(login_dict)

    async def place_order(self, product_type: GateProductType, symbol: str, side: GateOrderSide, order_type: GateOrderType, quantity: str,
                          price: str=None, time_in_force: GateTimeInForce=None, client_order_id: str=None, auto_borrow: bool=False) -> None:
        PlaceOrderDict = {
            'time': int(time.time()),
            'channel': 'spot.order_place', 
            "event": "api",
            "payload": {
                "req_header": self.req_header,
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

    
