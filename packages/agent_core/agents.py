"""Agent 定义与进程内注册表。

Agent 不是循环本体：只声明 name / system prompt / 工具白名单等边界；
真正的 FC while 在 loop.run_agent。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AgentDef:
    """单个 Agent 的静态定义。

    permission / can_spawn_task 等字段为 P1/P2 预留，P0 可留空。
    """

    name: str
    system_prompt: str
    tool_names: list[str]
    permission: list | None = None
    max_steps: int | None = None
    mode: str = "primary"  # primary | subagent（P2）
    can_spawn_task: bool = False  # 子 Agent 默认 False（P2）


class AgentRegistry:
    """按 name 查找 AgentDef；应用启动时 register。"""

    def __init__(self):
        self._agents: dict[str, AgentDef] = {}

    def register(self, agent: AgentDef) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> AgentDef:
        agent = self._agents.get(name)
        if agent is None:
            raise KeyError(f"unknown agent: {name}")
        return agent

    def list_names(self) -> list[str]:
        return list(self._agents.keys())


_default = AgentRegistry()


def get_default_registry() -> AgentRegistry:
    """进程默认注册表，便于 assemble() 与测试共用同一实例。"""
    return _default
