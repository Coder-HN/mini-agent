## MODIFIED Requirements

### 需求：min_agent Agent 装配

系统必须提供名为 `min_agent` 的应用 Agent：system prompt 描述管理后台 ChatOps 前台助手（查询只读），并注册 `query`、`navigate`、`ppt_generate`。prompt 须写清：查用户/登录日志走 `query`（`data_type=users|login_logs`）；写操作本里程碑未开放。系统 MUST NOT 再注册已下线的 `talk_assistant`。

#### 场景：查询与其它工具分工
- **当** 用户问「本部门有哪些人」或登录日志类只读问题
- **则** 查数须走 `query`，不得依赖其它占位工具冒充查数

### 需求：门面工具 query（go-admin 只读）

系统必须提供门面工具 `query`，参数含 `data_type`（至少 `users`、`login_logs`）与 `filters`。执行必须在 gateway 内按类型调用 go-admin REST，并携带调用方 JWT。意图由模型 FC 选择，不设预路由。

#### 场景：查用户列表
- **当** 用户问本部门/系统有哪些人
- **则** 模型选择 `query` 且 `data_type=users`；gateway 调用 `GET /api/v1/sys-user` 并带 Bearer；返回结构化列表供总结

#### 场景：查登录日志
- **当** 用户问登录失败/登录记录类问题
- **则** 模型选择 `query` 且 `data_type=login_logs`；gateway 调用 `GET /api/v1/sys-login-log` 并带 Bearer

### 需求：JWT 透传与权限拒绝可读

gateway 调用 go-admin 时 MUST 使用 `context.access_token`（或等价字段）作为 `Authorization: Bearer`。缺失 token 时 MUST NOT 匿名请求，MUST 返回结构化错误。上游 HTTP 401/403 时 MUST 返回可读权限拒绝说明（如无权查看），不得伪装为空成功列表。

#### 场景：无 token
- **当** 工具上下文无 access_token
- **则** 返回错误 JSON（含人类可读 message），且不向 go-admin 发请求

#### 场景：Casbin/数据权限拒绝
- **当** go-admin 返回 401 或 403
- **则** tool 结果含权限拒绝类可读说明，供模型中文转述

### 需求：HTTP 与 CLI 入口

`POST /chat` 与 CLI 契约不变。联调主路径为经控制面 `POST /api/v1/agent/chat`（自动注入 access_token）。

#### 场景：经代理验收（文档口径）
- **当** 使用 `admin` 与 `deptmgr` 的 JWT 分别经 `/api/v1/agent/chat` 问「本部门有哪些人」
- **则** 两侧均走 `query`/`users`，返回行集符合各自数据权限（可不相等）
