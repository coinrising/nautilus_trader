from decimal import Decimal

import msgspec

from nautilus_trader.model.objects import AccountBalance
from nautilus_trader.model.objects import Currency
from nautilus_trader.model.objects import Money


class MexcBalance(msgspec.Struct):
    """MEXC account balance schema."""
    asset: str
    free: str
    locked: str

    def parse_to_account_balance(self) -> AccountBalance:
        """Parse to Nautilus AccountBalance."""
        currency = Currency.from_str(self.asset)
        total = Decimal(self.free) + Decimal(self.locked)
        return AccountBalance(
            total=Money(total, currency),
            locked=Money(Decimal(self.locked), currency),
            free=Money(Decimal(self.free), currency),
        )


class MexcAccountInfo(msgspec.Struct):
    """MEXC account information schema."""
    makerCommission: int
    takerCommission: int
    buyerCommission: int
    sellerCommission: int
    canTrade: bool
    canWithdraw: bool
    canDeposit: bool
    updateTime: int
    accountType: str
    balances: list[MexcBalance]

    def parse_to_account_balances(self) -> list[AccountBalance]:
        """Parse all balances to Nautilus AccountBalance list."""
        return [balance.parse_to_account_balance() for balance in self.balances]

