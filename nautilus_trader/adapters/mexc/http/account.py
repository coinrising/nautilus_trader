"""MEXC account HTTP API."""

from __future__ import annotations

from typing import Any

from nautilus_trader.common.component import LiveClock
from nautilus_trader.core.correctness import PyCondition

from nautilus_trader.adapters.mexc.common.enums import MexcOrderSide
from nautilus_trader.adapters.mexc.common.enums import MexcOrderType
from nautilus_trader.adapters.mexc.common.enums import MexcProductType
from nautilus_trader.adapters.mexc.common.enums import MexcTimeInForce
from nautilus_trader.adapters.mexc.http.client import MexcHttpClient
from nautilus_trader.adapters.mexc.schemas.account.balance import MexcAccountInfo
from nautilus_trader.adapters.mexc.schemas.account.fee_rate import MexcFeeRate
from nautilus_trader.adapters.mexc.schemas.order import (
    MexcOrder,
    MexcPlaceOrderResponse,
    MexcCancelOrderResponse,
)
from nautilus_trader.adapters.mexc.schemas.trade import MexcTrade
from nautilus_trader.adapters.mexc.schemas.position import MexcPosition


class MexcAccountHttpAPI:
    """MEXC account HTTP API handler."""

    def __init__(
        self,
        client: MexcHttpClient,
        clock: LiveClock,
    ) -> None:
        PyCondition.not_none(client, "client")
        self.client = client
        self._clock = clock

    async def query_open_orders(
        self,
        product_type: MexcProductType,
        symbol: str | None = None,
    ) -> list[MexcOrder]:
        """Query open orders."""
        open_orders = await self.client.fetch_open_orders(product_type.value, symbol)
        orders = []
        for order in open_orders:
            orders.append(MexcOrder.from_dict(order))
        return orders

    async def query_order_history(
        self,
        product_type: MexcProductType,
        symbol: str | None = None,
        open_only: bool | None = None,
    ) -> list[MexcOrder]:
        """Query order history."""
        if not symbol:
            # MEXC requires symbol for order history
            return []
        order_history = await self.client.fetch_order_history(product_type.value, symbol)
        orders = []
        for order in order_history:
            orders.append(MexcOrder.from_dict(order))
        return orders

    async def query_order(
        self,
        product_type: MexcProductType,
        symbol: str,
        client_order_id: str | None = None,
        order_id: str | None = None,
    ) -> MexcOrder:
        """Query specific order."""
        order = await self.client.fetch_order(
            product_type.value,
            symbol,
            client_order_id,
            order_id
        )
        return MexcOrder.from_dict(order)

    async def query_trade_history(
        self,
        product_type: MexcProductType,
        symbol: str,
    ) -> list[MexcTrade]:
        """Query trade history."""
        trade_history = await self.client.fetch_trade_history(product_type.value, symbol)
        trades = []
        for trade in trade_history:
            trades.append(MexcTrade(**trade))
        return trades

    async def place_order(
        self,
        product_type: MexcProductType,
        symbol: str,
        side: MexcOrderSide,
        order_type: MexcOrderType,
        quantity: str,
        price: str | None = None,
        time_in_force: MexcTimeInForce | None = None,
        client_order_id: str | None = None,
    ) -> MexcPlaceOrderResponse:
        """Place a new order."""
        resp = await self.client.place_order(
            product_type.value,
            symbol,
            side.value,
            order_type.value,
            quantity,
            price,
            time_in_force.value if time_in_force else None,
            client_order_id,
        )
        return MexcPlaceOrderResponse(**resp)

    async def cancel_order(
        self,
        product_type: MexcProductType,
        symbol: str,
        venue_order_id: str | None = None,
        client_order_id: str | None = None,
    ) -> MexcCancelOrderResponse:
        """Cancel an order."""
        resp = await self.client.cancel_order(
            product_type.value,
            symbol,
            venue_order_id,
            client_order_id
        )
        return MexcCancelOrderResponse(**resp)

    async def cancel_all_orders(
        self,
        product_type: MexcProductType,
        symbol: str,
    ) -> list[MexcCancelOrderResponse]:
        """Cancel all orders for a symbol."""
        resp = await self.client.cancel_all_orders(product_type.value, symbol)
        return [MexcCancelOrderResponse(**r) for r in resp]

    async def fetch_fee_rate(self, product_type: MexcProductType) -> MexcFeeRate:
        """Fetch fee rates."""
        resp = await self.client.fetch_fee_rate(product_type.value)
        return MexcFeeRate(**resp)

    async def fetch_position_info(
        self,
        product_type: MexcProductType | None = None,
        symbol: str | None = None,
    ) -> list[MexcPosition]:
        """Fetch position information (account balances for spot)."""
        resp = await self.client.fetch_position_info(
            product_type.value if product_type else None,
            symbol
        )
        positions = []
        for r in resp:
            positions.append(MexcPosition(
                asset=r['asset'],
                free=r['free'],
                locked=r['locked']
            ))
        return positions

    async def fetch_wallet_balance(self) -> MexcAccountInfo:
        """Fetch wallet balance."""
        resp = await self.client.fetch_wallet_balance()
        return MexcAccountInfo(**resp)

