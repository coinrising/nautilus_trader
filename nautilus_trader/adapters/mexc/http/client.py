"""MEXC HTTP client implementation."""

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import urlencode

import requests

from nautilus_trader.common.component import LiveClock
from nautilus_trader.common.component import Logger
from nautilus_trader.core.nautilus_pyo3 import Quota


class MexcHttpClient:
    """
    HTTP client for MEXC API.
    
    Parameters
    ----------
    clock : LiveClock
        The clock instance.
    api_key : str
        The API key.
    api_secret : str
        The API secret.
    base_url : str
        The base URL for the HTTP API.
    recv_window_ms : int, default 5000
        The receive window in milliseconds.
    ratelimiter_quotas : list[tuple[str, Quota]] | None
        The rate limiter quotas.
    ratelimiter_default_quota : Quota | None
        The default rate limiter quota.
        
    """

    def __init__(
        self,
        clock: LiveClock,
        api_key: str,
        api_secret: str,
        base_url: str,
        recv_window_ms: int = 5_000,
        ratelimiter_quotas: list[tuple[str, Quota]] | None = None,
        ratelimiter_default_quota: Quota | None = None,
    ) -> None:
        self.clock: LiveClock = clock
        self._log: Logger = Logger(name=type(self).__name__)
        self.api_key: str = api_key
        self.api_secret: str = api_secret
        self.recv_window_ms: int = recv_window_ms
        self.base_url: str = base_url

    def _generate_signature(self, params: dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature for MEXC API."""
        query_string = urlencode(params)
        return hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _request(self, method: str, url: str, params: dict | None = None) -> Any:
        """Public API request without signature."""
        headers = {
            'Content-Type': 'application/json',
            'X-MEXC-APIKEY': self.api_key
        }
        full_url = self.base_url + url
        
        if method == 'GET':
            if params:
                full_url += '?' + urlencode(params)
            response = requests.get(full_url, headers=headers)
        else:
            response = requests.request(method, full_url, headers=headers, json=params)
        
        if response.status_code // 100 != 2:
            raise RuntimeError(
                f'MEXC request {method} {url} failed on [HTTP {response.status_code}]: {response.text}'
            )
        
        return response.json()

    def _sign_request(self, method: str, url: str, params: dict | None = None) -> Any:
        """Private API request with signature."""
        if params is None:
            params = {}
        
        params['timestamp'] = int(time.time() * 1000)
        params['recvWindow'] = self.recv_window_ms
        
        signature = self._generate_signature(params)
        params['signature'] = signature
        
        headers = {
            'Content-Type': 'application/json',
            'X-MEXC-APIKEY': self.api_key
        }
        
        full_url = self.base_url + url
        
        if method == 'GET' or method == 'DELETE':
            full_url += '?' + urlencode(params)
            response = requests.request(method, full_url, headers=headers)
        else:
            response = requests.request(method, full_url, headers=headers, json=params)
        
        if response.status_code // 100 != 2:
            raise RuntimeError(
                f'MEXC request {method} {url} failed on [HTTP {response.status_code}]: {response.text}'
            )
        
        return response.json()

    #####################
    #   Public APIs     #
    #####################

    async def fetch_exchange_info(self) -> dict:
        """Fetch exchange trading rules and symbol information."""
        return self._request('GET', '/api/v3/exchangeInfo')

    async def fetch_symbols(self) -> list[dict]:
        """Fetch all trading symbols."""
        exchange_info = await self.fetch_exchange_info()
        return exchange_info.get('symbols', [])

    #####################
    #   Private APIs    #
    #####################

    async def fetch_account_info(self) -> dict:
        """Fetch account information."""
        return self._sign_request('GET', '/api/v3/account')

    async def fetch_open_orders(self, product_type: str, symbol: str | None = None) -> list[dict]:
        """Fetch open orders."""
        params = {}
        if symbol:
            params['symbol'] = symbol
        return self._sign_request('GET', '/api/v3/openOrders', params)

    async def fetch_order_history(self, product_type: str, symbol: str) -> list[dict]:
        """Fetch order history."""
        params = {'symbol': symbol}
        return self._sign_request('GET', '/api/v3/allOrders', params)

    async def fetch_order(
        self,
        product_type: str,
        symbol: str,
        client_order_id: str | None = None,
        order_id: str | None = None
    ) -> dict:
        """Fetch specific order."""
        params = {'symbol': symbol}
        if order_id:
            params['orderId'] = order_id
        if client_order_id:
            params['origClientOrderId'] = client_order_id
        return self._sign_request('GET', '/api/v3/order', params)

    async def fetch_trade_history(self, product_type: str, symbol: str) -> list[dict]:
        """Fetch trade history."""
        params = {'symbol': symbol}
        return self._sign_request('GET', '/api/v3/myTrades', params)

    async def place_order(
        self,
        product_type: str,
        symbol: str,
        side: str,
        order_type: str,
        quantity: str,
        price: str | None = None,
        time_in_force: str | None = None,
        client_order_id: str | None = None,
    ) -> dict:
        """Place a new order."""
        params = {
            'symbol': symbol,
            'side': side,
            'type': order_type,
            'quantity': quantity,
        }
        if price:
            params['price'] = price
        if time_in_force:
            params['timeInForce'] = time_in_force
        if client_order_id:
            params['newClientOrderId'] = client_order_id
        
        return self._sign_request('POST', '/api/v3/order', params)

    async def amend_order(
        self,
        product_type: str,
        symbol: str,
        venue_order_id: str | None = None,
        client_order_id: str | None = None,
        quantity: str | None = None,
        price: str | None = None
    ) -> dict:
        """Modify an existing order."""
        # MEXC doesn't support order modification directly
        # Need to cancel and replace
        raise NotImplementedError("MEXC does not support order modification")

    async def cancel_order(
        self,
        product_type: str,
        symbol: str,
        venue_order_id: str | None = None,
        client_order_id: str | None = None
    ) -> dict:
        """Cancel an order."""
        params = {'symbol': symbol}
        if venue_order_id:
            params['orderId'] = venue_order_id
        if client_order_id:
            params['origClientOrderId'] = client_order_id
        return self._sign_request('DELETE', '/api/v3/order', params)

    async def cancel_all_orders(self, product_type: str, symbol: str) -> list[dict]:
        """Cancel all open orders for a symbol."""
        params = {'symbol': symbol}
        result = self._sign_request('DELETE', '/api/v3/openOrders', params)
        # MEXC returns a list of cancelled orders
        return result if isinstance(result, list) else [result]

    async def fetch_position_info(
        self,
        product_type: str | None = None,
        symbol: str | None = None
    ) -> list[dict]:
        """Fetch position information (account balances for spot)."""
        account_info = await self.fetch_account_info()
        return account_info.get('balances', [])

    async def fetch_wallet_balance(self) -> dict:
        """Fetch wallet balance."""
        return await self.fetch_account_info()

    async def fetch_fee_rate(self, product_type: str) -> dict:
        """Fetch trading fee rates."""
        # MEXC doesn't have a dedicated fee rate endpoint
        # Return default values or fetch from account info
        account_info = await self.fetch_account_info()
        return {
            'makerFeeRate': str(account_info.get('makerCommission', 20) / 10000),
            'takerFeeRate': str(account_info.get('takerCommission', 20) / 10000),
        }

