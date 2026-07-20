"""业务数据网关：P0 佣金走本地桩，不发 HTTP。

真接 Go 时替换 search_commission 实现；路径与身份头（X-CRM-*）见下方注释。
Python 不直连业务 MySQL。
"""

from __future__ import annotations

from typing import Any


# 真 Go 路径（P0 仅注释预留，桩路径不请求）：
# GET/POST {GO_GATEWAY_URL}/v1/min-agent/commission/search/agent
# Headers（延后到真接 Go）：X-CRM-* 员工/租户身份

COMMISSION_STUB: list[dict[str, Any]] = [
    {
        "store_name": "睿德志行",
        "channel": "京东",
        "plan": "日常佣金方案A",
        "status": "已驳回",
        "reason": "佣金比例超出渠道上限",
        "applied_at": "2026-07-01",
    },
    {
        "store_name": "睿德志行",
        "channel": "淘宝",
        "plan": "大促佣金方案B",
        "status": "已驳回",
        "reason": "材料不齐，缺少活动截图",
        "applied_at": "2026-07-08",
    },
]


def search_commission(filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """按店铺等条件过滤本地桩；后端就绪后改为调 Go。"""
    filters = filters or {}
    store_name = (
        filters.get("store_name")
        or filters.get("keyword")
        or filters.get("shop_name")
        or ""
    )
    rows = COMMISSION_STUB
    if store_name:
        rows = [r for r in rows if store_name in r["store_name"]]
    status = filters.get("status")
    if status:
        rows = [r for r in rows if status in r["status"]]
    return {
        "data_type": "commission",
        "filters": filters,
        "count": len(rows),
        "items": rows,
        "source": "local_stub",
    }


def route_query(data_type: str, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """门面路由：禁止为每个后端接口各发明一个 tool，统一经 data_type 分发。"""
    if data_type == "commission":
        return search_commission(filters)
    return {
        "data_type": data_type,
        "filters": filters or {},
        "count": 0,
        "items": [],
        "error": f"data_type '{data_type}' 尚未接入",
        "source": "local_stub",
    }
