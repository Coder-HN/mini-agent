# tools-registry

## Purpose

工具接口与注册表：按 Agent 白名单 resolve OpenAI schema，校验后 execute；失败隔离。

## 需求

### 需求：工具接口与注册表

系统必须为工具定义 name、description 与 Pydantic（或等价）参数 schema，并提供注册表，能够：(1) 为某个 Agent 解析出 OpenAI 兼容的 tools schema 列表；(2) 按名称校验参数并执行工具。每轮 Loop 迭代必须调用 resolve，不得把未过滤的静态 tools 列表写死在循环外且从不按 Agent 过滤（`design.md` §5、§7）。

#### 场景：按 Agent 解析 schema
- **当** 循环为 Agent `min_agent` 开始一轮
- **则** `resolve` 只返回该 Agent 已注册的工具（含 `query` / `write` 与占位工具，见 `min-agent-app`）

#### 场景：执行前校验
- **当** 模型请求某个工具并附带 JSON 参数
- **则** 注册表按 schema 校验参数后执行，并向模型返回字符串或 JSON 结果

#### 场景：占位工具也可走同一执行路径
- **当** 模型调用已注册的占位工具
- **则** 仍经 registry execute；结果为占位短文，不因「未实现」跳过注册表

### 需求：工具失败隔离与结构化错误

系统必须保证单个工具执行失败不会拖垮整次聊天请求或服务进程。凡工具在执行中调用外部 HTTP/IO（或其它可能抛错的依赖）时，应当捕获失败并返回可供模型消费的结构化错误字符串（建议 JSON，含可读说明）；`run_agent` 必须对 `registry.execute` 保留总兜底：若工具仍抛出未捕获异常，须将该错误写入 tool 角色消息并继续编排，不得让异常冒泡导致进程崩溃或整次 `POST /chat` 因该工具失败而裸 500。

#### 场景：外部服务不可达
- **当** 某工具依赖的外部服务不可达（错误地址、断网、连接拒绝、超时等）
- **则** 该次工具结果必须表现为错误信息（结构化 JSON 或兜底 `{"error":...}`），且同一次用户请求仍能结束并给出对用户的说明性回复；服务进程必须继续运行

#### 场景：Loop 兜底不可删除
- **当** 实现或修改 FC 主循环
- **则** 必须保留对工具 execute 的异常捕获与回灌；不得改为让工具异常直接中断整个 `run_agent` 而不写 tool_result

### 需求：P0 权限基线

P0 只暴露 Agent 定义里声明的工具（隐式白名单）。schema 阶段 deny、执行阶段 ask/deny 延后到 `p1-streaming-permission`（`design.md` §9）。P0 不得在 Python 侧另造业务数据范围 ACL（真实 API 接入后由 Go 负责；身份经 execute 的 ctx 透传）。

#### 场景：未声明工具不进 schema
- **当** 某工具不在 Agent 工具集中
- **则** 发给 LLM 的 schema 中不出现该工具
