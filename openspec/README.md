# OpenSpec — min-agent

本目录是实现规格的事实来源。先改这里，再写代码。

## 布局

| 路径 | 用途 |
|------|------|
| `config.yaml` | 项目上下文与编写规则（含：文档用中文、写完过 avoid-ai-writing） |
| `changes/` | 进行中的变更 |
| `changes/archive/` | 已归档变更 |
| `specs/` | 当前基线规格 |

## 当前基线规格

- `specs/agent-runtime`
- `specs/session-store`
- `specs/tools-registry`
- `specs/min-agent-app`
- `specs/talk-assistant-mount`
- `specs/context-compaction`

来自归档：`changes/archive/2026-07-15-p0-chat-fc-loop/`、`changes/archive/2026-07-16-p1-talk-assistant/`、`changes/archive/2026-07-17-p2-loop-max-steps-align/`、`changes/archive/2026-07-20-p3-context-compaction/`。

## 当前活动变更

（无）

命令：`/opsx:propose` → `/opsx:apply` → `/opsx:archive`。

## 后续 change（建议）

| Change | 阶段 |
|--------|------|
| `p1-streaming-permission` | 流式 Turn + 边做边提示（SSE）+ 权限两道门 |
| `p2-task-subagent` | `task` + 纪要/PPT 固定流水线挂载 |
| `p2-long-term-memory` | 长期记忆 |
| `migrate-session-to-go` | 会话迁 Go |

## 架构笔记（叙事；冲突以本目录为准）

本仓库 [`documents/仿Opencode&Claude-code架构设计/`](../documents/仿Opencode&Claude-code架构设计/)：

- `01`–`04`：OpenCode / Claude 解读
- `05` / `05a` / `05b` / `06`：min-agent 架构与模块
