## 为什么做

P0 的 `talk_assistant` 仅占位。要把已上线的 **ai_crew 话术分析**（CrewAI `SalesScriptFlow` + FastAPI）接到 fengou-ai 前台，员工才能在同一助手里「问 CRM + 要话术」。

## 改什么

- **对接方式（已定）：** HTTP 调用现网 ai_crew，**不迁代码、不进程内 import**
- **产品形态（已定）：** 一键出回复：tool 内 create → upload → 轮询 status → result，同步等待后回灌摘要
- 将 `talk_assistant` 占位 `execute` 换成薄 HTTP 客户端（见 `design.md`）
- Settings 增加 `AI_CREW_BASE_URL` 等；更新 prompt/description 分工
- **稳定性：** 话术接口不通（错 URL / 断网 / 超时）→ 结构化 `ok:false` + 用户可读提示，进程与 `/chat` 不崩；并在 `tools-registry` 固化「全 tool 失败隔离」约定（Tool 自捕 + Loop 兜底）

**本 change 不做（Non-goals）：**

- 迁 `SalesScriptFlow` / CrewAI 进本仓库
- Loop 步数对齐（`p2-loop-max-steps-align`）
- 流式 SSE / 边做边提示（`p1-streaming-permission`）
- 权限 ask、纪要/PPT、`task`、compaction、长期记忆
- 改写 ai_crew 内部流水线；差评再生成 UI

## 能力

### 新增能力

- `talk-assistant-mount`：经 HTTP 挂载 ai_crew 的入参/出参/轮询/错误约定

### 修改能力

- `fengou-ai-app`：`talk_assistant` 从占位变为真 HTTP 调用；装配与 prompt 分工
- `tools-registry`：补充「工具失败隔离与结构化错误」（约束本工具及后续所有外部 IO 工具）

## 影响

- 代码：主要 `apps/fengou_ai/tools/talk_assistant.py` + `config.py`；确认 `loop.py` execute 兜底仍在；不新建话术 app
- 运行时依赖：可访问的 ai_crew 服务（`AI_CREW_BASE_URL`）；不通时降级为可读错误而非崩溃
- 对照 API：`crm-ai/ai_crew` 的 `/session/create|upload|status|result`
- 架构笔记：话术真挂载从「P2」改为本 P1
