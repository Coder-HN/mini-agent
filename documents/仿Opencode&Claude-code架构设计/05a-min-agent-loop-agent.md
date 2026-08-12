# min-agent · Loop / Agent / 工具

> 父文档：[05-min-agent-architecture.md](./05-min-agent-architecture.md)
> 状态与数据流：[05b-min-agent-state-dataflow.md](./05b-min-agent-state-dataflow.md)
> 对照：OpenCode `SessionPrompt` + `SessionProcessor` + tools；Claude `queryLoop` + ToolExecutor
> 实现规格：本仓库 `openspec/specs/agent-runtime` · `openspec/specs/tools-registry`

---

## 1. 谁干什么

| 模块 | 职责 |
|------|------|
| **Agent** | 配置：name、system prompt、tool 名单、权限、max_steps；不是循环本身 |
| **Loop** (`run_agent`) | `while` / `for`：resolve → Turn → 有 tool_calls 则回灌再开一轮；否则收尾 |
| **Turn** | 一次 LLM 调用（P0 同步 create；P1 改为 stream） |
| **Registry** | 每轮现算 schema；execute 校验参数并跑工具 |

```text
Loop
  └─ 每轮：compact? → A.resolve(tools) → B.Turn(LLM)
       ├─ C. 无 tool_calls → 存 assistant → return
       └─ D. 有 tool_calls → execute → 写回 messages → 下一轮
```

一轮 = 一次 provider turn。模型看不到工具返回值，必须写回历史再调。

---

## 2. 主循环骨架（含 P2 步数软收口）

同步版骨架。上线时把 `create` 换成流式；压缩 / 权限 / 子 Agent / 长期记忆按注释挂阶段能力。

有效步数：`AgentDef.max_steps` → 调用方 `max_turns` → `HARD_MAX_TURNS`（64）。  
**主跟 OpenCode**：最后一步 `tools=[]` + `tool_choice=none` + 注入总结约束（`MAX_STEPS_PROMPT`），取模型文本为 `reply`。  
**不跟 Claude**：触达后抛 `error_max_turns` / 控制面错误（我们 `/chat` 需要可读 reply）。  
禁止「处理超时，请简化问题后重试。」假超时文案。

```python
def run_agent(session, user_input, agent_name, user_permissions=None, max_turns=None):
    limit = agent.max_steps if agent.max_steps is not None else max_turns
    if limit is None:
        limit = HARD_MAX_TURNS  # 64
    messages = [
        {"role": "system", "content": build_system_prompt(agent_name)},
        *load_history(session.id),
        {"role": "user", "content": user_input},
    ]
    store.append_message(session.id, role="user", content=user_input)
    # P2：可在此处把 retrieve_long_term(...) 拼进 system 或 user 前缀

    step = 1
    while step <= limit:
        is_last = step >= limit
        # P3：用量 ≥ 窗口 − reserved 时 maybe_compact（prune → summarize → 硬截断）
        if estimate_tokens(messages) >= (context_tokens - reserved):
            messages = maybe_compact(messages, usable=context_tokens - reserved, ...)

        if is_last:
            tools = []
            tool_choice = "none"
            messages.append({"role": "user", "content": MAX_STEPS_PROMPT})  # D5-B：避免连续 assistant
        else:
            tools = registry.resolve(agent=agent_name, permissions=user_permissions)
            tool_choice = "auto"

        response = client.chat.completions.create(
            model=session.model,
            messages=messages,
            tools=tools or None,
            tool_choice=tool_choice,
        )
        msg = response.choices[0].message
        messages.append(msg.model_dump())

        if not msg.tool_calls:
            store.append_message(session.id, role="assistant", content=msg.content or "")
            return msg.content

        if is_last:
            # 不 execute；回灌禁用说明；再开一轮纯文本（仍禁工具）
            ...
            return summary_or_fallback  # 非「处理超时」

        for call in msg.tool_calls:
            result = registry.execute(name, args, permissions=user_permissions)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": ...})
            # P2：task 工具内部再调一遍 run_agent（子 Session）

        step += 1
```

完整步骤：

```text
每轮开始
  → （可选）compact
  → A. registry.resolve() 或最后一步空 tools
  → B. create(..., tool_choice=auto|none)
  → C. 无 tool_calls → 落库结束
  → D. 有 tool_calls → 非最后一步则 execute 回灌；最后一步则禁用回灌 + 纯文本收口
```

约束：

- 一轮 = 一次 provider turn；工具结果必须回灌后才能被模型看见
- 中断时给未完成 tool 补 error/interrupted result，否则下一轮协议会坏
- 步数软收口（OpenCode `isLastStep`）；不要只信 `finish_reason`；不要假超时文案
- 对照：OpenCode `llm.ts` `isLastStep` + `max-steps.ts`；Claude `max_turns_reached`（我们不采用错误面）

---

## 3. Agent 定义

```python
@dataclass
class AgentDef:
    name: str
    system_prompt: str
    tool_names: list[str]
    permission: list[Rule] | None = None   # P1
    max_steps: int | None = None
    mode: str = "primary"                 # primary | subagent
    can_spawn_task: bool = False          # 子 Agent 默认 False
```

首个前台 Agent：`min_agent`。ChatOps 查询只读说明，不自动改写权限数据（见总体规划与 `min-agent-app` 规格）。

---

## 4. 工具与权限

### 4.1 接口

- `name` / `description` / `args_schema`（Pydantic）
- `execute(args, ctx) -> ToolResult`（至少 `content` 字符串给模型）

### 4.2 每轮 resolve（对应骨架 A）

1. 取 Agent 工具集（+ 日后 MCP）
2. 去掉硬 deny（P1）
3. 转成 provider tool schema
4. `task` 的 description 动态附上可调 subagent 列表（P2）

### 4.3 两道门（P1）

| 阶段 | 行为 |
|------|------|
| schema | deny 的工具模型看不见 |
| 执行 | allow / deny / ask |

P0：只有 Agent 白名单。数据范围不在 Python 发明第二套 ACL。

### 4.4 业务门面（ChatOps 查询）

单一 `query(data_type, filters)`，gateway 内按 `data_type` 路由。现行：`users` / `login_logs` → go-admin REST（JWT）；`commission` 已下线。

---

## 5. Turn、流式与边做边提示（P1）

P0：`chat.completions.create` 同步；整次 `run_agent` 结束再返回最终人话，没有实时进度。

P1 起两条通道并行（不能只靠 `messages` list 刷 UI）：

| 通道 | 给谁 | 内容 |
|------|------|------|
| Transcript（内存 `messages` → 可选落库） | 模型 | user / assistant / tool，决定下一轮 FC |
| 进度事件（bus → SSE / WebSocket） | 用户 | 正在做什么 |

Loop 内在关键节点 `emit`（名称可微调，语义固定）：

```text
tool 执行前     →  tool_start { name, args_summary }
tool 执行后     →  tool_end   { name, ok | error }
LLM 流式出字    →  text_delta { text }
整次结束        →  done       { reply }
可选            →  status     { phase: thinking | calling_tools | … }
```

对照 OpenCode：`ToolPart` 的 `pending` / `running` / `completed` + 事件推 TUI。  
实现：`processor` / `bus` + `GET/SSE`（或 WebSocket）。Loop 仍只负责「要不要再来一轮」。

---

## 6. 压缩与记忆（挂在 Loop 上）

- 压缩（P3）：触发为用量 ≥ 模型窗口 − reserved（默认 reserved=10000）；prune 旧 tool 正文 → summarize 旧前缀 → 硬截断；只压内存、不改 PG；见 `openspec/changes/p3-context-compaction`。
- 短记忆：Store 会话历史（见 [05b](./05b-min-agent-state-dataflow.md)）。
- 长期记忆（P2）：检索结果注入 prompt 前缀；与压缩分开。
