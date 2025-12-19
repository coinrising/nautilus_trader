"""MEXC adapter configuration."""

from __future__ import annotations

from typing import Dict

from nautilus_trader.config import LiveDataClientConfig
from nautilus_trader.config import LiveExecClientConfig
from nautilus_trader.config import PositiveFloat
from nautilus_trader.config import PositiveInt
from nautilus_trader.adapters.mexc.common.enums import MexcProductType


class MexcDataClientConfig(LiveDataClientConfig, frozen=True):
    """
    Configuration for `MexcDataClient`.
    
    Parameters
    ----------
    api_key : str, optional
        The MEXC API key.
    api_secret : str, optional
        The MEXC API secret.
    base_url_http : str, optional
        The HTTP API base URL.
    base_urls_ws : dict[str, str], optional
        The WebSocket base URLs by product type.
    product_types : list[MexcProductType], optional
        The product types to subscribe to.
    update_instruments_interval_mins : PositiveInt, optional
        The interval (minutes) to update instruments.
    recv_window_ms : PositiveInt, default 5000
        The receive window in milliseconds.
        
    """
    
    api_key: str | None = None
    api_secret: str | None = None
    base_url_http: str | None = None
    base_urls_ws: Dict[str, str] | None = None
    product_types: list[MexcProductType] | None = None
    update_instruments_interval_mins: PositiveInt | None = 60
    recv_window_ms: PositiveInt = 5_000


class MexcExecClientConfig(LiveExecClientConfig, frozen=True):
    """
    Configuration for `MexcExecutionClient`.
    
    Parameters
    ----------
    api_key : str, optional
        The MEXC API key.
    api_secret : str, optional
        The MEXC API secret.
    base_url_http : str, optional
        The HTTP API base URL.
    base_urls_ws : str, optional
        The WebSocket base URL.
    product_types : list[MexcProductType], optional
        The product types to trade.
    max_retries : PositiveInt, optional
        The maximum number of retries for failed requests.
    retry_delay : PositiveFloat, optional
        The delay (seconds) between retries.
    recv_window_ms : PositiveInt, default 5000
        The receive window in milliseconds.
        
    """
    
    api_key: str | None = None
    api_secret: str | None = None
    base_url_http: str | None = None
    base_urls_ws: str | None = None
    product_types: list[MexcProductType] | None = None
    max_retries: PositiveInt | None = None
    retry_delay: PositiveFloat | None = None
    recv_window_ms: PositiveInt = 5_000

