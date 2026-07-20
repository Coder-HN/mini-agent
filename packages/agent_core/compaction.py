"""上下文压缩（P3）：按「窗口 − reserved」触发，prune → summarize → 硬截断。

只改本轮喂模型的内存 messages，不写回 PostgreSQL。
估算为字符启发式，跳过 data-URL / 超长 base64。
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

from agent_core.message import to_openai_messages

logger = logging.getLogger(__name__)

# 摘要专用：禁止对用户口吻的最终答复；保留实体与未决问题
SUMMARY_PROMPT = (
    "请将以上较早的对话整理为一段简短中文摘要，供后续轮次继续处理。"
    "必须保留：关键实体名、已得结论、未决问题与待办。"
    "不要写成对用户的最终答复，不要寒暄，不要调用工具。"
)

PRUNE_PLACEHOLDER = "[tool 输出已裁剪]"

# 只剥离图片 data-URL，避免把普通长文本当 base64 误删
_DATA_URL_RE = re.compile(r"data:image/[^;]+;base64,[A-Za-z0-9+/=\s]+", re.IGNORECASE)


class _ChatLLM(Protocol):
    model: str

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        tool_choice: str = "auto",
    ) -> Any: ...


@dataclass(frozen=True)
class CompactionConfig:
    """压缩开关与水位；model_context_tokens 未配则不自动 compact。"""

    enabled: bool = True
    model_context_tokens: int | None = None
    reserved_tokens: int = 10_000
    keep_recent_messages: int = 12

    def usable(self) -> int | None:
        """可用水位；无效配置返回 None（调用方应跳过压缩）。"""
        if not self.enabled:
            return None
        ctx = self.model_context_tokens
        if ctx is None or ctx <= 0:
            return None
        if ctx <= self.reserved_tokens:
            logger.warning(
                "MODEL_CONTEXT_TOKENS(%s) <= reserved(%s)，跳过自动压缩",
                ctx,
                self.reserved_tokens,
            )
            return None
        return ctx - self.reserved_tokens


def _strip_heavy_payloads(text: str) -> str:
    return _DATA_URL_RE.sub("[image-data-omitted]", text)


def _content_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(content)


def estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """字符启发式 token 估算（约 chars/4）；不计 image data-URL。"""
    parts: list[str] = []
    for msg in messages:
        parts.append(msg.get("role") or "")
        parts.append(_strip_heavy_payloads(_content_text(msg.get("content"))))
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            parts.append(str(fn.get("name") or ""))
            parts.append(_strip_heavy_payloads(str(fn.get("arguments") or "")))
        if msg.get("tool_call_id"):
            parts.append(str(msg["tool_call_id"]))
    return max(0, len("".join(parts)) // 4)


def _keep_start(messages: list[dict[str, Any]], keep_recent: int) -> int:
    """近端保留起点；system（若有）始终在前缀外单独处理。"""
    n = len(messages)
    if keep_recent <= 0:
        return n
    return max(0, n - keep_recent)


def prune_tool_results(
    messages: list[dict[str, Any]],
    *,
    keep_recent: int,
) -> list[dict[str, Any]]:
    """裁较旧 tool 正文为占位，保留 tool_call_id；近端 keep_recent 条不动。"""
    start = _keep_start(messages, keep_recent)
    out: list[dict[str, Any]] = []
    for i, msg in enumerate(messages):
        if i >= start or msg.get("role") != "tool":
            out.append(msg)
            continue
        content = _content_text(msg.get("content"))
        if len(content) <= len(PRUNE_PLACEHOLDER):
            out.append(msg)
            continue
        pruned = dict(msg)
        pruned["content"] = PRUNE_PLACEHOLDER
        out.append(pruned)
    return out


def hard_truncate(
    messages: list[dict[str, Any]],
    *,
    keep_recent: int,
) -> list[dict[str, Any]]:
    """保留首条 system（若有）+ 近端 keep_recent 条。"""
    if not messages:
        return messages
    system: list[dict[str, Any]] = []
    rest = messages
    if messages[0].get("role") == "system":
        system = [messages[0]]
        rest = messages[1:]
    if keep_recent <= 0:
        return system
    return system + rest[-keep_recent:]


def summarize_prefix(
    messages: list[dict[str, Any]],
    *,
    keep_recent: int,
    llm: _ChatLLM,
    model: str | None = None,
) -> list[dict[str, Any]]:
    """把 system 之后、近端之前的前缀摘要成一条，再拼近端。"""
    if not messages:
        return messages
    system: list[dict[str, Any]] = []
    body = messages
    if messages[0].get("role") == "system":
        system = [messages[0]]
        body = messages[1:]
    if len(body) <= keep_recent:
        return messages
    prefix = body[:-keep_recent] if keep_recent > 0 else body
    recent = body[-keep_recent:] if keep_recent > 0 else []
    if not prefix:
        return messages

    summary_msgs = [
        *system,
        *prefix,
        {"role": "user", "content": SUMMARY_PROMPT},
    ]
    response = llm.chat(
        messages=to_openai_messages(summary_msgs),
        tools=None,
        model=model,
        tool_choice="none",
    )
    text = (response.choices[0].message.content or "").strip()
    if not text:
        raise RuntimeError("摘要模型返回空内容")
    summary = {
        "role": "user",
        "content": f"[对话摘要]\n{text}",
    }
    return [*system, summary, *recent]


def maybe_compact(
    messages: list[dict[str, Any]],
    *,
    usable: int,
    keep_recent: int,
    llm: _ChatLLM,
    model: str | None = None,
) -> list[dict[str, Any]]:
    """用量 ≥ usable 时：prune → 仍超则 summarize 一次 → 仍超则硬截断。"""
    if usable <= 0 or estimate_tokens(messages) < usable:
        return messages

    compacted = prune_tool_results(messages, keep_recent=keep_recent)
    if estimate_tokens(compacted) < usable:
        return compacted

    try:
        compacted = summarize_prefix(
            compacted,
            keep_recent=keep_recent,
            llm=llm,
            model=model,
        )
    except Exception:
        logger.exception("上下文摘要失败，回退硬截断")
        return hard_truncate(compacted, keep_recent=keep_recent)

    if estimate_tokens(compacted) >= usable:
        return hard_truncate(compacted, keep_recent=keep_recent)
    return compacted
