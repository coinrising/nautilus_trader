from decimal import Decimal

import msgspec

from nautilus_trader.adapters.gate.common.enums import GateEnumParser
from nautilus_trader.adapters.gate.common.enums import GateOrderSide
from nautilus_trader.core.datetime import millis_to_nanos
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.reports import FillReport
from nautilus_trader.execution.reports import OrderStatusReport
from nautilus_trader.model.enums import LiquiditySide
from nautilus_trader.model.identifiers import AccountId
from nautilus_trader.model.identifiers import ClientOrderId
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.identifiers import TradeId
from nautilus_trader.model.identifiers import VenueOrderId
from nautilus_trader.model.objects import Currency
from nautilus_trader.model.objects import Money
from nautilus_trader.model.objects import Price
from nautilus_trader.model.objects import Quantity


class GateExecution(msgspec.Struct, omit_defaults=True, kw_only=True):
    execId: str  # "id": "1232893232",
    orderId: str  # "order_id": "4128442423",
    clientOrderId: str  # "text": "t-test"
    side: GateOrderSide  # "side": "buy",
    execFee: str  # "fee": "0.0005",
    execPrice: str  # "price": "0.03",
    execQty: str  # "amount": "0.15",
    execTime: str  # "create_time_ms": "1548000000123.456",
    feeCurrency: str  # "fee_currency": "ETH",
    isMaker: bool  # "role": "maker",
    seq: int  # "sequence_id": "588018",

    def parse_to_fill_report(
        self,
        account_id: AccountId,
        instrument_id: InstrumentId,
        report_id: UUID4,
        enum_parser: GateEnumParser,
        ts_init: int,
    ) -> OrderStatusReport:
        client_order_id = ClientOrderId(self.orderId) if self.orderId else None
        return FillReport(
            client_order_id=client_order_id,
            venue_order_id=VenueOrderId(str(self.execId)),
            trade_id=TradeId(self.execId),
            account_id=account_id,
            instrument_id=instrument_id,
            order_side=enum_parser.parse_gate_order_side(self.side),
            last_qty=Quantity.from_str(self.execQty),
            last_px=Price.from_str(self.execPrice),
            commission=Money(
                Decimal(self.execFee or 0),
                Currency.from_str(self.feeCurrency or "USDT"),
            ),
            liquidity_side=LiquiditySide.MAKER if self.isMaker else LiquiditySide.TAKER,
            report_id=report_id,
            ts_event=millis_to_nanos(Decimal(self.execTime)),
            ts_init=ts_init,
        )