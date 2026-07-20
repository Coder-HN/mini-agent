# P3 上下文压缩 — 任务

## 1. 配置与模块骨架

- [x] 1.1 Settings / `.env.example` 增加 `MODEL_CONTEXT_TOKENS`、`CONTEXT_RESERVED_TOKENS`（默认 10000）、`CONTEXT_KEEP_RECENT_MESSAGES`（默认 12）、`CONTEXT_COMPACT_ENABLED`（默认 true）；注释写清触发公式和 reserved 用途
- [x] 1.2 新增 `packages/agent_core/compaction.py`：`estimate_tokens`（跳过 data-URL）、`prune_tool_results`、`summarize_prefix`、`hard_truncate`、`maybe_compact(usable, ...)`
- [x] 1.3 摘要 prompt 用中文：保留实体名、结论、未决问题；不要写成对用户的最终答复

## 2. 接入 Loop

- [x] 2.1 `_run_locked` 每轮业务 `llm.chat` 前：若启用且 `MODEL_CONTEXT_TOKENS > reserved`，则 `usable = context - reserved`，调用 `maybe_compact`
- [x] 2.2 摘要调用：空 tools + `tool_choice=none`；不计入业务 `max_steps`（或独立上限 1）
- [x] 2.3 摘要失败或仍超 usable → `hard_truncate`；禁止摘要死循环
- [x] 2.4 不写回/删除 PostgreSQL `agent_messages`；估算不计 `image_ref` / data-URL

## 3. 测试

- [x] 3.1 单测：旧超长 tool_result → prune 后变短且 `tool_call_id` 仍在
- [x] 3.2 单测：用量 ≥ usable 时走 summarize，近端消息保留
- [x] 3.3 单测：未配置 `MODEL_CONTEXT_TOKENS` → 不 compact；摘要失败 → 硬截断不抛崩
- [x] 3.4 回归：短对话佣金桩路径不变

## 4. 规格与笔记

- [x] 4.1 实现与本 change specs 一致
- [x] 4.2 同步 `05`/`05a`/`06`：compaction 为 P3，触发写明「窗口 − reserved」
- [x] 4.3 核对展望文档与 `openspec/README.md`

## 5. 验收

- [x] 5.1 构造超长假历史，`MODEL_CONTEXT_TOKENS`/`reserved` 可复现触发 compact，请求成功
- [x] 5.2 PostgreSQL 历史不被压缩逻辑改写
- [x] 5.3 `CONTEXT_COMPACT_ENABLED=false` 时不压缩
