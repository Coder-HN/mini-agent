## 新增需求

### 需求：fengou_ai Agent 装配

系统必须提供名为 `fengou_ai` 的应用 Agent（`design.md` §7.1）：system prompt 描述粉够 AI 前台助手（CRM 查询/导航对审批只读：可解释、可查询，不自动审批），并注册 `query` 以及三个占位工具 `navigate`、`talk_assistant`、`ppt_generate`（`design.md` §7.4）。prompt 须写清分工，便于模型在多工具 schema 下选对工具。话术/PPT 的真实流水线挂载按方案 A（`design.md` §8）留到后续 change，本 P0 只占位。

#### 场景：Agent 可用
- **当** 服务或 CLI 启动
- **则** `fengou_ai` 可作为聊天的默认 Agent

#### 场景：多工具进 schema
- **当** 循环为 `fengou_ai` 开始一轮
- **则** `resolve` 返回的 schema 同时包含 `query`、`navigate`、`talk_assistant`、`ppt_generate`

### 需求：门面工具 query

系统必须提供单一门面工具 `query`（`design.md` §7.3），参数包括 `data_type`（枚举至少含 `commission`，可含 `shop`、`baokuan`、`dataoke`）与 `filters`（对象，如 `store_name` / `keyword` / `status`）。执行必须在 gateway 内按 `data_type` 确定性路由，不得为每个后端接口各发明一个 tool。意图由模型 FC 选择该工具，不设预路由。

#### 场景：自然语言查佣金
- **当** 用户问「睿德志行佣金审核通过了吗？」
- **则** 模型选择 `query`，`data_type=commission`，且 `filters` 能标识睿德志行（或等价字段）；gateway 返回结构化佣金记录，供下一轮模型总结；本轮不得调用三个占位工具

### 需求：P0 占位工具

系统必须注册以下占位工具（`design.md` §7.4），各有明确 description 与参数 schema；`execute` 只返回表示尚未实现的短文，不得调用外部 HTTP、不得跑真实流水线：

| 工具 | 语义 |
|------|------|
| `navigate` | 按意图帮助跳转到 CRM/业务网页路由 |
| `talk_assistant` | 分析微信聊天图片，给出对商家的推荐回复 |
| `ppt_generate` | 按主题撰写/生成 PPT |

#### 场景：占位可调用但不冒充业务结果
- **当** 模型调用任一占位工具
- **则** 工具结果为「尚未实现」类说明，且不得被当成佣金查询成功数据

### 需求：佣金桩 gateway

P0 的佣金查询必须返回本地桩数据，形态类似已驳回的佣金申请（至少两条，覆盖如京东/淘宝等渠道，含方案/状态/原因）。真实 Go 路径 `/v1/fengou-ai/commission/search/agent` 可写注释预留，P0 验收不要求该 HTTP 成功；桩路径不发 Go 请求。

#### 场景：桩返回驳回申请
- **当** `query` 以 `data_type=commission` 且店铺名为睿德志行执行
- **则** 工具结果含足够桩数据，可供中文总结「已驳回」等事实

### 需求：HTTP 与 CLI 入口

系统必须提供 `POST /chat`，接受 `{session_id?, message, context?}`，返回 `{session_id, reply}`；并提供 CLI，接受单次用户消息并打印回复（`design.md` §14）。

#### 场景：CLI 验收
- **当** 用「睿德志行佣金审核通过了吗？」跑 CLI
- **则** 进程成功退出；轨迹含 `query` 且不含占位工具调用；打印与桩数据一致的中文总结（如已驳回）

#### 场景：HTTP 验收
- **当** 客户端对 `/chat` POST 同一消息
- **则** 响应含 `session_id` 与非空 `reply`，内容与桩数据一致
