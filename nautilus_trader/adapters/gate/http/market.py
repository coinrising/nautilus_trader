# -------------------------------------------------------------------------------------------------
#  Copyright (C) 2015-2025 Nautech Systems Pty Ltd. All rights reserved.
#  https://nautechsystems.io
#
#  Licensed under the GNU Lesser General Public License Version 3.0 (the "License");
#  You may not use this file except in compliance with the License.
#  You may obtain a copy of the License at https://www.gnu.org/licenses/lgpl-3.0.en.html
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
# -------------------------------------------------------------------------------------------------

from __future__ import annotations

from typing import TYPE_CHECKING

from nautilus_trader.adapters.gate.common.enums import GateKlineInterval
from nautilus_trader.adapters.gate.common.enums import GateProductType
from nautilus_trader.adapters.gate.common.symbol import GateSymbol

from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.adapters.gate.http.client import GateHttpClient
from nautilus_trader.adapters.gate.schemas.common import SpotLotSizeFilter
from nautilus_trader.adapters.gate.schemas.common import SpotPriceFilter
from nautilus_trader.adapters.gate.schemas.instrument import GateInstrument, GateInstrumentSpot
from nautilus_trader.adapters.gate.schemas.instrument import GateInstrumentList
from nautilus_trader.adapters.gate.schemas.market.ticker import BybitTickerList

if TYPE_CHECKING:
    from nautilus_trader.common.component import LiveClock
    from nautilus_trader.model.data import Bar
    from nautilus_trader.model.data import BarType
    from nautilus_trader.model.data import TradeTick
    from nautilus_trader.model.identifiers import InstrumentId

def _cvt_precision(raw_precision: str) -> str:
    if raw_precision == '0':
        return '1'
    else:
        return '0.' + '0' * (int(raw_precision) - 1) + '1'

class GateMarketHttpAPI:
    def __init__(
        self,
        client: GateHttpClient,
        clock: LiveClock,
    ) -> None:
        PyCondition.not_none(client, "client")
        self.client = client
        self._clock = clock
        self.base_endpoint = "/v5/market/"

    def _get_url(self, url: str) -> str:
        return self.base_endpoint + url

    async def fetch_tickers(
        self,
        product_type: GateProductType,
        symbol: str | None = None,
        base_coin: str | None = None,
    ) -> BybitTickerList:
        response = await self._endpoint_tickers.get(
            BybitTickersGetParams(
                category=product_type,
                symbol=symbol,
                baseCoin=base_coin,
            ),
        )
        return response.result.list

    # async def fetch_server_time(self) -> BybitServerTime:
    #     response = await self._endpoint_server_time.get()
    #     return response.result

    async def fetch_all_instruments(
        self,
        product_type: GateProductType,
        symbol: str | None = None,
        status: str | None = None,
        base_coin: str | None = None,
    ) -> GateInstrumentList:
        all_instruments: list[GateInstrument] = []
        if product_type == GateProductType.SPOT:
            pair_infos = await self.client.fetch_currencie_pairs()
            for pair_info in pair_infos:
                all_instruments.append(GateInstrumentSpot(
                    symbol=pair_info['id'],
                    status=pair_info['trade_status'],
                    baseCoin=pair_info['base'],
                    quoteCoin=pair_info['quote'],
                    marginTrading=False,
                    lotSizeFilter=SpotLotSizeFilter(
                        basePrecision=_cvt_precision(pair_info['amount_precision']),
                        quotePrecision=_cvt_precision(pair_info['amount_precision']),
                        minOrderQty=pair_info['min_base_amount'],
                        maxOrderQty=pair_info.get('max_base_amount', '100000000'),
                        minOrderAmt=pair_info['min_quote_amount'],
                        maxOrderAmt=pair_info.get('max_quote_amount', '100000000'),
                    ),
                    priceFilter=SpotPriceFilter(
                        tickSize=_cvt_precision(pair_info['precision']),
                    )
                ))
        else:
            raise ValueError(f"Unsupported product type: {product_type}")
        return all_instruments

    async def request_bybit_trades(
        self,
        instrument_id: InstrumentId,
        ts_init: int,
        limit: int = 1000,
    ) -> list[Bar]:
        bybit_symbol = GateSymbol(instrument_id.symbol.value)
        trades = await self.fetch_public_trades(
            symbol=bybit_symbol.raw_symbol,
            product_type=bybit_symbol.product_type,
            limit=limit,
        )
        trade_ticks: list[TradeTick] = [t.parse_to_trade(instrument_id, ts_init) for t in trades]
        return trade_ticks

    async def request_bybit_bars(
        self,
        bar_type: BarType,
        interval: GateKlineInterval,
        ts_init: int,
        limit: int | None = None,
        start: int | None = None,
        end: int | None = None,
    ) -> list[Bar]:
        bybit_symbol = GateSymbol(bar_type.instrument_id.symbol.value)

        all_bars: list[Bar] = []
        prev_start: int | None = None
        seen_timestamps: set[int] = set()

        while True:
            if prev_start is not None and prev_start == start:
                break
            prev_start = start

            klines = await self.fetch_klines(
                symbol=bybit_symbol.raw_symbol,
                product_type=bybit_symbol.product_type,
                interval=interval,
                limit=1000,  # Limit for data size per page (maximum for the Bybit API)
                start=start,
                end=end,
            )

            if not klines:
                break

            klines.sort(key=lambda k: int(k.startTime))
            new_bars = [
                kline.parse_to_bar(bar_type, ts_init)
                for kline in klines
                if int(kline.startTime) not in seen_timestamps
            ]

            all_bars.extend(new_bars)
            seen_timestamps.update(int(kline.startTime) for kline in klines)

            start = int(klines[-1].startTime) + 1

            if end is not None and start > end:
                break

        if limit is not None and len(all_bars) > limit:
            return all_bars[-limit:]

        return all_bars
