## 新增需求

### 需求：工具接口与注册表

系统必须为工具定义 name、description 与 Pydantic（或等价）参数 schema，并提供注册表，能够：(1) 为某个 Agent 解析出 OpenAI 兼容的 tools schema 列表；(2) 按名称校验参数并执行工具。每轮 Loop 迭代必须调用 resolve，不得把未过滤的静态 tools 列表写死在循环外且从不按 Agent 过滤（`design.md` §5、§7）。

#### 场景：按 Agent 解析 schema
- **当** 循环为 Agent `fengou_ai` 开始一轮
- **则** `resolve` 只返回该 Agent 已注册的工具（P0 含 `query` 与三个占位，见 `fengou-ai-app`）

#### 场景：执行前校验
- **当** 模型请求某个工具并附带 JSON 参数
- **则** 注册表按 schema 校验参数后执行，并向模型返回字符串或 JSON 结果

#### 场景：占位工具也可走同一执行路径
- **当** 模型调用已注册的占位工具
- **则** 仍经 registry execute；结果为占位短文，不因「未实现」跳过注册表

### 需求：P0 权限基线

P0 只暴露 Agent 定义里声明的工具（隐式白名单）。schema 阶段 deny、执行阶段 ask/deny 延后到 `p1-streaming-permission`（`design.md` §9）。P0 不得在 Python 侧另造业务数据范围 ACL（真实 API 接入后由 Go 负责；身份经 execute 的 ctx 透传）。

#### 场景：未声明工具不进 schema
- **当** 某工具不在 Agent 工具集中
- **则** 发给 LLM 的 schema 中不出现该工具
