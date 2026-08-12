"""拼装 system prompt：Agent 模板 + 可选请求级 context。"""

from __future__ import annotations

from agent_core.agents import AgentDef, AgentRegistry

# 凭证与大材料不得写入 system prompt
_SKIP_IN_PROMPT = frozenset(
    {
        "access_token",
        "token",
        "image_ref",
        "image_refs",
    }
)


def build_system_prompt(
    agent: AgentDef | str,
    registry: AgentRegistry | None = None,
    context: dict | None = None,
) -> str:
    """生成本轮 system 文本。

    context 用于透传请求侧非敏感信息；密钥 / JWT 勿写入 prompt（工具经 ctx 读取）。
    """
    if isinstance(agent, str):
        if registry is None:
            raise ValueError("registry required when agent is a name")
        agent = registry.get(agent)

    parts = [agent.system_prompt.strip()]
    if context:
        extra_lines = [
            f"{k}: {v}"
            for k, v in context.items()
            if v is not None and k not in _SKIP_IN_PROMPT
        ]
        if extra_lines:
            parts.append("当前请求上下文：\n" + "\n".join(extra_lines))
    return "\n\n".join(parts)
