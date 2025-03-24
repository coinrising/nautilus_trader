import msgspec

from nautilus_trader.adapters.gate.common.enums import GatePositionSide
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.reports import PositionStatusReport
from nautilus_trader.model.identifiers import AccountId
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity


class GatePosition(msgspec.Struct):
    symbol: str
    side: GatePositionSide
    size: str
    lock: str

    def parse_to_position_status_report(
        self,
        account_id: AccountId,
        instrument_id: InstrumentId,
        report_id: UUID4,
        ts_init: int,
    ) -> PositionStatusReport:
        position_side = self.side.parse_to_position_side()
        size = Quantity.from_str(self.size)
        return PositionStatusReport(
            account_id=account_id,
            instrument_id=instrument_id,
            position_side=position_side,
            quantity=size,
            report_id=report_id,
            ts_init=ts_init,
            ts_last=ts_init,
        )
