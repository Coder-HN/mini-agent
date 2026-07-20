## MODIFIED Requirements

### 需求：fengou_ai Agent 装配

系统必须提供名为 `fengou_ai` 的应用 Agent：system prompt 描述粉够 AI 前台助手（CRM 查询/导航对审批只读：可解释、可查询，不自动审批），并注册 `query`、`navigate`、`talk_assistant`、`ppt_generate`。prompt 须写清分工。本 change apply 后，`talk_assistant` 必须经 HTTP 调用 ai_crew 完成话术分析（见 `talk-assistant-mount`）；`navigate` / `ppt_generate` 在本 change 内仍可为占位。

#### 场景：Agent 可用
- **当** 服务或 CLI 启动
- **则** `fengou_ai` 可作为聊天的默认 Agent

#### 场景：多工具进 schema
- **当** 循环为 `fengou_ai` 开始一轮
- **则** `resolve` 返回的 schema 同时包含 `query`、`navigate`、`talk_assistant`、`ppt_generate`

#### 场景：话术与查询分工
- **当** 用户询问佣金/审批状态
- **则** 不得依赖 `talk_assistant` 作为查数路径；查数须走 `query`

### 需求：P0 占位工具

系统必须注册 `navigate`、`ppt_generate` 为占位工具（各有明确 description 与参数 schema；`execute` 只返回尚未实现短文）。`talk_assistant` 在本 change apply 完成后不再属于占位工具，必须走 ai_crew HTTP 挂载；apply 前可继续占位。

#### 场景：navigate / ppt 占位可调用但不冒充业务结果
- **当** 模型调用 `navigate` 或 `ppt_generate`
- **则** 工具结果为「尚未实现」类说明，且不得被当成佣金查询成功数据

#### 场景：talk_assistant apply 后非占位
- **当** 本 change 已 apply 且 `AI_CREW_BASE_URL` 指向可用 ai_crew
- **则** 调用 `talk_assistant`（含有效 `image_ref`）必须返回真实话术摘要或结构化错误 JSON，不得仅返回「尚未实现」
