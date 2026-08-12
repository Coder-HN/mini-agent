## Context

控制面已提供 `POST /api/v1/agent/chat`，转发时写入 `context.access_token` 并带 Bearer。Loop 执行 tool 时把请求 `context` 放进 `tool_ctx["context"]`。本 change 只改 mini-agent 只读查询路径。

## Goals / Non-Goals

**Goals**

- `data_type=users` → `GET {GO_GATEWAY_URL}/api/v1/sys-user`
- `data_type=login_logs` → `GET {GO_GATEWAY_URL}/api/v1/sys-login-log`
- 必带调用方 JWT；缺失 token 时结构化失败，不发匿名请求
- 上游 401/403 → `ok:false` + 可读 `message`（权限拒绝）
- 验收口径：同问本部门人员，不同角色经 Casbin/数据权限得到不同行集

**Non-Goals**

- 写操作、二次确认、审计 UI
- 删除 talk_assistant / navigate / ppt 注册
- 改 go-admin 接口或 Casbin 策略

## Decisions

1. **仍用单一门面 `query`**，用 `data_type` 路由；去掉 `commission` 主路径（可返回「已下线」错误，避免旧模型误点）。
2. **`GO_GATEWAY_URL` 默认 `http://127.0.0.1:8000`**（控制面）；与本服务 `:8001` 错开。
3. **HTTP**：标准库 `urllib` 或已有依赖；超时用配置（可复用短超时，如 30s）。
4. **filters**：透传为 query string（如 `pageIndex`/`pageSize`/`username`）；缺省 `pageIndex=1&pageSize=20`。
5. **单测**：Mock HTTP，不依赖真 go-admin；覆盖无 token / 403 / 200。

## Risks

- 模型仍用旧 `commission` → description 与 prompt 写清新类型；commission 返回明确下线错误
- 直连 `/chat` 未带 context → 明确要求经控制面代理或手工带 access_token
