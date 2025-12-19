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

from typing import Final

from nautilus_trader.adapters.mexc.common.constants import MEXC_VENUE
from nautilus_trader.adapters.mexc.common.enums import MexcProductType
from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import Symbol


VALID_SUFFIXES: Final[list[str]] = ["-SPOT", "-LINEAR", "-INVERSE"]


def has_valid_mexc_suffix(symbol: str) -> bool:
    for suffix in VALID_SUFFIXES:
        if suffix in symbol:
            return True
    return False


class MexcSymbol(str):
    def __new__(cls, symbol: str) -> MexcSymbol:  # noqa: PYI034
        PyCondition.valid_string(symbol, "symbol")
        if not has_valid_mexc_suffix(symbol):
            raise ValueError(
                f"Invalid symbol '{symbol}': "
                f"does not contain a valid suffix from {VALID_SUFFIXES}",
            )

        return super().__new__(
            cls,
            symbol.upper(),
        )

    @property
    def raw_symbol(self) -> str:
        """
        Return the raw MEXC symbol (without the product type suffix).

        Returns
        -------
        str

        """
        return str(self).rpartition("-")[0]

    @property
    def product_type(self) -> MexcProductType:
        """
        Return the MEXC product type for the symbol.

        Returns
        -------
        MexcProductType

        """
        if "-SPOT" in self:
            return MexcProductType.SPOT
        elif "-LINEAR" in self:
            return MexcProductType.LINEAR
        elif "-INVERSE" in self:
            return MexcProductType.INVERSE
        else:
            raise ValueError(f"Unknown product type for symbol {self}")

    @property
    def is_spot(self) -> bool:
        """
        Return whether a SPOT product type.

        Returns
        -------
        bool

        """
        return self.product_type == MexcProductType.SPOT

    @property
    def is_linear(self) -> bool:
        """
        Return whether a LINEAR product type.

        Returns
        -------
        bool

        """
        return self.product_type == MexcProductType.LINEAR

    @property
    def is_inverse(self) -> bool:
        """
        Return whether an INVERSE product type.

        Returns
        -------
        bool

        """
        return self.product_type == MexcProductType.INVERSE

    def to_instrument_id(self) -> InstrumentId:
        """
        Parse the MEXC symbol into a Nautilus instrument ID.

        Returns
        -------
        InstrumentId

        """
        return InstrumentId(Symbol(str(self)), MEXC_VENUE)

