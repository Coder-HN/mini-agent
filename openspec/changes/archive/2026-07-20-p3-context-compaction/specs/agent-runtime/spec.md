## MODIFIED Requirements

### 需求：多轮 function calling 循环

系统必须实现 `run_agent`：拼装 system + 历史 + 用户消息；每一轮在调 LLM 前可按 `context-compaction` 规格检查用量并压缩；然后处理工具可见性，用一次 LLM 调用完成业务 Turn；有 tool_calls 就执行并回灌内存 messages；没有 tool_calls 就把 assistant 文本写入 Store 并结束。不用独立意图分类器或预路由。

步数软收口若已实现则保持；压缩与软收口可同时生效，互不替代。

#### 场景：先工具再终答
- **当** 用户问题需要业务查询工具
- **则** 循环至少完成一轮工具调用，再给出无 tool_calls 的最终 assistant 文本

#### 场景：每轮 Turn 前可压缩
- **当** 自动压缩启用且估算用量达到「模型窗口 − reserved」
- **则** 业务 Turn 使用的 messages 必须是压缩或截断之后的视图

#### 场景：工具结果在下一轮可见
- **当** 第 N 轮完成一次工具调用
- **则** 结果写入内存 messages，并在第 N+1 轮带着该历史（经可能的压缩后）再次调用模型
