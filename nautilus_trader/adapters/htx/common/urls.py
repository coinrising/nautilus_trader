from nautilus_trader.adapters.htx.common.enums import HtxProductType


def get_http_base_url() -> str:
    """Get HTX HTTP API base URL."""
    return "https://api.huobi.pro"


def get_ws_base_url(product_type: HtxProductType) -> str:
    """
    Get HTX WebSocket base URL for the given product type.
    
    Parameters
    ----------
    product_type : HtxProductType
        The product type.
        
    Returns
    -------
    str
        The WebSocket base URL.
        
    """
    if product_type == HtxProductType.SPOT:
        return "wss://api.huobi.pro/ws"
    elif product_type == HtxProductType.LINEAR:
        return "wss://api.hbdm.com/linear-swap-ws"
    elif product_type == HtxProductType.INVERSE:
        return "wss://api.hbdm.com/swap-ws"
    else:
        raise RuntimeError(f"invalid `HtxProductType`, was {product_type}")


def get_ws_private_url(product_type: HtxProductType) -> str:
    """
    Get HTX private WebSocket URL for the given product type.
    
    Parameters
    ----------
    product_type : HtxProductType
        The product type.
        
    Returns
    -------
    str
        The private WebSocket URL.
        
    """
    if product_type == HtxProductType.SPOT:
        return "wss://api.huobi.pro/ws/v2"
    elif product_type == HtxProductType.LINEAR:
        return "wss://api.hbdm.com/linear-swap-notification"
    elif product_type == HtxProductType.INVERSE:
        return "wss://api.hbdm.com/swap-notification"
    else:
        raise RuntimeError(f"invalid `HtxProductType`, was {product_type}")

