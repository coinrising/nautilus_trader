from decimal import Decimal

import msgspec

from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.reports import PositionStatusReport
from nautilus_trader.model.identifiers import AccountId
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Money
from nautilus_trader.model.objects import Quantity


class MexcPosition(msgspec.Struct):
    """
    MEXC position schema.
    
    For spot trading, positions are represented as account balances.
    """
    asset: str
    free: str
    locked: str

    def parse_to_position_status_report(
        self,
        account_id: AccountId,
        instrument_id: InstrumentId,
        report_id: UUID4,
        ts_init: int,
    ) -> PositionStatusReport:
        """Parse to Nautilus PositionStatusReport."""
        # For spot, we don't have actual positions in the derivatives sense
        # This is a placeholder implementation
        return PositionStatusReport(
            account_id=account_id,
            instrument_id=instrument_id,
            position_side=None,
            quantity=Quantity.from_str(self.free),
            report_id=report_id,
            ts_init=ts_init,
            ts_last=ts_init,
        )

