from nautilus_trader.adapters.gate.common.enums import GateProductType


def get_ws_base_url(product_type: GateProductType) -> str:
    if product_type == GateProductType.SPOT:
        return f"wss://api.gateio.ws/ws/v4/"
    else:
        raise RuntimeError(
            f"invalid `GateProductType`, was {product_type}",  # pragma: no cover
        )