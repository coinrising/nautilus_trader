from __future__ import annotations

import time
import asyncio
import traceback

from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import LiveClock
from nautilus_trader.common.component import MessageBus
from nautilus_trader.common.enums import LogColor
from nautilus_trader.common.enums import LogLevel
from nautilus_trader.core.datetime import millis_to_nanos
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.execution.messages import CancelAllOrders
from nautilus_trader.execution.messages import CancelOrder
from nautilus_trader.execution.messages import GenerateFillReports
from nautilus_trader.execution.messages import GenerateOrderStatusReport
from nautilus_trader.execution.messages import GenerateOrderStatusReports
from nautilus_trader.execution.messages import GeneratePositionStatusReports
from nautilus_trader.execution.messages import ModifyOrder
from nautilus_trader.execution.messages import SubmitOrder
from nautilus_trader.execution.reports import FillReport
from nautilus_trader.execution.reports import OrderStatusReport
from nautilus_trader.execution.reports import PositionStatusReport
from nautilus_trader.live.execution_client import LiveExecutionClient
from nautilus_trader.live.retry import RetryManagerPool
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.enums import OmsType
from nautilus_trader.model.enums import OrderType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import TimeInForce
from nautilus_trader.model.enums import LiquiditySide
from nautilus_trader.model.enums import account_type_to_str
from nautilus_trader.model.identifiers import AccountId
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.model.identifiers import ClientOrderId
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import TradeId
from nautilus_trader.model.identifiers import VenueOrderId
from nautilus_trader.model.orders import LimitOrder
from nautilus_trader.model.orders import Order
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity
from nautilus_trader.model.objects import Money


from nautilus_trader.adapters.gate.common.constants import GATE_VENUE
from nautilus_trader.adapters.gate.common.enums import GateEnumParser
from nautilus_trader.adapters.gate.common.enums import GateOrderType
from nautilus_trader.adapters.gate.common.enums import GateProductType
from nautilus_trader.adapters.gate.common.enums import GateTimeInForce
from nautilus_trader.adapters.gate.common.symbol import GateSymbol
from nautilus_trader.adapters.gate.config import GateExecClientConfig
from nautilus_trader.adapters.gate.http.account import GateAccountHttpAPI
from nautilus_trader.adapters.gate.http.client import GateHttpClient
from nautilus_trader.adapters.gate.http.errors import GateError
from nautilus_trader.adapters.gate.http.errors import should_retry
from nautilus_trader.adapters.gate.providers import GateInstrumentProvider
from nautilus_trader.adapters.gate.schemas.order import GateOrder
from nautilus_trader.adapters.gate.schemas.trade import GateTrade
from nautilus_trader.adapters.gate.websocket.client import GateWebSocketClient

class GateExecutionClient(LiveExecutionClient):
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        client: GateHttpClient,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
        instrument_provider: GateInstrumentProvider,
        product_types: list[GateProductType],
        config: GateExecClientConfig,
        name: str | None,
    ) -> None:
        if GateProductType.SPOT in product_types:
            if len(set(product_types)) > 1:
                raise ValueError("Cannot configure SPOT with other product types")
            account_type = AccountType.CASH
        else:
            account_type = AccountType.MARGIN

        super().__init__(
            loop=loop,
            client_id=ClientId(name or GATE_VENUE.value),
            venue=GATE_VENUE,
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
        self._use_ws_trade_api = config.use_ws_trade_api
        self._use_ws_execution_fast = config.use_ws_execution_fast
        self._use_http_batch_api = config.use_http_batch_api

        self._log.info(f"Account type: {account_type_to_str(account_type)}", LogColor.BLUE)
        self._log.info(f"Product types: {[p.value for p in product_types]}", LogColor.BLUE)
        self._log.info(f"{config.use_ws_execution_fast=}", LogColor.BLUE)
        self._log.info(f"{config.use_ws_trade_api=}", LogColor.BLUE)
        self._log.info(f"{config.use_http_batch_api=}", LogColor.BLUE)
        self._log.info(f"{config.max_retries=}", LogColor.BLUE)
        self._log.info(f"{config.retry_delay=}", LogColor.BLUE)
        self._log.info(f"{config.recv_window_ms=:_}", LogColor.BLUE)
        self._log.info(f"{config.ws_trade_timeout_secs=}", LogColor.BLUE)

        self._enum_parser = GateEnumParser()

        account_id = AccountId(f"{name or GATE_VENUE.value}-UNIFIED")
        self._set_account_id(account_id)

        # HTTP API
        self._http_clt = GateAccountHttpAPI(
            client=client,
            clock=clock,
        )

        # WebSocket API
        self._ws_clients: dict[GateProductType, GateWebSocketClient] = {}
        for product_type in set(product_types):
            self._ws_clients[product_type] = GateWebSocketClient(
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
        }

        # Hot caches
        self._instrument_ids: dict[str, InstrumentId] = {}

        self._retry_manager_pool = RetryManagerPool[None](
            pool_size=100,
            max_retries=config.max_retries or 0,
            retry_delay_secs=config.retry_delay or 0.0,
            logger=self._log,
            exc_types=(GateError,),
            retry_check=should_retry,
        )

    async def _connect(self) -> None:
        await self._instrument_provider.initialize()
        await self._update_account_state()

        for ws_client in self._ws_clients.values():
            await ws_client.connect()
            await ws_client.subscribe_balances_update()
            await ws_client.subscribe_orders_update()
            await ws_client.subscribe_trades_update()

    async def _disconnect(self):
        for ws_client in self._ws_clients.values():
            await ws_client.disconnect()

    def _stop(self) -> None:
        self._retry_manager_pool.shutdown()

    # -- EXECUTION REPORTS ------------------------------------------------------------------------

    async def generate_order_status_reports(self, command: GenerateOrderStatusReports) -> list[OrderStatusReport]:
        instrument_id = command.instrument_id

        self._log.debug("Requesting OrderStatusReports...")
        reports: list[OrderStatusReport] = []

        try:
            _symbol = instrument_id.symbol.value if instrument_id is not None else None
            symbol = GateSymbol(_symbol) if _symbol is not None else None
            for product_type in self._product_types:
                gate_orders = await self._http_clt.query_order_history(
                    product_type,
                    symbol,
                    command.open_only,
                )
                for order in gate_orders:
                    # Uncomment for development
                    gate_symbol = GateSymbol(order.symbol + f"-{product_type.value.upper()}")

                    client_order_id = ClientOrderId(order.orderLinkId) if order.orderLinkId else None
                    if client_order_id is None:
                        client_order_id = self._cache.client_order_id(VenueOrderId(order.orderId))
                    if not repr(client_order_id).startswith("t-"):
                        continue
                    report = order.parse_to_order_status_report(
                        client_order_id=client_order_id,
                        account_id=self.account_id,
                        instrument_id=gate_symbol.to_instrument_id(),
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
        instrument_id = command.instrument_id
        client_order_id = command.client_order_id
        venue_order_id = command.venue_order_id

        PyCondition.is_false(
            client_order_id is None and venue_order_id is None,
            "both `client_order_id` and `venue_order_id` were `None`",
        )

        if client_order_id:
            order = self._cache.order(client_order_id)
            if order and order.order_type in (
                OrderType.TRAILING_STOP_MARKET,
                OrderType.TRAILING_STOP_LIMIT,
            ):
                self._log.warning("Cannot query with client order ID for trailing stops")
                client_order_id = None

        self._log.info(
            f"Generating OrderStatusReport for {repr(client_order_id) if client_order_id else ''} {repr(venue_order_id) if venue_order_id else ''}",
        )
        try:
            gate_symbol = GateSymbol(instrument_id.symbol.value)
            product_type = gate_symbol.product_type
            target_order = await self._http_clt.query_order(
                product_type=product_type,
                symbol=gate_symbol.raw_symbol,
                # symbol=instrument_id.symbol.value,
                client_order_id=client_order_id.value if client_order_id else None,
                order_id=venue_order_id.value if venue_order_id else None,
            )
            if target_order is None:
                self._log.error(f"Order {client_order_id} not found")
                return None
            order_link_id = target_order.orderLinkId
            client_order_id = ClientOrderId(order_link_id) if order_link_id else None
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
        except Exception as e:
            exception_text = traceback.format_exc()
            self._log.error(f"Failed to generate OrderStatusReport: {exception_text}")
        return None

    async def generate_fill_reports(self, command: GenerateFillReports) -> list[FillReport]:
        instrument_id = command.instrument_id

        self._log.debug("Requesting FillReports...")
        reports: list[FillReport] = []
        if instrument_id is None:
            return reports

        try:
            # _symbol = instrument_id.symbol.value if instrument_id is not None else None
            # symbol = GateSymbol(_symbol).raw_symbol if _symbol is not None else None
            gate_symbol = GateSymbol(instrument_id.symbol.value)
            for product_type in self._product_types:
                gate_fills = await self._http_clt.query_trade_history(product_type, gate_symbol.raw_symbol)
                for fill in gate_fills:
                    # Uncomment for development
                    report = fill.parse_to_fill_report(
                        account_id=self.account_id,
                        instrument_id=gate_symbol.to_instrument_id(),
                        report_id=UUID4(),
                        enum_parser=self._enum_parser,
                        ts_init=self._clock.timestamp_ns(),
                    )
                    reports.append(report)
                    self._log.debug(f"Received {report}")
        except Exception as e:
            exception_text = traceback.format_exc()
            self._log.error(f"Failed to generate FillReports: {repr(exception_text)}")

        len_reports = len(reports)
        plural = "" if len_reports == 1 else "s"
        self._log.info(f"Received {len(reports)} FillReport{plural}")

        return reports

    async def generate_position_status_reports(self, command: GeneratePositionStatusReports) -> list[PositionStatusReport]:
        instrument_id = command.instrument_id

        reports: list[PositionStatusReport] = []

        try:
            if instrument_id:
                self._log.debug(f"Requesting PositionStatusReport for {instrument_id}")
                gate_symbol = GateSymbol(instrument_id.symbol.value)
                positions = await self._http_clt.fetch_position_info(
                    gate_symbol.product_type,
                    gate_symbol.raw_symbol,
                )
                for position in positions:
                    position_report = position.parse_to_position_status_report(
                        account_id=self.account_id,
                        instrument_id=instrument_id,
                        report_id=UUID4(),
                        ts_init=self._clock.timestamp_ns(),
                    )
                    self._log.debug(f"Received {position_report}")
                    reports.append(position_report)
            else:
                self._log.debug("Requesting PositionStatusReports...")
                for product_type in self._product_types:
                    if product_type == GateProductType.SPOT:
                        continue  # No positions on spot
                    positions = await self._http_clt.fetch_position_info(product_type)
                    for position in positions:
                        symbol = position.symbol
                        gate_symbol = GateSymbol(f"{symbol}-{product_type.value.upper()}")
                        position_report = position.parse_to_position_status_report(
                            account_id=self.account_id,
                            instrument_id=gate_symbol.to_instrument_id(),
                            report_id=UUID4(),
                            ts_init=self._clock.timestamp_ns(),
                        )
                        self._log.debug(f"Received {position_report}")
                        reports.append(position_report)
        except Exception as e:
            exception_text = traceback.format_exc()
            self._log.error(f"Failed to generate PositionReports: {exception_text}")

        len_reports = len(reports)
        plural = "" if len_reports == 1 else "s"
        self._log.info(f"Received {len(reports)} PositionReport{plural}")

        return reports

    def _get_cached_instrument_id(self, symbol: str, product_type: GateProductType) -> InstrumentId:
        gate_symbol = GateSymbol(f"{symbol}-{product_type.value.upper()}")
        return gate_symbol.to_instrument_id()

    def _determine_time_in_force(self, order: Order) -> GateTimeInForce:
        time_in_force: TimeInForce = order.time_in_force
        if order.is_post_only:
            return GateTimeInForce.POST_ONLY
        return self._enum_parser.parse_nautilus_time_in_force(time_in_force)

    async def _update_account_state(self) -> None:
        balance = await self._http_clt.fetch_wallet_balance()
        ts = time.time() * 1000
        balances = balance.parse_to_account_balance()
        margins = balance.parse_to_margin_balance()
        try:
            self.generate_account_state(
                balances=balances,
                margins=margins,
                reported=True,
                ts_event=millis_to_nanos(ts),
            )
        except Exception as e:
            exception_text = traceback.format_exc()
            self._log.error(f"Failed to generate AccountState: {repr(exception_text)}")

    # -- COMMAND HANDLERS -------------------------------------------------------------------------

    async def _submit_order(self, command: SubmitOrder) -> None:
        order = command.order

        if order.is_closed:
            self._log.warning(f"Order {order} is already closed")
            return

        gate_symbol = GateSymbol(command.instrument_id.symbol.value)
        if not self._check_order_validity(order, gate_symbol.product_type):
            return

        # Generate order submitted event, to ensure correct ordering of event
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
        gate_symbol = GateSymbol(order.instrument_id.symbol.value)
        time_in_force = self._determine_time_in_force(order)
        order_side = self._enum_parser.parse_nautilus_order_side(order.side)
        await self._http_clt.place_order(
            product_type=gate_symbol.product_type,
            symbol=gate_symbol.raw_symbol,
            side=order_side,
            order_type=GateOrderType.LIMIT,
            quantity=str(order.quantity),
            price=str(order.price),
            time_in_force=time_in_force,
            client_order_id=str(order.client_order_id),
            auto_borrow=True,  # 调试用
        )


    # -- WEBSOCKET HANDLERS -------------------------------------------------------------------------

    async def _handle_ws_message(self, msg: dict) -> None:
        try:
            if msg['event'] in {'subscribe', 'unsubscribe'}:
                return
            # print('\n\n\nmsg:', msg)
            channel = msg['channel']  # 目前看到的channel的格式都是 spot.*
            product_type, topic = channel.split('.')
            if topic == 'balances':
                await self._update_account_state()
            elif topic == 'orders':
                self._handle_account_order_update(product_type, msg)
            elif topic == 'usertrades':
                self._handle_account_trade_update(product_type, msg)
            else:
                raise ValueError(f"Unknown websocket channel: {channel}")
        except Exception as e:
            exception_text = traceback.format_exc()
            self._log.error(f"Failed to handle websocket msg {msg} with: {exception_text}")

    def _handle_account_order_update(self, product_type: str, msg: dict) -> None:
        try:
            result = msg['result']
            for order in result:
                gate_order = GateOrder.from_ws_dict(order)
                instrument_id = self._get_cached_instrument_id(gate_order.symbol, GateProductType(product_type))
                client_order_id = ClientOrderId(gate_order.orderLinkId) if gate_order.orderLinkId else None
                venue_order_id = VenueOrderId(gate_order.orderId)
                if client_order_id is None:
                    client_order_id = self._cache.client_order_id(venue_order_id)

                report = gate_order.parse_to_order_status_report(
                    client_order_id=client_order_id,
                    account_id=self.account_id,
                    instrument_id=instrument_id,
                    report_id=UUID4(),
                    enum_parser=self._enum_parser,
                    ts_init=self._clock.timestamp_ns(),
                )

                strategy_id = None
                if report.client_order_id:
                    strategy_id = self._cache.strategy_id_for_order(report.client_order_id)
                if strategy_id is None:
                    # External order
                    self._send_order_status_report(report)
                    return

                cache_order = self._cache.order(report.client_order_id)
                if cache_order is None:
                    exception_text = traceback.format_exc()
                    self._log.error(f"Cannot find {report.client_order_id!r}")
                    return
                
                if order['event'] == 'put':
                    self._log.info(f'order accepted: {cache_order}, {report}')
                    self.generate_order_accepted(
                        strategy_id=strategy_id,
                        instrument_id=report.instrument_id,
                        client_order_id=report.client_order_id,
                        venue_order_id=report.venue_order_id,
                        ts_event=report.ts_last,
                    )
                elif order['event'] == 'finish':
                    if order['finish_as'] == 'cancelled':
                        self._log.info(f'order cancelled: {cache_order}, {report}')
                        self.generate_order_canceled(
                            strategy_id=strategy_id,
                            instrument_id=report.instrument_id,
                            client_order_id=report.client_order_id,
                            venue_order_id=report.venue_order_id,
                            ts_event=report.ts_last,
                        )
                    else:
                        self._log.info(f'order rejected: {cache_order}, {report}')
                        self.generate_order_rejected(
                            strategy_id=strategy_id,
                            instrument_id=report.instrument_id,
                            client_order_id=report.client_order_id,
                            reason=order['finish_as'],
                            ts_event=report.ts_last,
                        )
        except Exception:
            exception_text = traceback.format_exc()
            self._log.error(f'Failed to handle order update: {exception_text}')

    def _handle_account_trade_update(self, product_type: str, msg: dict) -> None:
        try:
            result = msg['result']
            for raw_trade in result:
                gate_trade = GateTrade.from_ws_dict(raw_trade)
                instrument_id = self._get_cached_instrument_id(raw_trade["currency_pair"], GateProductType(product_type))
                client_order_id = ClientOrderId(gate_trade.orderLinkId) if gate_trade.orderLinkId else None
                venue_order_id = VenueOrderId(gate_trade.orderId)

                order_side: OrderSide = self._enum_parser.parse_gate_order_side(gate_trade.side)
                if client_order_id is None:
                    client_order_id = self._cache.client_order_id(venue_order_id)
                if client_order_id is None:
                    self._log.debug(
                        f"Cannot process order execution for {venue_order_id!r}: no `ClientOrderId` found (most likely due to being an external order)",
                    )
                    return
                order = self._cache.order(client_order_id)
                if order is None:
                    self._log.debug(
                        f"Cannot process order execution for {venue_order_id!r}: no `order` found (most likely due to being an external order)",
                    )
                    return
                else:
                    strategy_id = order.strategy_id
                    order_type = order.order_type

                instrument = self._cache.instrument(instrument_id)
                if instrument is None:
                    raise ValueError(f"Cannot handle trade event: instrument {instrument_id} not found")

                quote_currency = instrument.quote_currency
                is_maker = gate_trade.isMaker

                last_qty: Quantity = instrument.make_qty(gate_trade.execQty)
                last_px: Price = instrument.make_price(gate_trade.execPrice)
                commission: Money = Money(gate_trade.execFee, quote_currency)

                self.generate_order_filled(
                    strategy_id=strategy_id,
                    instrument_id=instrument_id,
                    client_order_id=client_order_id,
                    venue_order_id=venue_order_id,
                    venue_position_id=None,
                    trade_id=TradeId(gate_trade.execId),
                    order_side=order_side,
                    order_type=order_type,
                    last_qty=last_qty,
                    last_px=last_px,
                    quote_currency=quote_currency,
                    commission=commission,
                    liquidity_side=LiquiditySide.MAKER if is_maker else LiquiditySide.TAKER,
                    ts_event=millis_to_nanos(float(gate_trade.execTime)),
                )
        except Exception:
            exception_text = traceback.format_exc()
            self._log.error(f'Failed to handle order update: {exception_text}')

    # -- PRIVATTE FUNCIONS -------------------------------------------------------------------------

    def _check_order_validity(self, order: Order, product_type: GateProductType) -> bool:
        # Check post only
        if order.is_post_only and order.order_type != OrderType.LIMIT:
            self._log.error(
                f"Cannot submit {order} has invalid post only {order.is_post_only}, unsupported on Gate",
            )
            return False

        return True


    async def _cancel_order(self, command: CancelOrder) -> None:
        order: Order | None = self._cache.order(command.client_order_id)
        if order is None:
            self._log.error(f"{command.client_order_id!r} not found in cache")
            return

        if order.is_closed:
            self._log.warning(
                f"`CancelOrder` command for {command.client_order_id!r} when order already {order.status_string()} (will not send to exchange)",
            )
            return

        symbol = GateSymbol(command.instrument_id.symbol.value)
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
        gate_symbol = GateSymbol(command.instrument_id.symbol.value)

        async with self._retry_manager_pool as retry_manager:
            await retry_manager.run(
                "cancel_all_orders",
                None,
                self._http_clt.cancel_all_orders,
                product_type=gate_symbol.product_type,
                symbol=gate_symbol.raw_symbol,
            )
            if not retry_manager.result:
                orders_open = self._cache.orders_open(
                    venue=None,
                    instrument_id=command.instrument_id)
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

    async def _modify_order(self, command: ModifyOrder) -> None:
        order: Order | None = self._cache.order(command.client_order_id)
        if order is None:
            self._log.error(f"{command.client_order_id!r} not found in cache")
            return

        if order.is_closed:
            self._log.warning(
                f"`ModifyOrder` command for {command.client_order_id!r} when order already {order.status_string()} (will not send to exchange)",
            )
            return

        gate_symbol = GateSymbol(command.instrument_id.symbol.value)
        client_order_id = command.client_order_id.value
        venue_order_id = str(command.venue_order_id) if command.venue_order_id else None
        price = str(command.price) if command.price else None
        quantity = str(command.quantity) if command.quantity else None

        async with self._retry_manager_pool as retry_manager:
            await retry_manager.run(
                "modify_order",
                [client_order_id, venue_order_id],
                self._http_clt.amend_order,
                gate_symbol.product_type,
                gate_symbol.raw_symbol,
                venue_order_id=venue_order_id,
                client_order_id=client_order_id,
                quantity=quantity,
                price=price,
            )
            if not retry_manager.result:
                self.generate_order_modify_rejected(
                    order.strategy_id,
                    order.instrument_id,
                    order.client_order_id,
                    order.venue_order_id,
                    retry_manager.message,
                    self._clock.timestamp_ns(),
                )
