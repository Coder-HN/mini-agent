## Context

M1 已落地只读 `query` + JWT 透传。控制面代理把 `access_token` 放进请求 `context`，Loop 执行 tool 时写入 `tool_ctx["context"]`。本 change 只在 mini-agent 增加写路径与二次确认；go-admin 已有 `POST /api/v1/sys-user` 与 `PUT /api/v1/user/status`。

确认态靠同会话多轮对话：预览结果回灌内存 messages（本轮 transcript），用户下一句确认后模型再带 `confirmed=true` 调用；跨请求靠 PostgreSQL 会话历史，不另建确认表。

## Goals / Non-Goals

**Goals**

- 可演示：创建用户、停用用户（status 置为停用）
- 默认未确认：只返回影响清单，不发写 HTTP
- 确认后：带 JWT 调 go-admin；401/403 可读错误
- prompt 写清：先预览再确认，查数仍用 `query`

**Non-Goals**

- 完整 P1 执行门 ask UI / SSE 确认卡片
- 分配角色独立工具、改密码、删用户
- 审计轨迹落库（后续 `m3-audit-trail`）
- 改 go-admin-master

## Decisions

1. **单一写工具 `write`**，`action=create_user|disable_user`，字段放 `payload` 对象 + `confirmed: bool`（默认 false）。  
   - 备选：拆成两个 tool → 否（schema 膨胀；Rule of Three）。
2. **二次确认实现在 tool 内**，不新增 Permission 框架。  
   - `confirmed=false` → `{ok:true, needs_confirm:true, impact:[...]}`，零写副作用。  
   - `confirmed=true` → 才 POST/PUT。  
   - 备选：专用 confirm token 表 → 否（YAGNI；同会话 FC 足够）。
3. **上游映射**  
   - `create_user` → `POST /api/v1/sys-user`（JSON body 对齐 InsertReq 常用字段）  
   - `disable_user` → 预览可 `GET /api/v1/sys-user/{id}`；执行 `PUT /api/v1/user/status`，`status="1"`（种子正常用户为 `"2"`，停用取 `"1"`）
4. **HTTP**：复用 gateway 内 urllib；抽 `_http_json(method, path, token, body=None)`，GET 仍走现有 `_http_get`。
5. **密码**：创建时 payload 可带 `password`；缺省用固定演示口令 `123456`（与种子账号一致），并在 impact 中明示。
6. **单测**：Mock urllib，覆盖未确认不写、确认写、无 token、403。

## Risks / Trade-offs

- [模型跳过预览直接 confirmed=true] → prompt 强调必须先预览；验收脚本可人工两步；后续可加 P1 ask 门  
- [停用 status 语义与前端不一致] → 文档与 impact 写清 `"1"=停用/"2"=正常`；以种子数据为准  
- [deptmgr 无创建权限] → 验收主路径用 `admin`；权限拒绝仍可读

## Migration Plan

- 向后兼容：只读路径不变；新增工具进白名单  
- 回滚：去掉 `write` 注册与 gateway 写函数即可  

## Open Questions

（无阻塞项）

## 延后 change

- `m3-audit-trail`：轨迹落库 + 可查询  
- `p1-streaming-permission`：执行门 ask / SSE  
- React 聊天页确认 UX（总体规划 UI 后置）
