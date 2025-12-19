from nautilus_trader.adapters.mexc.common.enums import MexcProductType


def get_http_base_url() -> str:
    """Get MEXC HTTP API base URL."""
    return "https://api.mexc.com"


def get_ws_base_url(product_type: MexcProductType) -> str:
    """
    Get MEXC WebSocket base URL for the given product type.
    
    Parameters
    ----------
    product_type : MexcProductType
        The product type.
        
    Returns
    -------
    str
        The WebSocket base URL.
        
    """
    if product_type == MexcProductType.SPOT:
        return "wss://wbs.mexc.com/ws"
    else:
        raise RuntimeError(
            f"invalid `MexcProductType`, was {product_type}",  # pragma: no cover
        )

