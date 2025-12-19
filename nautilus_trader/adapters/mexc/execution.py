"""MEXC execution client implementation."""

from __future__ import annotations

import asyncio
import time
import traceback

from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import LiveClock
from nautilus_trader.common.component import MessageBus
from nautilus_trader.common.enums import LogColor
from nautilus_trader.common.enums import LogLevel
from nautilus_trader.core.datetime import millis_to_nanos
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.messages import CancelAllOrders
from nautilus_trader.execution.messages import CancelOrder
from nautilus_trader.execution.messages import GenerateFillReports
from nautilus_trader.execution.messages import GenerateOrderStatusReport
from nautilus_trader.execution.messages import GenerateOrderStatusReports
from nautilus_trader.execution.messages import GeneratePositionStatusReports
from nautilus_trader.execution.messages import SubmitOrder
from nautilus_trader.execution.reports import FillReport
from nautilus_trader.execution.reports import OrderStatusReport
from nautilus_trader.execution.reports import PositionStatusReport
from nautilus_trader.live.execution_client import LiveExecutionClient
from nautilus_trader.live.retry import RetryManagerPool
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.enums import OrderType
from nautilus_trader.model.enums import TimeInForce
from nautilus_trader.model.enums import LiquiditySide
from nautilus_trader.model.enums import account_type_to_str
from nautilus_trader.model.identifiers import AccountId
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.model.identifiers import ClientOrderId
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import VenueOrderId
from nautilus_trader.model.orders import LimitOrder
from nautilus_trader.model.orders import Order
from nautilus_trader.model.objects import Money
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity

from nautilus_trader.adapters.mexc.common.constants import MEXC_VENUE
from nautilus_trader.adapters.mexc.common.enums import MexcEnumParser
from nautilus_trader.adapters.mexc.common.enums import MexcOrderType
from nautilus_trader.adapters.mexc.common.enums import MexcProductType
from nautilus_trader.adapters.mexc.common.enums import MexcTimeInForce
from nautilus_trader.adapters.mexc.common.symbol import MexcSymbol
from nautilus_trader.adapters.mexc.config import MexcExecClientConfig
from nautilus_trader.adapters.mexc.http.account import MexcAccountHttpAPI
from nautilus_trader.adapters.mexc.http.client import MexcHttpClient
from nautilus_trader.adapters.mexc.http.errors import MexcError
from nautilus_trader.adapters.mexc.http.errors import should_retry
from nautilus_trader.adapters.mexc.providers import MexcInstrumentProvider
from nautilus_trader.adapters.mexc.schemas.order import MexcOrder
from nautilus_trader.adapters.mexc.websocket.client import MexcWebSocketClient


class MexcExecutionClient(LiveExecutionClient):
    """
    Live execution client for MEXC.
    
    Parameters
    ----------
    loop : asyncio.AbstractEventLoop
        The event loop.
    client : MexcHttpClient
        The HTTP client.
    msgbus : MessageBus
        The message bus.
    cache : Cache
        The cache.
    clock : LiveClock
        The clock.
    instrument_provider : MexcInstrumentProvider
        The instrument provider.
    product_types : list[MexcProductType]
        The product types.
    config : MexcExecClientConfig
        The configuration.
    name : str, optional
        The client name.
        
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        client: MexcHttpClient,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
        instrument_provider: MexcInstrumentProvider,
        product_types: list[MexcProductType],
        config: MexcExecClientConfig,
        name: str | None,
    ) -> None:
        if MexcProductType.SPOT in product_types:
            if len(set(product_types)) > 1:
                raise ValueError("Cannot configure SPOT with other product types")
            account_type = AccountType.CASH
        else:
            account_type = AccountType.MARGIN

        super().__init__(
            loop=loop,
            client_id=ClientId(name or MEXC_VENUE.value),
            venue=MEXC_VENUE,
            oms_type=OmsType.NETTING,
            instrument_provider=instrument_provider,
            account_type=account_type,
            base_currency=None,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
        )

        # Configuration
        self._product_types = product_types

        self._log.info(f"Account type: {account_type_to_str(account_type)}", LogColor.BLUE)
        self._log.info(f"Product types: {[p.value for p in product_types]}", LogColor.BLUE)
        self._log.info(f"{config.max_retries=}", LogColor.BLUE)
        self._log.info(f"{config.retry_delay=}", LogColor.BLUE)
        self._log.info(f"{config.recv_window_ms=:_}", LogColor.BLUE)

        self._enum_parser = MexcEnumParser()

        account_id = AccountId(f"{name or MEXC_VENUE.value}-SPOT")
        self._set_account_id(account_id)

        # HTTP API
        self._http_clt = MexcAccountHttpAPI(
            client=client,
            clock=clock,
        )

        # WebSocket API
        self._ws_clients: dict[MexcProductType, MexcWebSocketClient] = {}
        for product_type in set(product_types):
            self._ws_clients[product_type] = MexcWebSocketClient(
                clock=clock,
                product_type=product_type,
                base_url=config.base_urls_ws[product_type],
                handler=self._handle_ws_message,
                api_key=config.api_key,
                api_secret=config.api_secret,
                loop=loop,
            )

        # Order submission
        self._submit_order_methods = {
            OrderType.LIMIT: self._submit_limit_order,
            OrderType.MARKET: self._submit_market_order,
        }

        # Hot caches
        self._instrument_ids: dict[str, InstrumentId] = {}

        self._retry_manager_pool = RetryManagerPool[None](
            pool_size=100,
            max_retries=config.max_retries or 0,
            retry_delay_secs=config.retry_delay or 0.0,
            logger=self._log,
            exc_types=(MexcError,),
            retry_check=should_retry,
        )

    async def _connect(self) -> None:
        """Connect to the execution client."""
        await self._instrument_provider.initialize()
        await self._update_account_state()

        for ws_client in self._ws_clients.values():
            await ws_client.connect()
            await ws_client.subscribe_balances_update()
            await ws_client.subscribe_orders_update()

    async def _disconnect(self):
        """Disconnect from the execution client."""
        for ws_client in self._ws_clients.values():
            await ws_client.disconnect()

    def _stop(self) -> None:
        """Stop the execution client."""
        self._retry_manager_pool.shutdown()

    # -- EXECUTION REPORTS ------------------------------------------------------------------------

    async def generate_order_status_reports(
        self,
        command: GenerateOrderStatusReports,
    ) -> list[OrderStatusReport]:
        """Generate order status reports."""
        instrument_id = command.instrument_id

        self._log.debug("Requesting OrderStatusReports...")
        reports: list[OrderStatusReport] = []

        try:
            _symbol = instrument_id.symbol.value if instrument_id is not None else None
            symbol = MexcSymbol(_symbol) if _symbol is not None else None
            for product_type in self._product_types:
                if command.open_only:
                    mexc_orders = await self._http_clt.query_open_orders(
                        product_type,
                        symbol.raw_symbol if symbol else None,
                    )
                else:
                    if not symbol:
                        continue  # MEXC requires symbol for history
                    mexc_orders = await self._http_clt.query_order_history(
                        product_type,
                        symbol.raw_symbol,
                    )
                
                for order in mexc_orders:
                    mexc_symbol = MexcSymbol(order.symbol + f"-{product_type.value.upper()}")
                    client_order_id = ClientOrderId(order.clientOrderId) if order.clientOrderId else None
                    if client_order_id is None:
                        client_order_id = self._cache.client_order_id(VenueOrderId(order.orderId))
                    
                    report = order.parse_to_order_status_report(
                        client_order_id=client_order_id,
                        account_id=self.account_id,
                        instrument_id=mexc_symbol.to_instrument_id(),
                        report_id=UUID4(),
                        enum_parser=self._enum_parser,
                        ts_init=self._clock.timestamp_ns(),
                    )
                    reports.append(report)
                    self._log.debug(f"Received {report}", LogColor.MAGENTA)
        except Exception:
            exception_text = traceback.format_exc()
            self._log.error(f"Failed to generate OrderStatusReports: {exception_text}")

        len_reports = len(reports)
        plural = "" if len_reports == 1 else "s"
        receipt_log = f"Received {len(reports)} OrderStatusReport{plural}"

        if command.log_receipt_level == LogLevel.INFO:
            self._log.info(receipt_log)
        else:
            self._log.debug(receipt_log)

        return reports

    async def generate_order_status_report(
        self,
        command: GenerateOrderStatusReport,
    ) -> OrderStatusReport | None:
        """Generate single order status report."""
        instrument_id = command.instrument_id
        client_order_id = command.client_order_id
        venue_order_id = command.venue_order_id

        self._log.info(
            f"Generating OrderStatusReport for {repr(client_order_id) if client_order_id else ''} {repr(venue_order_id) if venue_order_id else ''}",
        )
        
        try:
            mexc_symbol = MexcSymbol(instrument_id.symbol.value)
            product_type = mexc_symbol.product_type
            target_order = await self._http_clt.query_order(
                product_type=product_type,
                symbol=mexc_symbol.raw_symbol,
                client_order_id=client_order_id.value if client_order_id else None,
                order_id=venue_order_id.value if venue_order_id else None,
            )
            
            if target_order.clientOrderId:
                client_order_id = ClientOrderId(target_order.clientOrderId)
            venue_order_id = VenueOrderId(target_order.orderId)
            if client_order_id is None:
                client_order_id = self._cache.client_order_id(venue_order_id)

            order_report = target_order.parse_to_order_status_report(
                client_order_id=client_order_id,
                account_id=self.account_id,
                instrument_id=instrument_id,
                report_id=UUID4(),
                enum_parser=self._enum_parser,
                ts_init=self._clock.timestamp_ns(),
            )
            self._log.debug(f"Received {order_report}", LogColor.MAGENTA)
            return order_report
        except Exception:
            exception_text = traceback.format_exc()
            self._log.error(f"Failed to generate OrderStatusReport: {exception_text}")
        return None

    async def generate_fill_reports(
        self,
        command: GenerateFillReports,
    ) -> list[FillReport]:
        """Generate fill reports."""
        instrument_id = command.instrument_id

        self._log.debug("Requesting FillReports...")
        reports: list[FillReport] = []
        if instrument_id is None:
            return reports

        try:
            mexc_symbol = MexcSymbol(instrument_id.symbol.value)
            for product_type in self._product_types:
                mexc_fills = await self._http_clt.query_trade_history(
                    product_type,
                    mexc_symbol.raw_symbol,
                )
                for fill in mexc_fills:
                    report = fill.parse_to_fill_report(
                        account_id=self.account_id,
                        instrument_id=mexc_symbol.to_instrument_id(),
                        report_id=UUID4(),
                        enum_parser=self._enum_parser,
                        ts_init=self._clock.timestamp_ns(),
                    )
                    reports.append(report)
                    self._log.debug(f"Received {report}")
        except Exception:
            exception_text = traceback.format_exc()
            self._log.error(f"Failed to generate FillReports: {repr(exception_text)}")

        len_reports = len(reports)
        plural = "" if len_reports == 1 else "s"
        self._log.info(f"Received {len(reports)} FillReport{plural}")

        return reports

    async def generate_position_status_reports(
        self,
        command: GeneratePositionStatusReports,
    ) -> list[PositionStatusReport]:
        """Generate position status reports (for spot, returns empty list)."""
        self._log.debug("Requesting PositionStatusReports...")
        # For spot trading, we don't have positions in the derivatives sense
        return []

    def _get_cached_instrument_id(
        self,
        symbol: str,
        product_type: MexcProductType,
    ) -> InstrumentId:
        """Get cached instrument ID."""
        mexc_symbol = MexcSymbol(f"{symbol}-{product_type.value.upper()}")
        return mexc_symbol.to_instrument_id()

    def _determine_time_in_force(self, order: Order) -> MexcTimeInForce:
        """Determine time in force for order."""
        time_in_force: TimeInForce = order.time_in_force
        if order.is_post_only:
            return MexcTimeInForce.GTC  # MEXC uses LIMIT_MAKER for post-only
        return self._enum_parser.parse_nautilus_time_in_force(time_in_force)

    async def _update_account_state(self) -> None:
        """Update account state."""
        balance = await self._http_clt.fetch_wallet_balance()
        ts = time.time() * 1000
        balances = balance.parse_to_account_balances()
        try:
            self.generate_account_state(
                balances=balances,
                margins=[],
                reported=True,
                ts_event=millis_to_nanos(ts),
            )
        except Exception:
            exception_text = traceback.format_exc()
            self._log.error(f"Failed to generate AccountState: {repr(exception_text)}")

    # -- COMMAND HANDLERS -------------------------------------------------------------------------

    async def _submit_order(self, command: SubmitOrder) -> None:
        """Submit an order."""
        order = command.order

        if order.is_closed:
            self._log.warning(f"Order {order} is already closed")
            return

        mexc_symbol = MexcSymbol(command.instrument_id.symbol.value)
        if not self._check_order_validity(order, mexc_symbol.product_type):
            return

        # Generate order submitted event
        self.generate_order_submitted(
            strategy_id=order.strategy_id,
            instrument_id=order.instrument_id,
            client_order_id=order.client_order_id,
            ts_event=self._clock.timestamp_ns(),
        )

        async with self._retry_manager_pool as retry_manager:
            await retry_manager.run(
                "submit_order",
                [order.client_order_id],
                self._submit_order_methods[order.order_type],
                order,
            )
            if not retry_manager.result:
                self.generate_order_rejected(
                    strategy_id=order.strategy_id,
                    instrument_id=order.instrument_id,
                    client_order_id=order.client_order_id,
                    reason=retry_manager.message,
                    ts_event=self._clock.timestamp_ns(),
                )

    async def _submit_limit_order(self, order: LimitOrder) -> None:
        """Submit a limit order."""
        mexc_symbol = MexcSymbol(order.instrument_id.symbol.value)
        time_in_force = self._determine_time_in_force(order)
        order_side = self._enum_parser.parse_nautilus_order_side(order.side)
        order_type = MexcOrderType.LIMIT_MAKER if order.is_post_only else MexcOrderType.LIMIT
        
        return await self._http_clt.place_order(
            product_type=mexc_symbol.product_type,
            symbol=mexc_symbol.raw_symbol,
            side=order_side,
            order_type=order_type,
            quantity=str(order.quantity),
            price=str(order.price),
            time_in_force=time_in_force,
            client_order_id=str(order.client_order_id),
        )

    async def _submit_market_order(self, order: Order) -> None:
        """Submit a market order."""
        mexc_symbol = MexcSymbol(order.instrument_id.symbol.value)
        order_side = self._enum_parser.parse_nautilus_order_side(order.side)
        
        return await self._http_clt.place_order(
            product_type=mexc_symbol.product_type,
            symbol=mexc_symbol.raw_symbol,
            side=order_side,
            order_type=MexcOrderType.MARKET,
            quantity=str(order.quantity),
            client_order_id=str(order.client_order_id),
        )

    # -- WEBSOCKET HANDLERS -----------------------------------------------------------------------

    async def _handle_ws_message(self, msg: dict) -> None:
        """Handle WebSocket message."""
        try:
            # MEXC WebSocket handles order updates and account updates
            if 'c' in msg:  # Channel
                channel = msg['c']
                if 'account' in channel:
                    await self._update_account_state()
                elif 'orders' in channel:
                    self._handle_account_order_update(msg)
        except Exception:
            exception_text = traceback.format_exc()
            self._log.error(f"Failed to handle websocket msg {msg} with: {exception_text}")

    def _handle_account_order_update(self, msg: dict) -> None:
        """Handle account order update."""
        try:
            data = msg.get('d', {})
            # Implementation depends on MEXC's actual WebSocket order update format
            # This is a placeholder
            self._log.info(f"Order update received: {data}")
        except Exception:
            exception_text = traceback.format_exc()
            self._log.error(f'Failed to handle order update: {exception_text}')

    # -- PRIVATE FUNCTIONS ------------------------------------------------------------------------

    def _check_order_validity(self, order: Order, product_type: MexcProductType) -> bool:
        """Check order validity."""
        # Check post only
        if order.is_post_only and order.order_type != OrderType.LIMIT:
            self._log.error(
                f"Cannot submit {order} has invalid post only {order.is_post_only}, unsupported on MEXC",
            )
            return False

        return True

    async def _cancel_order(self, command: CancelOrder) -> None:
        """Cancel an order."""
        order: Order | None = self._cache.order(command.client_order_id)
        if order is None:
            self._log.error(f"{command.client_order_id!r} not found in cache")
            return

        if order.is_closed:
            self._log.warning(
                f"`CancelOrder` command for {command.client_order_id!r} when order already {order.status_string()} (will not send to exchange)",
            )
            return

        symbol = MexcSymbol(command.instrument_id.symbol.value)
        client_order_id = command.client_order_id.value
        venue_order_id = str(command.venue_order_id) if command.venue_order_id else None

        async with self._retry_manager_pool as retry_manager:
            await retry_manager.run(
                "cancel_order",
                [client_order_id, venue_order_id],
                self._http_clt.cancel_order,
                symbol.product_type,
                symbol.raw_symbol,
                venue_order_id=venue_order_id,
                client_order_id=client_order_id,
            )
            if not retry_manager.result:
                self.generate_order_cancel_rejected(
                    order.strategy_id,
                    order.instrument_id,
                    order.client_order_id,
                    order.venue_order_id,
                    retry_manager.message,
                    self._clock.timestamp_ns(),
                )

    async def _cancel_all_orders(self, command: CancelAllOrders) -> None:
        """Cancel all orders."""
        mexc_symbol = MexcSymbol(command.instrument_id.symbol.value)

        async with self._retry_manager_pool as retry_manager:
            await retry_manager.run(
                "cancel_all_orders",
                None,
                self._http_clt.cancel_all_orders,
                product_type=mexc_symbol.product_type,
                symbol=mexc_symbol.raw_symbol,
            )
            if not retry_manager.result:
                orders_open = self._cache.orders_open(
                    venue=None,
                    instrument_id=command.instrument_id
                )
                for order in orders_open:
                    if order.is_closed:
                        continue
                    self.generate_order_cancel_rejected(
                        order.strategy_id,
                        order.instrument_id,
                        order.client_order_id,
                        order.venue_order_id,
                        retry_manager.message,
                        self._clock.timestamp_ns(),
                    )

