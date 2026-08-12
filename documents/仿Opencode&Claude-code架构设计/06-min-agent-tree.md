# min-agent 目录树

> 上篇：[05-min-agent-architecture.md](./05-min-agent-architecture.md)
> 仓库：本仓 `mini-agent`
> 实现规格：本仓库 `openspec/`（冲突以 openspec 为准）
> 产品真源：`documents/系统总体规划.md`
> 目录写法对照：[02](./02-opencode-tree.md) · [04](./04-claude-code-tree.md)

---

## 1. 优先级

| 阶段 | 目标 |
|------|------|
| **P0** | 一条对话跑通：FC → query → go-admin / 落库 |
| **P1** | 边做边提示（tool_start/end、text_delta → SSE）、流式 Turn、权限两道门、历史截断 |
| **P2** | 写工具 + 二次确认（总体规划 M2）、`task` / 长期记忆等 |
| **P3** | 上下文压缩增强、审计轨迹可视化（总体规划 M3） |

---

## 2. 目录结构（含阶段）

```text
min-agent/
├── pyproject.toml
├── .env.example                 # OPENAI_* · GO_GATEWAY_URL · POSTGRES_DSN
├── README.md
├── openspec/                    # OpenSpec 规格
├── packages/
│   ├── agent_core/
│   │   ├── loop.py              P0
│   │   ├── message.py           P0
│   │   ├── context.py           P0
│   │   ├── store.py             P0   PostgreSQL sessions/messages
│   │   ├── agents.py            P0
│   │   ├── tools/base.py        P0
│   │   ├── tools/registry.py    P0
│   │   ├── tools/builtin.py     P1 question · P2 task
│   │   ├── permission.py        P1
│   │   ├── history.py           P1
│   │   ├── processor.py / bus   P1 流式 + 边做边提示事件
│   │   ├── compaction.py        P3（窗口 − reserved → prune + summarize）
│   │   └── memory.py            P2
│   ├── agent_llm/client.py      P0
│   └── agent_server/
│       ├── app.py / routes.py   P0  POST /chat · P1 SSE 进度事件
│       └── middleware.py        P1
└── apps/
    └── min_agent/                 # ChatOps 前台 FC Agent（默认）
        ├── agent.py · config.py · main.py · cli.py   P0
        ├── gateway.py                               P0 go-admin REST（JWT）
        ├── context.py
        └── tools/
            ├── query.py                             P0
            ├── navigate.py                          P0/P1 占位
            └── ppt_generate.py                      P0/P2 占位
```

共享进 `packages/`；前台装配进 `apps/min_agent`。纪要/PPT 等固定流水线若需要再各自成 app，经 tool 挂到前台。`task` 属平台能力，放 `agent_core`。已下线的招商话术 / ai_crew 不再进本仓。

---

## 3. P0 验收

样例：`本部门有哪些人？`

```text
用户 → POST /chat 或 CLI
  → Loop 第1轮：query(users, ...)
  → gateway → go-admin REST（带 JWT）
  → Loop 第2轮：人话总结
  → PostgreSQL 有 user/assistant（及 session）
```

不做：流式、边做边提示、ask 权限、compaction、task、写操作。

P0 任务清单（已归档）：`openspec/changes/archive/2026-07-15-p0-chat-fc-loop/tasks.md`。

---

## 4. OpenSpec 后续 change（建议名）

| Change | 阶段 |
|--------|------|
| `p0-chat-fc-loop` | P0（已归档） |
| `m0-clean-internship-copy` / `m1-readonly-tools-jwt` | 对齐总体规划 M0/M1 |
| `p1-streaming-permission` | P1：边做边提示 + 流式 + 权限 |
| `p2-task-subagent` | P2：task + 可选纪要/PPT 挂载 |
| `p2-long-term-memory` | P2 长期记忆（与压缩分模块） |
| `p3-context-compaction` | P3 上下文压缩 |
| `migrate-session-to-go` | 会话权威迁 Go |

OpenSpec 命令：`/opsx:propose` → `/opsx:apply` → `/opsx:archive`。

---

## 5. 系统边界（摘自落地 ADR）

- Python 不做 L0 业务编排（鉴权落库调谁归 Go）
- 工具取数只经 Go API；过渡桩可本地
- 运行时无状态：续接靠 Store / 入参历史，不靠进程内隐式会话
