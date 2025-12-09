# Gate.io WebSocket 认证失效处理架构

## 问题背景

Gate.io 的私有频道 WebSocket 需要 login 认证，但在运行过程中认证可能会失效，导致：
- 私有频道订阅失败
- 订单操作失败
- 账户更新消息丢失

## 架构设计

### 1. 认证状态管理

在 `GateWebSocketClient` 中添加了完整的认证状态管理：

- **状态跟踪**：`_is_authenticated` 布尔标志跟踪当前认证状态
- **锁机制**：`_auth_lock` 确保认证操作的线程安全
- **时间戳**：`_last_login_time` 记录最后登录时间
- **重试计数**：`_login_retry_count` 跟踪重试次数

### 2. 多层认证失效检测

#### 2.1 消息级别检测
在 `_keep_listening` 中，对所有接收到的消息进行认证错误检测：
```python
if self._check_auth_error(msg):
    await self._handle_auth_failure()
```

#### 2.2 统一错误检测方法
`_check_auth_error()` 方法统一检测各种格式的认证错误：
- `data.errs.message` 中包含 "not login"、"unauthorized"、"authentication"
- `error` 字段中包含认证相关错误

#### 2.3 执行客户端级别检测
在 `GateExecutionClient._check_and_handle_auth_error()` 中，对所有私有频道消息进行统一检测。

### 3. 自动重认证机制

#### 3.1 定期刷新
`_keep_login` 任务每 5 分钟自动刷新认证，确保认证不会过期。

#### 3.2 失效时重认证
当检测到认证失效时：
1. 立即触发 `_handle_auth_failure()`
2. 使用 `_perform_login_with_retry()` 进行重试登录（最多 3 次）
3. 登录成功后自动重新订阅所有私有频道

#### 3.3 重试策略
- 最多重试 3 次
- 指数退避：2^attempt 秒延迟
- 失败后 30 秒后再次尝试

### 4. 重新订阅机制

认证成功后，`_resubscribe_private_channels()` 会自动：
- 遍历所有已保存的私有频道订阅
- 逐个重新订阅
- 添加小延迟避免服务器过载

### 5. 连接重建时的处理

当 WebSocket 连接断开并重建时：
- 自动重置认证状态（`_is_authenticated = False`）
- 在 `_subscribe_all()` 中，如果启用登录且未认证，会先尝试登录
- 然后按顺序订阅公共和私有频道

## 关键改进点

### 1. 移除 `asyncio.run()` 的使用
之前代码在同步上下文中使用 `asyncio.run()` 会导致问题，现在所有操作都是异步的。

### 2. 统一错误处理
所有私有频道消息都通过统一的 `_check_and_handle_auth_error()` 方法检测认证错误。

### 3. 状态同步
登录响应通过 `set_authenticated()` 方法更新客户端状态，确保状态一致性。

### 4. 防止重复处理
使用 `_auth_lock` 锁机制防止并发认证操作导致的竞态条件。

## 使用流程

### 初始化
```python
ws_client = GateWebSocketClient(...)
ws_client.enable_login = True  # 启用登录
await ws_client.connect()  # 连接并启动后台任务
```

### 订阅私有频道
```python
await ws_client.subscribe_balances_update()
await ws_client.subscribe_orders_update()
```

### 认证状态查询
```python
if ws_client.is_authenticated:
    # 已认证，可以安全操作
    pass
```

## 错误处理流程

1. **检测到认证错误** → `_check_auth_error()` 返回 True
2. **触发重认证** → `_handle_auth_failure()` 被调用
3. **执行登录** → `_perform_login_with_retry()` 尝试登录
4. **等待响应** → 登录响应通过 `_handle_login_response()` 处理
5. **更新状态** → `set_authenticated(True)` 更新状态
6. **重新订阅** → `_resubscribe_private_channels()` 恢复所有订阅

## 配置参数

- `_max_login_retries`: 最大重试次数（默认 3）
- 定期刷新间隔：300 秒（5 分钟）
- 失败后重试间隔：30 秒

## 注意事项

1. **认证状态是异步的**：登录请求发送后，需要等待服务器响应才能确认成功
2. **重订阅可能有延迟**：重新订阅所有频道需要一些时间，期间可能丢失部分消息
3. **网络问题**：如果网络不稳定，可能需要多次重试才能成功
4. **并发安全**：使用锁机制确保认证操作的线程安全

## 未来改进方向

1. **健康检查**：定期发送测试请求验证认证是否有效
2. **消息队列**：认证失效期间缓存消息，认证恢复后处理
3. **指标监控**：记录认证失败次数、重试次数等指标
4. **配置化**：将重试次数、间隔等参数配置化
