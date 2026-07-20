# context-compaction

## Purpose

按「模型窗口 − reserved」触发的上下文压缩：prune 旧 tool 正文 → summarize 旧前缀 → 硬截断。只压本轮内存 messages，不改写 PostgreSQL 权威历史。

## 需求

### 需求：上下文压缩挂在 Loop

系统必须在 `run_agent` 每一轮业务 Turn 之前检查内存 messages 用量。自动压缩开启且已配置有效模型上下文上限时，若估算 token ≥ `MODEL_CONTEXT_TOKENS - CONTEXT_RESERVED_TOKENS`，必须先压缩（必要时硬截断），再 `registry.resolve` 和调模型。压缩不能改「意图 = tool_calls」，不能加预路由。P3 首版只改本轮内存 messages，不能删改已落库的 `agent_messages`。

#### 场景：按窗口与 reserved 触发
- **当** `CONTEXT_COMPACT_ENABLED` 为真，且 `MODEL_CONTEXT_TOKENS > CONTEXT_RESERVED_TOKENS`，且估算用量 ≥ `MODEL_CONTEXT_TOKENS - CONTEXT_RESERVED_TOKENS`
- **则** 本轮业务 Turn 前先 prune，仍超则 summarize，仍超则硬截断，直到用量低于可用水位或只剩 system + 近端

#### 场景：未超水位
- **当** 估算用量低于可用水位（窗口 − reserved）
- **则** 不调摘要模型，直接 resolve → Turn

#### 场景：未配置模型窗口
- **当** 未配置 `MODEL_CONTEXT_TOKENS`，或上限不大于 reserved
- **则** 不按错误阈值盲目压缩；跳过自动压缩（可记配置问题日志）

#### 场景：不改 Store 权威历史
- **当** 本轮做了内存侧压缩
- **则** PostgreSQL 里已有的 user / assistant 行保持不变（首版）

### 需求：prune 与 summarize 两级策略

系统按两级策略压缩（函数名可不同）：

1. **prune**：缩短或占位替换较旧的 `tool` 正文，保留 `tool_call_id` 可配对
2. **summarize**：prune 后仍超可用水位时，留 system 与近端若干条，把更早前缀总结成一条摘要写进内存 messages，再拼近端

摘要专用调用不暴露业务 tools（`tool_choice=none` 或空 tools）。摘要输出不能直接当对用户的最终 `reply`。summarize 后仍超水位就硬截断（保 system + 近端），同一轮不能无限重复摘要。

`context.image_ref` 和 data-URL 图片载荷不计入文本用量估算（首版）。

#### 场景：prune 裁旧 tool_result
- **当** 存在超长旧 `tool` 正文且总用量触发压缩
- **则** 先 prune 较旧 tool 正文，后续 messages 仍带原 `tool_call_id`

#### 场景：摘要后继续业务 Turn
- **当** summarize 成功
- **则** 必须把摘要纳入内存 messages 后继续业务 resolve → Turn，不得把摘要当作 `POST /chat` 的最终 `reply`

#### 场景：摘要失败或仍超水位
- **当** 摘要失败或之后仍超可用水位
- **则** 必须硬截断（保留 system 与近端），不得崩溃或无限循环

### 需求：与步数上限正交

摘要专用 Turn 不得计入业务 `max_steps`（或单独限制且上限为一次）。最后一步禁工具总结时，仍允许 prune 与硬截断。

#### 场景：压缩不耗尽业务步数
- **当** 配置了较小的 `max_steps` 且本轮触发了 summarize
- **则** 业务工具可调用次数不得仅因一次摘要而减少一次有效业务步

### 需求：压缩相关配置

系统必须支持以下配置（名称可有别名，语义必须具备）：

- 模型上下文上限（token）
- reserved（token，默认 10000）
- 近端保留消息条数
- 自动压缩总开关

不得再要求用户分别配置「固定字符预算」「单独的 micro 开关」「单独的摘要开关」作为首版必选项。

#### 场景：reserved 可调整
- **当** 运维修改 reserved（例如仍为 10000 或改为其它正整数）并重启服务
- **则** 触发水位必须按新的「窗口 − reserved」计算
