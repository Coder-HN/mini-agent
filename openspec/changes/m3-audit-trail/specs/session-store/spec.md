## ADDED Requirements

### 需求：工具轨迹落库

系统必须在每次工具执行后向 PostgreSQL 表 `agent_tool_events` 写入一条记录，至少含：`id`、`session_id`、`tool_call_id`、`tool_name`、`arguments`（JSON 文本）、`result_summary`（可截断）、`permission_denied`（布尔）、`duration_ms`、`prompt_tokens` / `completion_tokens` / `total_tokens`（可空）、`created_at`。连接仍使用 `POSTGRES_DSN`。轨迹表与续聊用的 `agent_messages` 分离；`load_history` MUST NOT 把轨迹行当作 OpenAI messages 加载。

#### 场景：执行 query 后可查到轨迹
- **当** 某次 `/chat` 调用了工具 `query`
- **则** 该 `session_id` 下存在对应 `agent_tool_events` 行，含 tool_name=`query` 与 arguments

#### 场景：权限拒绝标记
- **当** 工具结果 JSON 含 `error` 为 `permission_denied` 或 `missing_token`
- **则** 该事件 `permission_denied` 为 true

### 需求：按 session 查询轨迹

系统必须提供 HTTP `GET /sessions/{session_id}/trail`，按 `created_at`（及稳定次序）返回该会话工具事件列表。会话不存在时返回空列表或 404（实现选定一种并保持稳定）。

#### 场景：curl 按 session_id 拉取
- **当** 客户端请求 `GET /sessions/{session_id}/trail` 且该会话曾有工具调用
- **则** 响应含工具名、参数、permission_denied、duration_ms 及 token 字段（有则填）
