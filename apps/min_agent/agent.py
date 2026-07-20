"""装配 min_agent：system prompt + query / navigate / talk_assistant / ppt。

查数据必须走 query；talk_assistant 经 HTTP 挂 ai_crew（方案 A）。
"""

from __future__ import annotations

from agent_core.agents import AgentDef, AgentRegistry, get_default_registry
from agent_core.tools.registry import ToolRegistry
from min_agent.tools.navigate import navigate_tool
from min_agent.tools.ppt_generate import ppt_generate_tool
from min_agent.tools.query import query_tool
from min_agent.tools.talk_assistant import talk_assistant_tool

# 审批只读 + 工具分工写进 prompt，减少误点 navigate/话术/PPT
SYSTEM_PROMPT = """你是 min-agent 前台助手，面向电商/销售 CRM 场景。

对审批与佣金：只读——可以查询与解释，不要声称已替用户审批或改状态。

工具分工（必须遵守）：
- query：查 CRM 业务数据（佣金审核、店铺等）。用户问「审过了吗」「佣金状态」时用它。
- navigate：跳转到 CRM/业务网页。仅当用户要打开某个页面时用。
- talk_assistant：分析微信聊天截图，生成对商家的推荐回复。用户要话术/分析截图时用；若请求上下文标明已附带截图，必须直接调用本工具（image_ref 可留空），不要向用户索要截图链接。若工具返回 ok=false，用中文说明真实原因（如话术服务不可用），不要编造「没收到截图」或编造话术。
- ppt_generate：撰写/生成 PPT。仅做演示文稿时用。

一次请求选最相关的工具；查数据不要点 navigate / talk_assistant / ppt_generate。
回答用简洁中文。"""

TOOL_NAMES = ["query", "navigate", "talk_assistant", "ppt_generate"]


def build_tool_registry() -> ToolRegistry:
    """注册本应用全部工具实例。"""
    registry = ToolRegistry()
    for tool in (query_tool, navigate_tool, talk_assistant_tool, ppt_generate_tool):
        registry.register(tool)
    return registry


def build_agent_registry() -> AgentRegistry:
    """注册默认前台 Agent。"""
    registry = get_default_registry()
    registry.register(
        AgentDef(
            name="min_agent",
            system_prompt=SYSTEM_PROMPT,
            tool_names=list(TOOL_NAMES),
            max_steps=20,  # 产品默认步数；触达后 OpenCode 式软收口
        )
    )
    return registry


def assemble() -> tuple[AgentRegistry, ToolRegistry]:
    """CLI / HTTP / test 共用的一站式装配。"""
    return build_agent_registry(), build_tool_registry()
