## MODIFIED Requirements

### 需求：min_agent Agent 装配

系统必须提供名为 `min_agent` 的应用 Agent：system prompt 描述管理后台 / ChatOps 前台助手（查询只读、不自动改写权限数据），并注册 `query`、`navigate`、`talk_assistant`、`ppt_generate`。prompt 须写清：查业务数据走 `query`；`navigate` / `ppt_generate` 可为占位；`talk_assistant` 若保留则非本里程碑主验收路径。

#### 场景：Agent 可用
- **当** 服务或 CLI 启动
- **则** `min_agent` 可作为聊天的默认 Agent

#### 场景：多工具进 schema
- **当** 循环为 `min_agent` 开始一轮
- **则** `resolve` 返回的 schema 同时包含 `query`、`navigate`、`talk_assistant`、`ppt_generate`

#### 场景：查询与其它工具分工
- **当** 用户询问示例审批 / 门店状态类只读问题
- **则** 不得依赖 `talk_assistant` 作为查数路径；查数须走 `query`

### 需求：门面工具 query

系统必须提供单一门面工具 `query`，参数包括 `data_type`（枚举至少含 `commission` 作为 M0 本地演示类型键，可含其它占位类型）与 `filters`（对象，如 `store_name` / `keyword` / `status`）。执行必须在 gateway 内按 `data_type` 确定性路由。意图由模型 FC 选择该工具，不设预路由。工具 description 不得再绑定实习品牌店名。

#### 场景：自然语言查示例审批
- **当** 用户问「示例门店甲的审批通过了吗？」或等价句
- **则** 模型选择 `query`，`data_type=commission`，且 `filters` 能标识示例门店甲（或等价字段）；gateway 返回结构化示例记录，供下一轮模型总结；本轮不得调用占位工具冒充查数结果

### 需求：占位工具（navigate / ppt_generate）

系统必须注册 `navigate`、`ppt_generate` 为占位工具（各有明确 description 与参数 schema；`execute` 只返回尚未实现短文）。

#### 场景：navigate / ppt 占位可调用但不冒充业务结果
- **当** 模型调用 `navigate` 或 `ppt_generate`
- **则** 工具结果为「尚未实现」类说明，且不得被当成查询成功数据

### 需求：本地演示桩 gateway

M0 的 `data_type=commission` 查询必须返回本地中性示例审批记录（至少两条，含渠道/状态/原因；不得再出现实习品牌店名「睿德志行」）。真 go-admin REST 路径可写注释预留；桩路径不发 HTTP。

#### 场景：桩返回驳回申请
- **当** `query` 以 `data_type=commission` 且店铺名为示例门店甲执行
- **则** 工具结果含足够桩数据，可供中文总结「已驳回」等事实

### 需求：HTTP 与 CLI 入口

系统必须提供 `POST /chat`，接受 `{session_id?, message, context?}`，返回 `{session_id, reply}`；并提供 CLI，接受单次用户消息并打印回复。

#### 场景：CLI 验收
- **当** 用「示例门店甲的审批通过了吗？」跑 CLI
- **则** 进程成功退出；轨迹含 `query` 且不含占位工具调用；打印与桩数据一致的中文总结（如已驳回）

#### 场景：HTTP 验收
- **当** 客户端对 `/chat` POST 同一消息
- **则** 响应含 `session_id` 与非空 `reply`，内容与桩数据一致
