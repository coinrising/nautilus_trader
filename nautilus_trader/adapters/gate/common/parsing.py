from __future__ import annotations

from nautilus_trader.model.enums import AggressorSide


def parse_aggressor_side(value: str) -> AggressorSide:
    match value:
        case "buy":
            return AggressorSide.BUYER
        case "sell":
            return AggressorSide.SELLER
        case _:
            raise ValueError(f"Invalid aggressor side value, was '{value}'")