"""消息形态与 OpenAI chat messages 互转。

Store 落库的是简化行；Loop 内存里是完整 transcript（含 tool_calls / tool）。
"""

from __future__ import annotations

from typing import Any


def to_openai_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """规范化内存 transcript，保证 tool 行带 tool_call_id、assistant 可带 tool_calls。"""
    out: list[dict[str, Any]] = []
    for m in messages:
        role = m["role"]
        item: dict[str, Any] = {"role": role}
        if role == "tool":
            item["tool_call_id"] = m["tool_call_id"]
            item["content"] = m.get("content") or ""
        elif role == "assistant":
            item["content"] = m.get("content")
            if m.get("tool_calls"):
                item["tool_calls"] = m["tool_calls"]
        else:
            item["content"] = m.get("content") or ""
        out.append(item)
    return out


def history_row_to_message(role: str, content: str) -> dict[str, Any]:
    """把 Store 历史行转成 loop 可用的简单 message。"""
    return {"role": role, "content": content or ""}
