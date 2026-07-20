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
