## 背景

架构笔记在本仓库 `documents/仿Opencode&Claude-code架构设计/`（`05` / `05a` / `05b` / `06`）。**本文是实现与 AI coding 的事实来源**；与笔记冲突时以本文 + `openspec/specs/` 为准。

对齐 OpenCode V1（SessionPrompt + SessionProcessor）与 Claude Code（queryLoop）的 Store / Loop / Turn。主对话不做 BPM Workflow，也不用 CrewAI Flow 当聊天编排器。

系统目标态：Client → Go → Python；业务数据归 Go；会话权威目标在 Go Chat。过渡态允许 Client 直打 Python，跨请求短记忆落本仓 PostgreSQL。

---

## 目标 / 非目标

目标：

- 跑通一条对话：自然语言 → 多工具 schema 下 FC 选 `query`（非占位）→ gateway 桩 → 中文总结 → 落库
- 建立可复用 `agent_core` + 首个 `apps/fengou_ai`
- 验收句：`睿德志行佣金审核通过了吗？`

非目标（本 change 不实现；设计约定写在后文，留给后续 change）：

- 流式 SSE、边做边提示、权限 ask、历史截断、compaction、skill、task/固定流水线挂载、长期记忆
- 真实 commission Go 接口（仅预留路径注释）
- 编码工具、斜杠命令、ToolSearch、ML 权限、swarm
- OpenCode V2 inbox / steer / queue（P0 用户消息直接进历史）

---

## 1. 系统分层

两圈：

| 圈 | 内容 |
|----|------|
| 系统圈（目标态） | Client → Go 网关 / 编排 / Chat → Python；业务数据 API 归 Go |
| Python 运行时圈 | HTTP/SSE → Agent Runtime（FC）→ Tool/权限 → LLM；工具取数走 Go |

```text
Client → Go(网关/编排/Chat) → Python(fengou-ai)
                              ├─ Loop / Turn / Registry
                              ├─ 内存 messages（本轮）
                              └─ PostgreSQL（跨请求）
                    工具 ──→ Go 业务 API（P0 佣金可用本地桩）
```

要点：

- 目标态：Client 不直连 Python；Go 唯一对外入口
- 业务数据归 Go；Python 不直连业务 MySQL
- 过渡态：可直打 Python；短记忆暂落 Python 侧 PostgreSQL，再迁 Go Chat

「Python 不做业务编排」指 **L0**（鉴权、取会话、调谁、业务落库归 Go），不是说没有 L1/L2 对话编排。Agent 平台不做 BPM/DAG Workflow 引擎。

编排分层：

| 层 | 谁 | 干什么 |
|----|-----|--------|
| L0 | Go / 业务系统 | 鉴权 → 取会话 → 调 Python → 落库 → 回传；审批流、页面流 |
| L1 | Python Loop | FC while：输入进历史、同会话串行、Turn 续跑 |
| L2 | task / 固定流水线 tool（P2+） | 子 Session 或独立 Workflow；窄通道回传 |

---

## 2. Store / Loop / Turn + 两层状态

| 角色 | 职责 | 对标 |
|------|------|------|
| Store | PostgreSQL：`agent_sessions` / `agent_messages`（跨请求会话记忆） | OpenCode SQLite messages |
| 内存 messages | 本轮 transcript（含中途 tool_result）；主要喂模型 | 进程内消息列表 |
| Loop | `run_agent`：resolve → LLM → 有 tool 则回灌再开一轮 | SessionPrompt / queryLoop |
| Turn | 单次 LLM 调用（P0 同步 create；P1 改为 stream） | SessionProcessor「一轮」 |
| Registry | 每轮现算 schema；execute 校验并跑工具 | ToolRegistry |
| Agent | name / system prompt / tool 名单 / 权限 / max_steps；不是循环本体 | Agent 定义 |

不要做成「一个 Processor 包办状态与编排」。

状态两层：

| 层 | 存什么 | 生命周期 |
|----|--------|----------|
| PostgreSQL | session 元数据 + user / 最终 assistant（P0） | 跨请求续聊 |
| 内存 `messages` | system + 历史 + 本轮 user + 本轮 assistant/tool | 单次 `run_agent` |

权威会话状态是消息历史，不是 `SalesScriptState` 那种业务字段袋。

---

## 3. 一次请求路径（过渡态 · P0）

```text
用户 → POST /chat 或 CLI
  → DB 载历史
  → 内存拼 [system, *history, user]
  → DB 存 user
  → run_agent:
       每轮: resolve tools → LLM
         有 tool_calls → execute → 内存 append tool → 继续
         无 tool_calls → DB 存 assistant → return reply
```

同 `session_id` 同一时间只跑一个 drain（实现可用锁/队列）。P0 不做 inbox/steer/queue。

---

## 4. 仓库目录

与架构笔记 `06` 一致。P0 只实现标了 P0 的路径；P1/P2 可先不建文件。

```text
fengou-ai/
├── pyproject.toml
├── .env.example                 # OPENAI_* · GO_GATEWAY_URL · POSTGRES_DSN
├── README.md
├── openspec/
├── packages/
│   ├── agent_core/
│   │   ├── loop.py              P0
│   │   ├── message.py           P0
│   │   ├── context.py           P0
│   │   ├── store.py             P0
│   │   ├── agents.py            P0
│   │   ├── tools/base.py        P0
│   │   ├── tools/registry.py    P0
│   │   ├── tools/builtin.py     P1 question · P2 task
│   │   ├── permission.py        P1
│   │   ├── history.py           P1
│   │   ├── processor.py / bus   P1 流式 + 边做边提示
│   │   ├── compaction.py        P2
│   │   └── memory.py            P2
│   ├── agent_llm/client.py      P0
│   └── agent_server/
│       ├── app.py / routes.py   P0  POST /chat · P1 SSE
│       └── middleware.py        P1
└── apps/
    ├── fengou_ai/               # 前台 FC Agent（P0）
    │   ├── agent.py · config.py · main.py · cli.py
    │   ├── gateway.py           # 佣金桩 + Go 预留
    │   └── tools/query.py       # P0 实装
    │       navigate.py          # P0 占位 schema；真跳转 P1+
    │       talk_assistant.py    # P0 占位；真流水线 P2
    │       ppt_generate.py      # P0 占位；真流水线 P2
    │       meeting_minutes.py   # P2+
    ├── talk_assistant/          # 后续固定流水线 app
    ├── meeting_minutes/
    └── ppt/
```

共享进 `packages/`；业务装配进 `apps/fengou_ai`。P0 注册话术/PPT/`navigate` 占位（§7.4）；真 Workflow app 与挂载仍属 P2（§8）。`task` 放 `agent_core`（P2）。

---

## 5. 意图识别：FC，无预路由

不做：独立意图分类器、正则/embedding 预路由、固定「先分类再调用」两阶段管道。

做：

| 方式 | 含义 |
|------|------|
| 显式边界 | 当前 Agent 的 tool 名单 + system prompt +（P1）权限规则 |
| 隐式选择 | 模型在 schema 约束下产出 `tool_calls`（`tool_choice=auto`） |

用户意图 = 这组 `tool_calls`。业务 Agent 与编码 Agent 的差异只在工具语义（query/navigate vs read/edit），不在「另写一套路由引擎」。

实现约束：

- 每轮调用 LLM 前必须 `registry.resolve(...)`，把当前可见 tools 传给模型
- 禁止写死 `tools = [...]` 在循环外且从不按 Agent 过滤
- 禁止用 finish_reason 单独决定是否结束；以「有无 tool_calls」+ `max_turns` 为准

---

## 6. 主循环骨架（P0 必实现）

一轮 = 一次 provider turn。模型看不到工具返回值，必须写回内存 messages 再调。

```python
def run_agent(session, user_input, agent_name, user_permissions=None, max_turns=6):
    messages = [
        {"role": "system", "content": build_system_prompt(agent_name)},
        *load_history(session.id),
        {"role": "user", "content": user_input},
    ]
    store.append_message(session.id, role="user", content=user_input)

    for _ in range(max_turns):
        # P1: truncate；P2: compact（本 change 不做）
        tools = registry.resolve(
            agent=agent_name,
            permissions=user_permissions,  # P0 可忽略，仅按 Agent 白名单
        )
        response = client.chat.completions.create(
            model=session.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        messages.append(msg.model_dump())

        if not msg.tool_calls:
            store.append_message(session.id, role="assistant", content=msg.content or "")
            return msg.content

        for call in msg.tool_calls:
            name = call.function.name
            args = json.loads(call.function.arguments)
            result = registry.execute(name, args, permissions=user_permissions)
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result, ensure_ascii=False),
            })

    fallback = "处理超时，请简化问题后重试。"
    store.append_message(session.id, role="assistant", content=fallback)
    return fallback
```

每轮步骤：

```text
A. registry.resolve()     → 工具 schema 从哪来
B. create(..., tools=)    → FC 决策
C. 无 tool_calls          → 落库 assistant，结束
D. 有 tool_calls          → execute，append tool，回到 A
```

约束：

- 每轮恰好一次 LLM chat completion
- 中断时给未完成 tool 补 error/interrupted result（P0 至少不要留下悬挂 tool_call）
- `max_turns` 默认 6，禁止空转

对应规格：`specs/agent-runtime`。

---

## 7. Agent 与工具

### 7.1 AgentDef（`agents.py`）

```python
@dataclass
class AgentDef:
    name: str
    system_prompt: str
    tool_names: list[str]
    permission: list | None = None   # P1
    max_steps: int | None = None
    mode: str = "primary"            # primary | subagent（P2）
    can_spawn_task: bool = False     # 子 Agent 默认 False（P2）
```

P0 默认 Agent：`fengou_ai`。system prompt：电商/销售 CRM 助手；对审批只读（可解释、可查询，不自动审批）。工具：`query`（实装）+ 三个占位（见 §7.4）。

### 7.2 Tool 接口与 Registry（`tools/`）

- `name` / `description` / `args_schema`（Pydantic）
- `execute(args, ctx) ->` 至少能变成给模型的字符串（JSON 亦可）
- `resolve(agent)`：取 Agent 工具集 →（P1 去掉 deny）→ 转 OpenAI tools schema
- `execute(name, args, ctx)`：校验参数后执行

P0 权限：仅 Agent 声明工具白名单。不做 schema deny / 执行 ask。数据范围不在 Python 另造 ACL（真实 API 时由 Go 裁；身份经 `ctx` 透传）。

### 7.3 门面 `query` + gateway（`apps/fengou_ai`）

单一工具 `query(data_type, filters)`：

- `data_type`：至少 `commission`；可预留 `shop` / `baokuan` / `dataoke`
- `filters`：如 `store_name` / `keyword` / `status`
- gateway 内按 `data_type` 确定性路由；禁止为每个后端接口各发明一个 tool
- P0：`commission` → 本地桩（至少 2 条已驳回记录，含渠道/方案/状态/原因）；桩路径不发 HTTP
- Go 路径注释预留：`/v1/fengou-ai/commission/search/agent`；身份头（如 `X-CRM-*`）等真接 Go 再补

### 7.4 P0 占位工具（只注册 schema，不实装能力）

验收句只有 `query` 时，模型没有「错选」空间，FC 选工具测不准。P0 额外注册三个占位，**写清 description / 参数，execute 固定返回「尚未实现」类短文**，不调外部服务、不跑流水线：

| name | 用途（给模型看的语义） | 参数（示意） | execute |
|------|------------------------|--------------|---------|
| `navigate` | 按意图跳到 CRM/业务网页路由 | `target` 或 `path` / `hint` | 占位回复 |
| `talk_assistant` | 分析微信聊天图片，给对商家的推荐回复 | `image_ref` 或 `note`；可空 | 占位回复 |
| `ppt_generate` | 按主题撰写/生成 PPT | `topic` / `outline?` | 占位回复 |

约束：

- 四个工具都进 `fengou_ai` 白名单与每轮 `resolve` schema
- description 必须让模型能区分：查 CRM 数据 → `query`；跳页 → `navigate`；话术图 → `talk_assistant`；做 PPT → `ppt_generate`
- 佣金验收句**不得**调用三个占位；若误调，属失败（或至少不得以占位文案冒充佣金结论）

真能力：`navigate` 跳转与事件在 P1+；话术/PPT 挂真实 Workflow 在 P2（§8）。

对应规格：`tools-registry` · `fengou-ai-app`。

---

## 8. 固定流水线挂载（方案 A · 设计锁定，P2+ 实现）

`fengou_ai` 是 FC 前台。话术、会议纪要、PPT 等步骤固定的能力不塞进 Loop，做成独立 Workflow，再挂到前台：

```text
用户 ↔ fengou_ai（FC + transcript）
         ├─ query（P0 实装）
         ├─ navigate / talk_assistant / ppt_generate（P0 占位 → 后续换真实现）
         ├─ meeting_minutes(...)      → 会议纪要 Workflow（P2+）
         └─ 或 task(subagent=…)
```

| 约定 | 说明 |
|------|------|
| 边界 | tool 入参 = 任务说明 + 材料；出参 = 摘要 + 产物链接/ID |
| 内部 | CrewAI 或自研状态机均可；不要嵌进 `agent_core` |
| 进度 | 经 P1 事件转 UI，或异步完成后通知 |
| 隔离 | 父 Session 默认看不到子流程完整中间态 |

与话术 Flow 的分工：固定链路用 Workflow（字段袋 + 状态机）；开放问答用 FC Loop（transcript）。本 change：`query` 实装 + 三占位；真流水线仍属 P2。

---

## 9. 权限两道门（P1 · 设计锁定）

| 阶段 | 行为 |
|------|------|
| schema | deny 的工具不进本轮 schema，模型看不见 |
| 执行 | allow / deny / ask |

P0：只有 Agent 白名单。`question` 工具、HTTP 中间件同属 P1 change `p1-streaming-permission`。

---

## 10. 持久化（P0）

表（普通关系表，非 vector）：

- `agent_sessions`：id, agent, created_at, …
- `agent_messages`：id, session_id, role, content, tool_call_id, created_at, …

读写：

- 无可用 `session_id` → 新建 session 并返回
- 有 `session_id` → load 历史进内存再跑 Loop
- user：入循环前存一次
- 最终 assistant：循环成功结束时存一次
- 中途 tool_result：P0 可只留内存；P1+ 可落全量 parts

连接：`POSTGRES_DSN`。对应规格：`session-store`。

---

## 11. 边做边提示与流式（P1 · 设计锁定）

P0：同步 `create`；整次结束后再返回最终人话。

P1：两条通道分开（不能只靠 `messages` 刷 UI）：

| 通道 | 给谁 | 内容 |
|------|------|------|
| Transcript（内存 messages → 可选落库） | 模型 | user / assistant / tool |
| 进度事件（bus → SSE） | 用户 | 正在做什么 |

关键节点 emit：

```text
tool_start { name, args_summary }
tool_end   { name, ok | error }
text_delta { text }
done       { reply }
status     { phase }   # 可选
```

对照 OpenCode ToolPart：`pending` / `running` / `completed`。实现落在 `processor` / `bus` + SSE；Loop 仍只负责「要不要再来一轮」。

---

## 12. L2 多 Agent 通道（P2 · 设计锁定）

```text
主 Loop → task(subagent, prompt)
  → 派生子权限（继承 deny，默认禁再 task）
  → 子 Session 独立 transcript → 同一套 Loop
  → 同步：tool_result 摘要回父
  → 异步（P3）：通知进父队列，下一回合才看见
```

合法通道：Spawn / Sync result / Async notify / Continue。  
禁止：共享可变内存、默认同读父 messages、全局黑板。

---

## 13. 阶段能力总表

| 能力 | 阶段 | 本 change |
|------|------|-----------|
| FC Loop + query 桩 + 三占位 tool + PG user/assistant | P0 | 做 |
| 流式 + 边做边提示 SSE | P1 | 不做 |
| 历史截断 | P1 | 不做 |
| 权限两道门 / question；navigate 真跳转 | P1 | 不做 |
| task / 话术·纪要·PPT 真挂载 | P2 | 不做 |
| compaction / 长期记忆 / skill | P2 | 不做 |
| MCP / 后台 / 联网 | P3 | 不做 |

不搬：read/edit/bash/lsp/git/worktree、斜杠命令、ML 权限、swarm、fork cache。

后续 change 名：

| Change | 内容 |
|--------|------|
| `p1-streaming-permission` | 流式 Turn、边做边提示、权限 ask |
| `p2-task-subagent` | task + 固定流水线挂载（方案 A） |
| `p2-compaction` / `p2-long-term-memory` | 压缩 / 长期记忆 |
| `migrate-session-to-go` | 会话权威迁 Go |

---

## 14. HTTP / CLI（P0）

- `POST /chat`：`{session_id?, message, context?}` → `{session_id, reply}`
- CLI：单次用户消息，打印 reply
- 验收：`睿德志行佣金审核通过了吗？` → schema 含 query+三占位 → 至少一轮 **仅** `query`（不点占位）→ 中文总结驳回桩数据；PG 有 session + user + assistant

---

## 风险

- 过渡态 Session 在 Python PG，目标迁 Go：字段契约尽早稳定
- 验收依赖佣金桩：后端就绪只改 gateway
- P0 无流式 / 无 ask：体验与安全在 P1 补

## 迁移步骤

1. 按 `tasks.md` 实现并通过 CLI + `POST /chat` 验收  
2. `/opsx:archive` → specs 进入 `openspec/specs/`  
3. 架构笔记交叉引用保持指向本仓库 `documents/仿Opencode&Claude-code架构设计/` 与本归档目录  
4. 开 P1 change  

## 已确认（原未决）

- P0 注册 `navigate` / `talk_assistant` / `ppt_generate` 为占位（§7.4），不实装能力；佣金验收句必须选 `query`、不得点占位
- P0 佣金走本地桩，不发 Go HTTP；Gateway 身份头（如 `X-CRM-*`）延后到真接 Go
