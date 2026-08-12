"""业务数据网关：go-admin REST + 调用方 JWT；只读 query 与写工具二次确认。

Python 不直连业务库。写操作默认先预览 impact，confirmed=true 才发写请求。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# 与 go-admin 种子一致：正常="2"；停用取 "1"
_USER_STATUS_ACTIVE = "2"
_USER_STATUS_DISABLED = "1"
_DEFAULT_PASSWORD = "123456"


def _access_token(ctx: dict[str, Any] | None) -> str:
    """从 tool_ctx 取控制面注入的 JWT。"""
    if not ctx:
        return ""
    nested = ctx.get("context")
    if isinstance(nested, dict):
        token = nested.get("access_token") or nested.get("token")
        if token:
            return str(token).strip()
    token = ctx.get("access_token") or ctx.get("token")
    return str(token).strip() if token else ""


def _go_base() -> str:
    from min_agent.config import Settings

    return Settings.load().go_gateway_url.rstrip("/")


def _missing_token() -> dict[str, Any]:
    return {
        "ok": False,
        "error": "missing_token",
        "message": "缺少调用方凭证，请经控制面 /api/v1/agent/chat 访问",
        "source": "gateway",
    }


def _http_error_result(exc: urllib.error.HTTPError, *, write: bool) -> dict[str, Any]:
    raw = exc.read().decode("utf-8", errors="replace")
    detail: Any
    try:
        detail = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        detail = raw
    if exc.code in (401, 403):
        verb = "执行该写操作" if write else "查看该数据"
        return {
            "ok": False,
            "error": "permission_denied",
            "http_status": exc.code,
            "message": f"你无权{verb}（权限或数据范围受限）",
            "detail": detail,
            "source": "go-admin",
        }
    return {
        "ok": False,
        "error": "upstream_http",
        "http_status": exc.code,
        "message": f"go-admin 返回 HTTP {exc.code}",
        "detail": detail,
        "source": "go-admin",
    }


def _http_get(path: str, *, token: str, params: dict[str, Any]) -> dict[str, Any]:
    """GET go-admin；401/403 转可读权限错误。"""
    q = {k: v for k, v in params.items() if v is not None and str(v) != ""}
    q.setdefault("pageIndex", 1)
    q.setdefault("pageSize", 20)
    url = f"{_go_base()}{path}"
    if q:
        url = f"{url}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body) if body else {}
            return {
                "ok": True,
                "http_status": getattr(resp, "status", 200),
                "data": data,
                "source": "go-admin",
            }
    except urllib.error.HTTPError as exc:
        return _http_error_result(exc, write=False)
    except urllib.error.URLError as exc:
        return {
            "ok": False,
            "error": "unreachable",
            "message": "go-admin 服务暂时不可用，请确认控制面已启动",
            "detail": str(exc.reason),
            "source": "go-admin",
        }


def _http_json(
    method: str,
    path: str,
    *,
    token: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """POST/PUT JSON 到 go-admin。"""
    url = f"{_go_base()}{path}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method=method.upper(),
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw) if raw else {}
            return {
                "ok": True,
                "http_status": getattr(resp, "status", 200),
                "data": parsed,
                "source": "go-admin",
            }
    except urllib.error.HTTPError as exc:
        return _http_error_result(exc, write=True)
    except urllib.error.URLError as exc:
        return {
            "ok": False,
            "error": "unreachable",
            "message": "go-admin 服务暂时不可用，请确认控制面已启动",
            "detail": str(exc.reason),
            "source": "go-admin",
        }


def list_users(filters: dict[str, Any] | None, ctx: dict[str, Any] | None) -> dict[str, Any]:
    token = _access_token(ctx)
    if not token:
        return _missing_token()
    return {
        "data_type": "users",
        "filters": filters or {},
        **_http_get("/api/v1/sys-user", token=token, params=dict(filters or {})),
    }


def list_login_logs(
    filters: dict[str, Any] | None, ctx: dict[str, Any] | None
) -> dict[str, Any]:
    token = _access_token(ctx)
    if not token:
        return _missing_token()
    return {
        "data_type": "login_logs",
        "filters": filters or {},
        **_http_get("/api/v1/sys-login-log", token=token, params=dict(filters or {})),
    }


def route_query(
    data_type: str,
    filters: dict[str, Any] | None = None,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """门面路由：统一经 data_type 分发到 go-admin 只读 API。"""
    if data_type == "users":
        return list_users(filters, ctx)
    if data_type == "login_logs":
        return list_login_logs(filters, ctx)
    if data_type == "commission":
        return {
            "ok": False,
            "error": "retired",
            "data_type": data_type,
            "message": "commission 演示桩已下线；请用 users 或 login_logs",
            "source": "gateway",
        }
    return {
        "ok": False,
        "error": "unsupported_data_type",
        "data_type": data_type,
        "filters": filters or {},
        "message": f"data_type '{data_type}' 尚未接入；可用 users / login_logs",
        "source": "gateway",
    }


def _create_body(payload: dict[str, Any]) -> dict[str, Any]:
    """组装创建用户 body；缺省密码与 status。"""
    body = {
        "username": str(payload.get("username") or "").strip(),
        "nickName": str(
            payload.get("nickName") or payload.get("nickname") or ""
        ).strip(),
        "phone": str(payload.get("phone") or "").strip(),
        "email": str(payload.get("email") or "").strip(),
        "password": str(payload.get("password") or _DEFAULT_PASSWORD),
        "deptId": int(payload.get("deptId") or 1),
        "roleId": int(payload.get("roleId") or 0),
        "postId": int(payload.get("postId") or 0),
        "sex": str(payload.get("sex") or "1"),
        "status": str(payload.get("status") or _USER_STATUS_ACTIVE),
        "remark": str(payload.get("remark") or ""),
    }
    if payload.get("avatar"):
        body["avatar"] = str(payload["avatar"])
    return body


def create_user(
    payload: dict[str, Any] | None,
    *,
    confirmed: bool,
    ctx: dict[str, Any] | None,
) -> dict[str, Any]:
    """创建用户：未确认只预览；确认后 POST /api/v1/sys-user。"""
    payload = dict(payload or {})
    body = _create_body(payload)
    impact = [
        {
            "op": "create_user",
            "username": body["username"],
            "nickName": body["nickName"],
            "phone": body["phone"],
            "email": body["email"],
            "deptId": body["deptId"],
            "roleId": body["roleId"],
            "status": body["status"],
            "password": body["password"],
            "note": "将创建上述账号；请向用户展示并征求确认后再 confirmed=true",
        }
    ]
    if not body["username"] or not body["nickName"]:
        return {
            "ok": False,
            "error": "validation",
            "message": "create_user 需要 username 与 nickName",
            "impact": impact,
            "source": "gateway",
        }
    if not confirmed:
        return {
            "ok": True,
            "needs_confirm": True,
            "action": "create_user",
            "impact": impact,
            "message": "尚未执行创建。请向用户列出影响对象，确认后再调用 write(confirmed=true)",
            "source": "gateway",
        }
    if not body["phone"] or not body["email"]:
        return {
            "ok": False,
            "error": "validation",
            "message": "创建用户还需要 phone 与 email（go-admin 校验）",
            "impact": impact,
            "source": "gateway",
        }
    token = _access_token(ctx)
    if not token:
        return _missing_token()
    result = _http_json("POST", "/api/v1/sys-user", token=token, body=body)
    return {
        "action": "create_user",
        "needs_confirm": False,
        "impact": impact,
        **result,
    }


def _resolve_disable_target(
    payload: dict[str, Any], token: str
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """解析停用目标；返回 (impact_item, error_result)。"""
    user_id = payload.get("userId") or payload.get("user_id")
    username = str(payload.get("username") or "").strip()
    nick = str(payload.get("nickName") or payload.get("nickname") or "").strip()

    if user_id:
        uid = int(user_id)
        detail = _http_get(f"/api/v1/sys-user/{uid}", token=token, params={})
        item: dict[str, Any] = {
            "op": "disable_user",
            "userId": uid,
            "newStatus": _USER_STATUS_DISABLED,
            "note": "将把该用户状态设为停用(1)；正常为 2",
        }
        if detail.get("ok") and isinstance(detail.get("data"), dict):
            data = detail["data"].get("data") or detail["data"]
            if isinstance(data, dict):
                item["username"] = data.get("username") or username
                item["nickName"] = data.get("nickName") or nick
                item["currentStatus"] = data.get("status")
        else:
            if username:
                item["username"] = username
            if nick:
                item["nickName"] = nick
        return item, None

    if not username:
        return None, {
            "ok": False,
            "error": "validation",
            "message": "disable_user 需要 userId 或 username",
            "source": "gateway",
        }

    listed = _http_get(
        "/api/v1/sys-user",
        token=token,
        params={"username": username, "pageIndex": 1, "pageSize": 5},
    )
    if not listed.get("ok"):
        return None, listed
    data = listed.get("data") or {}
    inner = data.get("data") if isinstance(data, dict) else {}
    rows = []
    if isinstance(inner, dict):
        rows = inner.get("list") or inner.get("rows") or []
    elif isinstance(data, dict):
        rows = data.get("list") or []
    if not rows:
        return None, {
            "ok": False,
            "error": "not_found",
            "message": f"未找到用户名 {username}",
            "source": "gateway",
        }
    row = rows[0] if isinstance(rows[0], dict) else {}
    return {
        "op": "disable_user",
        "userId": row.get("userId") or row.get("user_id"),
        "username": row.get("username") or username,
        "nickName": row.get("nickName") or nick,
        "currentStatus": row.get("status"),
        "newStatus": _USER_STATUS_DISABLED,
        "note": "将把该用户状态设为停用(1)；正常为 2",
    }, None


def disable_user(
    payload: dict[str, Any] | None,
    *,
    confirmed: bool,
    ctx: dict[str, Any] | None,
) -> dict[str, Any]:
    """停用用户：未确认只预览；确认后 PUT /api/v1/user/status。"""
    payload = dict(payload or {})
    token = _access_token(ctx)

    # 预览阶段：有 token 时尽量补全 impact；无 token 仍可基于 payload 粗预览，确认执行再拦
    if not confirmed:
        if token:
            item, err = _resolve_disable_target(payload, token)
            if err:
                return err
            assert item is not None
            return {
                "ok": True,
                "needs_confirm": True,
                "action": "disable_user",
                "impact": [item],
                "message": "尚未执行停用。请向用户列出影响对象，确认后再调用 write(confirmed=true)",
                "source": "gateway",
            }
        user_id = payload.get("userId") or payload.get("user_id")
        if not user_id and not payload.get("username"):
            return {
                "ok": False,
                "error": "validation",
                "message": "disable_user 需要 userId 或 username",
                "source": "gateway",
            }
        return {
            "ok": True,
            "needs_confirm": True,
            "action": "disable_user",
            "impact": [
                {
                    "op": "disable_user",
                    "userId": user_id,
                    "username": payload.get("username"),
                    "nickName": payload.get("nickName") or payload.get("nickname"),
                    "newStatus": _USER_STATUS_DISABLED,
                    "note": "预览未带凭证，详情可能不全；确认执行时须经控制面注入 JWT",
                }
            ],
            "message": "尚未执行停用。请向用户列出影响对象，确认后再调用 write(confirmed=true)",
            "source": "gateway",
        }

    if not token:
        return _missing_token()
    item, err = _resolve_disable_target(payload, token)
    if err:
        return err
    assert item is not None
    uid = item.get("userId")
    if not uid:
        return {
            "ok": False,
            "error": "validation",
            "message": "无法解析 userId，不能停用",
            "impact": [item],
            "source": "gateway",
        }
    result = _http_json(
        "PUT",
        "/api/v1/user/status",
        token=token,
        body={"userId": int(uid), "status": _USER_STATUS_DISABLED},
    )
    return {
        "action": "disable_user",
        "needs_confirm": False,
        "impact": [item],
        **result,
    }


def route_write(
    action: str,
    payload: dict[str, Any] | None = None,
    *,
    confirmed: bool = False,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """写工具路由：create_user / disable_user。"""
    if action == "create_user":
        return create_user(payload, confirmed=confirmed, ctx=ctx)
    if action == "disable_user":
        return disable_user(payload, confirmed=confirmed, ctx=ctx)
    return {
        "ok": False,
        "error": "unsupported_action",
        "message": f"action '{action}' 不支持；可用 create_user / disable_user",
        "source": "gateway",
    }
