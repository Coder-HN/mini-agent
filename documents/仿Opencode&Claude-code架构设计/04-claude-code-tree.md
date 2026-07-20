# Claude Code 目录结构

> 上篇：`03-claude-code-architecture.md`（讲清了主循环、意图识别、权限、subagent 的运行原理）
> 本篇一件事：理出 `claude-code-source-code/src` 的业务代码目录树，标出核心模块和编码专用模块，跳过 UI / i18n / 纯基础设施
> 对照 `02-opencode-tree.md` 的写法（本次不含任何 Python 规划）

---

## 阅读前提

`claude-code-source-code/src` 是反编译还原的真实客户端源码（v2.1.88，约 16 万行）。它不是 monorepo，全部塞在一个 `src/` 下，但内部分层清楚。标记约定：

- `★` 核心业务模块，读源码/借鉴优先看
- `⚠` 编码 Agent 专用（读写代码、跑命令、git），做非编码助手时用不上
- `∅` UI / 终端渲染 / 输入法这类表现层，理解架构时整体跳过

---

## src 顶层文件

```
src/
├── main.tsx              ∅ CLI 入口 + REPL 启动装配（790KB，只装配不跑循环）
├── query.ts              ★ 主循环 queryLoop：一轮一次 provider turn
├── QueryEngine.ts        ★ SDK / headless 的查询生命周期引擎
├── Tool.ts               ★ 工具接口定义 + buildTool 工厂
├── tools.ts              ★ 工具注册与每轮组装（getAllBaseTools / getTools）
├── commands.ts           ~87 个斜杠命令的元数据（旁路，不是意图识别）
├── context.ts            ★ 用户/系统上下文组装
├── history.ts            输入历史 / 粘贴存储（不是对话转录，别搞混）
├── cost-tracker.ts       API 成本追踪
├── setup.ts              首次运行初始化
└── Task.ts / tasks.ts    运行时任务类型入口
```

---

## 运行时核心（★ 重点）

```
src/
├── query.ts                        ★ 主循环：压缩 → callModel → 执行工具 → 回灌 → 收尾
├── services/
│   ├── api/claude.ts               ★ 调 Anthropic API：拼 tool schema、流式、ToolSearch 延迟加载判定
│   ├── tools/                      ★ 工具执行
│   │   ├── toolOrchestration.ts    批量执行：按 isConcurrencySafe 分并行/串行组
│   │   ├── StreamingToolExecutor.ts 流式执行：边收边跑
│   │   └── toolExecution.ts        单工具：校验 → canUseTool → tool.call
│   ├── compact/                    ★ 上下文压缩
│   │   ├── autoCompact.ts          主动压缩（阈值 = 窗口 − 13000 缓冲）
│   │   ├── microCompact.ts         轻量压缩：替换老 tool_result 正文
│   │   ├── compact.ts              fork 摘要 Agent 做压缩
│   │   └── reactiveCompact.ts      API 报「太长」时的被动恢复
│   ├── mcp/                        MCP 客户端：接外部工具
│   ├── lsp/                        ⚠ 语言服务
│   ├── SessionMemory / extractMemories / autoDream  记忆与「做梦」整理
│   └── (analytics / oauth / plugins / tips 等外围)
├── context.ts                      ★ getUserContext / getSystemContext
├── constants/prompts.ts            ★ getSystemPrompt：按启用工具动态拼各段
└── utils/queryContext.ts           ★ fetchSystemPromptParts：并行取三份上下文
```

---

## 输入路由（★ Claude Code 特有的前置层）

```
src/utils/processUserInput/
├── processUserInput.ts     ★ 单一路由入口：/命令 · bash · 自然语言 分流
├── processSlashCommand.tsx 斜杠命令：local / prompt / forked 分类
├── processTextPrompt.ts    ★ 自然语言 → UserMessage，shouldQuery=true
└── processBashCommand.tsx  ⚠ bash 模式：本地跑 shell
```

`utils/slashCommandParsing.ts` 负责解析 `/foo args`。这一层是 OpenCode 没有的确定性旁路（见 03 文 §3.1）。

---

## 工具系统（★ 骨架借鉴 / ⚠ 具体工具编码专用）

```
src/
├── Tool.ts                     ★ Tool 接口 + buildTool + TOOL_DEFAULTS
├── tools.ts                    ★ 注册与每轮组装 + filterToolsByDenyRules
├── constants/tools.ts          ★ 各类 agent 的工具白/黑名单常量
├── utils/toolPool.ts           ★ mergeAndFilterTools：协调者过滤
├── utils/toolSearch.ts         ★ 延迟加载 / 工具发现
└── tools/                      40+ 内置工具，每个一个子目录
    ├── AgentTool/              ★ 唤起 subagent（见 03 文 §5）
    ├── TaskOutputTool/         ★ 读任务输出
    ├── TaskStopTool/           ★ 停任务
    ├── SendMessageTool/        ★ agent 间发消息
    ├── TeamCreateTool/·TeamDeleteTool/  ★ 队伍管理
    ├── TaskCreate/Update/Get/List Tool/ ★ Todo V2 任务板
    ├── TodoWriteTool/          ★ 待办清单
    ├── AskUserQuestionTool/    ★ 向用户提问
    ├── SkillTool/              ★ 调用技能
    ├── ToolSearchTool/         ★ 工具发现（延迟加载配套）
    ├── WebFetchTool/·WebSearchTool/  ★ 联网
    ├── EnterPlanModeTool/·ExitPlanModeTool/  规划模式进出
    ├── ScheduleCronTool/·RemoteTriggerTool/·SleepTool/  调度与触发
    ├── MCPTool/·ListMcpResourcesTool/·ReadMcpResourceTool/·McpAuthTool/  MCP 接入
    ├── FileReadTool/·FileEditTool/·FileWriteTool/  ⚠ 读写代码文件
    ├── GlobTool/·GrepTool/     ⚠ 搜代码
    ├── BashTool/·PowerShellTool/  ⚠ 跑命令
    ├── NotebookEditTool/·REPLTool/·LSPTool/  ⚠ 代码环境
    ├── EnterWorktreeTool/·ExitWorktreeTool/  ⚠ git 工作树
    ├── BriefTool/              KAIROS 通信（实验）
    └── SyntheticOutputTool/·testing/  内部/测试用
```

工具分类速览（README 口径）：文件操作、代码搜索、系统执行、联网、任务管理、子 agent、代码环境、git、配置权限、记忆规划、自动化、MCP。做非编码助手时，⚠ 那一批（文件/搜索/bash/notebook/lsp/worktree）整体替换成业务动作即可，其余框架照搬。

---

## 权限系统（★ 重点，含 ML 分类器）

```
src/
├── utils/permissions/
│   ├── permissions.ts          ★ hasPermissionsToUseTool 判定链主体
│   ├── PermissionMode.ts       ★ 6 种模式：default/plan/acceptEdits/bypassPermissions/dontAsk/auto
│   ├── permissionRuleParser.ts 规则解析 "Tool(content)"
│   ├── PermissionUpdate.ts     规则持久化到 settings
│   ├── filesystem.ts           ⚠ 读写路径权限、acceptEdits CWD 放行
│   ├── yoloClassifier.ts       ★ auto 模式 ML 分类器（OpenCode 没有）
│   ├── classifierDecision.ts   ★ 分类器快速路径 / 安全工具白名单
│   └── bashClassifier.ts       ⚠ bash 命令分类器
├── types/permissions.ts        ★ ToolPermissionContext / 规则类型
├── hooks/useCanUseTool.tsx     ★ 执行前的 canUseTool 钩子
├── hooks/toolPermission/       ★ 交互/协调者/swarm 三种权限处理器
└── components/permissions/     ∅ 权限弹窗 UI
```

---

## 多 Agent（★ 重点）

```
src/
├── tools/AgentTool/
│   ├── AgentTool.tsx           ★ Agent 工具：参数、路由（普通/fork/队友）
│   ├── runAgent.ts             ★ 跑子 agent 的 query 循环 + sidechain 转录
│   ├── loadAgentsDir.ts        ★ 合并 agent 定义（内置→插件→md→json）
│   ├── builtInAgents.ts        ★ 内置 subagent_type 定义
│   ├── forkSubagent.ts         ★ fork 模式（共享父上下文/缓存）
│   └── resumeAgent.ts          唤醒后台子 agent
├── coordinator/coordinatorMode.ts  ★ 协调者模式（worker 定义文件缺失）
├── tasks/                      ★ 运行时任务后端
│   ├── LocalAgentTask/         后台子 agent
│   ├── RemoteAgentTask/        云端 CCR 会话
│   ├── InProcessTeammateTask/  同进程队友（AsyncLocalStorage 隔离）
│   ├── LocalShellTask/         ⚠ 后台 bash
│   └── DreamTask/              记忆整理（仅 UI）
├── utils/swarm/                ★ 队伍/队友编排：spawn、邮箱、权限桥接
├── utils/task/                 ★ 任务框架：registerTask、输出文件、SDK 进度
├── utils/tasks.ts              ★ Todo V2 任务板持久化（与运行时任务不同）
└── components/agents/          ∅ agent 编辑/向导 UI
```

---

## 其余模块（按需看）

```
src/
├── commands/                   ~87 个斜杠命令实现（一命令一目录）
├── skills/ + utils/skills/     技能发现与加载
├── memdir/ + utils/memory/     长期记忆管理
├── plugins/ + services/plugins/ 插件系统
├── remote/ + bridge/           远程模式 / Claude Desktop 桥接
├── server/ + upstreamproxy/    本地服务 / 代理
├── assistant/                  KAIROS 助手模式（实验）
├── buddy/ + moreright/         实验特性
├── schemas/ + types/           Zod schema 与类型
├── state/                      应用状态
├── hooks/                      React hooks（含权限、通知）
├── native-ts/                  ⚠ 原生实现（file-index、yoga-layout、color-diff）
├── migrations/                 数据迁移
└── ∅ 表现层（整体跳过）:
    components/  ink/  screens/  vim/  voice/  keybindings/
    outputStyles/  constants(部分)  cli/handlers·transports
```

---

## 小结

看 Claude Code 源码的最短路径：

1. **`processUserInput/`** —— 搞懂 /命令·bash·文本怎么分流（这是它比 OpenCode 多的一层）
2. **`query.ts`** —— 主循环，一轮一次 provider turn，压缩→调模型→执行工具→回灌
3. **`Tool.ts` + `tools.ts` + `services/tools/`** —— 工具怎么定义、每轮怎么组装、怎么并行执行
4. **`utils/permissions/`** —— 两道门禁的判定链 + 6 模式 + ML 分类器
5. **`tools/AgentTool/` + `tasks/`** —— subagent 派生、后台任务、协调者/队伍

⚠ 标记的编码专用部分（文件读写、代码搜索、bash、notebook、lsp、git worktree）是「工具内容」，∅ 标记的表现层是「壳」，两者在理解架构时都可以跳过——真正的运行时骨架就是上面 1-5 那五块，和 OpenCode 是同构的。
