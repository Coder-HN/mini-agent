"""Loop 步数软收口单测（不依赖真实 LLM / PostgreSQL）。

用法（仓库根目录）:
  python -m unittest tests.test_loop_max_steps -v
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from agent_core.agents import AgentDef, AgentRegistry
from agent_core.loop import run_agent
from agent_core.max_steps import MAX_STEPS_PROMPT
from agent_core.store import Session
from agent_core.tools.base import Tool
from agent_core.tools.registry import ToolRegistry


class _EchoArgs(BaseModel):
    pass


@dataclass
class FakeStore:
    rows: list[dict[str, str]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)

    def load_history(self, session_id: str) -> list[dict]:
        del session_id
        return [
            {"role": r["role"], "content": r["content"]}
            for r in self.rows
            if r["role"] in ("user", "assistant")
        ]

    def append_message(
        self,
        session_id: str,
        role: str = "",
        content: str = "",
        tool_call_id: str | None = None,
        **kwargs: Any,
    ) -> None:
        del session_id, tool_call_id
        role = kwargs.get("role", role)
        content = kwargs.get("content", content)
        self.rows.append({"role": role, "content": content})

    def append_tool_event(self, session_id: str, **kwargs: Any) -> str:
        event = {"session_id": session_id, **kwargs}
        self.events.append(event)
        return "evt-1"

    def list_tool_events(self, session_id: str) -> list[dict]:
        return [e for e in self.events if e.get("session_id") == session_id]


def _tool_call(name: str = "echo", call_id: str = "call_1") -> Any:
    return SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments="{}"),
    )


def _assistant_msg(*, content: str | None = None, tool_calls: list | None = None) -> Any:
    return SimpleNamespace(content=content, tool_calls=tool_calls)


def _chat_response(msg: Any) -> Any:
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


class LoopMaxStepsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = FakeStore()
        self.session = Session(
            id="sess-test",
            agent="t",
            model="fake-model",
            created_at=datetime.now(timezone.utc),
        )
        self.agents = AgentRegistry()
        self.tools = ToolRegistry()
        self.execute_count = 0

        def _echo(_args: _EchoArgs, _ctx: dict[str, Any]) -> str:
            self.execute_count += 1
            return '{"ok": true}'

        self.tools.register(
            Tool(name="echo", description="echo", args_schema=_EchoArgs, execute=_echo)
        )
        self.agents.register(
            AgentDef(name="t", system_prompt="sys", tool_names=["echo"], max_steps=1)
        )
        self.llm = MagicMock()
        self.llm.model = "fake-model"
        self.chat_calls: list[dict[str, Any]] = []

        def _chat(**kwargs: Any) -> Any:
            self.chat_calls.append(kwargs)
            return self._next_response()

        self.llm.chat.side_effect = _chat
        self._responses: list[Any] = []

    def _next_response(self) -> Any:
        if not self._responses:
            raise AssertionError("LLM 响应队列已空")
        return self._responses.pop(0)

    def test_last_step_disables_tools_and_injects_prompt(self) -> None:
        """max_steps=1：首轮即最后一步，tool_choice=none，messages 含步数约束。"""
        self._responses = [
            _chat_response(_assistant_msg(content="总结：未调用工具。")),
        ]
        result = run_agent(
            store=self.store,  # type: ignore[arg-type]
            llm=self.llm,
            tool_registry=self.tools,
            agent_registry=self.agents,
            session=self.session,
            user_input="你好",
            agent_name="t",
        )
        self.assertEqual(result.reply, "总结：未调用工具。")
        self.assertEqual(len(self.chat_calls), 1)
        call = self.chat_calls[0]
        self.assertEqual(call.get("tool_choice"), "none")
        self.assertTrue(call.get("tools") in (None, []))
        contents = [
            (m.get("role"), m.get("content"))
            for m in call["messages"]
            if isinstance(m, dict)
        ]
        self.assertTrue(
            any(role == "user" and MAX_STEPS_PROMPT in (c or "") for role, c in contents)
        )
        self.assertEqual(self.execute_count, 0)
        self.assertNotIn("处理超时", result.reply)

    def test_last_step_tool_calls_not_executed(self) -> None:
        """最后一步仍 tool_calls：不 execute，补救轮给出文本。"""
        self._responses = [
            _chat_response(
                _assistant_msg(content=None, tool_calls=[_tool_call()])
            ),
            _chat_response(_assistant_msg(content="步数用尽后的总结。")),
        ]
        result = run_agent(
            store=self.store,  # type: ignore[arg-type]
            llm=self.llm,
            tool_registry=self.tools,
            agent_registry=self.agents,
            session=self.session,
            user_input="需要工具",
            agent_name="t",
        )
        self.assertEqual(self.execute_count, 0)
        self.assertEqual(result.reply, "步数用尽后的总结。")
        self.assertEqual(result.tool_names_called, [])
        # 第一轮禁工具后仍造 tool_calls → 回灌禁用说明再要文本
        self.assertEqual(len(self.chat_calls), 2)
        self.assertEqual(self.chat_calls[1].get("tool_choice"), "none")
        self.assertNotIn("处理超时", result.reply)
        self.assertNotIn("处理超时", self.store.rows[-1]["content"])

    def test_hard_max_fallback_has_no_fake_timeout(self) -> None:
        """未配置上限时走 HARD_MAX；触达后 reply 不含处理超时。"""
        self.agents.register(
            AgentDef(name="t", system_prompt="sys", tool_names=["echo"], max_steps=None)
        )
        with patch("agent_core.loop.HARD_MAX_TURNS", 1):
            self._responses = [
                _chat_response(_assistant_msg(content="硬保险收口总结")),
            ]
            result = run_agent(
                store=self.store,  # type: ignore[arg-type]
                llm=self.llm,
                tool_registry=self.tools,
                agent_registry=self.agents,
                session=self.session,
                user_input="测硬保险",
                agent_name="t",
                max_turns=None,
            )
        self.assertEqual(result.reply, "硬保险收口总结")
        self.assertNotIn("处理超时", result.reply)
        self.assertEqual(self.chat_calls[0].get("tool_choice"), "none")

    def test_normal_tool_then_reply(self) -> None:
        """非最后一步：resolve → execute → 终答（回归）。"""
        self.agents.register(
            AgentDef(name="t", system_prompt="sys", tool_names=["echo"], max_steps=5)
        )
        self._responses = [
            _chat_response(
                _assistant_msg(content=None, tool_calls=[_tool_call()])
            ),
            _chat_response(_assistant_msg(content="工具已执行，结果正常。")),
        ]
        result = run_agent(
            store=self.store,  # type: ignore[arg-type]
            llm=self.llm,
            tool_registry=self.tools,
            agent_registry=self.agents,
            session=self.session,
            user_input="请 echo",
            agent_name="t",
        )
        self.assertEqual(self.execute_count, 1)
        self.assertEqual(result.tool_names_called, ["echo"])
        self.assertEqual(result.reply, "工具已执行，结果正常。")
        self.assertEqual(self.chat_calls[0].get("tool_choice"), "auto")
        self.assertTrue(self.chat_calls[0].get("tools"))


if __name__ == "__main__":
    unittest.main()
