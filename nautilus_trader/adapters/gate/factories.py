from __future__ import annotations
import asyncio

from functools import lru_cache
from typing import TYPE_CHECKING

from nautilus_trader.adapters.gate.common.enums import GateProductType
from nautilus_trader.adapters.gate.config import GateDataClientConfig, GateExecClientConfig
from nautilus_trader.adapters.gate.data import GateDataClient
from nautilus_trader.adapters.gate.execution import GateExecutionClient
from nautilus_trader.adapters.gate.http.client import GateHttpClient
from nautilus_trader.adapters.gate.providers import GateInstrumentProvider
from nautilus_trader.config import InstrumentProviderConfig
from nautilus_trader.core.nautilus_pyo3 import Quota
from nautilus_trader.live.factories import LiveDataClientFactory
from nautilus_trader.live.factories import LiveExecClientFactory
from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import LiveClock
from nautilus_trader.common.component import MessageBus


@lru_cache(1)
def get_gate_http_client(
    clock: LiveClock,
    key: str | None = None,
    secret: str | None = None,
    base_url: str | None = None,
    recv_window_ms: int = 5_000,
) -> GateHttpClient:
    ratelimiter_quotas: list[tuple[str, Quota]] = []
    ratelimiter_default_quota = Quota.rate_per_second(20)

    return GateHttpClient(
        clock=clock,
        api_key=key,
        api_secret=secret,
        base_url=base_url,
        recv_window_ms=recv_window_ms,
        ratelimiter_quotas=ratelimiter_quotas,
        ratelimiter_default_quota=ratelimiter_default_quota,
    )


@lru_cache(1)
def get_gate_instrument_provider(
    client: GateHttpClient,
    clock: LiveClock,
    product_types: frozenset[GateProductType],
    config: InstrumentProviderConfig,
) -> GateInstrumentProvider:
    return GateInstrumentProvider(
        client=client,
        config=config,
        clock=clock,
        product_types=list(product_types),
    )


class GateLiveDataClientFactory(LiveDataClientFactory):
    @staticmethod
    def create(  # type: ignore
        loop: asyncio.AbstractEventLoop,
        name: str,
        config: GateDataClientConfig,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
    ) -> GateDataClient:
        client: GateHttpClient = get_gate_http_client(
            clock=clock,
            key=config.api_key,
            secret=config.api_secret,
            base_url=config.base_url_http,
            recv_window_ms=config.recv_window_ms,
        )
        provider = get_gate_instrument_provider(
            client=client,
            clock=clock,
            product_types=frozenset(config.product_types),
            config=config.instrument_provider,
        )
        return GateDataClient(
            loop=loop,
            client=client,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            instrument_provider=provider,
            product_types=config.product_types,
            config=config,
            name=name,
        )


class GateLiveExecClientFactory(LiveExecClientFactory):
    @staticmethod
    def create(  # type: ignore
        loop: asyncio.AbstractEventLoop,
        name: str,
        config: GateExecClientConfig,
        msgbus: MessageBus,
        cache: Cache,
        clock: LiveClock,
    ) -> GateExecutionClient:
        client: GateHttpClient = get_gate_http_client(
            clock=clock,
            key=config.api_key,
            secret=config.api_secret,
            base_url=config.base_url_http,
            recv_window_ms=config.recv_window_ms,
        )
        provider = get_gate_instrument_provider(
            client=client,
            clock=clock,
            product_types=frozenset(config.product_types),
            config=config.instrument_provider,
        )
        return GateExecutionClient(
            loop=loop,
            client=client,
            msgbus=msgbus,
            cache=cache,
            clock=clock,
            instrument_provider=provider,
            product_types=config.product_types,
            config=config,
            name=name,
        )
