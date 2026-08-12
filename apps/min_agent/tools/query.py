"""门面工具 query：按 data_type 查 go-admin 只读数据，意图由模型 FC 选择。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from agent_core.tools.base import Tool
from min_agent.gateway import route_query


class QueryArgs(BaseModel):
    data_type: Literal["users", "login_logs", "commission"] = Field(
        description="users=用户列表；login_logs=登录日志；commission 已下线勿用"
    )
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="过滤条件，如 username / status / pageIndex / pageSize",
    )


def _execute(args: QueryArgs, ctx: dict[str, Any]) -> dict[str, Any]:
    return route_query(args.data_type, args.filters, ctx)


query_tool = Tool(
    name="query",
    description=(
        "查询管理后台只读数据：用户列表（users）、登录日志（login_logs）。"
        "当用户问本部门有哪些人、用户列表、登录失败记录等时使用。"
        "不要用于改账号、跳转页面或 PPT 生成。"
    ),
    args_schema=QueryArgs,
    execute=_execute,
)
