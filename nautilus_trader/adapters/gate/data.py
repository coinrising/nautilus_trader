from __future__ import annotations

import asyncio
import json

from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import LiveClock
from nautilus_trader.common.component import MessageBus
from nautilus_trader.common.enums import LogColor
from nautilus_trader.core.datetime import millis_to_nanos
from nautilus_trader.data.messages import RequestData
from nautilus_trader.data.messages import SubscribeQuoteTicks
from nautilus_trader.data.messages import SubscribeTradeTicks
from nautilus_trader.data.messages import SubscribeOrderBook
from nautilus_trader.data.messages import UnsubscribeQuoteTicks
from nautilus_trader.data.messages import UnsubscribeTradeTicks
from nautilus_trader.data.messages import UnsubscribeOrderBook
from nautilus_trader.live.data_client import LiveMarketDataClient
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.data import TradeTick
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import TradeId
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity
from nautilus_trader.adapters.gate.schemas.ws import decoder_ws_orderbook


from nautilus_trader.adapters.gate.common.constants import GATE_VENUE
from nautilus_trader.adapters.gate.common.enums import GateEnumParser
from nautilus_trader.adapters.gate.common.enums import GateProductType
from nautilus_trader.adapters.gate.common.parsing import parse_aggressor_side
from nautilus_trader.adapters.gate.common.symbol import GateSymbol
from nautilus_trader.adapters.gate.config import GateDataClientConfig
from nautilus_trader.adapters.gate.http.client import GateHttpClient
from nautilus_trader.adapters.gate.providers import GateInstrumentProvider
from nautilus_trader.adapters.gate.schemas.market.ticker import GateTickerData
from nautilus_trader.adapters.gate.websocket.client import GateWebSocketClient


class GateDataClient(LiveMarketDataClient):
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        client: GateHttpClient,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
        instrument_provider: GateInstrumentProvider,
        product_types: list[GateProductType],
        config: GateDataClientConfig,
        name: str | None,
    ) -> None:
        self._enum_parser = GateEnumParser()
        super().__init__(
            loop=loop,
            client_id=ClientId(name or GATE_VENUE.value),
            venue=GATE_VENUE,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            instrument_provider=instrument_provider,
        )
        # Configuration
        self._log.info(f"Product types: {[p.value for p in product_types]}", LogColor.BLUE)
        self._log.info(f"{config.update_instruments_interval_mins=}", LogColor.BLUE)
        self._log.info(f"{config.recv_window_ms=:_}", LogColor.BLUE)
        # HTTP API
        # self._http_market = GateMarketHttpAPI(client=client, clock=clock)

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

        # self._tob_quotes: set[InstrumentId] = set()
        # self._depths: dict[InstrumentId, int] = {}
        # self._topic_bar_type: dict[str, BarType] = {}

        self._update_instruments_interval_mins: int | None = config.update_instruments_interval_mins
        self._update_instruments_task: asyncio.Task | None = None

        self._decoder_ws_orderbook = decoder_ws_orderbook()

        # self._msgbus.register(endpoint="gate.data.tickers", handler=self.complete_fetch_tickers_task)

        # Hot caches
        # self._instrument_ids: dict[str, InstrumentId] = {}
        self._last_quotes: dict[InstrumentId, QuoteTick] = {}


    async def _connect(self) -> None:
        await self._instrument_provider.initialize()
        self._send_all_instruments_to_data_engine()

        if self._update_instruments_interval_mins:
            self._update_instruments_task = self.create_task(
                self._update_instruments(self._update_instruments_interval_mins),
            )

        for ws_client in self._ws_clients.values():
            await ws_client.connect()

    async def _disconnect(self) -> None:
        if self._update_instruments_task:
            self._log.debug("Canceling task 'update_instruments'")
            self._update_instruments_task.cancel()
            self._update_instruments_task = None

        for ws_client in self._ws_clients.values():
            await ws_client.disconnect()

    def _send_all_instruments_to_data_engine(self) -> None:
        for instrument in self._instrument_provider.get_all().values():
            self._handle_data(instrument)
        for currency in self._instrument_provider.currencies().values():
            self._cache.add_currency(currency)

    async def _update_instruments(self, interval_mins: int) -> None:
        try:
            while True:
                self._log.debug(
                    f"Scheduled task 'update_instruments' to run in {interval_mins} minutes",
                )
                await asyncio.sleep(interval_mins * 60)
                await self._instrument_provider.initialize(reload=True)
                self._send_all_instruments_to_data_engine()
        except asyncio.CancelledError:
            self._log.debug("Canceled task 'update_instruments'")

    async def _subscribe_quote_ticks(self, command: SubscribeQuoteTicks) -> None:
        symbol = GateSymbol(command.instrument_id.symbol.value)
        ws_client = self._ws_clients[symbol.product_type]
        await ws_client.subscribe_book_ticker(symbol.raw_symbol)

    async def _subscribe_trade_ticks(self, command: SubscribeTradeTicks) -> None:
        symbol = GateSymbol(command.instrument_id.symbol.value)
        ws_client = self._ws_clients[symbol.product_type]
        await ws_client.subscribe_trades(symbol.raw_symbol)

    async def _subscribe_order_book_deltas(self, command: SubscribeOrderBook) -> None:
        symbol = GateSymbol(command.instrument_id.symbol.value)
        ws_client = self._ws_clients[symbol.product_type]
        await ws_client.subscribe_order_book_deltas(symbol.raw_symbol)

    async def _unsubscribe_quote_ticks(self, command: UnsubscribeQuoteTicks) -> None:
        symbol = GateSymbol(command.instrument_id.symbol.value)
        ws_client = self._ws_clients[symbol.product_type]
        await ws_client.unsubscribe_book_ticker(symbol.raw_symbol)

    async def _unsubscribe_trade_ticks(self, command: UnsubscribeTradeTicks) -> None:
        symbol = GateSymbol(command.instrument_id.symbol.value)
        ws_client = self._ws_clients[symbol.product_type]
        await ws_client.unsubscribe_trades(symbol.raw_symbol)

    def _get_cached_instrument_id(self, symbol: str, product_type: str) -> InstrumentId:
        symbol = GateSymbol(f"{symbol}-{product_type.upper()}")
        return symbol.to_instrument_id()

    async def _handle_ws_message(self, msg: dict) -> None:
        try:
            if msg['event'] in {'subscribe', 'unsubscribe'}:
                return
            channel = msg['channel']  # 目前看到的channel的格式都是 spot.*
            product_type, topic = channel.split('.')
            if topic == 'trades':
                self.handle_trade_tick(product_type, msg)
            elif topic == 'book_ticker':
                self.handle_quote_tickers(product_type, msg)
            elif topic == 'order_book_update':
                self.handle_orderbook(product_type, msg)
            else:
                raise ValueError(f"Unknown websocket channel: {channel}")
        except Exception as e:
            self._log.error(f"Failed to handle websocket message with: {e}")

    def handle_quote_tickers(self, product_type: str, msg: dict) -> None:
        try:
            result = msg['result']
            symbol = result['s']
            instrument_id = self._get_cached_instrument_id(symbol, product_type)
            instrument = self._cache.instrument(instrument_id)
            if instrument is None:
                self._log.error(f"Cannot parse quote ticker: no instrument for {instrument_id}")
                return

            bid_price = ask_price = bid_size = ask_size = None

            last_quote = self._last_quotes.get(instrument_id)
            if last_quote is not None:
                bid_price = last_quote.bid_price
                ask_price = last_quote.ask_price
                bid_size = last_quote.bid_size
                ask_size = last_quote.ask_size

            if result['b'] is not None:
                bid_price = Price(float(result['b']), instrument.price_precision)
            if result['a'] is not None:
                ask_price = Price(float(result['a']), instrument.price_precision)
            if result['B'] is not None:
                bid_size = Quantity(float(result['B']), instrument.size_precision)
            if result['A'] is not None:
                ask_size = Quantity(float(result['A']), instrument.size_precision)

            quote = QuoteTick(
                instrument_id=instrument_id,
                bid_price=bid_price,
                ask_price=ask_price,
                bid_size=bid_size,
                ask_size=ask_size,
                ts_event=millis_to_nanos(result['t']),
                ts_init=self._clock.timestamp_ns(),
            )
            self._last_quotes[quote.instrument_id] = quote
            self._handle_data(quote)
        except Exception as e:
            self._log.error(f"Failed to handle quote ticker: {msg} with error {e}")

    def handle_trade_tick(self, product_type: str, msg: dict) -> None:
        try:
            result = msg['result']
            symbol = result['currency_pair']
            instrument_id = self._get_cached_instrument_id(symbol, product_type)
            instrument = self._cache.instrument(instrument_id)
            if instrument is None:
                self._log.error(f"Cannot parse trade ticker: no instrument for {instrument_id}")
                return
            ts_init = self._clock.timestamp_ns()
            trade = TradeTick(
                instrument_id=instrument_id,
                price=Price.from_str(result['price']),
                size=Quantity.from_str(result['amount']),
                aggressor_side=parse_aggressor_side(result['side']),
                trade_id=TradeId(str(result['id'])),
                ts_event=millis_to_nanos(int(float(result['create_time_ms']))),
                ts_init=ts_init,
            )
            # print('trade tick:', trade)
            self._handle_data(trade)
        except Exception as e:
            self._log.error(f"Failed to handle trade tick: {msg} with error {e}")

    def handle_orderbook(self, product_type: str, msg: dict) -> None:
        print('orderbook:', msg)
        # msg_bytes = json.dumps(msg).encode('utf-8')
        # msg = self._decoder_ws_orderbook.decode(msg_bytes)
        # instrument_id = self._get_cached_instrument_id(msg.result.s, product_type)
        # instrument = self._cache.instrument(instrument_id)
        # if instrument is None:
        #     self._log.error(f"Cannot parse trade ticker: no instrument for {instrument_id}")
        #     return
        # deltas = msg.result.parse_to_deltas(
        #     instrument_id=instrument_id,
        #     price_precision=instrument.price_precision,
        #     size_precision=instrument.size_precision,
        #     ts_event=millis_to_nanos(msg.ts),
        #     ts_init=self._clock.timestamp_ns(),
        # )
        # self._handle_data(deltas)


    async def _request(self, request: RequestData) -> None:
        # print('data recv request:', request)
        if request.data_type.type == GateTickerData:
            symbol = request.data_type.metadata["symbol"]
            await self._handle_ticker_data_request(symbol, request.id)
