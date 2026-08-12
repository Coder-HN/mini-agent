# agent-runtime

## Purpose

多轮 function calling 循环（Store / Loop / Turn）：每轮可 compact → resolve tools → LLM → 有 tool 则回灌内存 messages。

## 需求

### 需求：多轮 function calling 循环

系统必须实现 `run_agent`：拼装 system + 历史 + 用户消息；每一轮在调 LLM 前可按 `context-compaction` 规格检查用量并压缩；然后处理工具可见性，用一次 LLM 调用完成业务 Turn；有 tool_calls 就执行并回灌内存 messages；没有 tool_calls 就把 assistant 文本写入 Store 并结束。不用独立意图分类器或预路由。

步数上限必须按 OpenCode 式软收口：

- 有效上限来自 `AgentDef.max_steps`，否则来自调用方 `max_turns`；二者皆空时使用实现内硬保险上限（不得再用默认 6 + 假超时文案）
- 到达上限的那一轮（最后一步）：必须禁用工具（空 tools + `tool_choice=none`），并向 messages 注入「最大步数已到、禁止再调工具、须文本总结」类约束
- 最后一步的正常结局：模型返回无 tool_calls 的总结文本，写入 Store 并作为 `reply`
- 若最后一步仍返回 tool_calls：不得执行真实工具；须回灌禁用说明；并再开一轮纯文本 Turn 取总结
- 禁止返回或落库「处理超时，请简化问题后重试。」这类假超时文案

压缩与软收口可同时生效，互不替代。

#### 场景：先工具再终答
- **当** 用户问题需要业务查询工具
- **则** 循环至少完成一轮工具调用，再给出无 tool_calls 的最终 assistant 文本

#### 场景：每轮 Turn 前可压缩
- **当** 自动压缩启用且估算用量达到「模型窗口 − reserved」
- **则** 业务 Turn 使用的 messages 必须是压缩或截断之后的视图

#### 场景：最后一步强制文本总结
- **当** 当前步已达有效步数上限
- **则** 本轮不得向模型提供可执行 tools（或 tools 为空且 `tool_choice=none`），且 messages 中须含最大步数约束；最终 `reply` 为模型文本总结（或纯文本补救轮的文本），不得为「处理超时…」固定句

#### 场景：最后一步仍请求工具
- **当** 最后一步模型仍返回 tool_calls
- **则** 系统不得调用 `registry.execute` 跑业务工具；须为每个 call 回灌禁用说明，并继续取得文本终答

#### 场景：未配置步数上限
- **当** Agent 未设 `max_steps` 且调用方未传 `max_turns`
- **则** 循环可持续至模型无 tool_calls 结束，或触达硬保险上限后走同一套软收口（仍禁止假超时文案）

### 需求：每轮仅一次 provider 调用

系统每一轮循环必须只发起一次业务 LLM chat completion（摘要专用调用除外，见 `context-compaction`）。工具结果只能通过下一轮的消息历史被模型看见，不得把供应商内部隐藏 tool loop 当作唯一编排。

#### 场景：工具结果在下一轮可见
- **当** 第 N 轮完成一次工具调用
- **则** 结果写入内存 messages，并在第 N+1 轮带着该历史（经可能的压缩后）再次调用模型

### 需求：中途状态放在内存 transcript

本轮 tool_call / tool_result 必须进入内存 messages 供后续 Turn 使用。续聊用的 PostgreSQL `agent_messages` 仍可不存中途 tool 行；审计轨迹写入独立表 `agent_tool_events`（见 `session-store`），不得替代本需求的内存回灌。

#### 场景：同一次请求内多轮工具
- **当** 同一 `run_agent` 内连续两次 tool_calls
- **则** 第二次 LLM 调用的 messages 中已包含第一次的 tool 结果

### 需求：工具执行写入审计轨迹

系统在 Loop 内执行工具时，MUST 测量单次执行耗时，并将工具名、参数、结果摘要、权限拒绝标记与可选的本轮 LLM token usage 交给 Store 持久化。MUST NOT 因轨迹写入失败而让整次聊天崩溃：写入失败应吞掉或记录后继续编排，仍须回灌 tool_result。

#### 场景：工具执行伴随落库调用
- **当** 模型产出 tool_calls 且 Loop 执行某一工具
- **则** 在返回 tool 角色消息的同时，尝试写入一条会话轨迹事件
