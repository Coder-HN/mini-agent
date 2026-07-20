"""多轮 FC 主循环（对齐 openspec agent-runtime）。

两层状态：
- PostgreSQL：跨请求的 user / 最终 assistant
- 内存 messages：本轮 transcript（含中途 tool_result），主要喂模型

同 session_id 用进程内锁串行，避免并发 drain 交错写历史。
步数上限：OpenCode 式软收口（最后一步禁工具 + 总结指令）。
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Any

from agent_core.agents import AgentRegistry
from agent_core.compaction import CompactionConfig, maybe_compact
from agent_core.context import build_system_prompt
from agent_core.max_steps import (
    HARD_MAX_TURNS,
    MAX_STEPS_FALLBACK,
    MAX_STEPS_PROMPT,
    TOOLS_DISABLED_RESULT,
)
from agent_core.message import history_row_to_message, to_openai_messages
from agent_core.store import Session, Store
from agent_core.tools.registry import ToolRegistry
from agent_llm.client import LLMClient

_session_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(session_id: str) -> threading.Lock:
    with _locks_guard:
        if session_id not in _session_locks:
            _session_locks[session_id] = threading.Lock()
        return _session_locks[session_id]


@dataclass
class RunResult:
    """单次 run_agent 的对外结果；tool 轨迹便于验收「是否误点占位」。"""

    reply: str
    session_id: str
    tool_names_called: list[str] = field(default_factory=list)
    resolved_tool_names: list[str] = field(default_factory=list)


def _assistant_dict(msg: Any) -> dict[str, Any]:
    """把 SDK message 转成可回灌的 dict；保留 tool_calls 供下一轮配对 tool 结果。"""
    data: dict[str, Any] = {
        "role": "assistant",
        "content": msg.content,
    }
    if msg.tool_calls:
        data["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments or "{}",
                },
            }
            for tc in msg.tool_calls
        ]
    return data


def _effective_limit(agent_max_steps: int | None, max_turns: int | None) -> int:
    """agent.max_steps > 调用方 max_turns > HARD_MAX_TURNS。"""
    if agent_max_steps is not None:
        return agent_max_steps
    if max_turns is not None:
        return max_turns
    return HARD_MAX_TURNS


def run_agent(
    store: Store,
    llm: LLMClient,
    tool_registry: ToolRegistry,
    agent_registry: AgentRegistry,
    session: Session,
    user_input: str,
    agent_name: str,
    user_permissions: Any = None,
    max_turns: int | None = None,
    context: dict | None = None,
    compaction: CompactionConfig | None = None,
) -> RunResult:
    """执行一轮用户请求的 FC Loop。

    结束条件：模型无 tool_calls（终答），或触达步数上限后的软收口总结。
    中途 tool_result 只进内存 messages，不强制落库。
    compaction 非空且配置有效时，每轮业务 llm.chat 前可压缩内存 messages。
    """
    agent = agent_registry.get(agent_name)
    limit = _effective_limit(agent.max_steps, max_turns)

    with _lock_for(session.id):
        return _run_locked(
            store=store,
            llm=llm,
            tool_registry=tool_registry,
            agent_registry=agent_registry,
            session=session,
            user_input=user_input,
            agent_name=agent_name,
            user_permissions=user_permissions,
            limit=limit,
            context=context,
            compaction=compaction,
        )


def _execute_tools(
    *,
    msg: Any,
    tool_registry: ToolRegistry,
    user_permissions: Any,
    session_id: str,
    context: dict | None,
    tool_names_called: list[str],
    messages: list[dict[str, Any]],
) -> None:
    for call in msg.tool_calls:
        name = call.function.name
        tool_names_called.append(name)
        try:
            args = json.loads(call.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        try:
            tool_ctx: dict[str, Any] = {"session_id": session_id}
            if context:
                tool_ctx["context"] = context
            result = tool_registry.execute(
                name,
                args,
                ctx=tool_ctx,
                permissions=user_permissions,
            )
        except Exception as exc:
            result = json.dumps({"error": str(exc)}, ensure_ascii=False)
        messages.append(
            {
                "role": "tool",
                "tool_call_id": call.id,
                "content": result
                if isinstance(result, str)
                else json.dumps(result, ensure_ascii=False),
            }
        )


def _force_text_turn(
    *,
    llm: LLMClient,
    messages: list[dict[str, Any]],
    model: str,
) -> str:
    """禁工具后再要一轮纯文本；仍无内容则用非超时兜底。"""
    # D5-B：用 user 注入约束，避免连续 assistant 触发部分兼容 API 挑剔
    messages.append({"role": "user", "content": MAX_STEPS_PROMPT})
    response = llm.chat(
        messages=to_openai_messages(messages),
        tools=None,
        model=model,
        tool_choice="none",
    )
    msg = response.choices[0].message
    messages.append(_assistant_dict(msg))
    if msg.tool_calls:
        for call in msg.tool_calls:
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": TOOLS_DISABLED_RESULT,
                }
            )
        return MAX_STEPS_FALLBACK
    return (msg.content or "").strip() or MAX_STEPS_FALLBACK


def _run_locked(
    store: Store,
    llm: LLMClient,
    tool_registry: ToolRegistry,
    agent_registry: AgentRegistry,
    session: Session,
    user_input: str,
    agent_name: str,
    user_permissions: Any,
    limit: int,
    context: dict | None,
    compaction: CompactionConfig | None,
) -> RunResult:
    history = store.load_history(session.id)
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": build_system_prompt(
                agent_name, registry=agent_registry, context=context
            ),
        },
        *[history_row_to_message(h["role"], h["content"]) for h in history],
        {"role": "user", "content": user_input},
    ]
    store.append_message(session.id, role="user", content=user_input)

    tool_names_called: list[str] = []
    resolved_tool_names: list[str] = []
    model = session.model or llm.model
    usable = compaction.usable() if compaction else None

    step = 1
    while step <= limit:
        # 业务 Turn 前压缩内存视图；摘要调用不计入 step / max_steps
        if usable is not None and compaction is not None:
            messages = maybe_compact(
                messages,
                usable=usable,
                keep_recent=compaction.keep_recent_messages,
                llm=llm,
                model=model,
            )

        is_last = step >= limit

        if is_last:
            tools: list[dict[str, Any]] = []
            tool_choice = "none"
            messages.append({"role": "user", "content": MAX_STEPS_PROMPT})
        else:
            tools = tool_registry.resolve(
                agent=agent_name,
                agent_registry=agent_registry,
                permissions=user_permissions,
            )
            tool_choice = "auto"
            if not resolved_tool_names:
                resolved_tool_names = [t["function"]["name"] for t in tools]

        response = llm.chat(
            messages=to_openai_messages(messages),
            tools=tools or None,
            model=model,
            tool_choice=tool_choice,
        )
        msg = response.choices[0].message
        messages.append(_assistant_dict(msg))

        if not msg.tool_calls:
            reply = msg.content or ""
            store.append_message(session.id, role="assistant", content=reply)
            return RunResult(
                reply=reply,
                session_id=session.id,
                tool_names_called=tool_names_called,
                resolved_tool_names=resolved_tool_names,
            )

        if is_last:
            for call in msg.tool_calls:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": TOOLS_DISABLED_RESULT,
                    }
                )
            reply = _force_text_turn(llm=llm, messages=messages, model=model)
            store.append_message(session.id, role="assistant", content=reply)
            return RunResult(
                reply=reply,
                session_id=session.id,
                tool_names_called=tool_names_called,
                resolved_tool_names=resolved_tool_names,
            )

        _execute_tools(
            msg=msg,
            tool_registry=tool_registry,
            user_permissions=user_permissions,
            session_id=session.id,
            context=context,
            tool_names_called=tool_names_called,
            messages=messages,
        )
        step += 1

    # while 在 is_last 分支应已 return；此处仅作安全网
    store.append_message(session.id, role="assistant", content=MAX_STEPS_FALLBACK)
    return RunResult(
        reply=MAX_STEPS_FALLBACK,
        session_id=session.id,
        tool_names_called=tool_names_called,
        resolved_tool_names=resolved_tool_names,
    )
