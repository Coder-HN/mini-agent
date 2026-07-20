# min-agent · 状态与编排数据流

> 父文档：[05-min-agent-architecture.md](./05-min-agent-architecture.md)
> Loop / 工具：[05a-min-agent-loop-agent.md](./05a-min-agent-loop-agent.md)
> 对照：OpenCode Session/SQLite + task 子 Session；Claude messages/sidechain + 通知队列
> 实现规格：本仓库 `openspec/specs/session-store`；多 Agent 见后续 change `p2-task-subagent`

---

## 1. 全局状态：Session transcript（会话聊天记录）

一个用户会话的权威状态是消息历史，不是业务流水线大对象（对比话术 `SalesScriptState`）。

| 存储 | 表/形态 | 阶段 |
|------|---------|------|
| PostgreSQL | `agent_sessions` / `agent_messages` | P0 过渡 |
| Go Chat | 目标会话权威 | 迁移动作另开 change |

字段要点：session（id, agent, created_at）；message（role, content, tool_call_id, …）。

读写：

- Loop 开始：按 `session_id` 从 PostgreSQL 加载历史到内存 messages  
- 用户话：先落库再进循环  
- 中途 tool_result：进内存 messages；P0 可不落库  
- 最终 assistant：落库后返回  

同 `session_id` 多端续聊读同一库。与 openspec `session-store` / `agent-runtime` 一致。

---

## 2. 编排分三层（别混）

```text
L0  业务编排（Go）     鉴权 → 取会话 → 调 Python → 落库 → 回传
L1  Session 编排       FC while：输入进历史、同会话串行、Turn 续跑
L2  多 Agent           task 开子 Session；窄通道回传
```

- 业务 Workflow（审批流、页面）→ L0 / 业务系统  
- 对话编排 → L1  
- CRM 调话术专家 → L2  

「Python 不做业务编排」指 L0，不是说没有 L1/L2。  
Agent 平台不做 BPM/DAG Workflow 引擎。

---

## 3. L1：单 Session 数据流

```text
user message → Store
  → Loop 读 transcript（聊天记录）
  → Turn：LLM →（可选）tools → tool_result 写入 transcript
  → 继续 Turn 或结束
```

跨轮唯一主通道：历史里的 tool_result（下一轮再读出）。  
P0 不做 inbox/steer/queue；需要「跑中插话」时再对齐 OpenCode V2。

同 Session 同一时间一个 drain（实现上可用锁/队列）。

P1 边做边提示：进度事件走 bus/SSE，不是改 transcript 的替代品；见 [05a §5](./05a-min-agent-loop-agent.md)。

---

## 4. L2：多 Agent（P2）

### 4.1 调用

```text
主 Loop → 模型产出 task(subagent, prompt)
  → 派生子权限（继承 deny，默认禁再 task）
  → 子 Session 独立 transcript（聊天记录）→ 再跑同一套 Loop
  → 同步：tool_result 摘要回父
  → 异步（P3）：通知/合成消息进父队列，下一回合才看见
```

子 Agent 默认看不到父完整闲聊；只收 spawn 时的 prompt（及显式附件）。

### 4.2 四条合法通道

| # | 通道 | 传什么 |
|---|------|--------|
| 1 | Spawn | 任务说明 + 必要业务字段 |
| 2 | Sync result | 结论摘要 + child_session_id |
| 3 | Async notify | status + 摘要（全文可落文件/DB） |
| 4 | Continue | 追加指令 / task_id 续跑 |

禁止：共享可变内存、默认同读父 `messages`、全局黑板广播。

### 4.3 管控

工具可见性、执行权限、结果长度、嵌套深度、租户身份透传、父子 session 审计。

---

## 5. 和话术 Flow 的区别（避免混用）

| | 话术 `SalesScriptFlow` | min_agent 前台 FC |
|--|------------------------|-------------|
| 下一步谁定 | `_STATE_TRANSITIONS` / 固定步骤 | 模型 `tool_calls` |
| 状态 | 业务字段袋（ocr/structured/…） | transcript（聊天记录） |
| 编排 | 自研状态机（可不用 CrewAI 图） | FC Loop |

话术 / 纪要 / PPT 等固定链路仍用 Workflow；开放问答用本文这套。这些 Workflow 经 tool 挂到前台（[05 §3.1](./05-min-agent-architecture.md)）。
