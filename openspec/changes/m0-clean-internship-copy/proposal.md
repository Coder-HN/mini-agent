## Why

活跃文档与代码仍以实习期「睿德志行 / 佣金 / CRM 话术」为叙事，与 `documents/系统总体规划.md`（ChatOps + go-admin RBAC）冲突，拉长 OpenSpec 上下文并误导后续实现。M0 先清本仓活跃面文案与演示桩，不接真 REST。

## What Changes

- 重写 `openspec/config.yaml` 与 README 的产品定位为总体规划 ChatOps
- 更新 `min-agent-app`：演示查询用语去佣金品牌；本地桩改为中性「示例审批记录」
- 更新 `agent` prompt / `gateway` 桩数据 / 相关测试与试聊示例句
- **Non-goals**：不接 go-admin REST、不做 JWT 透传、不改 Loop/Store、不删除 `talk_assistant` 代码（仅从产品主叙事降级为非 M0 验收项）、不改 `openspec/changes/archive/**`、不改其他三仓

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `min-agent-app`：Purpose / query 演示场景 / gateway 桩需求改为中性示例数据；CLI/HTTP 验收句不再绑定「睿德志行佣金」

## Impact

- 代码：`apps/min_agent/gateway.py`、`agent.py`、`tools/query.py`（description 文案）、`tests/*` 示例句、`README.md`、`openspec/config.yaml`
- API：`POST /chat` 契约不变；桩 JSON 字段语义中性化（可能仍用 `data_type=commission` 键以降低工具 schema  churn，或改为 `demo_approval`——design 定一种）
- 文档：总体规划 M0 相关勾选在本 change 收尾时更新
