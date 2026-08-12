## 1. 规格与配置

- [x] 1.1 同步 `openspec/specs/min-agent-app/spec.md`；更新 `openspec/config.yaml` 验收句
- [x] 1.2 `GO_GATEWAY_URL` 默认改为 `http://127.0.0.1:8000`；更新 `.env.example` / README

## 2. 网关与工具

- [x] 2.1 `gateway.py`：实现 users / login_logs HTTP 调用 + JWT；权限错误可读；去掉演示桩主路径
- [x] 2.2 `query.py` / `agent.py`：data_type 与 prompt 对齐 ChatOps 只读查询
- [x] 2.3 单测：无 token / 403 / 成功路径（Mock HTTP）→ `tests/test_gateway_jwt.py`

## 3. 总体规划

- [x] 3.1 勾选 R3 中 REST / 只读工具 / JWT 透传 / 权限拒绝可读 四项；更新 mini-agent 现状行
