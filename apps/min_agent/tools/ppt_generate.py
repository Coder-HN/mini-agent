"""占位工具 ppt_generate：按主题写 PPT，P0 不生成真实产物（真 Workflow 属 P2）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agent_core.tools.base import Tool


class PptGenerateArgs(BaseModel):
    topic: str = Field(description="PPT 主题或标题")
    outline: str = Field(default="", description="可选大纲或要点")


def _execute(args: PptGenerateArgs, ctx: dict[str, Any]) -> str:
    del args, ctx
    return "ppt_generate 尚未实现：暂不支持撰写或生成 PPT。"


ppt_generate_tool = Tool(
    name="ppt_generate",
    description=(
        "PPT 助手：按主题撰写或生成演示文稿。"
        "仅在用户明确要求做 PPT / 幻灯片时使用。"
        "查询 CRM 数据请用 query。"
    ),
    args_schema=PptGenerateArgs,
    execute=_execute,
)
