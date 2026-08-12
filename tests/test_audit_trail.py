"""工具审计轨迹：落库字段与权限拒绝标记（不依赖真实 PG）。"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from pydantic import BaseModel

from agent_core.agents import AgentDef, AgentRegistry
from agent_core.loop import _permission_denied, run_agent
from agent_core.store import Session
from agent_core.tools.base import Tool
from agent_core.tools.registry import ToolRegistry
from tests.test_loop_max_steps import FakeStore, _assistant_msg, _tool_call


class _EchoArgs(BaseModel):
    pass


class AuditTrailTests(unittest.TestCase):
    def test_permission_denied_helper(self) -> None:
        self.assertTrue(
            _permission_denied('{"error":"permission_denied","message":"无权"}')
        )
        self.assertTrue(_permission_denied('{"error":"missing_token"}'))
        self.assertFalse(_permission_denied('{"ok":true}'))
        self.assertFalse(_permission_denied("not-json"))

    def test_execute_records_event(self) -> None:
        store = FakeStore()
        session = Session(
            id="sess-audit",
            agent="t",
            model="fake",
            created_at=datetime.now(timezone.utc),
        )
        agents = AgentRegistry()
        tools = ToolRegistry()

        def _echo(_args: _EchoArgs, _ctx: dict[str, Any]) -> str:
            return json.dumps({"ok": True, "error": "permission_denied"})

        tools.register(
            Tool(name="echo", description="echo", args_schema=_EchoArgs, execute=_echo)
        )
        agents.register(
            AgentDef(name="t", system_prompt="sys", tool_names=["echo"], max_steps=5)
        )

        llm = MagicMock()
        llm.model = "fake"
        llm.chat.side_effect = [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=_assistant_msg(tool_calls=[_tool_call("echo")])
                    )
                ],
                usage=SimpleNamespace(
                    prompt_tokens=10, completion_tokens=2, total_tokens=12
                ),
            ),
            SimpleNamespace(
                choices=[
                    SimpleNamespace(message=_assistant_msg(content="done"))
                ],
                usage=None,
            ),
        ]

        result = run_agent(
            store=store,
            llm=llm,
            tool_registry=tools,
            agent_registry=agents,
            session=session,
            user_input="hi",
            agent_name="t",
        )
        self.assertEqual(result.reply, "done")
        self.assertEqual(len(store.events), 1)
        ev = store.events[0]
        self.assertEqual(ev["tool_name"], "echo")
        self.assertTrue(ev["permission_denied"])
        self.assertEqual(ev["prompt_tokens"], 10)
        self.assertEqual(ev["total_tokens"], 12)
        self.assertGreaterEqual(ev["duration_ms"], 0)
        listed = store.list_tool_events("sess-audit")
        self.assertEqual(len(listed), 1)


if __name__ == "__main__":
    unittest.main()
