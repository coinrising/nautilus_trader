"""HTX adapter configuration."""

from __future__ import annotations

from typing import Dict

from nautilus_trader.config import LiveDataClientConfig, LiveExecClientConfig
from nautilus_trader.config import PositiveFloat, PositiveInt
from nautilus_trader.adapters.htx.common.enums import HtxProductType


class HtxDataClientConfig(LiveDataClientConfig, frozen=True):
    """Configuration for `HtxDataClient`."""
    api_key: str | None = None
    api_secret: str | None = None
    base_url_http: str | None = None
    base_urls_ws: Dict[str, str] | None = None
    product_types: list[HtxProductType] | None = None
    update_instruments_interval_mins: PositiveInt | None = 60
    recv_window_ms: PositiveInt = 5_000


class HtxExecClientConfig(LiveExecClientConfig, frozen=True):
    """Configuration for `HtxExecutionClient`."""
    api_key: str | None = None
    api_secret: str | None = None
    base_url_http: str | None = None
    base_urls_ws: str | None = None
    product_types: list[HtxProductType] | None = None
    max_retries: PositiveInt | None = None
    retry_delay: PositiveFloat | None = None
    recv_window_ms: PositiveInt = 5_000
    account_id: int | None = None  # HTX requires account-id for trading

