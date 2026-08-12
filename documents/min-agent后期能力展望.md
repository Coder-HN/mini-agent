# min-agent 后期能力展望

> 只记录**尚未立项**、但后续要关注的能力。  
> 已开 change 见 [`openspec/README.md`](../openspec/README.md)；冲突以 `openspec/` 与 `documents/系统总体规划.md` 为准。

---

## 后续必须做

缺了会在长会话、取消请求或持久化上踩坑；排期在对应里程碑完成后单独开 change。

| 能力 | 含义 | 备注 |
|------|------|------|
| 压缩结果落库（OpenCode 式） | P3 首版只压本轮内存；后续把 prune 标记 / summarize checkpoint 写回 Store，加载时从 checkpoint + 近端拼上下文 | 在 `p3-context-compaction` 验证后再开；勿与长期记忆混模块 |
| 用户中止（interrupt） | 取消请求时，中止信号传到 LLM 调用与正在执行的 tool；未完成 tool 补 interrupted 结果 | 长工具链无取消会占连接与费用；建议与流式/权限 change 一并设计 |

---

## 可以考虑做

改善体感，缺了不挡 FC Loop + ChatOps 主路径；按产品优先级再排。

| 能力 | 含义 | 对照 |
|------|------|------|
| 跑中插话（inbox / steer / queue） | 工具执行中用户再发消息：先入收件箱，再插话或排队并入本轮 | OpenCode Session Drain |
| doom-loop 检测 | 连续相同参数调同一工具 → 打断或询问 | OpenCode 连续相同调用检测 |
| 按 token / 美元预算掐停 | 单次或会话累计超限则停 | Claude / OpenCode 预算控制 |
| 长期记忆检索 | 跨会话提炼事实，检索后注入 prompt 前缀 | 与 compaction 分模块；见 `p2-long-term-memory` |
