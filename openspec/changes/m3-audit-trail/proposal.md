## Why

总体规划 M3/R4 要求每轮工具调用可审计（工具名、参数、权限拒绝、耗时、token），并按 `session_id` 查询。当前 Store 只落 user/最终 assistant，工具轨迹仅在内存与 `/chat` 瞬时字段，无法回放。

## What Changes

- 新增表 `agent_tool_events`，在 Loop 执行工具时写入结构化轨迹
- 记录：工具名、参数、结果摘要、是否权限拒绝、耗时 ms、本轮 LLM usage（若有）
- 提供按 `session_id` 查询契约：`GET /sessions/{session_id}/trail`
- 更新 `session-store` / 必要时 `agent-runtime` 规格；续聊历史仍只加载 user/assistant
- **Non-goals**：React 会话详情页（下一切片）、管理员跨用户会话权限（建议项）、改 go-admin、SSE/流式

## Capabilities

### New Capabilities

（无独立新能力名；挂在既有 session-store）

### Modified Capabilities

- `session-store`：增加工具轨迹落库与按 session 查询
- `agent-runtime`：明确执行工具时须写入轨迹（不改 FC 主结构）

## Impact

- `packages/agent_core/store.py`、`loop.py`
- `packages/agent_server/app.py`（trail 路由）
- 单测；`openspec/config.yaml`、总体规划 R4 前两项
- Web 回放依赖本 API，本 change 不改 React
