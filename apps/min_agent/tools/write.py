"""写工具 write：创建/停用用户；默认预览，confirmed=true 才落地。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from agent_core.tools.base import Tool
from min_agent.gateway import route_write


class WriteArgs(BaseModel):
    action: Literal["create_user", "disable_user"] = Field(
        description="create_user=创建用户；disable_user=停用用户"
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "create_user: username, nickName, phone, email, deptId?, roleId?, password?；"
            "disable_user: userId 或 username"
        ),
    )
    confirmed: bool = Field(
        default=False,
        description="false=只预览影响对象；true=用户已确认后才执行写操作",
    )


def _execute(args: WriteArgs, ctx: dict[str, Any]) -> dict[str, Any]:
    return route_write(
        args.action,
        args.payload,
        confirmed=args.confirmed,
        ctx=ctx,
    )


write_tool = Tool(
    name="write",
    description=(
        "管理后台写操作：创建用户或停用用户。"
        "必须先以 confirmed=false 预览 impact，把将影响对象告诉用户；"
        "仅当用户明确确认后再以 confirmed=true 执行。"
        "查列表/登录日志请用 query，不要用 write。"
    ),
    args_schema=WriteArgs,
    execute=_execute,
)
