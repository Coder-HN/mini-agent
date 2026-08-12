# session-store

## Purpose

PostgreSQL 跨请求会话记忆（sessions / messages）；与本轮内存 transcript 分离。

## 需求

### 需求：会话与消息持久化

系统必须把跨请求会话记忆落到 PostgreSQL 普通关系表（P0 不用向量列）：至少 `agent_sessions`（id, agent, created_at）与 `agent_messages`（id, session_id, role, content, tool_call_id, created_at）。连接使用 `POSTGRES_DSN`。这是跨请求续聊的 Store；本轮 FC 使用的内存 messages 见 `agent-runtime` 与 `design.md` §2。

#### 场景：首条消息建会话
- **当** 请求未带可用 `session_id`
- **则** 系统新建 session 行并返回新的 `session_id`

#### 场景：带历史续聊
- **当** 请求带已有 `session_id`
- **则** 循环在调用 LLM 前将该会话历史加载进内存 messages

### 需求：落库粒度（P0）

系统必须在循环开始前（或开始时）写入用户消息，并在循环成功结束时写入最终 assistant 回复。中途 tool_call / tool_result 可以落库，但 P0 至少必须保留 user + 最终 assistant。中途工具结果可以只留在内存 messages（`design.md` §10）。

#### 场景：同 session 多端续聊
- **当** 两个 HTTP 客户端使用同一 `session_id` 发消息
- **则** 双方从共享库看到连续历史（至少含此前的 user 与最终 assistant）

### 需求：会话归属与可见范围

系统必须在 `agent_sessions` 持久化 `owner_user_id`（可空字符串）。新建会话时，若请求 `context.owner_user_id` 非空，MUST 写入该值。`GET /sessions/{session_id}/trail` MUST 接受查询参数 `viewer_user_id` 与 `data_scope`：当 `data_scope` 为 `"1"`（全部）时允许查看任意会话；否则仅当会话 `owner_user_id` 与 `viewer_user_id` 一致时允许，否则 MUST 返回 403（或等价拒绝）。无归属的旧会话仅 `data_scope=1` 可查看。

#### 场景：普通用户不能看他人轨迹
- **当** `data_scope` 非 `"1"` 且 `viewer_user_id` 与会话 owner 不同
- **则** 拒绝返回轨迹事件

#### 场景：全部数据权限可看他人
- **当** `data_scope` 为 `"1"`
- **则** 可返回任意存在会话的轨迹

### 需求：工具轨迹落库

系统必须在每次工具执行后向 PostgreSQL 表 `agent_tool_events` 写入一条记录，至少含：`id`、`session_id`、`tool_call_id`、`tool_name`、`arguments`（JSON 文本）、`result_summary`（可截断）、`permission_denied`（布尔）、`duration_ms`、`prompt_tokens` / `completion_tokens` / `total_tokens`（可空）、`created_at`。连接仍使用 `POSTGRES_DSN`。轨迹表与续聊用的 `agent_messages` 分离；`load_history` MUST NOT 把轨迹行当作 OpenAI messages 加载。

#### 场景：执行 query 后可查到轨迹
- **当** 某次 `/chat` 调用了工具 `query`
- **则** 该 `session_id` 下存在对应 `agent_tool_events` 行，含 tool_name=`query` 与 arguments

#### 场景：权限拒绝标记
- **当** 工具结果 JSON 含 `error` 为 `permission_denied` 或 `missing_token`
- **则** 该事件 `permission_denied` 为 true

### 需求：按 session 查询轨迹

系统必须提供 HTTP `GET /sessions/{session_id}/trail`，按 `created_at`（及稳定次序）返回该会话工具事件列表。会话不存在或尚无事件时返回空列表。

#### 场景：curl 按 session_id 拉取
- **当** 客户端请求 `GET /sessions/{session_id}/trail` 且该会话曾有工具调用
- **则** 响应含工具名、参数、permission_denied、duration_ms 及 token 字段（有则填）
