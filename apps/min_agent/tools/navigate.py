"""占位工具 navigate：语义是跳转 CRM/业务页，P0 execute 不落地。

进 schema 是为了让佣金验收句有「错选」空间；真跳转与前端事件属 P1+。
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agent_core.tools.base import Tool


class NavigateArgs(BaseModel):
    target: str = Field(
        default="",
        description="目标页面名或业务意图，如「佣金审批列表」「店铺详情」",
    )
    path: str = Field(default="", description="可选的前端路由 path")
    hint: str = Field(default="", description="补充说明，帮助定位页面")


def _execute(args: NavigateArgs, ctx: dict[str, Any]) -> str:
    del args, ctx
    return "navigate 尚未实现：暂不支持跳转到 CRM/业务网页。"


navigate_tool = Tool(
    name="navigate",
    description=(
        "按意图帮助用户快速跳转到 CRM 或业务网页路由。"
        "仅在用户明确要求打开/跳转到某个页面时使用。"
        "查数据、问审核结果请用 query，不要用 navigate。"
    ),
    args_schema=NavigateArgs,
    execute=_execute,
)
