## MODIFIED Requirements

### 需求：min_agent Agent 装配

系统必须提供名为 `min_agent` 的应用 Agent：system prompt 描述管理后台 ChatOps 前台助手，并注册 `query`、`write`、`navigate`、`ppt_generate`。prompt 须写清：查用户/登录日志走 `query`（`data_type=users|login_logs`）；创建/停用用户走 `write`，且必须先以 `confirmed=false` 预览影响对象，待用户明确确认后再以 `confirmed=true` 执行；不得声称已改权限数据除非写工具成功。系统 MUST NOT 再注册已下线的 `talk_assistant`。

#### 场景：Agent 可用
- **当** 服务或 CLI 启动
- **则** `min_agent` 可作为聊天的默认 Agent

#### 场景：多工具进 schema
- **当** 循环为 `min_agent` 开始一轮
- **则** `resolve` 返回的 schema 同时包含 `query`、`write`、`navigate`、`ppt_generate`，且不含 `talk_assistant`

#### 场景：查询与写分工
- **当** 用户问「本部门有哪些人」或登录日志类只读问题
- **则** 查数须走 `query`，不得用 `write` 冒充查数

### 需求：JWT 透传与权限拒绝可读

gateway 调用 go-admin（含只读与写）时 MUST 使用 `context.access_token`（或等价字段）作为 `Authorization: Bearer`。缺失 token 时 MUST NOT 匿名请求，MUST 返回结构化错误。上游 HTTP 401/403 时 MUST 返回可读权限拒绝说明，不得伪装为空成功列表或伪造成功写入。`access_token` MUST NOT 写入 system prompt。

#### 场景：无 token
- **当** 工具上下文无 access_token
- **则** 返回错误 JSON（含人类可读 message），且不向 go-admin 发请求

#### 场景：Casbin/数据权限拒绝
- **当** go-admin 返回 401 或 403
- **则** tool 结果含权限拒绝类可读说明，供模型中文转述

### 需求：HTTP 与 CLI 入口

系统必须提供 `POST /chat`，接受 `{session_id?, message, context?}`，返回 `{session_id, reply}`；并提供 CLI。联调主路径为经控制面 `POST /api/v1/agent/chat`（自动注入 access_token）。

#### 场景：经代理验收写路径（文档口径）
- **当** 使用具备用户管理权限的 JWT（如 `admin`）经 `/api/v1/agent/chat` 请求「给张三开账号」类写意图
- **则** 首轮须出现 `write` 预览（`needs_confirm`），确认后再执行成功；不得在未确认时完成创建

## ADDED Requirements

### 需求：写工具 write（创建 / 停用 + 二次确认）

系统必须提供工具 `write`，参数至少含：`action`（枚举 `create_user`、`disable_user`）、`payload`（对象）、`confirmed`（布尔，默认 false）。执行必须在 gateway 内映射到 go-admin：

- `create_user` → `POST /api/v1/sys-user`
- `disable_user` → `PUT /api/v1/user/status`（停用时 `status` 置为 `"1"`；正常为 `"2"`）

当 `confirmed` 为 false 时，MUST 返回结构化预览（含 `needs_confirm: true` 与将影响对象清单 `impact`），MUST NOT 发出写 HTTP。当 `confirmed` 为 true 时，MUST 携带调用方 JWT 执行对应写请求，并将上游结果结构化回灌。

#### 场景：创建用户须先预览
- **当** 模型调用 `write` 且 `action=create_user`、`confirmed=false`，payload 含用户名/昵称等必要字段
- **则** 返回 `needs_confirm=true` 与 impact（至少含将创建的用户标识字段），且不向 go-admin 发送 POST

#### 场景：确认后创建用户
- **当** 同会话用户明确确认后，模型调用 `write` 且 `action=create_user`、`confirmed=true`
- **则** gateway 以 Bearer JWT 调用 `POST /api/v1/sys-user`；成功时 tool 结果 `ok=true` 并含上游摘要

#### 场景：停用用户须先预览
- **当** 模型调用 `write` 且 `action=disable_user`、`confirmed=false`，payload 能标识用户（如 `userId` 或 `username`）
- **则** 返回将停用对象的 impact（尽量含 userId/用户名/昵称）；不得发出 status 写请求

#### 场景：确认后停用用户
- **当** `write` 且 `action=disable_user`、`confirmed=true`
- **则** gateway 调用 `PUT /api/v1/user/status` 将目标用户 `status` 设为 `"1"`
