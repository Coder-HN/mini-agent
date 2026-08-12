## ADDED Requirements

### 需求：会话归属与可见范围

系统必须在 `agent_sessions` 持久化 `owner_user_id`（可空字符串）。新建会话时，若请求 `context.owner_user_id` 非空，MUST 写入该值。`GET /sessions/{session_id}/trail` MUST 接受查询参数 `viewer_user_id` 与 `data_scope`：当 `data_scope` 为 `"1"`（全部）时允许查看任意会话；否则仅当会话 `owner_user_id` 与 `viewer_user_id` 一致时允许，否则 MUST 返回 403（或等价拒绝）。无归属的旧会话仅 `data_scope=1` 可查看。

#### 场景：普通用户不能看他人轨迹
- **当** `data_scope` 非 `"1"` 且 `viewer_user_id` 与会话 owner 不同
- **则** 拒绝返回轨迹事件

#### 场景：全部数据权限可看他人
- **当** `data_scope` 为 `"1"`
- **则** 可返回任意存在会话的轨迹
