"""拼装 system prompt：Agent 模板 + 可选请求级 context。"""

from __future__ import annotations

from agent_core.agents import AgentDef, AgentRegistry


def build_system_prompt(
    agent: AgentDef | str,
    registry: AgentRegistry | None = None,
    context: dict | None = None,
) -> str:
    """生成本轮 system 文本。

    context 用于透传租户/员工等请求侧信息（P0 可选）；不要把密钥写进 prompt。
    """
    if isinstance(agent, str):
        if registry is None:
            raise ValueError("registry required when agent is a name")
        agent = registry.get(agent)

    parts = [agent.system_prompt.strip()]
    if context:
        # 大图/材料字段只给 tool 用，勿塞进 system（避免 token 爆炸）
        _skip_in_prompt = frozenset({"image_ref", "image_refs"})
        extra_lines: list[str] = []
        # 不传图内容，但必须告知模型「已有图」，否则会误以为没截图而不调 talk_assistant
        has_image = bool(str(context.get("image_ref") or "").strip())
        refs = context.get("image_refs")
        if isinstance(refs, (list, tuple)) and any(str(x or "").strip() for x in refs):
            has_image = True
        if has_image:
            extra_lines.append(
                "has_attached_screenshot: true"
                "（本请求已附带微信聊天截图；分析话术时请直接调用 talk_assistant，"
                "image_ref 可留空，后端会使用已附带截图。不要向用户索要截图链接。）"
            )
        extra_lines.extend(
            f"{k}: {v}"
            for k, v in context.items()
            if v is not None and k not in _skip_in_prompt
        )
        if extra_lines:
            parts.append("当前请求上下文：\n" + "\n".join(extra_lines))
    return "\n\n".join(parts)
