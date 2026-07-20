## Context

P0 `run_agent`（`packages/agent_core/loop.py`）用 `for _ in range(max_turns)`，默认 `max_turns=6`，耗尽后写入并返回「处理超时，请简化问题后重试。」。该文案误导（并非网络超时），且与参考实现不符。

对照：

| 项目 | 上限策略 |
|------|----------|
| OpenCode V2 | 可选 `agent.steps`；最后一步注入 `MAX_STEPS_PROMPT`，`tools=[]`，`toolChoice: "none"`，再开一轮要文本总结；若仍发 tool-call 则标记失败 |
| Claude Code | 可选 `maxTurns`（交互 REPL 常不设）；触达后发 `max_turns_reached` attachment → SDK `error_max_turns`，不伪造 assistant 超时句 |
| fengou P0 | 硬切 + 假超时文案 |

主路径仍保持：Store 跨请求 + 内存 messages 本轮 + Loop（每轮 resolve → Turn → 有 tool 则 execute 回灌）。意图仍只靠 FC，无预路由。方案 A（话术等固定流水线）与权限/SSE 不在本 change。

参考代码：

- OpenCode：`packages/core/src/session/runner/llm.ts`（`isLastStep`）、`max-steps.ts`（`MAX_STEPS_PROMPT`）
- Claude：`src/query.ts`（`maxTurns` / `max_turns_reached`）— 作对照，本 change **主跟 OpenCode 软收口**

## Goals / Non-Goals

**Goals:**

1. 废除假超时兜底；触达步数上限时走「最后一步禁工具 + 总结指令」
2. `AgentDef.max_steps` / 调用方 `max_turns` 语义清晰：可选；配置了才软收口
3. 更新 `agent-runtime` 规格与 `05a` 骨架描述，避免文档继续教错误写法
4. 单测覆盖最后一步行为

**Non-Goals:**

- 改话术挂载（已由 `p1-talk-assistant` 完成）；纪要 / PPT 真挂载另开
- 流式 / SSE / 权限 ask（`p1-streaming-permission`）
- 跑中插话、doom-loop、预算、interrupt 等 → 见 [`documents/fengou-ai后期能力展望.md`](../../../documents/fengou-ai后期能力展望.md)；上下文压缩见 `p3-context-compaction`
- 把 Loop 重写成 async generator / Effect 运行时

## Decisions

### D1 · 主跟 OpenCode 软收口，不跟 Claude 纯错误面

| 选项 | 结论 |
|------|------|
| A. Claude：控制面 `error_max_turns`，无模型总结 | 否（HTTP `/chat` 仍要给员工可读 reply） |
| B. OpenCode：最后一步禁工具 + 强制总结 | **是** |
| C. 保留假超时字符串 | 否 |

理由：粉够场景 `/chat` 同步返回 `reply`；软收口能给出「做到哪、还剩什么」，比裸错误或假超时更有用。

### D2 · 步数配置语义

```text
effective_steps =
  若 AgentDef.max_steps 有值：用该值
  否则若 run_agent(max_turns=...) 显式传入：用该值
  否则：None（本请求不启用步数软收口）
```

P0 默认 `max_turns=6` **要改掉**：

- `run_agent` 的 `max_turns` 默认改为 `None`（不启用上限），或改为很大的硬保险（见 D3）
- 前台 Agent `fengou_ai` 的 `max_steps`：P2 可先设一个产品默认（例如 12 或 20），须在 tasks 写死选定值；未设则依赖调用方

与 OpenCode 一致：**未配置 steps 时跟到模型停**（无 tool_calls），而不是默认 6。

### D3 · 硬保险（防进程挂死）

即使产品上「未配置 steps」，仍建议保留一个极高的 `HARD_MAX_TURNS`（例如 64 或 100），防止模型空转打爆账单。行为：

- 触达 `HARD_MAX_TURNS` 时 **同样走软收口**（禁工具 + 总结），不要假超时
- 与可配置 `max_steps` 共用同一套最后一步逻辑；差别只是阈值来源

### D4 · 循环形态（最小改动）

不要大改成 `while True` 状态机；在现有 `_run_locked` 上改：

```text
step = 1
limit = effective_steps or HARD_MAX_TURNS

while step <= limit:
  is_last = (step == limit)
  tools = [] if is_last else tool_registry.resolve(...)
  tool_choice = "none" if is_last else "auto"
  if is_last:
    messages.append(总结指令)  # 见 D5；角色见下

  response = llm.chat(..., tools=tools or None, tool_choice=tool_choice)
  ...
  if not tool_calls:
    落库 assistant，return
  if is_last and tool_calls:
    每个 call 回灌错误结果（不真正 execute），再继续？ 
    → 采用 OpenCode：标记失败并不再 continuation；我们同步 API 下：
       回灌失败串后，若还想要文本，可再强制一轮纯文本；
       P2 最小实现：is_last 时根本不 resolve tools，若模型仍返回 tool_calls，
       则对每个 call 写入 tool role 错误内容，然后 **再发起一轮** tool_choice=none 的纯文本
       （或：直接把错误说明拼进 reply 结束——次优）。
  step += 1
```

**P2 推荐最小实现（与 OpenCode 对齐到可测）：**

1. `is_last` 时：`tools=[]`（或不传）、`tool_choice="none"`，并注入 `MAX_STEPS_PROMPT` 等价中文/英文指令
2. 正常期望：模型返回无 `tool_calls` 的文本 → 落库 return
3. 若仍出现 `tool_calls`：不调用 `execute`；对每个 call 回灌固定错误（如 `Tools are disabled after the maximum agent steps`）；然后 **立即再开一轮** 纯文本 Turn（仍禁工具），取文本结束。若第二轮仍无文本，再用简短系统兜底（说明步数用尽且模型未总结）——**禁止**再用「处理超时」措辞

### D5 · 总结指令文本与注入角色

移植 OpenCode `MAX_STEPS_PROMPT` 语义，常量放在 `packages/agent_core/max_steps.py`。

要点（必须覆盖）：

- 已达最大步数，工具已禁用
- 禁止再发起任何 tool call
- 必须用文本总结：已完成 / 未完成 / 建议下一步

**注入角色（已定 `role=user`）：** 在最后一步（及补救纯文本轮）向内存 messages **追加一条**约束消息，再调 LLM。规格只要求模型能看见该约束，不绑定必须用某一角色。

| 方式 | 说明 | 结论 |
|------|------|------|
| A. `role=assistant` 伪消息 | 贴近 OpenCode；易与下一轮真实 assistant 连成两条 assistant | 否（部分兼容 API 挑剔） |
| B1. `role=user` | 尾部追加一条「本轮收口指令」，改动最小、几乎所有兼容口都认 | **是（采用）** |
| B2. `role=system` | 语义上更像「硬规则」；但常要求 system 仅一条且靠前，尾部再插 system 或改写已有 system 更麻烦 | 否（工程成本高） |

为何选 user 而不选 system：

1. **改动最小**：`messages.append({"role":"user",...})` 即可；不必改 `build_system_prompt`，也不必维护「第二条 system」兼容性。
2. **时序清楚**：约束出现在「马上要总结」之前，跟在近期对话后，像临时加一句收口要求。
3. **兼容优先**：尾部 user 普遍安全；中间/末尾再插 system 时，部分网关会忽略、合并或要求 system 只能在开头。

说明：约束消息只进本轮内存 transcript，**不**作为真实用户话落 PostgreSQL（落库仍只有真正的 user 提问与最终 assistant 总结）。

### D6 · LLMClient 契约

`LLMClient.chat` 必须支持：

- `tools=None` 或 `[]`：请求不带 tools 或空列表（以实现时 provider 兼容为准）
- `tool_choice="none"` | `"auto"`

### D7 · 持久化

- 用户消息、最终 assistant 总结：仍写 PostgreSQL（跨请求）
- 中途 tool_result、最后一步错误回灌：P2 仍可只留内存 messages（与 P0 一致）
- **禁止**把「处理超时…」写入 `agent_messages`

### D8 · 与调用链其它节点的关系

```text
POST /chat → get_or_create_session → run_agent
  →（本 change 只改这里的步数/最后一步）
  → resolve / llm.chat / execute 语义不变（非最后一步）
```

`assemble` / `query` / gateway **不动**。

## 目标 Loop 伪代码

```python
MAX_STEPS_PROMPT = "..."  # 见 D5
HARD_MAX_TURNS = 64

def _run_locked(..., max_turns: int | None, ...):
    agent = agent_registry.get(agent_name)
    limit = agent.max_steps if agent.max_steps is not None else max_turns
    if limit is None:
        limit = HARD_MAX_TURNS
    # ... 拼 messages、append user ...

    step = 1
    while step <= limit:
        is_last = step >= limit
        tools = [] if is_last else tool_registry.resolve(...)
        if is_last:
            messages.append({"role": "user", "content": MAX_STEPS_PROMPT})  # D5-B
        response = llm.chat(
            messages=...,
            tools=tools or None,
            tool_choice="none" if is_last else "auto",
        )
        msg = response.choices[0].message
        messages.append(_assistant_dict(msg))

        if not msg.tool_calls:
            store.append_message(..., role="assistant", content=msg.content or "")
            return RunResult(reply=msg.content or "", ...)

        if is_last:
            for call in msg.tool_calls:
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": "Tools are disabled after the maximum agent steps",
                })
            # 强制再一轮纯文本（仍禁工具）；成功则 return；否则非超时文案兜底
            ...
            return RunResult(...)

        for call in msg.tool_calls:
            # 现有 execute + 回灌
            ...
        step += 1

    # 理论上走不到：while 在 is_last 分支应 return
```

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 部分模型忽略 `tool_choice=none` | 错误回灌 + 强制再一轮纯文本 |
| 去掉默认 6 导致偶发长链费 token | `HARD_MAX_TURNS` + 可为 `fengou_ai` 设 `max_steps` |
| 伪 assistant 注入导致 API 报错 | 已改用 D5-B（user） |
| 文档/测试仍断言「处理超时」 | tasks 含全文检索替换 |

## Migration Plan

1. 改 `loop.py` + `LLMClient` +（可选）`max_steps.py`
2. 更新/新增单测
3. 同步 `openspec/specs/agent-runtime`（本 change delta）与 `documents/.../05a`
4. 手工：故意压低 `max_steps=1` 或 `2`，确认回复是总结而非「处理超时」

回滚：恢复 `for` + 假超时（不推荐）；或 feature flag（P2 可不加，保持最小 diff）

## 延后 change

详见 [`documents/fengou-ai后期能力展望.md`](../../../documents/fengou-ai后期能力展望.md)。与本 change 邻近的：

| Change | 内容 |
|--------|------|
| `p1-talk-assistant` | 话术已挂载（本 change 不依赖、不改） |
| `p1-streaming-permission` | 流式 + 权限；便于后续做 interrupt |
| `p3-context-compaction` | 上下文压缩（P3，方案已拟） |
| （未排期） | 跑中插话、doom-loop、预算（展望 §1） |

## Open Questions

1. `fengou_ai` 产品默认 `max_steps` 取多少？（建议 12 或 20）→ **已定 20**
2. `HARD_MAX_TURNS` 取 64 还是 100？→ **已定 64**
3. `MAX_STEPS_PROMPT` 用中文还是中英双语？（模型为国产时中文更稳）→ **已定中文**
4. 最后一步注入角色最终选 A 还是 B？→ **已定 B（user）**
