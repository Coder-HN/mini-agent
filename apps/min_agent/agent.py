"""装配 min_agent：system prompt + query / write / navigate / ppt。

查数据走 query；写账号走 write（先预览再确认）；写操作属总体规划 M2。
"""

from __future__ import annotations

from agent_core.agents import AgentDef, AgentRegistry, get_default_registry
from agent_core.tools.registry import ToolRegistry
from min_agent.tools.navigate import navigate_tool
from min_agent.tools.ppt_generate import ppt_generate_tool
from min_agent.tools.query import query_tool
from min_agent.tools.write import write_tool

SYSTEM_PROMPT = """你是 min-agent 前台助手，面向管理后台 ChatOps 场景。

对用户与业务数据：可以查询与解释；写操作必须先预览再确认，不要声称已改数据除非 write 已成功执行。

工具分工（必须遵守）：
- query：查管理后台数据。问「本部门有哪些人 / 用户列表」用 data_type=users；问登录记录/登录失败用 data_type=login_logs。
- write：创建用户（action=create_user）或停用用户（action=disable_user）。
  第一步务必 confirmed=false，根据返回的 impact 用中文列出将影响对象并请用户确认；
  仅当用户明确说确认/同意后再 confirmed=true 执行。禁止跳过预览直接写。
- navigate：跳转到管理后台页面。仅当用户要打开某个页面时用。
- ppt_generate：撰写/生成 PPT。仅做演示文稿时用。

一次请求选最相关的工具；查数据不要点 write / navigate / ppt_generate。
若工具返回权限拒绝或缺少凭证，用中文如实说明，不要编造结果。
回答用简洁中文。"""

TOOL_NAMES = ["query", "write", "navigate", "ppt_generate"]


def build_tool_registry() -> ToolRegistry:
    """注册本应用全部工具实例。"""
    registry = ToolRegistry()
    for tool in (query_tool, write_tool, navigate_tool, ppt_generate_tool):
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
            max_steps=20,
        )
    )
    return registry


def assemble() -> tuple[AgentRegistry, ToolRegistry]:
    """CLI / HTTP / test 共用的一站式装配。"""
    return build_agent_registry(), build_tool_registry()
