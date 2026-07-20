## Context

P0 已在 `fengou_ai` 白名单注册 `talk_assistant`，模型能选中，但 `execute` 仍是占位文案。真实话术分析由 **crm-ai / ai_crew** 独立上线：CrewAI `SalesScriptFlow` + FastAPI（`ai_crew.api.server:app`），管理端「麦总 AI」已在用。

本 change 按方案 A：**不迁代码、不 import Flow**，fengou-ai 只做 HTTP 薄客户端，把 ai_crew 挂到前台 FC 的 `talk_assistant` tool。

状态分层不变：

| 层 | 存什么 |
|----|--------|
| PostgreSQL（fengou Store） | 前台 session 的 user / 最终 assistant |
| 内存 messages（本轮 transcript） | `talk_assistant` 的 tool_result，供下一 Turn 总结 |
| ai_crew 会话（SalesScriptState） | OCR / 检索 / 推荐回复全量中间态；**父 Session 默认不可见** |

## Goals / Non-Goals

**Goals:**

1. `talk_assistant` execute 经 HTTP 调 ai_crew，跑通「一键出回复」：create → 交材料 → 轮询至 `reply_done` → 回灌摘要
2. 窄通道：入参 = 图 URL/文字说明（+ 可选身份）；出参 = JSON 字符串（`primary_reply` 等 + `crew_session_id`）
3. 话术失败（含接口不通）用结构化 `ok:false` JSON 回灌，提示问题，**进程与 `/chat` 不崩**；此稳定性约定适用于所有 tool（见 D10）

**Non-Goals:**

- 迁 `SalesScriptFlow` / CrewAI 进 fengou-ai，或进程内 `import ai_crew`
- 改写 ai_crew 内部节点、OCR、向量库、审计
- Loop 步数软收口（`p2-loop-max-steps-align`）
- 流式 SSE / 边做边提示进度条（`p1-streaming-permission`）；P1 同步阻塞即可
- 权限 ask、纪要/PPT、`task` 子 Agent
- 在统一助手里做「差评再生成」完整 UI（可后续用 `regenerate` API；本 change 不做）

## Decisions

### D1 · 挂载位置（锁定）

| 选项 | 结论 |
|------|------|
| 把 `SalesScriptFlow` 塞进 `run_agent` | 否 |
| 独立 ai_crew 服务 + `talk_assistant` tool | **是**（方案 A） |

代码落点（防过度工程）：

- **优先**只改 [`apps/fengou_ai/tools/talk_assistant.py`](../../../apps/fengou_ai/tools/talk_assistant.py)
- HTTP 轮询逻辑可同文件内联；若明显超长再抽同目录 `talk_assistant_client.py`（仍属 fengou_ai.tools）
- **禁止**新建 `apps/talk_assistant/` 整 app、禁止把 CrewAI 装进 fengou-ai 依赖

### D2 · 对接路径 = HTTP（锁定）

权威服务：已部署的 ai_crew FastAPI（与 PHP `fengou_crew_ai_base` 同源）。

| 候选 | 结论 |
|------|------|
| A. HTTP 调现有 API | **采用** |
| B. 进程内 import | 否（依赖重、发布耦合） |
| C. 经 Go Gateway | 否（话术面已在 Python；P1 不绕一层） |

配置（fengou-ai `Settings` 新增）：

| 环境变量 | 含义 | 建议默认 |
|----------|------|----------|
| `AI_CREW_BASE_URL` | ai_crew 根地址，无尾斜杠 | `http://127.0.0.1:8000`（与 ai_crew README 本地一致） |
| `AI_CREW_TIMEOUT_SEC` | 单次 HTTP 读超时 | `30` |
| `AI_CREW_POLL_INTERVAL_SEC` | 轮询间隔 | `1.5` |
| `AI_CREW_POLL_MAX_SEC` | 同步等待总上限 | `180`（话术链路含 OCR+多 Crew，宜偏长） |

鉴权：P1 与现网管理端一致——内网直打、无额外 token（若生产已有网关鉴权，把 Header 透传约定补进配置，不改业务契约）。

依赖：标准库 `urllib` 或已有 HTTP 库即可；**不**新增 CrewAI。

### D3 · 产品形态 = 一键出回复 + 同步轮询（锁定）

```text
talk_assistant.execute
  → POST {base}/session/create
  → 有图：POST {base}/session/{id}/upload   （立即返回 processing，后台跑全链路）
     无图仅文字：POST .../dialogue 再视 ai_crew 约定推进（见 §调用序列）
  → 循环 GET .../status 直到 reply_done | is_terminal | 超时
  → GET .../result
  → 把摘要 JSON 字符串作为 tool_result 返回
```

- **同步**：阻塞在 tool 内直到有终态或超时；结果进内存 messages，下一 Turn 由模型写成对用户的中文回复
- **异步推送 / SSE**：不做；进度不进前台 transcript
- 超时：返回结构化 error（含已创建的 `crew_session_id`，便于去原话术页续看），**不**抛未捕获异常导致整次 `/chat` 500（Loop 已有 execute 包一层；tool 自身仍应返回 JSON error 字符串为佳）

### D4 · 意图边界（锁定）

system prompt + tool description 保持：

- 查佣金/审批 → `query`
- 跳页 → `navigate`
- 微信聊天图 / 要推荐回复 → `talk_assistant`
- PPT → `ppt_generate`

### D5 · 入参 schema（对齐 ai_crew）

在现有 `TalkAssistantArgs` 上扩展（保持模型友好字段名，execute 内映射到 ai_crew body）：

| tool 字段 | 映射到 ai_crew | 说明 |
|-----------|----------------|------|
| `image_ref` | `upload.screenshot_url`（或加入 `screenshot_urls`） | 公网/内网可拉取的图片 URL，或 `data:image/...;base64,...`（ai_crew 已支持） |
| `image_refs`（可选 list） | `screenshot_urls` | 多图；P1 可先只支持单图 `image_ref` |
| `note` | `upload.user_context_note` | 谈判背景、语气等补充说明 |
| `merchant_shop_label`（可选） | `upload.merchant_shop_label` | 对方店铺/联系人名 |
| （无图时）`dialogue_text`（可选） | `POST .../dialogue` 的 `dialogue_text` | 跳过 OCR 的文字对话；与图二选一或图优先 |

身份（不进模型 schema 也行，从 `ctx` / `ChatRequest.context` 取）：

| 来源 | 写入 create |
|------|-------------|
| `context.operator_uid` / `user_id` | `CreateSessionRequest.operator_uid` / `user_id` |
| `context.operator_username` 等 | 同名字段 |
| fengou `session_id` | `client_conversation_id`（便于审计关联前台会话） |

**材料校验：** `image_ref` 与 `dialogue_text` / `note` 不能全空；全空则 tool 直接返回 error，不调 create。

### D6 · 出参（回灌 Loop 的 JSON 字符串）

成功时（`ensure_ascii=False`）：

```json
{
  "ok": true,
  "crew_session_id": "...",
  "primary_reply": "...",
  "personalized_reply": "...",
  "alternative_replies": [],
  "negotiation_advice": "...",
  "shop_label": "...",
  "source": "ai_crew"
}
```

字段取自 `GET /session/{id}/result` 的 `reply.*`（`ReplyOutput`）及 status 侧标签；**不要**把 `structured_info` / 候选库全量塞进 tool_result（太大、污染 transcript）。需要时只留一行 `dialogue_scene` 摘要可选。

失败 / 超时：

```json
{
  "ok": false,
  "error": "timeout|terminal|http|validation",
  "message": "人类可读说明",
  "crew_session_id": "...",
  "status": "processing|..."
}
```

### D7 · 与 ai_crew 的调用序列（实现必须遵守）

对照源码：`D:\workplace\crm-ai\ai_crew\src\ai_crew\api\server.py`。

**路径 A — 有截图（主路径）**

1. `POST /session/create`  
   body: `{ user_id, operator_uid, operator_username?, client_conversation_id }`  
   → `session_id`（下文称 `crew_session_id`）

2. `POST /session/{crew_session_id}/upload`  
   body: `{ screenshot_url, user_context_note, merchant_shop_label?, client_conversation_id? }`  
   → 立即 `{ status: "processing", accepted: true }`；**全链路在后台线程**

3. 轮询 `GET /session/{id}/status`  
   - 结束条件：`status == "reply_done"`，或 `is_terminal == true`  
   - 仍跑：`running == true` 或 status 为中间态  
   - 间隔 `AI_CREW_POLL_INTERVAL_SEC`，累计不超过 `AI_CREW_POLL_MAX_SEC`

4. `GET /session/{id}/result`  
   - `reply_done`：取 `reply.primary_reply` 等  
   - terminal 失败：用返回的 failure payload 填 `ok: false`

**路径 B — 无图、仅对话文本（次路径）**

1. create（同上）
2. `POST /session/{id}/dialogue` 写入对话  
3. 按 ai_crew 约定用 `POST .../next` 推进，或若后续提供「dialogue 后自动 pipeline」则跟现网行为；**实现前读一眼现网 dialogue 后是否自动跑后台**——若否，P1 文档约定：无图路径必须调用推进到 `reply_done` 的 API 组合，否则返回「请提供截图 URL」简化为仅支持路径 A

**P1 最小范围建议：先实装路径 A（有 `image_ref`）；无图仅 `note` 时返回明确 error，引导提供截图。** 路径 B 标为可选任务。

健康检查（启动或首次调用）：可选 `GET /healthz`；失败则 tool 返回 `ai_crew unreachable`。

### D8 · Session 隔离（锁定）

| Session | 职责 |
|---------|------|
| fengou `agent_sessions.id` | 前台多轮问答 |
| ai_crew `crew_session_id` | 单次话术流水线 |

- 一次 `talk_assistant` 调用 → **新建**一个 crew session（不复用旧流水线状态，除非后续做「续聊再生成」）
- 父 Store **不**持久化 OCR/检索中间态；只在 tool_result 里带 `crew_session_id` + 摘要
- 前台 `session_id` 仅作 `client_conversation_id` 关联审计

### D9 · 错误与超时策略（锁定 · 话术）

| 情况 | tool 行为 |
|------|-----------|
| 入参全空 | `ok:false` validation，不调 HTTP |
| **base URL 错误 / DNS 失败 / 连接拒绝 / 断网** | `ok:false`，`error=unreachable`（或 `network`），`message` 人类可读（如「话术服务暂时不可用，请稍后重试」） |
| create/upload HTTP 4xx/5xx | `ok:false` http，带 status code 摘要 |
| 单次请求读超时 | `ok:false` timeout |
| 轮询总时长超时 | `ok:false` timeout，带 `crew_session_id`（若已 create） |
| `is_terminal` 且非 reply_done | `ok:false` terminal，带 `failure_message` |

**硬性：** 上述任一情况都不得导致 uvicorn 进程退出、不得让 `POST /chat` 因 tool 失败而 500。应回灌 tool_result，由下一 Turn 用中文向用户说明问题。

### D10 · 全 tool 稳定性（锁定 · 跨工具）

两层防护，缺一不可：

| 层 | 职责 |
|----|------|
| **Tool 层（优先）** | 凡调外部 HTTP/IO 的 tool（`talk_assistant`、将来真 `query` Go、会议 chunk 等）必须自己 `try/except`，返回结构化 JSON（建议含 `ok` / `error` / `message`），**禁止**把连接异常直接抛出冒充「成功业务结果」 |
| **Loop 层（兜底）** | `run_agent` 对 `registry.execute` 的 `except Exception` 必须保留：任何未捕获异常 → 写成 tool 角色 JSON（如 `{"error": "..."}`）回灌，继续循环或终答；**不得**让异常冒泡成整次请求崩溃 |

说明：

- P0 Loop 已有兜底层（`loop.py` 中 execute 的 try/except）——本 change **保持该兜底，禁止删掉**
- 本 change 实现 `talk_assistant` 时必须做好 Tool 层；顺带在 `tools-registry` 规格写明「工具失败隔离」约定，约束后续所有 tool
- `message` 面向员工可读；技术细节可放 `detail` 字段，避免只回堆栈

## 目标调用链（对齐 POST /chat）

```text
POST /chat
  → store.get_or_create_session
  → run_agent
       → resolve（含 talk_assistant schema）
       → llm.chat
       → tool_calls 含 talk_assistant
            → talk_assistant._execute
                 → HTTP ai_crew（D7）
                 → 不通/超时 → ok:false JSON（D9），不抛崩
            → tool_result 进内存 messages
       → 下一 Turn 模型用中文提示「话术服务不可用…」
  → ChatResponse 仍 200 + 非空 reply（说明问题，而非进程崩溃）
```

本 change主要动 `_execute` + Settings +（必要时）prompt；**不得削弱** Loop 的 execute 兜底。若为统一错误 JSON 形状需微调整 Loop 兜底字段，允许小改且保持「捕获一切、回灌、不崩」。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 同步阻塞 `/chat` 最长 ~180s | 超时返回 session_id；后续用 SSE 做进度（另 change） |
| 图片 URL 外网不可达 | 约定传 ai_crew 能拉的 URL 或 data-URL；文档写清 |
| tool_result 过大 | 只回 reply 摘要字段（D6） |
| ai_crew 与 fengou 端口都 8000 | 本地用不同 port；配置写死 base URL |
| 无图路径行为与现网细节差 | P1 先只做有图路径 A |

## Migration Plan

1. 配置 `AI_CREW_BASE_URL` 指向现网或本地 ai_crew
2. 实现薄客户端 + 替换占位 execute
3. 联调：带 `image_ref` 的话术请求 → `tool_names_called` 含 talk_assistant → reply 含推荐话术
4. 回归：佣金句仍只走 `query`
5. 同步架构笔记：话术真挂载属 P1，非 P2

回滚：恢复占位 execute；ai_crew 本身不动。

## 延后 change

| Change | 关系 |
|--------|------|
| `p2-loop-max-steps-align` | 无关；可并行 |
| `p1-streaming-permission` | 以后话术进度条 / 不阻塞 chat |
| `p2-task-subagent` | 纪要/PPT；话术已在本 P1 |

## Open Questions（仅剩实现细节）

1. ~~对接路径~~ → **HTTP**（D2）
2. ~~同步/异步~~ → **同步轮询**（D3）
3. ~~出参~~ → **D6 JSON**
4. ~~Session 隔离~~ → **D8**
5. 生产 `AI_CREW_BASE_URL` 最终域名 / 是否需反代 Header（部署时填进 `.env.example`）
6. P1 是否做路径 B（无图 dialogue）——**默认不做**，确认即可关题

## 实现约定

- Open Questions 1–4 已关闭；**可以**按本 design `/opsx:apply`
- 未关题 5–6 不阻塞编码（用本地默认 URL；路径 B 不做）
- 禁止把 CrewAI / `SalesScriptFlow` 引入 fengou-ai
