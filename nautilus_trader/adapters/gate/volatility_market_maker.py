import time
from decimal import Decimal

from nautilus_trader.adapters.gate.schemas.order import gate_client_order_id
from nautilus_trader.common.enums import LogColor
from nautilus_trader.config import PositiveFloat
from nautilus_trader.config import PositiveInt
from nautilus_trader.config import StrategyConfig
from nautilus_trader.core.data import Data
from nautilus_trader.core.message import Event
from nautilus_trader.indicators.atr import AverageTrueRange
from nautilus_trader.model.data import BarType
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.data import TradeTick
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import TimeInForce
from nautilus_trader.model.enums import TriggerType
from nautilus_trader.model.events import OrderFilled
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.orders import LimitOrder
from nautilus_trader.trading.strategy import Strategy
# from nautilus_trader.common.factories cimport OrderFactory


# *** THIS IS A TEST STRATEGY WITH NO ALPHA ADVANTAGE WHATSOEVER. ***
# *** IT IS NOT INTENDED TO BE USED TO TRADE LIVE WITH REAL MONEY. ***


class VolatilityMarketMakerConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId
    bar_type: BarType
    atr_period: PositiveInt
    atr_multiple: PositiveFloat
    trade_size: Decimal
    emulation_trigger: str = "NO_TRIGGER"
    client_id: ClientId | None = None

class VolatilityMarketMaker(Strategy):

    def __init__(self, config: VolatilityMarketMakerConfig) -> None:
        super().__init__(config)

        self.instrument: Instrument | None = None  # Initialized in on_start
        self.client_id = config.client_id

        # Create the indicators for the strategy
        self.atr = AverageTrueRange(config.atr_period)
        self.last_place_order = 0

    def on_start(self) -> None:
        """
        Actions to be performed on strategy start.
        """
        self.instrument = self.cache.instrument(self.config.instrument_id)
        if self.instrument is None:
            self.log.error(f"Could not find instrument for {self.config.instrument_id}")
            self.stop()
            return
        self.subscribe_quote_ticks(self.config.instrument_id, client_id=self.client_id)
        self.subscribe_trade_ticks(self.config.instrument_id, client_id=self.client_id)

    def on_data(self, data: Data) -> None:
        pass
        # self.log.info(repr(data), LogColor.CYAN)

    def on_instrument(self, instrument: Instrument) -> None:
        pass
        # self.log.info(repr(instrument), LogColor.CYAN)

    def on_quote_tick(self, tick: QuoteTick) -> None:
        self.log.debug(repr(tick), LogColor.CYAN)
        if not self.instrument:
            self.log.error("No instrument loaded.")
            return

        if not self.indicators_initialized():
            self.log.info(
                f"Waiting for indicators to warm up [{self.cache.bar_count(self.config.bar_type)}]",
                color=LogColor.BLUE,
            )

        last: QuoteTick = self.cache.quote_tick(self.config.instrument_id)
        if last is None:
            self.log.info("No quotes yet")
            return

        open_orders = self.cache.orders_open()
        # print('strategy open orders:', open_orders)

        # if buy_order:
        #     self.cancel_order(buy_order)
        self.create_buy_order(last)

        # if self.sell_order:
        #     self.cancel_order(self.sell_order)
        self.create_sell_order(last)
        return

    def on_trade_tick(self, tick: TradeTick) -> None:
        last: TradeTick = self.cache.trade_tick(self.config.instrument_id)
        # self.log.info(repr(tick), LogColor.CYAN)
        
    def create_buy_order(self, last: QuoteTick) -> None:
        if not self.instrument:
            self.log.error("No instrument loaded")
            return
        if time.time() - self.last_place_order < 10:
            return

        print('buying:', last.bid_price, self.atr.value, self.config.atr_multiple)
        # price: Decimal = last.bid_price - (self.atr.value * self.config.atr_multiple)
        price: Decimal = last.bid_price - 500
        order: LimitOrder = self.order_factory.limit(
            instrument_id=self.config.instrument_id,
            order_side=OrderSide.BUY,
            quantity=self.instrument.make_qty(self.config.trade_size),
            price=self.instrument.make_price(price),
            time_in_force=TimeInForce.GTC,
            post_only=True,
            emulation_trigger=TriggerType[self.config.emulation_trigger],
            client_order_id=gate_client_order_id(),
        )
        self.submit_order(order, client_id=self.client_id)
        self.last_place_order = time.time()

    def create_sell_order(self, last: QuoteTick) -> None:
        if not self.instrument:
            self.log.error("No instrument loaded")
            return
        if time.time() - self.last_place_order < 10:
            return

        print('selling:', last.ask_price, self.atr.value, self.config.atr_multiple)
        # price: Decimal = last.ask_price + (self.atr.value * self.config.atr_multiple)
        price: Decimal = last.ask_price + 500
        order: LimitOrder = self.order_factory.limit(
            instrument_id=self.config.instrument_id,
            order_side=OrderSide.SELL,
            quantity=self.instrument.make_qty(self.config.trade_size),
            price=self.instrument.make_price(price),
            time_in_force=TimeInForce.GTC,
            post_only=True,
            emulation_trigger=TriggerType[self.config.emulation_trigger],
            client_order_id=gate_client_order_id(),
        )
        self.sell_order = order
        self.submit_order(order, client_id=self.client_id)
        self.last_place_order = time.time()

    def on_event(self, event: Event) -> None:
        # print('on event:' + repr(event))
        return
        # last: QuoteTick = self.cache.quote_tick(self.config.instrument_id)
        # if last is None:
        #     self.log.info("No quotes yet")
        #     return
        # self.log.info('on event:' + repr(last))

        # If order filled then replace order at ATR multiple distance from the market
        if isinstance(event, OrderFilled):
            if self.buy_order and event.order_side == OrderSide.BUY:
                if self.buy_order.is_closed:
                    self.create_buy_order(last)
            elif (
                self.sell_order and event.order_side == OrderSide.SELL and self.sell_order.is_closed
            ):
                self.create_sell_order(last)

    def on_stop(self) -> None:
        self.cancel_all_orders(self.config.instrument_id, client_id=self.client_id)
        self.unsubscribe_quote_ticks(self.config.instrument_id, client_id=self.client_id)
        self.unsubscribe_trade_ticks(self.config.instrument_id, client_id=self.client_id)

    def on_reset(self) -> None:
        self.atr.reset()