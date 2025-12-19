from decimal import Decimal
import msgspec

from nautilus_trader.model.objects import AccountBalance, Currency, Money


class HtxBalance(msgspec.Struct):
    """HTX account balance schema."""
    currency: str
    type: str  # 'trade', 'frozen'
    balance: str


class HtxAccountInfo(msgspec.Struct):
    """HTX account information schema."""
    id: int
    type: str  # 'spot', 'margin', etc.
    state: str
    list: list[HtxBalance]
    
    def parse_to_account_balances(self) -> list[AccountBalance]:
        """Parse all balances to Nautilus AccountBalance list."""
        balance_dict = {}
        for bal in self.list:
            currency_code = bal.currency.upper()
            if currency_code not in balance_dict:
                balance_dict[currency_code] = {'trade': Decimal('0'), 'frozen': Decimal('0')}
            balance_dict[currency_code][bal.type] = Decimal(bal.balance)
        
        result = []
        for currency_code, amounts in balance_dict.items():
            currency = Currency.from_str(currency_code)
            total = amounts['trade'] + amounts['frozen']
            result.append(AccountBalance(
                total=Money(total, currency),
                locked=Money(amounts['frozen'], currency),
                free=Money(amounts['trade'], currency),
            ))
        return result

