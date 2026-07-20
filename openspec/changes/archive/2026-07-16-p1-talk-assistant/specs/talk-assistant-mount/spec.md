## ADDED Requirements

### 需求：话术助手经 HTTP 挂载 ai_crew

系统必须按方案 A 将已上线的 ai_crew 话术分析挂到前台工具 `talk_assistant`：通过 HTTP 调用 ai_crew（不得进程内 import `SalesScriptFlow` / CrewAI），在 tool 内同步完成「创建会话 → 提交截图材料 → 轮询至完成 → 取结果」，并将摘要以 JSON 字符串回灌内存 messages。不得把话术状态机嵌入 `run_agent`。

#### 场景：有图一键出回复
- **当** 模型调用 `talk_assistant` 且提供非空 `image_ref`（可拉取的图片 URL 或 data-URL）
- **则** 系统必须请求 ai_crew `POST /session/create` 与 `POST /session/{id}/upload`，轮询 `GET /session/{id}/status` 直至 `reply_done` 或终态失败或超时，成功时 tool 结果 JSON 含 `ok: true`、`crew_session_id`、`primary_reply`

#### 场景：回灌供下一 Turn 使用
- **当** `talk_assistant` 成功返回摘要 JSON
- **则** 该字符串必须进入本轮内存 messages 的 tool 角色内容，并在后续 Turn 中对模型可见

#### 场景：超时或终态失败
- **当** 轮询超过配置的最大等待时间，或 ai_crew 报告 `is_terminal` 且非 `reply_done`
- **则** tool 结果必须为 `ok: false` 的 JSON（含 `error` / `message`，超时或失败时尽量带上 `crew_session_id`），不得伪造成功话术

#### 场景：话术服务不可达
- **当** `AI_CREW_BASE_URL` 错误、服务未启动、断网或连接被拒绝
- **则** `talk_assistant` 必须返回 `ok: false` 的 JSON（`error` 为 `unreachable` 或 `network` 等，且含人类可读 `message`）；`POST /chat` 不得因该失败而进程崩溃或返回未处理的 500；最终 `reply` 须能提示用户话术服务暂不可用（由模型根据 tool_result 组织中文，或等价明确提示）

#### 场景：禁止迁入编排引擎
- **当** 实现本挂载
- **则** fengou-ai 依赖中不得新增 CrewAI；execute 路径不得直接实例化 `SalesScriptFlow`

#### 场景：材料不足
- **当** `image_ref` 为空且无其它已支持的材料字段
- **则** 不得调用 ai_crew create；直接返回 `ok: false` 的 validation 类错误 JSON
