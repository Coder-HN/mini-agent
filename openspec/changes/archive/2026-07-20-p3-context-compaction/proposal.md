## 为什么做

`run_agent` 每轮把 PostgreSQL 历史加上本轮内存 messages（含 tool_result）整段喂给模型，不按窗口压。多轮续聊加大块 tool JSON 后，容易顶满上下文或费用失控。`05` / `05a` 已在 Loop 顶部预留 compaction；本 change 为 **P3**，触发条件参照 OpenCode：`估算 token ≥ 窗口 − reserved`，先 prune 再 summarize。

## 改什么

- 触发：`估算 token ≥ MODEL_CONTEXT_TOKENS − CONTEXT_RESERVED_TOKENS`（不用固定 8 万字符当主阈值）
- 压缩分两步：prune 裁旧 tool 正文 → 仍超则 summarize（摘要换掉旧前缀，保留 system + 近端）
- 配置只留模型窗口、reserved（默认 10000 token）、近端保留条数；prune / 摘要随自动压缩默认开启
- `context.image_ref`、data-URL 不计入估算（图走 ai_crew，不进 Loop 文本预算）
- 更新 `agent-runtime` 与 `05` / `05a` / `06`

本 change 不做（Non-goals）：

- 长期记忆检索（`p2-long-term-memory` / 展望）
- 跑中插话、doom-loop、USD 预算掐停
- 照搬 QueryEngine / Session Drain；不做独立压缩 HTTP API
- 精确 tokenizer / 厂商视觉 token 账单对齐（首版启发式即可）
- interrupt / AbortController

## 能力

### 新增能力

- `context-compaction`：按模型窗口与 reserved 触发的 prune + summarize

### 修改能力

- `agent-runtime`：每轮 Turn 前可 compact；与步数软收口互不替代

## 影响

- 代码：`packages/agent_core/compaction.py` + `loop.py`；`Settings` / `.env.example` 增加少量项
- API：`POST /chat` 字段可不变
- Store：首版只压本轮内存 messages，不改写 PostgreSQL
- 参考：OpenCode `compaction.reserved` / prune+summarize；Claude micro/autoCompact
