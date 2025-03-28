import os
import sys
sys.path.append(os.path.dirname(os.getcwd()))
from decimal import Decimal

from nautilus_trader.adapters.gate.common.enums import GateProductType
from nautilus_trader.adapters.gate.common.urls import get_ws_base_url
from nautilus_trader.adapters.gate.config import GateDataClientConfig, GateExecClientConfig
from nautilus_trader.adapters.gate.factories import GateLiveDataClientFactory
from nautilus_trader.adapters.gate.factories import GateLiveExecClientFactory
from nautilus_trader.cache.config import CacheConfig
from nautilus_trader.config import InstrumentProviderConfig
from nautilus_trader.config import LiveExecEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.config import TradingNodeConfig
from nautilus_trader.adapters.gate.volatility_market_maker import VolatilityMarketMaker
from nautilus_trader.examples.strategies.volatility_market_maker import VolatilityMarketMakerConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.data import BarType
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import TraderId



api_key = os.getenv('GATE_API_KEY')
api_secret = os.getenv('GATE_API_SECRET')

product_types = [GateProductType.SPOT]
testnet = False
symbol = f"BTC_USDT"
trade_size = Decimal("0.00004")

base_url_http = 'https://api.gateio.ws'
base_urls_ws: dict[GateProductType, str] = {}
for product_type in product_types:
    base_urls_ws[product_type] = get_ws_base_url(product_type)


symbols = frozenset(['BTC_USDT'])
# symbols = ['BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'XRP_USDT', 'DOGE_USDT']
instrument_provider_config = InstrumentProviderConfig(load_all=True, filters={'symbol': symbols})

# Configure the trading node
config_node = TradingNodeConfig(
    trader_id=TraderId("TESTER-001"),
    # logging=LoggingConfig(log_level="DEBUG", use_pyo3=True),
    logging=LoggingConfig(log_level="INFO", use_pyo3=True),
    exec_engine=LiveExecEngineConfig(
        reconciliation=True,
        open_check_interval_secs=5.0,
        open_check_open_only=True,
    ),
    cache=CacheConfig(
        timestamps_as_iso8601=True,
        buffer_interval_ms=100,
    ),
    # message_bus=MessageBusConfig(
    #     database=DatabaseConfig(),
    #     timestamps_as_iso8601=True,
    #     buffer_interval_ms=100,
    #     streams_prefix="bybit",
    #     use_trader_prefix=False,
    #     use_trader_id=False,
    #     use_instance_id=False,
    #     stream_per_topic=False,
    #     types_filter=[QuoteTick],
    #     autotrim_mins=30,
    #     heartbeat_interval_secs=1,
    # ),
    data_clients={
        "GATE": GateDataClientConfig(
            api_key=api_key,
            api_secret=api_secret,
            base_url_http=base_url_http,
            base_urls_ws=base_urls_ws,
            instrument_provider=instrument_provider_config,
            product_types=product_types,  # Will load all instruments
            recv_window_ms=5_000,  # Default
        ),
    },
    exec_clients={
        "GATE": GateExecClientConfig(
            api_key=api_key,
            api_secret=api_secret,
            base_url_http=base_url_http,
            base_urls_ws=base_urls_ws,
            product_types=product_types,
            use_ws_trade_api=True,
            instrument_provider=instrument_provider_config,
            max_retries=1,
            retry_delay=1.0,
            recv_window_ms=5_000,  # Default
        ),
    },
    timeout_connection=20.0,
    timeout_reconciliation=10.0,
    timeout_portfolio=10.0,
    timeout_disconnection=10.0,
    timeout_post_stop=5.0,
)

node = TradingNode(config=config_node)

strat_config = VolatilityMarketMakerConfig(
    instrument_id=InstrumentId.from_str(f"{symbol}-SPOT.GATE"),
    external_order_claims=[InstrumentId.from_str(f"{symbol}-SPOT.GATE")],
    bar_type=BarType.from_str(f"{symbol}.GATE-1-MINUTE-LAST-EXTERNAL"),
    atr_period=20,
    atr_multiple=3.0,
    trade_size=trade_size,
)
strategy = VolatilityMarketMaker(config=strat_config)

node.trader.add_strategy(strategy)
node.add_data_client_factory("GATE", GateLiveDataClientFactory)
node.add_exec_client_factory("GATE", GateLiveExecClientFactory)
node.build()

if __name__ == "__main__":
    try:
        node.run()
    finally:
        node.dispose()
