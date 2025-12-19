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

from typing import Final

from nautilus_trader.adapters.mexc.common.enums import MexcProductType
from nautilus_trader.model.identifiers import Venue


MEXC: Final[str] = "MEXC"
MEXC_VENUE: Final[Venue] = Venue(MEXC)

MEXC_ALL_PRODUCTS: Final[list[MexcProductType]] = [
    MexcProductType.SPOT,
]

# Set of MEXC error codes for which Nautilus will attempt retries,
# potentially temporary conditions where a retry might make sense.
MEXC_RETRY_ERRORS: Final[set[int]] = {
    # > ------------------------------------------------------------
    # > Self defined error codes
    -10_408,  # Client request timed out
    # > ------------------------------------------------------------
    # > MEXC defined error codes
    # > https://mexcdevelop.github.io/apidocs/spot_v3_en/#error-codes
    10_000,  # Server Timeout
    10_002,  # The request time exceeds the time window range
    10_006,  # Too many visits. Exceeded the API Rate Limit
    10_016,  # Server error
    429,     # Rate limit exceeded
    500,     # Internal server error
    503,     # Service unavailable
}

MEXC_MINUTE_INTERVALS: Final[tuple[int, ...]] = (1, 3, 5, 15, 30, 60)
MEXC_HOUR_INTERVALS: Final[tuple[int, ...]] = (1, 2, 4, 6, 12)

MEXC_SPOT_DEPTHS: Final[tuple[int, ...]] = (5, 10, 20, 50, 100)

