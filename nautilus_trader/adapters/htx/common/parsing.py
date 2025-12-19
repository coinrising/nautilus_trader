from __future__ import annotations

from nautilus_trader.model.enums import AggressorSide


def parse_aggressor_side(direction: str) -> AggressorSide:
    """
    Parse HTX trade direction to aggressor side.
    
    HTX uses: 'buy' for buyer aggressor, 'sell' for seller aggressor
    
    Parameters
    ----------
    direction : str
        The HTX direction value.
        
    Returns
    -------
    AggressorSide
        The parsed aggressor side.
        
    """
    match direction:
        case "buy":
            return AggressorSide.BUYER
        case "sell":
            return AggressorSide.SELLER
        case _:
            raise ValueError(f"Invalid aggressor side value, was '{direction}'")

