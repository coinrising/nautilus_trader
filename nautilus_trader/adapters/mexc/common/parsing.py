from __future__ import annotations

from nautilus_trader.model.enums import AggressorSide


def parse_aggressor_side(value: int) -> AggressorSide:
    """
    Parse MEXC aggressor side value.
    
    MEXC uses: 1 for buyer (taker buy), 2 for seller (taker sell)
    
    Parameters
    ----------
    value : int
        The MEXC side value.
        
    Returns
    -------
    AggressorSide
        The parsed aggressor side.
        
    """
    match value:
        case 1:
            return AggressorSide.BUYER
        case 2:
            return AggressorSide.SELLER
        case _:
            raise ValueError(f"Invalid aggressor side value, was '{value}'")

