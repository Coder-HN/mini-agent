# min-agent

多轮 Function Calling 前台 Agent：`min_agent`，门面工具 `query`（佣金本地桩），另有三个占位工具。

规格在 `openspec/`。架构说明在 `documents/仿Opencode&Claude-code架构设计/`（冲突以 openspec 为准）。注释规范见 `documents/规范/code-comments-standard.md`。

## 启用服务

```bash
uv sync
copy .env.example .env
# 填写 OPENAI_API_KEY、OPENAI_API_BASE、OPENAI_MODEL_NAME、POSTGRES_DSN
uv run min-agent-server
# 默认 http://127.0.0.1:8000
```

需要可连的 PostgreSQL；首次启动会建 `agent_sessions` / `agent_messages`。

## 测试

HTTP：

```bash
curl -X POST http://127.0.0.1:8000/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"睿德志行佣金审核通过了吗？\"}"
```

返回 `{"session_id":"...","reply":"..."}`。同一 `session_id` 可续聊。

CLI：

```bash
uv run python -m min_agent.cli "睿德志行佣金审核通过了吗？"
# 或：uv run min-agent "睿德志行佣金审核通过了吗？"
```

试聊脚本（可带上次 `session_id`）：

```bash
uv run python tests/chat.py 睿德志行佣金审核通过了吗？
uv run python tests/chat.py --session-id <上次session_id> 刚才那两笔是哪个渠道？
```

单测（Mock，不需要真服务）：

```bash
uv run python -m unittest discover -s tests -p "test_*.py" -v
```

期望：走 `query`、不点占位工具，并用中文总结桩数据里的驳回事实。
