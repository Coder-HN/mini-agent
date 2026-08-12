## Why

总体规划 M2 要求可演示写路径（创建用户 / 停用用户）且必须二次确认。M1 只有只读 `query`，无法兑现「给张三开账号 → 确认后执行」。

## What Changes

- 新增写工具 `write`：支持 `create_user`、`disable_user`，经 gateway 调 go-admin REST 并透传 JWT
- 二次确认：默认 `confirmed=false` 只返回将影响对象清单，不发写请求；用户确认后 `confirmed=true` 才执行
- 更新 `min_agent` prompt / 工具白名单：写操作须先预览再确认；查数仍走 `query`
- 单测覆盖：无 token、未确认不写、确认后 POST/PUT、401/403 可读错误
- **Non-goals**：改 go-admin API/Casbin、React/Electron UI、审计轨迹（M3）、流式/权限两道门完整 P1、真挂载 navigate/ppt

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `min-agent-app`：从「只读」扩展为含写工具 + 二次确认；装配与验收句对齐 M2
- `tools-registry`：若需固化「写工具失败隔离 / 未确认不得副作用」约定则增量修改（否则仅改 `min-agent-app`）

## Impact

- 代码：`apps/min_agent/gateway.py`、`tools/write.py`（新建）、`agent.py`、相关测试
- 规格：`openspec/specs/min-agent-app`；`openspec/config.yaml` 推进到 M2
- 联调：go-admin `:8000` + mini-agent `:8001`；经 `/api/v1/agent/chat`；演示「开账号」需具备创建用户权限的 JWT（如 `admin`）
