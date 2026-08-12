# min-agent

多轮 Function Calling 前台 Agent：`min_agent`。产品定位见 `documents/系统总体规划.md`（ChatOps）。  
M1：门面工具 `query` 调用 go-admin 只读 REST（`users` / `login_logs`），经控制面代理透传 JWT。

规格在 `openspec/`。架构说明在 `documents/仿Opencode&Claude-code架构设计/`（冲突以 openspec / 总体规划为准）。

## 启用服务

```bash
uv sync
copy .env.example .env
# 填写 OPENAI_API_KEY、OPENAI_API_BASE、OPENAI_MODEL_NAME、POSTGRES_DSN
# GO_GATEWAY_URL 默认 http://127.0.0.1:8000（go-admin 控制面）
uv run min-agent-server
# 默认 http://127.0.0.1:8001（与控制面 :8000 错开）
```

需要可连的 PostgreSQL；首次启动会建 `agent_sessions` / `agent_messages`。联调请先启动 go-admin-master。

## 测试

推荐经控制面代理（自动注入 JWT）：

```bat
REM 1) 登录拿 token（示例）
curl.exe -s -X POST http://127.0.0.1:8000/api/v1/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"123456\"}"

REM 2) 代理聊天
curl.exe -s -X POST http://127.0.0.1:8000/api/v1/agent/chat -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d "{\"message\":\"本部门有哪些人？\"}"
```

直连 Agent（需自行带 context.access_token）：

```bash
curl -X POST http://127.0.0.1:8001/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"本部门有哪些人？\",\"context\":{\"access_token\":\"<token>\"}}"
```

单测（Mock，不需要真服务）：

```bash
uv run python -m unittest discover -s tests -p "test_*.py" -v
```
