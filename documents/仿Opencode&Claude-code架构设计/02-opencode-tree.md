# OpenCode 业务目录树

> 上篇：`01-opencode-architecture.md`（意图识别与 subagent 的运行原理）
> 本篇一件事：理出 `D:\workplace\opencode` 的业务代码目录树，标出核心模块与编码专用模块，跳过 UI / i18n / 纯基础设施
> Python 业务助手见 [05-min-agent-architecture.md](./05-min-agent-architecture.md) · [06-min-agent-tree.md](./06-min-agent-tree.md)

---

OpenCode 是 monorepo，业务运行时集中在四个包：`opencode`（运行时主体）、`core`（可复用内核 + V2）、`llm`（多 provider 调用）、`server`（HTTP API）。其余包（tui / desktop / web / sdk / docs 等）是 UI 和外围，这里不展开。

标记约定：`★` 核心业务模块，读源码 / 借鉴优先看；`⚠` 编码 Agent 专用，做非编码助手时用不上。

## packages/opencode/src —— 运行时主体

```
opencode/src/
├── session/                    ★ 核心运行时：一次对话怎么跑
│   ├── prompt.ts               主循环 runLoop：拼上下文 → FC → 执行工具 → 回灌 → 收尾
│   ├── processor.ts            接住流式事件，驱动工具执行、写回消息
│   ├── tools.ts                每轮把工具包成 provider 能读的 schema
│   ├── system.ts               System Context：环境信息、技能列表、MCP 说明
│   ├── instruction.ts          载入 AGENTS.md / 项目说明
│   ├── reminders.ts            插入合成的系统提醒（如 plan 模式）
│   ├── compaction.ts           上下文超长时压缩
│   ├── summary.ts              会话摘要
│   ├── message*.ts             消息模型与序列化
│   ├── session.ts              Session 生命周期、切换 agent
│   ├── llm/                    组请求 + 调模型
│   │   ├── request.ts          合并 system prompt、按权限过滤工具 schema
│   │   ├── ai-sdk.ts           走 AI SDK 的实现
│   │   └── native-*.ts         原生 runtime 实现
│   └── prompt/                 各模型的 system prompt 模板（.txt）
├── agent/                      ★ 角色定义
│   ├── agent.ts                内置角色（build/plan/general/explore…）+ mode + 权限集
│   └── subagent-permissions.ts 子 session 权限继承规则
├── tool/                       ★ 内置工具（含编码专用，非编码助手要替换具体工具）
│   ├── tool.ts / registry.ts   工具接口 + 每轮工具组装
│   ├── task.ts                 subagent 调用：建子 session
│   ├── read/edit/write.ts      ⚠ 编码专用：读写代码文件
│   ├── grep/glob.ts            ⚠ 编码专用：搜代码
│   ├── shell/                  ⚠ 编码专用：跑命令
│   ├── apply_patch/patch       ⚠ 编码专用：打补丁
│   ├── lsp.ts                  ⚠ 编码专用：语言服务
│   ├── skill.ts                调用技能
│   ├── question.ts             向用户提问
│   ├── todo.ts                 任务清单
│   ├── webfetch/websearch.ts   联网
│   └── plan.ts                 plan 模式进出
├── permission/                 ★ 权限判定：allow / deny / ask
│   ├── index.ts                入口：evaluate / ask / disabled
│   └── evaluate.ts             规则合并与匹配
├── command/                    斜杠命令注册（显式快捷入口，非意图识别）
├── skill/                      技能发现与加载
├── mcp/                        MCP 客户端：接外部工具
├── provider/                   模型 provider 接入与鉴权
├── background/                 后台任务（后台 subagent 靠它）
├── question/                   向用户提问的 schema 与状态
├── config/                     配置加载
└── (基础设施, 略读)            bus / id / storage / snapshot / git /
                                worktree / ide / image / share / sync
```

## packages/core/src —— 可复用内核 + V2 运行时

`core` 是更底层、可持久化的一套（V2）。概念和上面一致，初读可略，理解思路时看这几个：

```
core/src/
├── session/
│   ├── runner/                 V2 版 runLoop（可持久化、事件溯源）
│   ├── execution/              本地执行编排
│   ├── history.ts              可见历史选择
│   ├── projector.ts            事件 → 消息投影
│   └── context-epoch.ts        上下文基线的版本管理
├── tool/                       V2 工具（builtins / registry / 各工具）
├── permission/                 权限持久化（saved / sql）
├── system-context/             ★ 类型化、可刷新的 System Context 注册表
├── skill/                      技能发现 + 基线文本
└── reference/                  引用（@file 等）指引文本
```

## packages/llm/src —— 多 Provider 调用

```
llm/src/
├── llm.ts / provider.ts        统一入口与 provider 抽象
├── tool.ts / tool-runtime.ts   工具在协议层的表示与执行
├── providers/                  anthropic / openai / google / xai / bedrock…
└── protocols/                  各家协议：anthropic-messages / openai-chat…
```

## packages/server/src —— HTTP API

```
server/src/
├── handlers/                   各 HTTP 路由处理
└── middleware/                 中间件
```

---

## 小结

看 OpenCode 业务代码的最短路径就是 `★` 那几块：`session/`（主循环 + 上下文 + 压缩 + 持久化）、`agent/`（角色与权限集）、`tool/`（工具接口与每轮组装）、`permission/`（两道门禁）、`core/system-context/`（结构化上下文）。`⚠` 标记的是编码专用工具，做非编码助手时整体替换成业务动作即可，运行时框架照搬。

想把这套结构落成 Python 业务助手，见 [05](./05-min-agent-architecture.md) / [06](./06-min-agent-tree.md)（同时对照 Claude Code，重点挑两个项目都有的模块）。
