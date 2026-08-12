## 1. 规格落地到主规格

- [x] 1.1 将 delta 合并进 `openspec/specs/min-agent-app/spec.md`（装配含 `write`；写工具 + 二次确认需求）
- [x] 1.2 更新 `openspec/config.yaml`：M2 写工具/二次确认；延后改为 M3 审计等

## 2. Gateway 写路径

- [x] 2.1 `gateway.py`：抽取 `_http_json`；实现 `create_user` / `disable_user`（未确认只预览；确认后 POST/PUT + JWT）
- [x] 2.2 停用预览：有 `userId` 时尽量 GET 详情丰富 impact；无 token / 401/403 可读错误

## 3. 工具与装配

- [x] 3.1 新增 `apps/min_agent/tools/write.py` 并注册到 `agent.py`；更新 SYSTEM_PROMPT 分工与二次确认约定
- [x] 3.2 `cli.py` 占位集合不含 `write`（write 为真工具）

## 4. 验证

- [x] 4.1 单测：未确认不发写请求；确认后调用正确 method/path；无 token / 403
- [x] 4.2 勾选本 tasks；同步 `documents/系统总体规划.md` R3 写工具与二次确认两项
