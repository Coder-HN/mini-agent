# P1 话术助手挂载 — 任务

> 决策已定：HTTP + 同步轮询（见 `design.md`）。可按本清单 `/opsx:apply`。
> **稳定性硬性要求：** 话术（及所有 tool）外部接口不通时必须结构化报错并提示用户，进程与 `/chat` 不得崩溃（`design.md` D9/D10）。

## 0. 配置

- [x] 0.1 `Settings` 增加 `AI_CREW_BASE_URL` / `AI_CREW_TIMEOUT_SEC` / `AI_CREW_POLL_INTERVAL_SEC` / `AI_CREW_POLL_MAX_SEC`
- [x] 0.2 `.env.example`（若有）写明变量含义与本地示例；生产域名部署时填写

## 1. 薄客户端（路径 A：有图）

- [x] 1.1 在 `apps/fengou_ai/tools/talk_assistant.py`（或同目录小模块）实现 HTTP：create → upload → poll status → result
- [x] 1.2 入参映射：`image_ref`→`screenshot_url`，`note`→`user_context_note`；`ctx`/context → create 身份与 `client_conversation_id`
- [x] 1.3 出参按 `design.md` D6 压缩为 JSON 字符串；成功必含 `primary_reply` 与 `crew_session_id`
- [x] 1.4 超时 / terminal / HTTP 4xx5xx / **断网与错误 base URL（unreachable）** → `ok: false` JSON（含可读 `message`）；材料全空不调 create；execute 内吞掉连接类异常，不向上抛导致 500
- [x] 1.5 替换占位 execute；**不**引入 CrewAI 依赖

## 2. 装配、文案与全 tool 稳定性

- [x] 2.1 按需微调 `TalkAssistantArgs` 与 tool description（仍强调与 `query` 分工）
- [x] 2.2 确认 `fengou_ai` system prompt 话术条款与真挂载一致
- [x] 2.3 确认 `loop.py` 对 `registry.execute` 的 `except Exception` 兜底仍在：未捕获异常 → tool_result JSON，不冒泡崩请求
- [x] 2.4 （约定落地）后续凡外部 IO 的 tool 均按 D10：自身返回结构化错误；以话术为样板，不要求本 change 重写占位工具

## 3. 联调与验收

- [x] 3.1 本地/测试 ai_crew 可用：`GET {base}/healthz`
- [x] 3.2 带可访问 `image_ref` 调 `POST /chat` → `tool_names_called` 含 `talk_assistant` → `reply` 含推荐话术（非「尚未实现」）；验收图 `test/招商反馈pic.png`（data-URL + context.image_ref）
- [x] 3.3 回归：佣金句仍走 `query`，不误点话术
- [x] 3.4 **必做：** 错误 `AI_CREW_BASE_URL` → 结构化失败、进程不崩（pipeline 验收；`/chat` 同路径由 tool 层保证）
- [x] 3.5 **必做：** 失败为 `ok: false` JSON，不伪造 `primary_reply`

## 4. 文档

- [x] 4.1 同步架构笔记：话术真挂载属 P1（方案 A HTTP），不再写「P2 才挂」
- [x] 4.2 （可选）路径 B 无图 dialogue — 本 change 默认不做；若要做另开任务

## 不做

- [x] （明确跳过）迁 `SalesScriptFlow`、SSE 进度、`regenerate` UI
