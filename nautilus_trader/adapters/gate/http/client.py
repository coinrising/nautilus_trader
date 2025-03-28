import json
import time
from typing import Any
import requests
import hashlib
import hmac

from nautilus_trader.common.component import LiveClock
from nautilus_trader.common.component import Logger
# from nautilus_trader.core.nautilus_pyo3 import HttpClient
from nautilus_trader.core.nautilus_pyo3 import Quota


class GateHttpClient:
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
        # self.recv_window_ms: int = recv_window_ms

        self.base_url: str = base_url
        # self._client = HttpClient(
        #     keyed_quotas=ratelimiter_quotas or [],
        #     default_quota=ratelimiter_default_quota,
        # )

    def _request(self, method, url, params={}):
        headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        res = requests.request(method, self.base_url + url, headers=headers, json=params)
        return res.json()

    def _gen_sign(self, method, url, query_string, payload_string):
        ts = int(time.time())
        m = hashlib.sha512()
        m.update(payload_string.encode('utf-8'))
        hashed_payload = m.hexdigest()
        s = '%s\n%s\n%s\n%s\n%s' % (method, url, query_string, hashed_payload, ts)
        sign = hmac.new(self.api_secret.encode('utf-8'), s.encode('utf-8'), hashlib.sha512).hexdigest()
        return {'KEY': self.api_key, 'Timestamp': str(ts), 'SIGN': sign}


    def _sign_request(self, method, url, params={}, payload=None):
        common_headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        if params:
            query_string = '&'.join([f'{k}={v}' for k, v in params.items()])
        else:
            query_string = ''
        if payload:
            payload_string = json.dumps(payload)
        else:
            payload_string = ''
        sign_headers = self._gen_sign(method, url, query_string, payload_string)
        sign_headers.update(common_headers)
        if query_string:
            resp = requests.request(method, self.base_url + url + '?' + query_string, headers=sign_headers, json=payload)
        else:
            resp = requests.request(method, self.base_url + url + query_string, headers=sign_headers, json=payload)
        data = resp.json()
        if resp.status_code // 100 != 2:
            raise RuntimeError(f'gate request {method} {url} failed on [HTTP {resp.status_code}]: {resp.text}')
        return data

    """
    非签名接口
    """

    async def fetch_currencie_pairs(self):
        return self._request('GET', '/api/v4/spot/currency_pairs')

    #####################
    #      签名接口      #
    #####################

    async def fetch_fee_rate(self, product_type):
        return self._sign_request('GET', '/api/v4/wallet/fee')

    async def fetch_open_orders(self, product_type, symbol):
        # https://www.gate.io/docs/developers/apiv4/zh_CN/#%E6%9F%A5%E8%AF%A2%E8%AE%A2%E5%8D%95%E5%88%97%E8%A1%A8
        params = {'status': 'open'}
        if symbol:
            params['currency_pair'] = symbol
        return self._sign_request('GET', '/api/v4/spot/orders', params)

    async def fetch_order_history(self, product_type, symbol):
        # https://www.gate.io/docs/developers/apiv4/zh_CN/#%E6%9F%A5%E8%AF%A2%E8%AE%A2%E5%8D%95%E5%88%97%E8%A1%A8
        params = {'status': 'finished'}
        if symbol:
            params['currency_pair'] = symbol
        return self._sign_request('GET', '/api/v4/spot/orders', params)

    async def fetch_trade_history(self, product_type, symbol):
        # https://www.gate.io/docs/developers/apiv4/zh_CN/#%E6%9F%A5%E8%AF%A2%E4%B8%AA%E4%BA%BA%E6%88%90%E4%BA%A4%E8%AE%B0%E5%BD%95
        params= {'currency_pair': symbol} if symbol else None
        return self._sign_request('GET', '/api/v4/spot/my_trades', params)

    async def fetch_order(self, product_type, symbol, client_order_id, order_id):
        # https://www.gate.io/docs/developers/apiv4/zh_CN/#%E6%9F%A5%E8%AF%A2%E5%8D%95%E4%B8%AA%E8%AE%A2%E5%8D%95%E8%AF%A6%E6%83%85
        params= {'currency_pair': symbol} if symbol else None
        if order_id:
            return self._sign_request('GET', f'/api/v4/spot/orders/{order_id}', params)
        else:
            return self._sign_request('GET', f'/api/v4/spot/orders/{client_order_id}', params)

    async def place_order(self, product_type, symbol, side, order_type, quantity, price, time_in_force, text, auto_borrow):
        # https://www.gate.io/docs/developers/apiv4/zh_CN/#%E4%B8%8B%E5%8D%95
        params= {
            'account': product_type,
            'currency_pair': symbol,
            'side': side,
            'type': order_type,
            'amount': quantity,
            'price': price,
            'time_in_force': time_in_force,
            'text': text,
            'auto_borrow': auto_borrow,
        }
        return self._sign_request('POST', f'/api/v4/spot/orders', payload=params)

    async def amend_order(self, product_type, symbol, venue_order_id, client_order_id, quantity, price):
        # https://www.gate.io/docs/developers/apiv4/zh_CN/#%E4%BF%AE%E6%94%B9%E5%8D%95%E4%B8%AA%E8%AE%A2%E5%8D%95
        params= {
            'currency_pair': symbol,
            'amount': quantity,
            'price': price,
        }
        return self._sign_request('PATCH', f'/api/v4/spot/orders/{venue_order_id}', payload=params)

    async def cancel_order(self, product_type, symbol, venue_order_id, client_order_id):
        # https://www.gate.io/docs/developers/apiv4/zh_CN/#%E6%92%A4%E9%94%80%E5%8D%95%E4%B8%AA%E8%AE%A2%E5%8D%95
        params= {'currency_pair': symbol} if symbol else None
        if venue_order_id:
            return self._sign_request('DELETE', f'/api/v4/spot/orders/{venue_order_id}', params)
        else:
            return self._sign_request('DELETE', f'/api/v4/spot/orders/{client_order_id}', params)

    async def cancel_all_orders(self, product_type, symbol):
        # https://www.gate.io/docs/developers/apiv4/zh_CN/#%E6%89%B9%E9%87%8F%E5%8F%96%E6%B6%88%E4%B8%80%E4%B8%AA%E4%BA%A4%E6%98%93%E5%AF%B9%E9%87%8C%E7%8A%B6%E6%80%81%E4%B8%BA-open-%E7%9A%84%E8%AE%A2%E5%8D%95
        params= {
            'account': product_type,
            'currency_pair': symbol,
        }
        return self._sign_request('DELETE', f'/api/v4/spot/orders', params)

    async def fetch_position_info(self, product_type=None, symbol=None):
        # https://www.gate.io/docs/developers/apiv4/zh_CN/#%E8%8E%B7%E5%8F%96%E7%8E%B0%E8%B4%A7%E4%BA%A4%E6%98%93%E8%B4%A6%E6%88%B7%E5%88%97%E8%A1%A8
        params= {'currency': symbol} if symbol else None
        return self._sign_request('GET', f'/api/v4/spot/accounts', params)

    async def fetch_wallet_balance(self, product_type, symbol):
        # https://www.gate.io/docs/developers/apiv4/zh_CN/#%E6%9F%A5%E8%AF%A2%E4%B8%AA%E4%BA%BA%E8%B4%A6%E6%88%B7%E6%80%BB%E9%A2%9D
        params= {'currency': 'USDT'}
        return self._sign_request('GET', f'/wallet/total_balance', params)