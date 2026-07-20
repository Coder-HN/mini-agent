## 为什么做

P0 的 `run_agent` 在 `max_turns` 耗尽后直接返回「处理超时，请简化问题后重试。」并落库。这既不像超时，也不对齐 OpenCode / Claude Code：成熟项目要么在最后一步禁工具并要求模型总结（OpenCode `MAX_STEPS_PROMPT` + `toolChoice: none`），要么以控制面错误结束（Claude `max_turns_reached` / `error_max_turns`），而不是伪造一条超时文案。

话术已由 `p1-talk-assistant` 经 HTTP 挂为 `talk_assistant` tool；本 change 只对齐 Loop 步数上限策略，避免后续长工具链踩坑。

## 改什么

- **BREAKING（行为）**：废除「假超时」兜底文案；触达步数上限时改为 OpenCode 式软收口（最后一轮禁工具 + 注入总结指令 + 取模型文本为 reply）
- `max_turns` / `AgentDef.max_steps` 语义对齐：可选配置；未配置时默认不硬掐（另可保留极高硬保险，须在 design 写明）
- 更新 `agent-runtime` 规格：删除「处理超时…」场景，改为「最后一步强制文本总结」
- 同步架构笔记 `05a` 中 P0 骨架的兜底段

**本 change 不做（Non-goals）：**

- 改话术 / 纪要 / PPT 挂载（话术已挂好；纪要、PPT 仍占位，另开 change）
- 流式 Turn、边做边提示 SSE、权限 ask（`p1-streaming-permission`）
- 跑中插话、doom-loop、预算、interrupt 等 → 见 [`documents/fengou-ai后期能力展望.md`](../../../documents/fengou-ai后期能力展望.md)；上下文压缩见 [`p3-context-compaction`](../p3-context-compaction/)

## 能力

### 新增能力

（无）

### 修改能力

- `agent-runtime`：步数上限从硬切假超时 → OpenCode 式最后一步软收口；可选 `steps`/`max_steps` 语义

## 影响

- 代码：主要 `packages/agent_core/loop.py`；可能小改 `LLMClient.chat`（支持 `tool_choice="none"` / 空 tools）、`AgentDef.max_steps`
- API：`POST /chat` 契约不变，但触达上限时 `reply` 变为模型总结而非固定中文超时句
- 测试：需覆盖「最后一步 tools 为空 / tool_choice=none」「仍发 tool_calls 时失败回灌」
- 对照：OpenCode `packages/core/src/session/runner/llm.ts` + `max-steps.ts`；Claude `src/query.ts` maxTurns（对照用，本 change 主跟 OpenCode）
