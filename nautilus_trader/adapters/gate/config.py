from __future__ import annotations

from typing import Dict

from nautilus_trader.config import LiveDataClientConfig
from nautilus_trader.config import LiveExecClientConfig
from nautilus_trader.config import PositiveFloat
from nautilus_trader.config import PositiveInt
from nautilus_trader.adapters.gate.common.enums import GateProductType


# from typing import TYPE_CHECKING
# if TYPE_CHECKING:
    # from nautilus_trader.adapters.bybit.common.enums import BybitMarginMode
    # from nautilus_trader.adapters.bybit.common.enums import BybitPositionMode
    # from nautilus_trader.adapters.bybit.common.enums import BybitProductType
    # from nautilus_trader.adapters.bybit.common.symbol import BybitSymbol


class GateDataClientConfig(LiveDataClientConfig, frozen=True):
    api_key: str | None = None
    api_secret: str | None = None
    base_url_http: str | None = None
    base_urls_ws: Dict[str, str] | None = None
    product_types: list[GateProductType] | None = None
    update_instruments_interval_mins: PositiveInt | None = 60
    recv_window_ms: PositiveInt = 5_000


class GateExecClientConfig(LiveExecClientConfig, frozen=True):
    api_key: str | None = None
    api_secret: str | None = None
    base_url_http: str | None = None
    base_urls_ws: str | None = None
    product_types: list[GateProductType] | None = None
    use_ws_execution_fast: bool = False
    use_ws_trade_api: bool = False
    use_http_batch_api: bool = False
    max_retries: PositiveInt | None = None
    retry_delay: PositiveFloat | None = None
    recv_window_ms: PositiveInt = 5_000
    ws_trade_timeout_secs: float | None = 5.0
