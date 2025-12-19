# HTX (Huobi) Exchange Adapter for NautilusTrader

## 概述

HTX（原火币）交易所适配器，为NautilusTrader提供完整的交易功能支持。

## 功能特性

- ✅ 现货交易 (Spot Trading)
- ✅ 实时市场数据 (WebSocket)
- ✅ 订单管理（限价单、市价单、IOC、Post-Only）
- ✅ 账户管理
- ✅ 自动重连机制

## 目录结构

```
htx/
├── common/          # 通用模块
├── http/            # HTTP REST API
├── websocket/       # WebSocket客户端
├── schemas/         # 数据模型
├── config.py        # 配置
├── data.py          # 行情客户端
├── execution.py     # 交易客户端
├── providers.py     # 工具提供者
└── factories.py     # 工厂类
```

## 配置示例

```python
from nautilus_trader.adapters.htx.config import HtxDataClientConfig, HtxExecClientConfig
from nautilus_trader.adapters.htx.common.enums import HtxProductType

# 数据客户端配置
data_config = HtxDataClientConfig(
    api_key="your_api_key",
    api_secret="your_api_secret",
    product_types=[HtxProductType.SPOT],
)

# 执行客户端配置
exec_config = HtxExecClientConfig(
    api_key="your_api_key",
    api_secret="your_api_secret",
    product_types=[HtxProductType.SPOT],
    account_id=12345678,  # HTX需要指定account-id
)
```

## HTX特点

### 订单类型
HTX使用组合式订单类型：
- `buy-limit` / `sell-limit`: 限价单
- `buy-market` / `sell-market`: 市价单
- `buy-limit-maker` / `sell-limit-maker`: Post-Only单
- `buy-ioc` / `sell-ioc`: IOC单

### 账户ID
HTX要求在下单时指定account-id，需要通过API获取：
```python
GET /v1/account/accounts
```

### WebSocket
- 公共数据: `wss://api.huobi.pro/ws`
- 私有数据: `wss://api.huobi.pro/ws/v2`
- 数据压缩: gzip压缩

## API文档

- REST API: https://huobiapi.github.io/docs/spot/v1/cn/
- WebSocket: https://huobiapi.github.io/docs/spot/v1/cn/#websocket

## 注意事项

1. HTX使用小写符号（如`btcusdt`）
2. 需要先获取account-id才能交易
3. WebSocket消息使用gzip压缩
4. 签名方式与其他交易所略有不同

## License

LGPL v3.0 (same as NautilusTrader)

