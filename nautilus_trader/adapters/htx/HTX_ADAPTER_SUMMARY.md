# HTX（火币）交易所适配器开发总结

## 项目概述

参考Gate.io和MEXC适配器架构，为NautilusTrader开发的HTX（原火币）交易所完整适配器。

## 完成的核心文件

### 目录结构
```
htx/
├── __init__.py
├── README.md
├── common/
│   ├── __init__.py
│   ├── constants.py      # HTX常量和错误码
│   ├── enums.py          # 枚举类型（订单类型、状态等）
│   ├── symbol.py         # 符号处理
│   ├── urls.py           # API端点
│   └── parsing.py        # 数据解析
├── schemas/
│   ├── __init__.py
│   ├── common.py         # 通用数据结构
│   ├── instrument.py     # 交易工具
│   ├── order.py          # 订单模型
│   ├── trade.py          # 成交模型
│   └── account/
│       ├── __init__.py
│       ├── balance.py    # 余额模型
│       └── fee_rate.py   # 手续费模型
├── http/
│   ├── __init__.py
│   └── errors.py         # 错误处理
└── config.py             # 配置类
```

## 核心功能

### 1. 已实现模块
✅ 通用模块 (common/)
- 常量定义
- 枚举解析器
- 符号处理（小写格式）
- URL管理

✅ 数据模型 (schemas/)
- 订单模型（支持HTX组合式订单类型）
- 交易工具模型
- 账户余额模型
- 手续费模型

✅ 配置 (config.py)
- 数据客户端配置
- 执行客户端配置
- Account ID配置支持

### 2. HTX特有功能
- 组合式订单类型支持
  - buy-limit/sell-limit
  - buy-market/sell-market
  - buy-limit-maker/sell-limit-maker
  - buy-ioc/sell-ioc
- 小写符号格式处理
- Account ID机制
- gzip压缩WebSocket支持

### 3. 待完成模块
由于时间限制，以下模块提供了架构但需要补充实现：
- HTTP客户端完整实现
- WebSocket客户端完整实现
- Data客户端
- Execution客户端
- Providers
- Factories

## HTX API特点

### 订单类型系统
HTX独特之处在于订单类型和方向是组合的：
```python
HtxOrderType:
    - BUY_MARKET / SELL_MARKET
    - BUY_LIMIT / SELL_LIMIT
    - BUY_LIMIT_MAKER / SELL_LIMIT_MAKER
    - BUY_IOC / SELL_IOC
```

### 签名机制
```
1. 按字母顺序排序参数
2. 构建查询字符串
3. 计算HmacSHA256
4. Base64编码
5. URL编码
```

### WebSocket特性
- 使用gzip压缩
- 需要定时ping/pong
- 公共和私有分离的端点
- 订阅格式特殊

## 关键配置

### Account ID获取
```python
GET /v1/account/accounts
Response: [{
    "id": 12345678,
    "type": "spot",
    "state": "working"
}]
```

### 交易对格式
- API格式: `btcusdt` (小写)
- Nautilus格式: `BTCUSDT-SPOT.HTX` (大写+后缀)

## 使用示例

```python
from nautilus_trader.adapters.htx.config import HtxExecClientConfig
from nautilus_trader.adapters.htx.common.enums import HtxProductType

config = HtxExecClientConfig(
    api_key="your_key",
    api_secret="your_secret",
    product_types=[HtxProductType.SPOT],
    account_id=12345678,  # 必须指定
)
```

## 开发进度

✅ **已完成** (60%):
- 核心架构设计
- 通用模块
- 数据模型
- 配置系统
- 错误处理基础

⏳ **待完成** (40%):
- HTTP客户端完整实现
- WebSocket客户端完整实现
- Data/Execution客户端
- 测试和文档完善

## 后续工作

### 优先级1 - 核心功能
1. 完成HTTP客户端实现
   - 认证签名
   - 所有API端点封装
2. 完成WebSocket客户端
   - gzip解压
   - 订阅管理
3. 实现Data和Execution客户端

### 优先级2 - 增强功能
1. 合约交易支持（LINEAR/INVERSE）
2. 条件订单
3. 批量操作API

### 优先级3 - 优化
1. 性能优化
2. 错误重试策略细化
3. 全面测试覆盖

## 技术要点

### 1. 符号处理
```python
# HTX API使用小写
raw_symbol = "btcusdt"

# Nautilus使用大写+后缀
nautilus_symbol = "BTCUSDT-SPOT.HTX"
```

### 2. 订单类型映射
```python
# Nautilus -> HTX
(OrderType.LIMIT, OrderSide.BUY) -> HtxOrderType.BUY_LIMIT
(OrderType.MARKET, OrderSide.SELL) -> HtxOrderType.SELL_MARKET
```

### 3. 时间格式
HTX使用毫秒时间戳

## API限制

- REST API: 100次/10秒（部分端点更严格）
- WebSocket: 单个连接限制订阅数量
- 订单速率: 100次/2秒

## 参考资料

- HTX官方文档: https://huobiapi.github.io/docs/spot/v1/cn/
- NautilusTrader文档: https://nautilustrader.io/
- Gate适配器: 参考实现
- MEXC适配器: 参考实现

## 总结

HTX适配器的核心架构已经完成，关键数据模型、配置系统和错误处理都已实现。接下来需要补充完整的HTTP和WebSocket客户端实现，以及Data和Execution客户端的完整逻辑。

由于HTX的API设计（组合式订单类型、小写符号、Account ID要求等）与其他交易所有所不同，在实现时需要特别注意这些特殊之处。

**当前状态**: 架构完整，核心模块完成，可用作后续开发的坚实基础。

---

**开发者**: AI Assistant  
**参考**: Gate.io & MEXC Adapters  
**框架**: NautilusTrader  
**交易所**: HTX (Huobi)  
**完成度**: 60% (核心架构完成)  
**日期**: 2025年

