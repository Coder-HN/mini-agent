## 新增需求

### 需求：多轮 function calling 循环

系统必须按 `design.md` §6 实现 `run_agent`：拼装 system + 历史 + 用户消息；每一轮先 `registry.resolve` 再以 `tool_choice=auto` 调用 LLM；若有 tool_calls 则执行并把结果追加到**内存** messages 后继续；若无 tool_calls 则将 assistant 文本视为最终回复、写入 Store 并结束。不得使用独立意图分类器或正则/embedding 预路由（见 `design.md` §5）。

#### 场景：先工具再终答
- **当** 用户问题需要业务查询工具
- **则** 循环至少完成一轮工具调用，再给出无 tool_calls 的最终 assistant 文本

#### 场景：max_turns 兜底
- **当** 模型持续请求工具超过配置的 `max_turns`（默认 6）
- **则** 循环停止，返回可控兜底文案（如「处理超时…」），不得无限挂起

### 需求：每轮仅一次 provider 调用

系统每一轮循环必须只发起一次 LLM chat completion。工具结果只能通过下一轮的消息历史被模型看见，不得把供应商内部隐藏 tool loop 当作唯一编排。

#### 场景：工具结果在下一轮可见
- **当** 第 N 轮完成一次工具调用
- **则** 结果写入内存 messages，并在第 N+1 轮带着该历史再次调用模型

### 需求：中途状态放在内存 transcript

本轮 tool_call / tool_result 必须进入内存 messages 供后续 Turn 使用。P0 不要求把中途 tool 结果写入 PostgreSQL（见 `design.md` §2、§10）。

#### 场景：同一次请求内多轮工具
- **当** 同一 `run_agent` 内连续两次 tool_calls
- **则** 第二次 LLM 调用的 messages 中已包含第一次的 tool 结果
