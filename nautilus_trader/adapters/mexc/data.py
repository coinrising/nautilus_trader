"""MEXC data client implementation."""

from __future__ import annotations

import asyncio

from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import LiveClock
from nautilus_trader.common.component import MessageBus
from nautilus_trader.common.enums import LogColor
from nautilus_trader.core.datetime import millis_to_nanos
from nautilus_trader.data.messages import SubscribeQuoteTicks
from nautilus_trader.data.messages import SubscribeTradeTicks
from nautilus_trader.data.messages import UnsubscribeQuoteTicks
from nautilus_trader.data.messages import UnsubscribeTradeTicks
from nautilus_trader.live.data_client import LiveMarketDataClient
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.data import TradeTick
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import TradeId
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity

from nautilus_trader.adapters.mexc.common.constants import MEXC_VENUE
from nautilus_trader.adapters.mexc.common.enums import MexcEnumParser
from nautilus_trader.adapters.mexc.common.enums import MexcProductType
from nautilus_trader.adapters.mexc.common.parsing import parse_aggressor_side
from nautilus_trader.adapters.mexc.common.symbol import MexcSymbol
from nautilus_trader.adapters.mexc.config import MexcDataClientConfig
from nautilus_trader.adapters.mexc.http.client import MexcHttpClient
from nautilus_trader.adapters.mexc.providers import MexcInstrumentProvider
from nautilus_trader.adapters.mexc.websocket.client import MexcWebSocketClient


class MexcDataClient(LiveMarketDataClient):
    """
    Live market data client for MEXC.
    
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
    config : MexcDataClientConfig
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
        config: MexcDataClientConfig,
        name: str | None,
    ) -> None:
        self._enum_parser = MexcEnumParser()
        super().__init__(
            loop=loop,
            client_id=ClientId(name or MEXC_VENUE.value),
            venue=MEXC_VENUE,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            instrument_provider=instrument_provider,
        )
        
        # Configuration
        self._log.info(f"Product types: {[p.value for p in product_types]}", LogColor.BLUE)
        self._log.info(f"{config.update_instruments_interval_mins=}", LogColor.BLUE)
        self._log.info(f"{config.recv_window_ms=:_}", LogColor.BLUE)

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

        self._update_instruments_interval_mins: int | None = config.update_instruments_interval_mins
        self._update_instruments_task: asyncio.Task | None = None

        # Hot caches
        self._last_quotes: dict[InstrumentId, QuoteTick] = {}

    async def _connect(self) -> None:
        """Connect to the data client."""
        await self._instrument_provider.initialize()
        self._send_all_instruments_to_data_engine()

        if self._update_instruments_interval_mins:
            self._update_instruments_task = self.create_task(
                self._update_instruments(self._update_instruments_interval_mins),
            )

        for ws_client in self._ws_clients.values():
            await ws_client.connect()

    async def _disconnect(self) -> None:
        """Disconnect from the data client."""
        if self._update_instruments_task:
            self._log.debug("Canceling task 'update_instruments'")
            self._update_instruments_task.cancel()
            self._update_instruments_task = None

        for ws_client in self._ws_clients.values():
            await ws_client.disconnect()

    def _send_all_instruments_to_data_engine(self) -> None:
        """Send all instruments to the data engine."""
        for instrument in self._instrument_provider.get_all().values():
            self._handle_data(instrument)
        for currency in self._instrument_provider.currencies().values():
            self._cache.add_currency(currency)

    async def _update_instruments(self, interval_mins: int) -> None:
        """Periodically update instruments."""
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
        """Subscribe to quote ticks."""
        symbol = MexcSymbol(command.instrument_id.symbol.value)
        ws_client = self._ws_clients[symbol.product_type]
        await ws_client.subscribe_book_ticker(symbol.raw_symbol)

    async def _subscribe_trade_ticks(self, command: SubscribeTradeTicks) -> None:
        """Subscribe to trade ticks."""
        symbol = MexcSymbol(command.instrument_id.symbol.value)
        ws_client = self._ws_clients[symbol.product_type]
        await ws_client.subscribe_trades(symbol.raw_symbol)

    async def _unsubscribe_quote_ticks(self, command: UnsubscribeQuoteTicks) -> None:
        """Unsubscribe from quote ticks."""
        symbol = MexcSymbol(command.instrument_id.symbol.value)
        ws_client = self._ws_clients[symbol.product_type]
        await ws_client.unsubscribe_book_ticker(symbol.raw_symbol)

    async def _unsubscribe_trade_ticks(self, command: UnsubscribeTradeTicks) -> None:
        """Unsubscribe from trade ticks."""
        symbol = MexcSymbol(command.instrument_id.symbol.value)
        ws_client = self._ws_clients[symbol.product_type]
        await ws_client.unsubscribe_trades(symbol.raw_symbol)

    def _get_cached_instrument_id(self, symbol: str, product_type: str) -> InstrumentId:
        """Get cached instrument ID."""
        symbol = MexcSymbol(f"{symbol}-{product_type.upper()}")
        return symbol.to_instrument_id()

    async def _handle_ws_message(self, msg: dict) -> None:
        """Handle WebSocket message."""
        try:
            # MEXC WebSocket message format
            if 'c' in msg:  # Channel
                channel = msg['c']
                if 'deals' in channel:
                    self._handle_trade_tick(msg)
                elif 'bookTicker' in channel:
                    self._handle_quote_ticker(msg)
                else:
                    self._log.warning(f"Unknown channel: {channel}")
        except Exception as e:
            self._log.error(f"Failed to handle websocket message with: {e}")

    def _handle_quote_ticker(self, msg: dict) -> None:
        """Handle quote ticker message."""
        try:
            data = msg.get('d', {})
            symbol = msg.get('s')
            if not symbol:
                return
            
            instrument_id = self._get_cached_instrument_id(symbol, 'spot')
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

            if 'b' in data:  # Bid price
                bid_price = Price(float(data['b']), instrument.price_precision)
            if 'a' in data:  # Ask price
                ask_price = Price(float(data['a']), instrument.price_precision)
            if 'B' in data:  # Bid size
                bid_size = Quantity(float(data['B']), instrument.size_precision)
            if 'A' in data:  # Ask size
                ask_size = Quantity(float(data['A']), instrument.size_precision)

            ts_event = millis_to_nanos(data.get('t', int(self._clock.timestamp_ns() / 1_000_000)))
            
            quote = QuoteTick(
                instrument_id=instrument_id,
                bid_price=bid_price,
                ask_price=ask_price,
                bid_size=bid_size,
                ask_size=ask_size,
                ts_event=ts_event,
                ts_init=self._clock.timestamp_ns(),
            )
            self._last_quotes[quote.instrument_id] = quote
            self._handle_data(quote)
        except Exception as e:
            self._log.error(f"Failed to handle quote ticker: {msg} with error {e}")

    def _handle_trade_tick(self, msg: dict) -> None:
        """Handle trade tick message."""
        try:
            data = msg.get('d', {})
            symbol = msg.get('s')
            if not symbol:
                return
            
            instrument_id = self._get_cached_instrument_id(symbol, 'spot')
            instrument = self._cache.instrument(instrument_id)
            if instrument is None:
                self._log.error(f"Cannot parse trade ticker: no instrument for {instrument_id}")
                return

            deals = data.get('deals', [])
            for deal in deals:
                trade = TradeTick(
                    instrument_id=instrument_id,
                    price=Price.from_str(str(deal['p'])),
                    size=Quantity.from_str(str(deal['v'])),
                    aggressor_side=parse_aggressor_side(deal['S']),
                    trade_id=TradeId(str(deal['t'])),
                    ts_event=millis_to_nanos(deal['t']),
                    ts_init=self._clock.timestamp_ns(),
                )
                self._handle_data(trade)
        except Exception as e:
            self._log.error(f"Failed to handle trade tick: {msg} with error {e}")

