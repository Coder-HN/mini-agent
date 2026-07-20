## Context

fengou-ai：Store（PostgreSQL）+ 内存 messages + Loop + Turn。意图只靠 FC；话术走方案 A（tool HTTP）。

现状：没有上下文压缩。`05` / `05a` 把 compaction 放在 P3；触发逻辑参照 OpenCode（窗口 − reserved），prune / 摘要分层参照 Claude。

主路径不变。只压更早前缀，近端原样留；`image_ref` 不进 messages 估算。

## Goals / Non-Goals

Goals:

1. 触发：用量 ≥ 模型窗口 − reserved（同 OpenCode）
2. prune → summarize → 硬截断；挂在 Turn 之前
3. 配置项少；reserved 默认 10000 token，可改
4. 纯函数可单测，Loop 只调一处；同步 `05` / `05a` / `06`

Non-Goals:

- 长期记忆、跑中插话、doom-loop、interrupt
- 改写 PG 权威历史
- 精确 tokenizer / 视觉 token 账单
- 照搬 QueryEngine

## Decisions

### D1 · 压内存视图，不改 PG（首版）

只压缩本轮喂模型的 `messages`；跨请求仍从 PG 加载后再压。

### D2 · 触发：窗口 − reserved（参照 OpenCode）

```text
usable = MODEL_CONTEXT_TOKENS - CONTEXT_RESERVED_TOKENS
trigger when estimate_tokens(messages) >= usable
```

| 项 | 结论 |
|----|------|
| 固定 `CONTEXT_BUDGET_CHARS=80000` 当主阈值 | 否 |
| 读模型上下文上限 + reserved | 是 |
| `CONTEXT_RESERVED_TOKENS` 默认 | 10000（粉够回复约 1000 字 + 摘要余量；可配置） |

`MODEL_CONTEXT_TOKENS` 首版走 Settings / `.env`（还没有 provider 目录自动读 limit）。未配置或 ≤ reserved 时不自动 compact，打日志跳过，避免误触发。

估算（首版）：对 messages JSON / 文本做字符启发式（如 `chars/4` 近似 token）；跳过 `data:image` 和超长 base64；不把 `context.image_ref` 拼进估算。

### D3 · 两步压缩：prune + summarize

参照 OpenCode / Claude：

1. **prune（micro）**：把较旧的 `role=tool` 正文换成短占位，保留 `tool_call_id`
2. **summarize**：仍超 `usable` 时，留 system + 近端 K 条；更早前缀做一次摘要 Turn（`tool_choice=none`），写回一条合成说明后再拼近端

仍超就硬截断（保 system + 近端），同一轮摘要最多一次。

`CONTEXT_COMPACT_ENABLED=true` 时 prune 和 summarize 默认都做，不再各开一个布尔。

### D4 · 压缩后继续业务 Turn

摘要不当 `reply`；compact 后继续 resolve → 业务 Turn。摘要 Turn 不计入业务 `max_steps`（或单独上限 1）。

### D5 · 模块落点

`packages/agent_core/compaction.py` + Loop 调用；复用 `LLMClient`。

### D6 · 配置（精简）

| 配置 | 含义 | 默认 |
|------|------|------|
| `MODEL_CONTEXT_TOKENS` | 当前模型上下文上限（token） | 必配才启用自动压缩；示例按所用模型填（如 128000） |
| `CONTEXT_RESERVED_TOKENS` | 预留给回复 + 压缩本身 | 10000 |
| `CONTEXT_KEEP_RECENT_MESSAGES` | 近端原样保留条数 | 12 |
| `CONTEXT_COMPACT_ENABLED` | 总开关 | true |

不再暴露：`CONTEXT_BUDGET_CHARS`、`CONTEXT_MICRO_COMPACT`、`CONTEXT_SUMMARY_COMPACT`。

### D7 · 意图与方案 A

不改变 FC；大 `talk_assistant` tool_result 靠 prune。图不进 Loop 文本预算。

## 伪代码

```python
usable = settings.model_context_tokens - settings.context_reserved_tokens
for step in loop:
    if settings.context_compact_enabled and usable > 0:
        messages = maybe_compact(messages, usable=usable, keep_recent=..., llm=llm)
    tools = registry.resolve(...)
    response = llm.chat(...)
```

`maybe_compact`：若 `estimate < usable` 则原样返回；否则 prune → 仍超则 summarize → 仍超则 truncate。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| `MODEL_CONTEXT_TOKENS` 填错 | `.env.example` 注明按模型文档填；未配则不 compact |
| 字符/4 估算偏差 | reserved=10000 留余量；联调可调 reserved |
| 摘要丢事实 | 近端 K 条 + 摘要 prompt 要求保留实体 |
| tool 配对坏掉 | prune 只改 content |

## Migration Plan

1. Settings + `compaction.py` + Loop
2. 单测：触发阈值、prune、摘要、硬截断、短对话回归
3. 归档时合并 specs；改 `05` / `05a` / `06`
4. 回滚：`CONTEXT_COMPACT_ENABLED=false`

## 延后

| Change | 内容 |
|--------|------|
| `p2-loop-max-steps-align` | 已归档 |
| provider 模型目录自动读 `limit.context` | 可替代手写 `MODEL_CONTEXT_TOKENS` |
| `p2-long-term-memory` / 流式 / interrupt | 另开 |

## Open Questions

1. `MODEL_CONTEXT_TOKENS` 示例默认填多少（随 `OPENAI_MODEL_NAME` 文档）？
2. 估算用 `chars/4` 还是 `chars/2`（中文偏多时）？
3. `RunResult.compacted` 要不要暴露给联调？
