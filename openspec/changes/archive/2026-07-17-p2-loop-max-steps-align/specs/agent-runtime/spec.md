## MODIFIED Requirements

### 需求：多轮 function calling 循环

系统必须实现 `run_agent`：拼装 system + 历史 + 用户消息；每一轮先处理工具可见性再以一次 LLM 调用完成 Turn；若有 tool_calls 则执行并把结果追加到**内存** messages 后继续；若无 tool_calls 则将 assistant 文本视为最终回复、写入 Store（PostgreSQL）并结束。不得使用独立意图分类器或正则/embedding 预路由。

步数上限必须按 OpenCode 式软收口：

- 有效上限来自 `AgentDef.max_steps`，否则来自调用方 `max_turns`；二者皆空时使用实现内硬保险上限（不得再用默认 6 + 假超时文案）
- 到达上限的那一轮（最后一步）：必须禁用工具（空 tools + `tool_choice=none`），并向 messages 注入「最大步数已到、禁止再调工具、须文本总结」类约束
- 最后一步的正常结局：模型返回无 tool_calls 的总结文本，写入 Store 并作为 `reply`
- 若最后一步仍返回 tool_calls：不得执行真实工具；须回灌禁用说明；并再开一轮纯文本 Turn 取总结
- 禁止返回或落库「处理超时，请简化问题后重试。」这类假超时文案

#### 场景：先工具再终答
- **当** 用户问题需要业务查询工具
- **则** 循环至少完成一轮工具调用，再给出无 tool_calls 的最终 assistant 文本

#### 场景：最后一步强制文本总结
- **当** 当前步已达有效步数上限
- **则** 本轮不得向模型提供可执行 tools（或 tools 为空且 `tool_choice=none`），且 messages 中须含最大步数约束；最终 `reply` 为模型文本总结（或纯文本补救轮的文本），不得为「处理超时…」固定句

#### 场景：最后一步仍请求工具
- **当** 最后一步模型仍返回 tool_calls
- **则** 系统不得调用 `registry.execute` 跑业务工具；须为每个 call 回灌禁用说明，并继续取得文本终答

#### 场景：未配置步数上限
- **当** Agent 未设 `max_steps` 且调用方未传 `max_turns`
- **则** 循环可持续至模型无 tool_calls 结束，或触达硬保险上限后走同一套软收口（仍禁止假超时文案）
