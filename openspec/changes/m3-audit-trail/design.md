## Context

M2 写工具已落地。Store 仅持久化续聊用的 user/最终 assistant；`_execute_tools` 已具备 name/args/result/session_id，是挂审计的最小切入点。LLM 响可能含 `usage`，当前未读。

## Goals / Non-Goals

**Goals**

- 每次工具执行落一条 `agent_tool_events`
- 字段覆盖：tool_name、arguments、permission_denied、duration_ms、token（来自触发该批 tool_calls 的 LLM usage，可缺省）
- `GET /sessions/{id}/trail` 按时间序返回
- 不影响续聊：`load_history` 仍只取 user/assistant

**Non-Goals**

- React 回放页（`m3-web-trail-replay`）
- 跨用户会话 ACL
- 把中途 tool 行塞进 `agent_messages` 喂模型

## Decisions

1. **独立表 `agent_tool_events`**，不复用 `agent_messages`（避免污染 OpenAI 历史）。
2. **挂点 `_execute_tools`**：`time.perf_counter` 包一层 execute；解析结果 JSON 的 `error in (permission_denied, missing_token)` → `permission_denied=true`。
3. **token**：在 `_run_locked` 于 `llm.chat` 后读取 `response.usage`，传入本批 `_execute_tools`；同批多工具可写相同 token（按工具行可查即可）。
4. **结果摘要**：存 JSON/字符串，超长截断（如 8KiB），避免大 tool_result 撑爆库。
5. **查询 API**：mini-agent `GET /sessions/{session_id}/trail`；curl 验收。Go 代理转发留给 React 切片。

## Risks / Trade-offs

- [usage 字段因厂商 SDK 差异缺失] → 允许 null，不阻塞落库  
- [模型跳过预览直接写] → 与本 change 无关  
- [结果截断丢失细节] → 审计以参数+拒绝+耗时为主；全文可后续再加

## Migration Plan

- `_ensure_schema` 幂等 `CREATE TABLE IF NOT EXISTS`
- 回滚：停写 + 忽略 trail 路由即可

## 延后 change

- `m3-web-trail-replay`：go-admin-react 会话详情回放
- 可选：go-admin 代理 `GET .../agent/sessions/{id}/trail`
