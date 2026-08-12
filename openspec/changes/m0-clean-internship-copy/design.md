## Context

产品真源为 `documents/系统总体规划.md`。本仓 M0 只清活跃叙事与演示桩，FC Loop / Store 不动。真接 go-admin REST + JWT 属后续 M1。

## Goals / Non-Goals

**Goals**

- 活跃 openspec context、README、`min-agent-app` 规格与代码提示语对齐 ChatOps 定位
- 本地桩去掉「睿德志行」等实习品牌；验收句改为中性示例
- 单测 / 试聊脚本同步，Mock 路径仍绿

**Non-Goals**

- 不实现 go-admin HTTP、不透传 JWT
- 不删除 talk_assistant / navigate / ppt 注册（主验收不再依赖话术）
- 不改 archive 历史 change
- 不改架构长笔记全文（可选只改 README 指向总体规划；05* 叙事可留待后清理）

## Decisions

1. **`data_type` 键名**：保留 `commission` 作为本地演示桩类型键（减少 schema/测试 churn），description 与规格写明「M0 本地示例审批记录；M1 替换为 go-admin REST」。不新增枚举值。
2. **桩数据**：两条示例记录，`store_name=示例门店甲`，`status=已驳回`，渠道/原因用中性措辞。
3. **验收句**：`示例门店甲的审批通过了吗？`（或等价）；期望仍走 `query`、总结驳回事实。
4. **system prompt**：定位为管理后台助手 / ChatOps 前台；查数走 query；写操作未开放（M2）。

## Risks

- 外部若有人仍用旧验收句 → README 注明已更换；桩按 store_name 过滤，旧店名将返回空列表
- talk_assistant 规格仍在 → M0 不改 `talk-assistant-mount`；产品主路径以 query 演示为准
