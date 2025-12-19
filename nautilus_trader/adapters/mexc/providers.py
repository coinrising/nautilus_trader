"""MEXC instrument provider."""

from __future__ import annotations

from nautilus_trader.adapters.mexc.common.constants import MEXC_VENUE
from nautilus_trader.adapters.mexc.common.enums import MexcProductType
from nautilus_trader.adapters.mexc.http.account import MexcAccountHttpAPI
from nautilus_trader.adapters.mexc.http.client import MexcHttpClient
from nautilus_trader.adapters.mexc.http.market import MexcMarketHttpAPI
from nautilus_trader.adapters.mexc.schemas.account.fee_rate import MexcFeeRate
from nautilus_trader.common.component import LiveClock
from nautilus_trader.common.providers import InstrumentProvider
from nautilus_trader.config import InstrumentProviderConfig
from nautilus_trader.model.enums import CurrencyType
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.model.objects import Currency


class MexcInstrumentProvider(InstrumentProvider):
    """
    Provides instruments for the MEXC exchange.
    
    Parameters
    ----------
    client : MexcHttpClient
        The HTTP client.
    clock : LiveClock
        The clock instance.
    product_types : list[MexcProductType]
        The product types to load.
    config : InstrumentProviderConfig, optional
        The configuration.
        
    """

    def __init__(
        self,
        client: MexcHttpClient,
        clock: LiveClock,
        product_types: list[MexcProductType],
        config: InstrumentProviderConfig | None = None,
    ) -> None:
        super().__init__(config=config)
        self._clock = clock
        self._client = client
        self._product_types = product_types

        self._http_market = MexcMarketHttpAPI(
            client=client,
            clock=clock,
        )
        self._http_account = MexcAccountHttpAPI(
            client=client,
            clock=clock,
        )
        self._log_warnings = config.log_warnings if config else True

    async def load_all_async(self, filters: dict | None = None) -> None:
        """
        Load all instruments asynchronously.
        
        Parameters
        ----------
        filters : dict, optional
            The filters to apply.
            
        """
        filter_symbols = filters.get('symbol') if filters else None
        await self._load_currencies(filter_symbols)

        for product_type in self._product_types:
            target_fee_rate = await self._http_account.fetch_fee_rate(product_type)
            instruments = await self._http_market.fetch_all_instruments(product_type)
            for instrument in instruments:
                if filter_symbols and instrument.symbol not in filter_symbols:
                    continue
                currency_pair = self._parse_instrument(instrument, target_fee_rate)
                self._log.info(f'Added instrument: {currency_pair}')
                self.add(instrument=currency_pair)
        self._log.info(f"Loaded {len(self._instruments)} instruments")

    async def _load_currencies(self, filter_symbols: list[str] | None) -> None:
        """Load currencies from exchange info."""
        symbols = await self._client.fetch_symbols()
        
        seen_currencies = set()
        for symbol_info in symbols:
            if filter_symbols and symbol_info['symbol'] not in filter_symbols:
                continue
            
            # Add base currency
            base_asset = symbol_info['baseAsset']
            if base_asset not in seen_currencies:
                base_precision = symbol_info.get('baseAssetPrecision', 8)
                currency = Currency(
                    code=base_asset,
                    name=base_asset,
                    currency_type=CurrencyType.CRYPTO,
                    precision=base_precision,
                    iso4217=0,
                )
                self.add_currency(currency)
                seen_currencies.add(base_asset)
            
            # Add quote currency
            quote_asset = symbol_info['quoteAsset']
            if quote_asset not in seen_currencies:
                quote_precision = symbol_info.get('quoteAssetPrecision', 8)
                currency = Currency(
                    code=quote_asset,
                    name=quote_asset,
                    currency_type=CurrencyType.CRYPTO,
                    precision=quote_precision,
                    iso4217=0,
                )
                self.add_currency(currency)
                seen_currencies.add(quote_asset)

    def _parse_instrument(
        self,
        instrument: any,
        fee_rate: MexcFeeRate,
    ) -> CurrencyPair:
        """Parse instrument to CurrencyPair."""
        try:
            base_currency = self.currency(instrument.baseCoin)
            quote_currency = self.currency(instrument.quoteCoin)
            ts_event = self._clock.timestamp_ns()
            ts_init = self._clock.timestamp_ns()
            return instrument.parse_to_instrument(
                base_currency=base_currency,
                quote_currency=quote_currency,
                fee_rate=fee_rate,
                ts_event=ts_event,
                ts_init=ts_init,
            )
        except ValueError as e:
            if self._log_warnings:
                self._log.warning(
                    f"Unable to parse {instrument.__class__.__name__} instrument {instrument.symbol}: {e}",
                )

