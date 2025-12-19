from decimal import Decimal

import msgspec

from nautilus_trader.core.datetime import millis_to_nanos
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.reports import FillReport
from nautilus_trader.model.identifiers import AccountId
from nautilus_trader.model.identifiers import ClientOrderId
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import TradeId
from nautilus_trader.model.identifiers import VenueOrderId
from nautilus_trader.model.enums import LiquiditySide
from nautilus_trader.model.objects import Money
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity

from nautilus_trader.adapters.mexc.common.enums import MexcEnumParser, MexcOrderSide


class MexcTrade(msgspec.Struct):
    """MEXC trade schema."""
    symbol: str
    id: str
    orderId: str
    price: str
    qty: str
    quoteQty: str
    commission: str
    commissionAsset: str
    time: int
    isBuyer: bool
    isMaker: bool
    isBestMatch: bool | None = None

    def parse_to_fill_report(
        self,
        account_id: AccountId,
        instrument_id: InstrumentId,
        report_id: UUID4,
        enum_parser: MexcEnumParser,
        ts_init: int,
    ) -> FillReport:
        """Parse to Nautilus FillReport."""
        from nautilus_trader.model.objects import Currency
        
        side = MexcOrderSide.BUY if self.isBuyer else MexcOrderSide.SELL
        
        return FillReport(
            account_id=account_id,
            instrument_id=instrument_id,
            venue_order_id=VenueOrderId(str(self.orderId)),
            trade_id=TradeId(str(self.id)),
            order_side=enum_parser.parse_mexc_order_side(side),
            last_qty=Quantity.from_str(self.qty),
            last_px=Price.from_str(self.price),
            commission=Money.from_str(f"{self.commission} {self.commissionAsset}"),
            liquidity_side=LiquiditySide.MAKER if self.isMaker else LiquiditySide.TAKER,
            ts_event=millis_to_nanos(self.time),
            report_id=report_id,
            ts_init=ts_init,
        )

