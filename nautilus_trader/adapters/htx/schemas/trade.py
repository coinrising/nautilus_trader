from decimal import Decimal
import msgspec

from nautilus_trader.core.datetime import millis_to_nanos
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.reports import FillReport
from nautilus_trader.model.identifiers import AccountId, InstrumentId, TradeId, VenueOrderId
from nautilus_trader.model.enums import LiquiditySide
from nautilus_trader.model.objects import Money, Price, Quantity

from nautilus_trader.adapters.htx.common.enums import HtxEnumParser, HtxOrderSide


class HtxTrade(msgspec.Struct):
    """HTX trade schema."""
    id: int
    order_id: int
    symbol: str
    price: str
    filled_amount: str
    filled_fees: str
    created_at: int
    role: str  # 'taker' or 'maker'
    match_id: int
    
    def parse_to_fill_report(
        self,
        account_id: AccountId,
        instrument_id: InstrumentId,
        report_id: UUID4,
        enum_parser: HtxEnumParser,
        ts_init: int,
    ) -> FillReport:
        """Parse to Nautilus FillReport."""
        # Determine side from context (needs to be provided separately in real implementation)
        return FillReport(
            account_id=account_id,
            instrument_id=instrument_id,
            venue_order_id=VenueOrderId(str(self.order_id)),
            trade_id=TradeId(str(self.id)),
            order_side=enum_parser.parse_htx_order_side(HtxOrderSide.BUY),  # Placeholder
            last_qty=Quantity.from_str(self.filled_amount),
            last_px=Price.from_str(self.price),
            commission=Money.from_str(f"{self.filled_fees} USDT"),  # Placeholder currency
            liquidity_side=LiquiditySide.MAKER if self.role == 'maker' else LiquiditySide.TAKER,
            ts_event=millis_to_nanos(self.created_at),
            report_id=report_id,
            ts_init=ts_init,
        )

