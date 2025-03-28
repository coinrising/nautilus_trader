from decimal import Decimal

import msgspec

from nautilus_trader.model.objects import AccountBalance
from nautilus_trader.model.objects import Currency
from nautilus_trader.model.objects import MarginBalance
from nautilus_trader.model.objects import Money


class GateCoinBalance(msgspec.Struct):
    coin: str
    available: str
    locked: str

    def parse_to_account_balance(self) -> AccountBalance:
        currency = Currency.from_str(self.coin)
        available = Decimal(self.available)
        locked = Decimal(self.locked)
        return AccountBalance(
            total=Money(available + locked, currency),
            free=Money(available, currency),
            locked=Money(locked, currency),
        )

    def parse_to_margin_balance(self) -> MarginBalance:
        currency: Currency = Currency.from_str(self.coin)
        return MarginBalance(
            initial=Money(Decimal(0), currency),
            maintenance=Money(Decimal(0), currency),
        )


class GateWalletBalance(msgspec.Struct):
    coins: list[GateCoinBalance]

    def parse_to_account_balance(self) -> list[AccountBalance]:
        return [coin.parse_to_account_balance() for coin in self.coins if Decimal(coin.available) >= 0]
        # return [coin.parse_to_account_balance() for coin in self.coins]

    def parse_to_margin_balance(self) -> list[MarginBalance]:
        return [coin.parse_to_margin_balance() for coin in self.coins]