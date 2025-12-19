"""MEXC adapter factories."""

from __future__ import annotations

import asyncio
from functools import lru_cache

from nautilus_trader.adapters.mexc.common.enums import MexcProductType
from nautilus_trader.adapters.mexc.common.urls import get_http_base_url, get_ws_base_url
from nautilus_trader.adapters.mexc.config import MexcDataClientConfig
from nautilus_trader.adapters.mexc.config import MexcExecClientConfig
from nautilus_trader.adapters.mexc.data import MexcDataClient
from nautilus_trader.adapters.mexc.execution import MexcExecutionClient
from nautilus_trader.adapters.mexc.http.client import MexcHttpClient
from nautilus_trader.adapters.mexc.providers import MexcInstrumentProvider
from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import LiveClock
from nautilus_trader.common.component import MessageBus
from nautilus_trader.config import InstrumentProviderConfig
from nautilus_trader.core.nautilus_pyo3 import Quota
from nautilus_trader.live.factories import LiveDataClientFactory
from nautilus_trader.live.factories import LiveExecClientFactory


@lru_cache(1)
def get_mexc_http_client(
    clock: LiveClock,
    key: str | None = None,
    secret: str | None = None,
    base_url: str | None = None,
    recv_window_ms: int = 5_000,
) -> MexcHttpClient:
    """
    Get or create a MEXC HTTP client.
    
    Parameters
    ----------
    clock : LiveClock
        The clock instance.
    key : str, optional
        The API key.
    secret : str, optional
        The API secret.
    base_url : str, optional
        The base URL.
    recv_window_ms : int, default 5000
        The receive window in milliseconds.
        
    Returns
    -------
    MexcHttpClient
    
    """
    ratelimiter_quotas: list[tuple[str, Quota]] = []
    ratelimiter_default_quota = Quota.rate_per_second(20)

    return MexcHttpClient(
        clock=clock,
        api_key=key,
        api_secret=secret,
        base_url=base_url or get_http_base_url(),
        recv_window_ms=recv_window_ms,
        ratelimiter_quotas=ratelimiter_quotas,
        ratelimiter_default_quota=ratelimiter_default_quota,
    )


@lru_cache(1)
def get_mexc_instrument_provider(
    client: MexcHttpClient,
    clock: LiveClock,
    product_types: frozenset[MexcProductType],
    config: InstrumentProviderConfig,
) -> MexcInstrumentProvider:
    """
    Get or create a MEXC instrument provider.
    
    Parameters
    ----------
    client : MexcHttpClient
        The HTTP client.
    clock : LiveClock
        The clock instance.
    product_types : frozenset[MexcProductType]
        The product types.
    config : InstrumentProviderConfig
        The configuration.
        
    Returns
    -------
    MexcInstrumentProvider
    
    """
    return MexcInstrumentProvider(
        client=client,
        config=config,
        clock=clock,
        product_types=list(product_types),
    )


class MexcLiveDataClientFactory(LiveDataClientFactory):
    """Factory for creating MEXC data clients."""

    @staticmethod
    def create(  # type: ignore
        loop: asyncio.AbstractEventLoop,
        name: str,
        config: MexcDataClientConfig,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
    ) -> MexcDataClient:
        """
        Create a MEXC data client.
        
        Parameters
        ----------
        loop : asyncio.AbstractEventLoop
            The event loop.
        name : str
            The client name.
        config : MexcDataClientConfig
            The configuration.
        msgbus : MessageBus
            The message bus.
        cache : Cache
            The cache.
        clock : LiveClock
            The clock.
            
        Returns
        -------
        MexcDataClient
        
        """
        # Build WebSocket URLs
        base_urls_ws = config.base_urls_ws or {}
        if not base_urls_ws:
            for product_type in config.product_types:
                base_urls_ws[product_type] = get_ws_base_url(product_type)

        client: MexcHttpClient = get_mexc_http_client(
            clock=clock,
            key=config.api_key,
            secret=config.api_secret,
            base_url=config.base_url_http,
            recv_window_ms=config.recv_window_ms,
        )
        provider = get_mexc_instrument_provider(
            client=client,
            clock=clock,
            product_types=frozenset(config.product_types),
            config=config.instrument_provider,
        )
        
        # Create a new config with WebSocket URLs
        config_with_ws = MexcDataClientConfig(
            **{**config.__dict__, 'base_urls_ws': base_urls_ws}
        )
        
        return MexcDataClient(
            loop=loop,
            client=client,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            instrument_provider=provider,
            product_types=config.product_types,
            config=config_with_ws,
            name=name,
        )


class MexcLiveExecClientFactory(LiveExecClientFactory):
    """Factory for creating MEXC execution clients."""

    @staticmethod
    def create(  # type: ignore
        loop: asyncio.AbstractEventLoop,
        name: str,
        config: MexcExecClientConfig,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
    ) -> MexcExecutionClient:
        """
        Create a MEXC execution client.
        
        Parameters
        ----------
        loop : asyncio.AbstractEventLoop
            The event loop.
        name : str
            The client name.
        config : MexcExecClientConfig
            The configuration.
        msgbus : MessageBus
            The message bus.
        cache : Cache
            The cache.
        clock : LiveClock
            The clock.
            
        Returns
        -------
        MexcExecutionClient
        
        """
        # Build WebSocket URLs
        base_urls_ws = config.base_urls_ws or {}
        if not base_urls_ws:
            for product_type in config.product_types:
                base_urls_ws[product_type] = get_ws_base_url(product_type)

        client: MexcHttpClient = get_mexc_http_client(
            clock=clock,
            key=config.api_key,
            secret=config.api_secret,
            base_url=config.base_url_http,
            recv_window_ms=config.recv_window_ms,
        )
        provider = get_mexc_instrument_provider(
            client=client,
            clock=clock,
            product_types=frozenset(config.product_types),
            config=config.instrument_provider,
        )
        
        # Create a new config with WebSocket URLs
        config_with_ws = MexcExecClientConfig(
            **{**config.__dict__, 'base_urls_ws': base_urls_ws}
        )
        
        return MexcExecutionClient(
            loop=loop,
            client=client,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            instrument_provider=provider,
            product_types=config.product_types,
            config=config_with_ws,
            name=name,
        )

