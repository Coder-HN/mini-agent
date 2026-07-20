## 为什么做

员工要用自然语言查 CRM（例如「睿德志行佣金审核通过了吗？」），并后续扩展话术/纪要/PPT。需要一套对齐 OpenCode / Claude Code 的多轮 FC 前台 `fengou_ai`（Store / Loop / Turn）。话术等固定流水线经 tool 挂载，不进主循环。

## 改什么

- 本仓库落地 Python monorepo（目录见 `design.md` §4）
- 多轮 FC 主循环（骨架见 `design.md` §6；意图见 §5）
- 两层状态：PostgreSQL 跨请求 + 内存 messages 本轮（`design.md` §2、§10）
- 门面工具 `query` + gateway 佣金桩（`design.md` §7.3）
- 占位工具 `navigate` / `talk_assistant` / `ppt_generate`（`design.md` §7.4；仅 schema + 未实现回复）
- HTTP `POST /chat` + CLI 验收（`design.md` §14）

本 change 不做：流式与边做边提示、权限 ask、历史截断、compaction、task/固定流水线真挂载、长期记忆、真实 commission API、斜杠/bash 路由（约定见 `design.md` §8–§13，留给后续 change）。

## 能力

### 新增

- `agent-runtime`：多轮 FC Loop / Turn；max_turns；tool_result 回灌内存 messages
- `session-store`：sessions / messages 持久化；按 session 加载历史
- `tools-registry`：Tool 接口、每轮 resolve schema、execute
- `fengou-ai-app`：fengou_ai 装配、query、三占位、gateway、chat API/CLI

### 修改

（无：仓库尚无基线 specs）

## 影响

- 仓库：`fengou-ai`
- 依赖：openai、pydantic、fastapi、uvicorn、psycopg
- 配置：`OPENAI_API_KEY` / `OPENAI_API_BASE` / `OPENAI_MODEL_NAME`、`GO_GATEWAY_URL`、`POSTGRES_DSN`
- 过渡态可直打 Python；目标态会话迁 Go Chat（另开 change）
- 架构笔记：本仓库 `documents/仿Opencode&Claude-code架构设计/` 的 `05` / `05a` / `05b` / `06`（冲突以本 openspec 为准）
