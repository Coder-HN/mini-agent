"""话术助手 talk_assistant：HTTP 挂载已上线 ai_crew（方案 A）。

create → upload → 轮询 status → result；失败返回 ok:false JSON，不抛崩请求。
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from pydantic import BaseModel, Field

from agent_core.tools.base import Tool
from min_agent.config import Settings


class TalkAssistantArgs(BaseModel):
    image_ref: str = Field(
        default="",
        description=(
            "微信聊天截图 URL（http(s) 或 data:image/...;base64,...）。"
            "若请求已附带截图可留空，后端会自动使用"
        ),
    )
    note: str = Field(
        default="",
        description="谈判背景、语气等补充说明；映射为 user_context_note",
    )
    merchant_shop_label: str = Field(
        default="",
        description="对方店铺/微信联系人备注；可空",
    )


def _fail(
    error: str,
    message: str,
    *,
    crew_session_id: str = "",
    status: str = "",
    detail: str = "",
) -> str:
    payload: dict[str, Any] = {
        "ok": False,
        "error": error,
        "message": message,
        "source": "ai_crew",
    }
    if crew_session_id:
        payload["crew_session_id"] = crew_session_id
    if status:
        payload["status"] = status
    if detail:
        payload["detail"] = detail[:500]
    return json.dumps(payload, ensure_ascii=False)


def _ok(crew_session_id: str, result: dict[str, Any], shop_label: str = "") -> str:
    reply = result.get("reply") or {}
    if not isinstance(reply, dict):
        reply = {}
    payload = {
        "ok": True,
        "crew_session_id": crew_session_id,
        "primary_reply": reply.get("primary_reply") or "",
        "personalized_reply": reply.get("personalized_reply") or "",
        "alternative_replies": reply.get("alternative_replies") or [],
        "negotiation_advice": reply.get("negotiation_advice") or "",
        "shop_label": shop_label,
        "source": "ai_crew",
    }
    return json.dumps(payload, ensure_ascii=False)


def _http_json(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: float,
) -> tuple[int, dict[str, Any] | list[Any] | str]:
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        code = getattr(resp, "status", None) or resp.getcode()
        if not raw.strip():
            return int(code), {}
        try:
            return int(code), json.loads(raw)
        except json.JSONDecodeError:
            return int(code), raw


def _request(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: float,
) -> tuple[str | None, dict[str, Any]]:
    """成功返回 (None, dict)；失败返回 (error_json_str, {})."""
    try:
        code, parsed = _http_json(method, url, body=body, timeout=timeout)
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            detail = str(exc)
        return (
            _fail(
                "http",
                f"话术服务返回 HTTP {exc.code}",
                detail=detail,
            ),
            {},
        )
    except urllib.error.URLError as exc:
        return (
            _fail(
                "unreachable",
                "话术服务暂时不可用，请稍后重试",
                detail=str(exc.reason if hasattr(exc, "reason") else exc),
            ),
            {},
        )
    except TimeoutError:
        return (
            _fail("timeout", "话术服务请求超时，请稍后重试"),
            {},
        )
    except OSError as exc:
        return (
            _fail(
                "unreachable",
                "话术服务暂时不可用，请稍后重试",
                detail=str(exc),
            ),
            {},
        )
    except Exception as exc:
        return (
            _fail("network", "话术服务调用失败，请稍后重试", detail=str(exc)),
            {},
        )

    if code >= 400:
        detail = parsed if isinstance(parsed, str) else json.dumps(parsed, ensure_ascii=False)
        return (
            _fail("http", f"话术服务返回 HTTP {code}", detail=str(detail)[:300]),
            {},
        )
    if not isinstance(parsed, dict):
        return _fail("http", "话术服务响应格式异常", detail=str(parsed)[:200]), {}
    return None, parsed


def run_talk_pipeline(
    *,
    image_ref: str,
    note: str = "",
    merchant_shop_label: str = "",
    ctx: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> str:
    """供 tool 与单测调用；永不抛出到请求层。"""
    settings = settings or Settings.load()
    image_ref = (image_ref or "").strip()
    note = (note or "").strip()
    merchant_shop_label = (merchant_shop_label or "").strip()
    if not image_ref:
        return _fail(
            "validation",
            "请提供微信聊天截图 URL（image_ref）后再分析话术",
        )

    base = (settings.ai_crew_base_url or "").rstrip("/")
    if not base:
        return _fail("validation", "未配置 AI_CREW_BASE_URL，无法调用话术服务")

    timeout = float(settings.ai_crew_timeout_sec)
    poll_interval = float(settings.ai_crew_poll_interval_sec)
    poll_max = float(settings.ai_crew_poll_max_sec)

    ctx = ctx or {}
    req_ctx = ctx.get("context") if isinstance(ctx.get("context"), dict) else {}
    if not isinstance(req_ctx, dict):
        req_ctx = {}
    session_id = str(ctx.get("session_id") or "")

    create_body = {
        "user_id": str(req_ctx.get("user_id") or ""),
        "operator_uid": str(req_ctx.get("operator_uid") or ""),
        "operator_username": str(req_ctx.get("operator_username") or ""),
        "operator_nickname": str(req_ctx.get("operator_nickname") or ""),
        "client_conversation_id": session_id[:64],
    }
    err, created = _request(
        "POST", f"{base}/session/create", body=create_body, timeout=timeout
    )
    if err:
        return err
    crew_session_id = str(created.get("session_id") or "")
    if not crew_session_id:
        return _fail("http", "话术服务未返回 session_id")

    upload_body: dict[str, Any] = {
        "screenshot_url": image_ref,
        "user_context_note": note[:4000],
        "merchant_shop_label": merchant_shop_label[:200],
        "client_conversation_id": session_id[:64],
    }
    err, _uploaded = _request(
        "POST",
        f"{base}/session/{crew_session_id}/upload",
        body=upload_body,
        timeout=timeout,
    )
    if err:
        # 补上已创建的 session，便于去原页续看
        try:
            data = json.loads(err)
            data["crew_session_id"] = crew_session_id
            return json.dumps(data, ensure_ascii=False)
        except json.JSONDecodeError:
            return err

    deadline = time.monotonic() + poll_max
    last_status = "processing"
    while time.monotonic() < deadline:
        err, status_body = _request(
            "GET",
            f"{base}/session/{crew_session_id}/status",
            timeout=timeout,
        )
        if err:
            try:
                data = json.loads(err)
                data["crew_session_id"] = crew_session_id
                return json.dumps(data, ensure_ascii=False)
            except json.JSONDecodeError:
                return err
        last_status = str(status_body.get("status") or "")
        is_terminal = bool(status_body.get("is_terminal"))
        if last_status == "reply_done" or is_terminal:
            break
        time.sleep(poll_interval)
    else:
        return _fail(
            "timeout",
            "话术分析超时，请稍后在话术页查看或重试",
            crew_session_id=crew_session_id,
            status=last_status,
        )

    err, result = _request(
        "GET",
        f"{base}/session/{crew_session_id}/result",
        timeout=timeout,
    )
    if err:
        try:
            data = json.loads(err)
            data["crew_session_id"] = crew_session_id
            data["status"] = last_status
            return json.dumps(data, ensure_ascii=False)
        except json.JSONDecodeError:
            return err

    if last_status != "reply_done" or result.get("status") not in (None, "reply_done"):
        # terminal failure payload from ai_crew
        msg = (
            str(result.get("failure_message") or result.get("message") or "")
            or "话术分析未完成"
        )
        return _fail(
            "terminal",
            msg,
            crew_session_id=crew_session_id,
            status=str(result.get("status") or last_status),
            detail=json.dumps(result, ensure_ascii=False)[:400],
        )

    shop = merchant_shop_label
    return _ok(crew_session_id, result, shop_label=shop)


def _execute(args: TalkAssistantArgs, ctx: dict[str, Any]) -> str:
    req_ctx = ctx.get("context") if isinstance(ctx.get("context"), dict) else {}
    image_ref = (args.image_ref or "").strip()
    if not image_ref and isinstance(req_ctx, dict):
        image_ref = str(req_ctx.get("image_ref") or "").strip()
    try:
        return run_talk_pipeline(
            image_ref=image_ref,
            note=args.note,
            merchant_shop_label=args.merchant_shop_label,
            ctx=ctx,
        )
    except Exception as exc:
        # 最后兜底：绝不把异常抛出 execute
        return _fail(
            "network",
            "话术服务调用失败，请稍后重试",
            detail=str(exc),
        )


talk_assistant_tool = Tool(
    name="talk_assistant",
    description=(
        "话术分析助手：根据微信聊天截图生成对商家的推荐回复。"
        "请求已附带截图时可直接调用（image_ref 可留空）；"
        "仅话术/回复建议场景使用；查询佣金或审批状态请用 query。"
    ),
    args_schema=TalkAssistantArgs,
    execute=_execute,
)
