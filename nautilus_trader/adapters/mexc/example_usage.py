"""Example usage of the MEXC adapter for NautilusTrader."""

from decimal import Decimal

from nautilus_trader.adapters.mexc.common.enums import MexcProductType
from nautilus_trader.adapters.mexc.config import MexcDataClientConfig
from nautilus_trader.adapters.mexc.config import MexcExecClientConfig
from nautilus_trader.adapters.mexc.factories import MexcLiveDataClientFactory
from nautilus_trader.adapters.mexc.factories import MexcLiveExecClientFactory
from nautilus_trader.config import LoggingConfig
from nautilus_trader.config import TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.book import OrderBook
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.enums import TimeInForce
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import TraderId
from nautilus_trader.model.orders import LimitOrder
from nautilus_trader.trading.strategy import Strategy


# Example 1: Basic Market Data Subscription Strategy
class MexcDataStrategy(Strategy):
    """
    A simple strategy that subscribes to MEXC market data.
    """

    def on_start(self) -> None:
        """Actions to be performed on strategy start."""
        self.instrument_id = InstrumentId.from_str("BTCUSDT-SPOT.MEXC")
        
        # Subscribe to quote ticks (best bid/ask)
        self.subscribe_quote_ticks(self.instrument_id)
        
        # Subscribe to trade ticks
        self.subscribe_trade_ticks(self.instrument_id)

    def on_quote_tick(self, tick: QuoteTick) -> None:
        """
        Handle quote tick updates.
        """
        self.log.info(
            f"Received quote: {tick.instrument_id} "
            f"bid={tick.bid_price} ask={tick.ask_price}"
        )

    def on_trade_tick(self, tick) -> None:
        """
        Handle trade tick updates.
        """
        self.log.info(
            f"Received trade: {tick.instrument_id} "
            f"price={tick.price} size={tick.size} side={tick.aggressor_side}"
        )


# Example 2: Simple Trading Strategy
class MexcTradingStrategy(Strategy):
    """
    A simple trading strategy that places orders on MEXC.
    """

    def on_start(self) -> None:
        """Actions to be performed on strategy start."""
        self.instrument_id = InstrumentId.from_str("BTCUSDT-SPOT.MEXC")
        self.instrument = self.cache.instrument(self.instrument_id)
        
        if self.instrument is None:
            self.log.error(f"Could not find instrument {self.instrument_id}")
            return
        
        # Subscribe to quote ticks
        self.subscribe_quote_ticks(self.instrument_id)

    def on_quote_tick(self, tick: QuoteTick) -> None:
        """
        Handle quote tick - example: place limit order below best bid.
        """
        if self.portfolio.is_flat(self.instrument_id):
            # Calculate order price (1% below best bid)
            order_price = tick.bid_price * Decimal("0.99")
            
            # Create limit order
            order = self.order_factory.limit(
                instrument_id=self.instrument_id,
                order_side=OrderSide.BUY,
                quantity=self.instrument.make_qty(0.001),  # 0.001 BTC
                price=self.instrument.make_price(order_price),
                time_in_force=TimeInForce.GTC,
                post_only=True,  # Use post-only for maker fees
            )
            
            # Submit order
            self.submit_order(order)
            self.log.info(f"Submitted limit order: {order}")


# Example 3: Configure and Run Trading Node
def create_trading_node():
    """
    Create and configure a trading node with MEXC adapters.
    """
    # Load API credentials from environment or config file
    # For production, use secure credential management
    api_key = "your_api_key_here"
    api_secret = "your_api_secret_here"
    
    # Configure trading node
    config = TradingNodeConfig(
        trader_id=TraderId("TRADER-001"),
        logging=LoggingConfig(
            log_level="INFO",
            log_level_file="DEBUG",
        ),
        data_clients={
            "MEXC": MexcDataClientConfig(
                api_key=api_key,
                api_secret=api_secret,
                product_types=[MexcProductType.SPOT],
                update_instruments_interval_mins=60,
                instrument_provider={"load_all": True},
            ),
        },
        exec_clients={
            "MEXC": MexcExecClientConfig(
                api_key=api_key,
                api_secret=api_secret,
                product_types=[MexcProductType.SPOT],
                max_retries=3,
                retry_delay=1.0,
                instrument_provider={"load_all": True},
            ),
        },
        timeout_connection=30.0,
        timeout_reconciliation=10.0,
        timeout_portfolio=10.0,
        timeout_disconnection=10.0,
    )
    
    # Create trading node
    node = TradingNode(config=config)
    
    # Register MEXC adapter factories
    node.add_data_client_factory("MEXC", MexcLiveDataClientFactory)
    node.add_exec_client_factory("MEXC", MexcLiveExecClientFactory)
    
    return node


# Example 4: Running a Strategy
def run_strategy():
    """
    Example of running a trading strategy with MEXC.
    """
    # Create node
    node = create_trading_node()
    
    # Create strategy instance
    strategy_config = {
        "instrument_id": "BTCUSDT-SPOT.MEXC",
    }
    strategy = MexcDataStrategy(config=strategy_config)
    
    # Add strategy to node
    node.trader.add_strategy(strategy)
    
    # Build and run
    node.build()
    
    try:
        node.run()
    except KeyboardInterrupt:
        node.stop()
    finally:
        node.dispose()


# Example 5: Instrument Loading
async def load_instruments_example():
    """
    Example of loading instruments from MEXC.
    """
    from nautilus_trader.adapters.mexc.common.urls import get_http_base_url
    from nautilus_trader.adapters.mexc.config import InstrumentProviderConfig
    from nautilus_trader.adapters.mexc.http.client import MexcHttpClient
    from nautilus_trader.adapters.mexc.providers import MexcInstrumentProvider
    from nautilus_trader.common.component import LiveClock
    
    # Create HTTP client
    clock = LiveClock()
    client = MexcHttpClient(
        clock=clock,
        api_key="your_api_key",
        api_secret="your_api_secret",
        base_url=get_http_base_url(),
    )
    
    # Create instrument provider
    provider = MexcInstrumentProvider(
        client=client,
        clock=clock,
        product_types=[MexcProductType.SPOT],
        config=InstrumentProviderConfig(load_all=True),
    )
    
    # Load instruments
    await provider.load_all_async()
    
    # Get all instruments
    instruments = provider.get_all()
    print(f"Loaded {len(instruments)} instruments")
    
    # Get specific instrument
    btc_usdt = provider.find(InstrumentId.from_str("BTCUSDT-SPOT.MEXC"))
    if btc_usdt:
        print(f"BTC/USDT: {btc_usdt}")
        print(f"  Min quantity: {btc_usdt.min_quantity}")
        print(f"  Price increment: {btc_usdt.price_increment}")
        print(f"  Maker fee: {btc_usdt.maker_fee}")
        print(f"  Taker fee: {btc_usdt.taker_fee}")


if __name__ == "__main__":
    # Run the strategy example
    # Uncomment to run:
    # run_strategy()
    
    # Or run instrument loading example:
    # import asyncio
    # asyncio.run(load_instruments_example())
    
    print("MEXC Adapter Examples")
    print("=====================")
    print()
    print("To run these examples:")
    print("1. Set your API credentials in the code")
    print("2. Uncomment the example you want to run")
    print("3. Execute: python example_usage.py")
    print()
    print("Available examples:")
    print("- MexcDataStrategy: Subscribe to market data")
    print("- MexcTradingStrategy: Place limit orders")
    print("- run_strategy(): Full trading node setup")
    print("- load_instruments_example(): Load instrument definitions")

