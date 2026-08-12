## Context

控制面 JWT 含 `identity`、`datascope`（1=全部，5=仅本人等）。会话在 Python Postgres。

## Goals / Non-Goals

**Goals：** 落 owner；trail/续聊按 datascope 过滤。  
**Non-Goals：** 部门树过滤会话。

## Decisions

1. `owner_user_id` 存字符串化用户 ID。  
2. 可见：`data_scope == "1"` → 全部；否则 `owner_user_id == viewer_user_id`。  
3. trail 查询参数：`viewer_user_id`、`data_scope`（由 Go 代理填）。  
4. 无归属的旧会话：仅 `data_scope=1` 可看。

## Risks

- [直连 :8001 绕过参数] → 联调主路径走 Go；文档写明

## 延后

- `GET /sessions` 列表页
