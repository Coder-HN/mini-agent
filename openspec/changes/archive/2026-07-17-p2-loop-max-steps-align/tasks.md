# P2 Loop 步数软收口 — 任务

## 1. 契约与常量

- [x] 1.1 在 `packages/agent_core` 增加 `MAX_STEPS_PROMPT`（或等价中文约束文案）；语义对齐 OpenCode `max-steps.ts`（禁工具、须总结已完成/未完成/下一步）
- [x] 1.2 确定并写入常量：`HARD_MAX_TURNS`（建议 64）；`fengou_ai` 是否设置产品默认 `max_steps`（建议 12 或 20，写入 `apps/fengou_ai/agent.py`）
- [x] 1.3 扩展 `LLMClient.chat`：支持 `tool_choice="none"`，以及 `tools=None`/`[]` 时不向 provider 暴露可执行工具

## 2. Loop 改造

- [x] 2.1 将 `_run_locked` 的 `for _ in range(max_turns)` 改为带 `step` / `is_last` 的循环（见 `design.md` 伪代码）
- [x] 2.2 `max_turns` 默认改为 `None`；有效上限 = `agent.max_steps` ?? `max_turns` ?? `HARD_MAX_TURNS`
- [x] 2.3 `is_last`：注入步数约束、`tools` 为空、`tool_choice="none"`
- [x] 2.4 `is_last` 且仍有 `tool_calls`：不 `execute`；回灌禁用说明；再开一轮纯文本；仍无文本则用非「处理超时」的简短兜底
- [x] 2.5 删除「处理超时，请简化问题后重试。」分支；全库检索确认无残留断言/文案依赖
- [x] 2.6 非最后一步行为保持不变：`resolve` → `chat` → execute 回灌

## 3. 测试

- [x] 3.1 单测：`max_steps=1`（或 mock LLM 第一轮就 tool_calls）→ 最后一轮请求带 `tool_choice=none` / 无 tools，且 messages 含步数约束
- [x] 3.2 单测：最后一步模型仍返回 tool_calls → 未调用真实 execute，仍得到文本 `reply`
- [x] 3.3 单测：未配置上限时可用到硬保险；`reply` 不含「处理超时」
- [x] 3.4 回归：正常「query → 终答」路径仍通过（佣金桩场景）

## 4. 规格与笔记

- [x] 4.1 确认本 change delta `specs/agent-runtime` 与实现一致
- [x] 4.2 同步 `documents/仿Opencode&Claude-code架构设计/05a-fengou-ai-loop-agent.md`：删掉假超时骨架，改成软收口描述
- [x] 4.3 （可选）在 `05a` 注明对照 OpenCode `llm.ts` `isLastStep` / Claude `max_turns_reached` 差异（我们主跟 OpenCode）

## 5. 验收

- [x] 5.1 手工：将 `fengou_ai.max_steps` 临时设为 2，构造需多轮工具的请求，确认最终回复为总结口吻而非超时句
- [x] 5.2 `POST /chat` 响应字段不变（`session_id` / `reply` / `tool_names_called`）；触达上限时 `reply` 非空且非假超时
- [x] 5.3 PostgreSQL 最终 assistant 行不是「处理超时…」
