# MEXC Exchange Adapter for NautilusTrader

This adapter provides integration with the MEXC cryptocurrency exchange for the NautilusTrader algorithmic trading platform.

## Overview

The MEXC adapter is built following the same architecture as the Gate.io adapter, providing support for:

- **Spot Trading**: Full support for MEXC spot markets
- **Real-time Market Data**: WebSocket streaming for quotes and trades
- **Order Management**: Place, modify, and cancel orders
- **Account Management**: Monitor balances and positions

## Architecture

The adapter follows NautilusTrader's standard adapter structure:

```
mexc/
├── __init__.py
├── common/              # Common utilities and constants
│   ├── constants.py     # Exchange constants and error codes
│   ├── enums.py         # Enum definitions and parsers
│   ├── parsing.py       # Data parsing utilities
│   ├── symbol.py        # Symbol handling
│   └── urls.py          # API endpoint URLs
├── http/                # HTTP REST API clients
│   ├── client.py        # Base HTTP client
│   ├── account.py       # Account API wrapper
│   ├── market.py        # Market data API wrapper
│   └── errors.py        # Error handling
├── websocket/           # WebSocket clients
│   └── client.py        # WebSocket connection manager
├── schemas/             # Data schemas (using msgspec)
│   ├── common.py        # Common schemas
│   ├── instrument.py    # Instrument definitions
│   ├── order.py         # Order schemas
│   ├── trade.py         # Trade/fill schemas
│   ├── position.py      # Position schemas
│   └── account/         # Account-related schemas
│       ├── balance.py
│       └── fee_rate.py
├── config.py            # Configuration classes
├── data.py              # Live data client
├── execution.py         # Live execution client
├── providers.py         # Instrument provider
└── factories.py         # Client factories

## Configuration

### Basic Configuration Example

```python
from nautilus_trader.adapters.mexc.config import MexcDataClientConfig, MexcExecClientConfig
from nautilus_trader.adapters.mexc.common.enums import MexcProductType
from nautilus_trader.adapters.mexc.factories import (
    MexcLiveDataClientFactory,
    MexcLiveExecClientFactory,
)

# Data client configuration
data_config = MexcDataClientConfig(
    api_key="your_api_key",
    api_secret="your_api_secret",
    product_types=[MexcProductType.SPOT],
    update_instruments_interval_mins=60,
)

# Execution client configuration
exec_config = MexcExecClientConfig(
    api_key="your_api_key",
    api_secret="your_api_secret",
    product_types=[MexcProductType.SPOT],
    max_retries=3,
    retry_delay=1.0,
)
```

### Full Trading Node Example

```python
from nautilus_trader.adapters.mexc.config import MexcDataClientConfig, MexcExecClientConfig
from nautilus_trader.adapters.mexc.common.enums import MexcProductType
from nautilus_trader.adapters.mexc.factories import (
    MexcLiveDataClientFactory,
    MexcLiveExecClientFactory,
)
from nautilus_trader.live.node import TradingNode
from nautilus_trader.config import TradingNodeConfig, LoggingConfig

# Configure the trading node
config = TradingNodeConfig(
    data_clients={
        "MEXC": MexcDataClientConfig(
            api_key="your_api_key",
            api_secret="your_api_secret",
            product_types=[MexcProductType.SPOT],
        ),
    },
    exec_clients={
        "MEXC": MexcExecClientConfig(
            api_key="your_api_key",
            api_secret="your_api_secret",
            product_types=[MexcProductType.SPOT],
        ),
    },
    logging=LoggingConfig(log_level="INFO"),
)

# Register factories
node = TradingNode(config=config)
node.add_data_client_factory("MEXC", MexcLiveDataClientFactory)
node.add_exec_client_factory("MEXC", MexcLiveExecClientFactory)

# Add your strategies here
# node.trader.add_strategy(your_strategy)

# Start the node
node.start()
```

## Features

### Market Data

- **Quote Ticks**: Best bid/ask updates via WebSocket
- **Trade Ticks**: Real-time trade feed
- **Instrument Updates**: Periodic instrument definition updates

### Order Types

- **Limit Orders**: Standard limit orders with configurable time-in-force
- **Market Orders**: Immediate execution at market price
- **Post-Only Orders**: Using MEXC's LIMIT_MAKER order type

### Time-in-Force Options

- **GTC (Good-Till-Cancel)**: Order remains active until filled or cancelled
- **IOC (Immediate-Or-Cancel)**: Fill immediately or cancel
- **FOK (Fill-Or-Kill)**: Fill completely or cancel

## API Reference

### MexcSymbol

Handles MEXC symbol formatting with product type suffixes:

```python
from nautilus_trader.adapters.mexc.common.symbol import MexcSymbol

symbol = MexcSymbol("BTCUSDT-SPOT")
print(symbol.raw_symbol)      # "BTCUSDT"
print(symbol.product_type)    # MexcProductType.SPOT
print(symbol.is_spot)         # True
```

### MexcHttpClient

Low-level HTTP client for MEXC API:

```python
from nautilus_trader.adapters.mexc.http.client import MexcHttpClient
from nautilus_trader.common.component import LiveClock

client = MexcHttpClient(
    clock=LiveClock(),
    api_key="your_key",
    api_secret="your_secret",
    base_url="https://api.mexc.com",
)

# Fetch account info
account = await client.fetch_account_info()

# Place order
response = await client.place_order(
    product_type="spot",
    symbol="BTCUSDT",
    side="BUY",
    order_type="LIMIT",
    quantity="0.001",
    price="50000.0",
)
```

## WebSocket Subscriptions

The adapter automatically manages WebSocket subscriptions for:

- **Public Channels**: Trade ticks, quote ticks
- **Private Channels**: Order updates, balance updates

Reconnection and resubscription are handled automatically.

## Error Handling

The adapter includes retry logic for transient errors:

```python
MEXC_RETRY_ERRORS = {
    429,   # Rate limit exceeded
    500,   # Internal server error
    503,   # Service unavailable
}
```

Configurable retry parameters:
- `max_retries`: Maximum number of retry attempts
- `retry_delay`: Delay between retries in seconds

## Testing

Before using in production:

1. **Verify API Credentials**: Test with small orders first
2. **Check Symbol Format**: Ensure symbols follow "BASEQUOTE-SPOT" format
3. **Monitor Rate Limits**: MEXC has rate limits on API calls
4. **Validate Order Sizes**: Check minimum order quantities and notional values

## Differences from Gate Adapter

Key differences to be aware of:

1. **Order Modification**: MEXC doesn't support direct order modification (would need cancel + replace)
2. **WebSocket Format**: Different message structure from Gate.io
3. **Authentication**: Different signature generation method
4. **Symbol Endpoints**: MEXC uses `exchangeInfo` instead of dedicated symbol endpoints

## API Documentation

For detailed MEXC API documentation, visit:
- REST API: https://mexcdevelop.github.io/apidocs/spot_v3_en/
- WebSocket API: https://mexcdevelop.github.io/apidocs/spot_v3_en/#websocket-market-data

## Rate Limits

MEXC has the following rate limits:
- REST API: Varies by endpoint (typically 20-100 requests per second)
- WebSocket: Connection limits apply

The adapter includes rate limiting configured with conservative defaults.

## Support

This adapter is based on the MEXC Spot API v3. For issues or questions:

1. Check MEXC API documentation
2. Review NautilusTrader documentation
3. Check error logs for detailed information

## License

This adapter follows the same license as NautilusTrader (LGPL v3.0).

