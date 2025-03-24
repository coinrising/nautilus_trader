from __future__ import annotations

from nautilus_trader.adapters.gate.common.constants import GATE_VENUE
from nautilus_trader.adapters.gate.common.enums import GateProductType
from nautilus_trader.adapters.gate.http.account import GateAccountHttpAPI
from nautilus_trader.adapters.gate.http.client import GateHttpClient
from nautilus_trader.adapters.gate.http.market import GateMarketHttpAPI
from nautilus_trader.adapters.gate.schemas.instrument import GateInstrument
from nautilus_trader.adapters.gate.schemas.account.fee_rate import GateFeeRate
from nautilus_trader.common.providers import InstrumentProvider
from nautilus_trader.config import InstrumentProviderConfig
from nautilus_trader.model.objects import Currency
from nautilus_trader.model.enums import CurrencyType
from nautilus_trader.model.instruments import CurrencyPair
from nautilus_trader.common.component import LiveClock


class GateInstrumentProvider(InstrumentProvider):
    def __init__(
        self,
        client: GateHttpClient,
        clock: LiveClock,
        product_types: list[GateProductType],
        config: InstrumentProviderConfig | None = None,
    ) -> None:
        super().__init__(config=config)
        self._clock = clock
        self._client = client
        self._product_types = product_types

        self._http_market = GateMarketHttpAPI(
            client=client,
            clock=clock,
        )
        self._http_account = GateAccountHttpAPI(
            client=client,
            clock=clock,
        )
        self._log_warnings = config.log_warnings if config else True

    async def load_all_async(self, filters: dict | None = None) -> None:
        filter_symbols = filters.get('symbol')
        await self._load_coins(filter_symbols)

        for product_type in self._product_types:
            target_fee_rate = await self._http_account.fetch_fee_rate(product_type)
            instruments = await self._http_market.fetch_all_instruments(product_type)
            for instrument in instruments:
                currency_pair = self._parse_instrument(instrument, target_fee_rate)
                if filter_symbols and instrument.symbol not in filter_symbols:
                    continue
                self._log.info(f'Added instrument: {currency_pair}')
                self.add(instrument=currency_pair)
        self._log.info(f"Loaded {len(self._instruments)} instruments")

    async def _load_coins(self, filter_symbols) -> None:
        pair_infos = await self._client.fetch_currencie_pairs()
        for pair_info in pair_infos:
            if pair_info['id'] not in filter_symbols:
                continue
            currency = Currency(
                code=pair_info['base'],
                name=pair_info['base'],
                currency_type=CurrencyType.CRYPTO,
                precision=int(pair_info['amount_precision']),
                iso4217=0,  # Currently unspecified for crypto assets
            )
            self.add_currency(currency)

    def _parse_instrument(
        self,
        instrument: GateInstrument,
        fee_rate: GateFeeRate,
    ) -> CurrencyPair:
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