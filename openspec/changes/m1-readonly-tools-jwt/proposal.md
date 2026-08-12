## Why

总体规划 M1 要求只读工具调 go-admin REST，并透传调用方 JWT，使 `admin` / `deptmgr` 同问「本部门有哪些人」答案不同。当前仍是本地演示桩，无法兑现验收。

## What Changes

- `query` 门面改为调用 go-admin：`users`（`GET /api/v1/sys-user`）、`login_logs`（`GET /api/v1/sys-login-log`）
- 工具执行携带 `context.access_token`（由控制面代理注入）作为 `Authorization: Bearer`
- 401/403 返回结构化可读错误（不得绕过 Casbin）
- 移除本地审批演示桩作为主路径；`GO_GATEWAY_URL` 默认指向 go-admin `:8000`
- 更新 prompt / README / `min-agent-app` 规格与验收句
- **Non-goals**：写工具与二次确认（M2）、审计轨迹落库（M3）、React/Electron UI、改 go-admin-master 代码

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `min-agent-app`：query / gateway 改为 go-admin 只读 REST + JWT 透传；验收改为部门用户查询场景

## Impact

- `apps/min_agent/gateway.py`、`tools/query.py`、`agent.py`、`config.py`、`.env.example`、`README.md`
- `openspec/config.yaml`、`openspec/specs/min-agent-app`
- 联调依赖：go-admin `:8000` + 有效 JWT（经 `/api/v1/agent/chat` 或直连 `/chat` 带 context）
