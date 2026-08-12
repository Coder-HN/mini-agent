"""上下文压缩单测（不依赖真实 LLM / PostgreSQL）。

用法（仓库根目录）:
  python -m unittest tests.test_compaction -v
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from pydantic import BaseModel

from agent_core.agents import AgentDef, AgentRegistry
from agent_core.compaction import (
    PRUNE_PLACEHOLDER,
    CompactionConfig,
    estimate_tokens,
    hard_truncate,
    maybe_compact,
    prune_tool_results,
)
from agent_core.loop import run_agent
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
        self.events.append({"session_id": session_id, **kwargs})
        return "evt-1"

    def list_tool_events(self, session_id: str) -> list[dict]:
        return [e for e in self.events if e.get("session_id") == session_id]


def _chat_response(content: str, tool_calls: list | None = None) -> Any:
    msg = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


class CompactionUnitTests(unittest.TestCase):
    def test_prune_shortens_old_tool_keeps_id(self) -> None:
        long_body = "x" * 5000
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "q1"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_old",
                        "type": "function",
                        "function": {"name": "echo", "arguments": "{}"},
                    }
                ],
            },
            {
                "role": "tool",
                "tool_call_id": "call_old",
                "content": long_body,
            },
            {"role": "user", "content": "q2"},
            {"role": "assistant", "content": "a2"},
        ]
        pruned = prune_tool_results(messages, keep_recent=2)
        self.assertEqual(pruned[3]["tool_call_id"], "call_old")
        self.assertEqual(pruned[3]["content"], PRUNE_PLACEHOLDER)
        self.assertLess(len(pruned[3]["content"]), len(long_body))
        self.assertEqual(pruned[-2]["content"], "q2")

    def test_estimate_skips_data_url(self) -> None:
        heavy = "data:image/png;base64," + ("A" * 8000)
        plain = "正文" * 4000
        self.assertLess(
            estimate_tokens([{"role": "user", "content": heavy}]),
            estimate_tokens([{"role": "user", "content": plain}]),
        )
        self.assertLess(
            estimate_tokens([{"role": "user", "content": heavy}]),
            100,
        )

    def test_maybe_compact_summarize_keeps_recent(self) -> None:
        keep = 2
        pad = "结论：渠道甲已通过。" + ("详" * 400)
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": pad},
            {"role": "assistant", "content": pad},
            {"role": "user", "content": "近端用户"},
            {"role": "assistant", "content": "近端助手"},
        ]
        usable = estimate_tokens(messages) - 10
        llm = MagicMock()
        llm.model = "fake"
        llm.chat.return_value = _chat_response("实体甲；结论已通过；未决：无")

        out = maybe_compact(
            messages, usable=usable, keep_recent=keep, llm=llm, model="fake"
        )
        self.assertTrue(llm.chat.called)
        kwargs = llm.chat.call_args.kwargs
        self.assertEqual(kwargs.get("tool_choice"), "none")
        self.assertTrue(kwargs.get("tools") is None)
        self.assertEqual(out[0]["role"], "system")
        self.assertIn("[对话摘要]", out[1]["content"])
        self.assertEqual(out[-2]["content"], "近端用户")
        self.assertEqual(out[-1]["content"], "近端助手")

    def test_summarize_failure_hard_truncates(self) -> None:
        pad = "y" * 2000
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": pad},
            {"role": "assistant", "content": pad},
            {"role": "user", "content": "近"},
            {"role": "assistant", "content": "端"},
        ]
        usable = 50
        llm = MagicMock()
        llm.model = "fake"
        llm.chat.side_effect = RuntimeError("boom")

        out = maybe_compact(
            messages, usable=usable, keep_recent=2, llm=llm, model="fake"
        )
        self.assertEqual(out[0]["content"], "sys")
        self.assertEqual(out[-2]["content"], "近")
        self.assertEqual(out[-1]["content"], "端")
        self.assertLessEqual(len(out), 3)

    def test_config_missing_context_skips(self) -> None:
        self.assertIsNone(CompactionConfig(enabled=True, model_context_tokens=None).usable())
        self.assertIsNone(CompactionConfig(enabled=False, model_context_tokens=128000).usable())
        self.assertIsNone(CompactionConfig(enabled=True, model_context_tokens=5000).usable())
        self.assertEqual(
            CompactionConfig(
                enabled=True, model_context_tokens=128000, reserved_tokens=10000
            ).usable(),
            118000,
        )

    def test_hard_truncate_keeps_system_and_recent(self) -> None:
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "1"},
            {"role": "assistant", "content": "2"},
            {"role": "user", "content": "3"},
        ]
        out = hard_truncate(messages, keep_recent=2)
        self.assertEqual([m["content"] for m in out], ["sys", "2", "3"])


class CompactionLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = FakeStore()
        self.session = Session(
            id="sess-compact",
            agent="t",
            model="fake-model",
            created_at=datetime.now(timezone.utc),
        )
        self.agents = AgentRegistry()
        self.tools = ToolRegistry()
        self.tools.register(
            Tool(
                name="echo",
                description="echo",
                args_schema=_EchoArgs,
                execute=lambda _a, _c: '{"ok": true}',
            )
        )
        self.agents.register(
            AgentDef(name="t", system_prompt="sys", tool_names=["echo"], max_steps=3)
        )
        self.llm = MagicMock()
        self.llm.model = "fake-model"

    def test_disabled_compaction_no_summarize(self) -> None:
        pad = "z" * 8000
        self.store.rows = [
            {"role": "user", "content": pad},
            {"role": "assistant", "content": pad},
        ]
        self.llm.chat.return_value = _chat_response("短答")
        result = run_agent(
            store=self.store,
            llm=self.llm,
            tool_registry=self.tools,
            agent_registry=self.agents,
            session=self.session,
            user_input="继续",
            agent_name="t",
            compaction=CompactionConfig(
                enabled=False, model_context_tokens=1000, reserved_tokens=100
            ),
        )
        self.assertEqual(result.reply, "短答")
        self.assertEqual(self.llm.chat.call_count, 1)

    def test_overflow_triggers_compact_then_reply(self) -> None:
        pad = "结论实体乙。" + ("文" * 500)
        self.store.rows = [
            {"role": "user", "content": pad},
            {"role": "assistant", "content": pad},
            {"role": "user", "content": pad},
            {"role": "assistant", "content": pad},
        ]
        history_snapshot = list(self.store.rows)

        def _chat(**kwargs: Any) -> Any:
            msgs = kwargs["messages"]
            # 摘要轮：末条含 SUMMARY 提示
            last = (msgs[-1].get("content") or "") if msgs else ""
            if "整理为一段简短中文摘要" in last:
                return _chat_response("实体乙；结论已记录")
            return _chat_response("业务终答")

        self.llm.chat.side_effect = _chat
        # 很小 usable，强制走 summarize
        cfg = CompactionConfig(
            enabled=True,
            model_context_tokens=200,
            reserved_tokens=100,
            keep_recent_messages=2,
        )
        result = run_agent(
            store=self.store,
            llm=self.llm,
            tool_registry=self.tools,
            agent_registry=self.agents,
            session=self.session,
            user_input="近端问题",
            agent_name="t",
            compaction=cfg,
        )
        self.assertEqual(result.reply, "业务终答")
        self.assertGreaterEqual(self.llm.chat.call_count, 2)
        # 5.2：压缩不改写已加载历史行（仅 append 本轮 user/assistant）
        self.assertEqual(self.store.rows[: len(history_snapshot)], history_snapshot)

    def test_short_chat_unchanged_path(self) -> None:
        """短对话不触发摘要，只一次业务 chat（演示桩路径形态）。"""
        self.llm.chat.return_value = _chat_response("示例门店甲已驳回")
        result = run_agent(
            store=self.store,
            llm=self.llm,
            tool_registry=self.tools,
            agent_registry=self.agents,
            session=self.session,
            user_input="示例门店甲的审批通过了吗？",
            agent_name="t",
            compaction=CompactionConfig(
                enabled=True,
                model_context_tokens=128000,
                reserved_tokens=10000,
            ),
        )
        self.assertEqual(result.reply, "示例门店甲已驳回")
        self.assertEqual(self.llm.chat.call_count, 1)
        self.assertIn("示例门店甲", self.store.rows[-1]["content"])


if __name__ == "__main__":
    unittest.main()
