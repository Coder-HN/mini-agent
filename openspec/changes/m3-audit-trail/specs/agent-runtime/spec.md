## ADDED Requirements

### 需求：工具执行写入审计轨迹

系统在 Loop 内执行工具（`_execute_tools` 或等价路径）时，MUST 测量单次执行耗时，并将工具名、参数、结果摘要、权限拒绝标记与可选的本轮 LLM token usage 交给 Store 持久化。MUST NOT 因轨迹写入失败而让整次聊天崩溃：写入失败应记录后继续编排（或等价降级），仍须回灌 tool_result。

#### 场景：工具执行伴随落库调用
- **当** 模型产出 tool_calls 且 Loop 执行某一工具
- **则** 在返回 tool 角色消息的同时，尝试写入一条会话轨迹事件
