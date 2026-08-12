## Why

总体规划 R4 要求管理员可查看他人会话、普通用户仅本人。当前 `agent_sessions` 无归属字段，trail 按 id 即可读，无法兑现数据权限。

## What Changes

- `agent_sessions` 增加 `owner_user_id`；建会话时从 `context.owner_user_id` 写入
- `GET /sessions/{id}/trail` 按 `viewer_user_id` + `data_scope` 鉴权：`data_scope=1` 可看全部，否则仅本人
- 续聊他人会话时拒绝（非全部范围）
- **Non-goals**：部门级会话范围、改 Casbin 策略表、React 会话列表大改

## Capabilities

### Modified Capabilities

- `session-store`：归属与可见范围

## Impact

- `store.py`、`agent_server/app.py`、单测；依赖控制面注入 context / trail 查询参数
