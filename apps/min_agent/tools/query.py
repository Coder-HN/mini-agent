"""门面工具 query：按 data_type 查 CRM 数据，意图由模型 FC 选择。

禁止为每个后端接口各发明一个 tool；路由在 gateway.route_query。
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from agent_core.tools.base import Tool
from min_agent.gateway import route_query


class QueryArgs(BaseModel):
    data_type: Literal["commission", "shop", "baokuan", "dataoke"] = Field(
        description="业务数据类型；查佣金/审批用 commission"
    )
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="过滤条件，如 store_name / keyword / status",
    )


def _execute(args: QueryArgs, ctx: dict[str, Any]) -> dict[str, Any]:
    del ctx  # 身份透传留给真 Go；桩路径不需要
    return route_query(args.data_type, args.filters)


query_tool = Tool(
    name="query",
    description=(
        "查询 CRM 业务数据（佣金审批、店铺、爆款、大淘客等）。"
        "当用户询问审核状态、佣金是否通过、店铺相关业务数据时使用本工具。"
        "不要用于页面跳转、话术回复或 PPT 生成。"
    ),
    args_schema=QueryArgs,
    execute=_execute,
)
