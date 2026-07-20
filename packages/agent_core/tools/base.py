"""单个 Tool 的 schema + 执行封装。

description / args_schema 直接进入发给模型的 OpenAI tools；
execute 返回值统一成字符串，方便回灌 role=tool。
"""

from __future__ import annotations

from typing import Any, Callable, Protocol

from pydantic import BaseModel


class ToolContext(Protocol):
    """执行上下文占位（如 session_id）；P0 用普通 dict 即可。"""

    pass


ExecuteFn = Callable[[BaseModel, dict[str, Any]], str | dict[str, Any]]


class Tool:
    """注册表中的一条工具定义。"""

    def __init__(
        self,
        name: str,
        description: str,
        args_schema: type[BaseModel],
        execute: ExecuteFn,
    ):
        self.name = name
        self.description = description
        self.args_schema = args_schema
        self._execute = execute

    def run(self, args: dict[str, Any], ctx: dict[str, Any] | None = None) -> str:
        """校验参数后执行；dict 结果序列化为 JSON 字符串。"""
        parsed = self.args_schema.model_validate(args or {})
        result = self._execute(parsed, ctx or {})
        if isinstance(result, str):
            return result
        import json

        return json.dumps(result, ensure_ascii=False)

    def openai_schema(self) -> dict[str, Any]:
        """转成 chat.completions 所需的 function tool schema。"""
        schema = self.args_schema.model_json_schema()
        # 去掉 Pydantic 默认 title，避免干扰模型对参数语义的理解
        schema.pop("title", None)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": schema,
            },
        }
