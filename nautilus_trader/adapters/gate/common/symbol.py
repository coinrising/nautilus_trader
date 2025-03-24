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

from nautilus_trader.adapters.gate.common.constants import GATE_VENUE
from nautilus_trader.adapters.gate.common.enums import GateProductType
from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import Symbol


VALID_SUFFIXES: Final[list[str]] = ["-SPOT", "-LINEAR", "-INVERSE", "-OPTION"]


def has_valid_bybit_suffix(symbol: str) -> bool:
    """
    Return whether the given `symbol` string contains a valid Bybit suffix.

    Parameters
    ----------
    symbol : str
        The symbol string value to check.

    Returns
    -------
    bool
        True if contains a valid suffix, else False.

    """
    for suffix in VALID_SUFFIXES:
        if suffix in symbol:
            return True
    return False


class GateSymbol(str):
    """
    Represents a Bybit specific symbol containing a product type suffix.
    """

    def __new__(cls, symbol: str) -> GateSymbol:  # noqa: PYI034
        PyCondition.valid_string(symbol, "symbol")
        if not has_valid_bybit_suffix(symbol):
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
        Return the raw Bybit symbol (without the product type suffix).

        Returns
        -------
        str

        """
        return str(self).rpartition("-")[0]

    @property
    def product_type(self) -> GateProductType:
        """
        Return the Bybit product type for the symbol.

        Returns
        -------
        GateProductType

        """
        if "-SPOT" in self:
            return GateProductType.SPOT
        elif "-LINEAR" in self:
            return GateProductType.LINEAR
        elif "-INVERSE" in self:
            return GateProductType.INVERSE
        elif "-OPTION" in self:
            return GateProductType.OPTION
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
        return self.product_type == GateProductType.SPOT

    @property
    def is_linear(self) -> bool:
        """
        Return whether a LINEAR product type.

        Returns
        -------
        bool

        """
        return self.product_type == GateProductType.LINEAR

    @property
    def is_inverse(self) -> bool:
        """
        Return whether an INVERSE product type.

        Returns
        -------
        bool

        """
        return self.product_type == GateProductType.INVERSE

    @property
    def is_option(self) -> bool:
        """
        Return whether an OPTION product type.

        Returns
        -------
        bool

        """
        return self.product_type == GateProductType.OPTION

    def to_instrument_id(self) -> InstrumentId:
        """
        Parse the Bybit symbol into a Nautilus instrument ID.

        Returns
        -------
        InstrumentId

        """
        return InstrumentId(Symbol(str(self)), GATE_VENUE)
