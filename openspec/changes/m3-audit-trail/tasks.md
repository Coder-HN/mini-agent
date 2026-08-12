## 1. 规格

- [x] 1.1 合并 delta 到 `openspec/specs/session-store` 与 `agent-runtime`
- [x] 1.2 更新 `openspec/config.yaml`：M3 轨迹落库；Web 回放延后

## 2. Store 与 Loop

- [x] 2.1 `store.py`：建表 `agent_tool_events`；`append_tool_event` / `list_tool_events`
- [x] 2.2 `loop.py`：`_execute_tools` 计时落库；读取 `response.usage` 传入本批

## 3. API 与验证

- [x] 3.1 `GET /sessions/{session_id}/trail` 返回事件列表
- [x] 3.2 单测：落库字段与权限拒绝标记；trail 查询
- [x] 3.3 勾选 tasks；同步总体规划 R4 前两项（Web 回放仍 `[ ]`）
