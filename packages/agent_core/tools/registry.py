"""工具注册表：register / 按 Agent resolve / execute。

关键约束：Loop 每轮必须调用 resolve，不得在循环外写死未过滤的 tools 列表。
P0 权限 = Agent.tool_names 白名单；schema deny / 执行 ask 留到 P1。
"""

from __future__ import annotations

import json
from typing import Any

from agent_core.agents import AgentDef, AgentRegistry
from agent_core.tools.base import Tool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"unknown tool: {name}")
        return tool

    def resolve(
        self,
        agent: AgentDef | str,
        agent_registry: AgentRegistry | None = None,
        permissions: Any = None,
    ) -> list[dict[str, Any]]:
        """返回当前 Agent 可见的 OpenAI tools schema。

        permissions 预留 P1；P0 故意忽略，只按 Agent 白名单裁剪。
        """
        del permissions  # P0: 仅 Agent 白名单
        if isinstance(agent, str):
            if agent_registry is None:
                raise ValueError("agent_registry required when agent is a name")
            agent = agent_registry.get(agent)
        schemas: list[dict[str, Any]] = []
        for name in agent.tool_names:
            schemas.append(self.get(name).openai_schema())
        return schemas

    def execute(
        self,
        name: str,
        args: dict[str, Any] | str,
        ctx: dict[str, Any] | None = None,
        permissions: Any = None,
    ) -> str:
        """按名称执行工具；占位工具也走同一路径，不得因「未实现」跳过注册表。"""
        del permissions
        if isinstance(args, str):
            args = json.loads(args) if args.strip() else {}
        return self.get(name).run(args, ctx)
