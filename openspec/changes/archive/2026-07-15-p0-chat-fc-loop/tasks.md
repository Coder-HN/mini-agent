## 1. 脚手架

- [x] 1.1 按 `design.md` §4 建立 monorepo 目录与 P0 文件骨架：`packages/agent_core`（loop/message/context/store/agents/tools）、`packages/agent_llm`、`packages/agent_server`、`apps/fengou_ai`（含 gateway 与 tools：query + 三占位）
- [x] 1.2 配置 `pyproject.toml` / 工作区依赖：openai、pydantic、pydantic-settings、fastapi、uvicorn、pyyaml、psycopg
- [x] 1.3 增加 `.env.example`：`OPENAI_API_KEY`、`OPENAI_API_BASE`、`OPENAI_MODEL_NAME`、`GO_GATEWAY_URL`、`POSTGRES_DSN`（与 ai_crew 命名对齐）
- [x] 1.4 根 README：CLI 与 HTTP 启动步骤

## 2. Store 与消息

- [x] 2.1 实现 `message.py`（角色 + 转 OpenAI messages）
- [x] 2.2 实现 `store.py`：建表；按 `session_id` append / load
- [x] 2.3 实现 `context.py`：按 Agent 拼 system prompt（可带可选 context）
- [x] 2.4 实现 `agents.py`：AgentDef + 注册表

## 3. 工具与 LLM

- [x] 3.1 实现 `tools/base.py`、`tools/registry.py`（register / resolve / execute）
- [x] 3.2 实现 `agent_llm/client.py`：OpenAI 兼容 chat，`tool_choice=auto`
- [x] 3.3 实现 `loop.py` `run_agent`：按 `design.md` §6 骨架；`max_turns` 默认 6；非流式；中途 tool_result 只进内存 messages

## 4. fengou_ai 应用

- [x] 4.1 实现 `gateway.py` 佣金桩（注释预留 Go 路径）
- [x] 4.2 实现 `tools/query.py` 门面（`data_type` + `filters`）
- [x] 4.3 实现三占位工具（`design.md` §7.4）：`navigate`、`talk_assistant`、`ppt_generate`——完整 description/schema，execute 仅返回「尚未实现」短文
- [x] 4.4 实现 `agent.py` / `config.py`：装配 `fengou_ai`，白名单含 query + 三占位；prompt 写清各工具分工
- [x] 4.5 实现 `agent_server` `POST /chat` 与 `fengou_ai` 的 `main.py` / `cli.py`

## 5. 验收

- [x] 5.1 CLI 跑 `睿德志行佣金审核通过了吗？`：resolve schema 含四个工具；至少一轮 **仅** `query`（未点占位）+ 桩驳回总结
- [x] 5.2 `POST /chat` 同文案：返回 `session_id` + reply；复用 `session_id` 能载入历史
- [x] 5.3 PostgreSQL 有 session 行，以及 user / 最终 assistant 消息行
