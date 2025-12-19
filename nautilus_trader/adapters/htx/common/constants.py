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

from nautilus_trader.adapters.htx.common.enums import HtxProductType
from nautilus_trader.model.identifiers import Venue


HTX: Final[str] = "HTX"
HTX_VENUE: Final[Venue] = Venue(HTX)

HTX_ALL_PRODUCTS: Final[list[HtxProductType]] = [
    HtxProductType.SPOT,
    HtxProductType.LINEAR,
]

# HTX error codes for retry
HTX_RETRY_ERRORS: Final[set[str]] = {
    "api-signature-not-valid",  # Signature verification failed
    "gateway-internal-error",   # Internal error
    "request-timeout",          # Request timeout
    "system-maintenance",       # System maintenance
    "rate-limit",              # Rate limit
}

HTX_MINUTE_INTERVALS: Final[tuple[str, ...]] = ("1min", "5min", "15min", "30min", "60min")
HTX_HOUR_INTERVALS: Final[tuple[str, ...]] = ("4hour", "1day", "1week", "1mon", "1year")

HTX_SPOT_DEPTHS: Final[tuple[int, ...]] = (5, 10, 20, 50, 100, 150)

