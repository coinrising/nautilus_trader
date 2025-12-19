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

from nautilus_trader.adapters.htx.common.constants import HTX_VENUE
from nautilus_trader.adapters.htx.common.enums import HtxProductType
from nautilus_trader.core.correctness import PyCondition
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import Symbol


VALID_SUFFIXES: Final[list[str]] = ["-SPOT", "-LINEAR", "-INVERSE"]


def has_valid_htx_suffix(symbol: str) -> bool:
    for suffix in VALID_SUFFIXES:
        if suffix in symbol:
            return True
    return False


class HtxSymbol(str):
    """HTX symbol with product type suffix."""
    
    def __new__(cls, symbol: str) -> HtxSymbol:  # noqa: PYI034
        PyCondition.valid_string(symbol, "symbol")
        if not has_valid_htx_suffix(symbol):
            raise ValueError(
                f"Invalid symbol '{symbol}': "
                f"does not contain a valid suffix from {VALID_SUFFIXES}",
            )
        
        return super().__new__(cls, symbol.lower())  # HTX uses lowercase
    
    @property
    def raw_symbol(self) -> str:
        """Return the raw HTX symbol (without the product type suffix)."""
        return str(self).rpartition("-")[0]
    
    @property
    def product_type(self) -> HtxProductType:
        """Return the HTX product type for the symbol."""
        upper_self = str(self).upper()
        if "-SPOT" in upper_self:
            return HtxProductType.SPOT
        elif "-LINEAR" in upper_self:
            return HtxProductType.LINEAR
        elif "-INVERSE" in upper_self:
            return HtxProductType.INVERSE
        else:
            raise ValueError(f"Unknown product type for symbol {self}")
    
    @property
    def is_spot(self) -> bool:
        return self.product_type == HtxProductType.SPOT
    
    @property
    def is_linear(self) -> bool:
        return self.product_type == HtxProductType.LINEAR
    
    @property
    def is_inverse(self) -> bool:
        return self.product_type == HtxProductType.INVERSE
    
    def to_instrument_id(self) -> InstrumentId:
        """Parse the HTX symbol into a Nautilus instrument ID."""
        return InstrumentId(Symbol(str(self).upper()), HTX_VENUE)

