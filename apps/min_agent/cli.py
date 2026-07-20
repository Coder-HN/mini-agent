"""min_agent 命令行入口：单次提问并打印回复，附带工具轨迹便于验收。"""

from __future__ import annotations

import argparse
import sys

from agent_core.loop import run_agent
from agent_core.store import Store
from agent_llm.client import LLMClient
from min_agent.agent import assemble
from min_agent.config import Settings

PLACEHOLDERS = {"navigate", "talk_assistant", "ppt_generate"}


def run_once(message: str, session_id: str | None = None) -> int:
    """跑一轮对话；佣金场景若点了占位或未调 query 会打 WARNING（仍返回 0）。"""
    settings = Settings.load()
    if not settings.openai_api_key:
        print("缺少 OPENAI_API_KEY，请配置 .env", file=sys.stderr)
        return 2

    agent_registry, tool_registry = assemble()
    store = Store(settings.postgres_dsn)
    llm = LLMClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url or None,
    )
    session = store.get_or_create_session(
        session_id,
        agent="min_agent",
        model=settings.openai_model,
    )
    result = run_agent(
        store=store,
        llm=llm,
        tool_registry=tool_registry,
        agent_registry=agent_registry,
        session=session,
        user_input=message,
        agent_name="min_agent",
        compaction=settings.compaction_config(),
    )

    print(f"session_id: {result.session_id}")
    print(f"resolved_tools: {', '.join(result.resolved_tool_names)}")
    print(f"tools_called: {', '.join(result.tool_names_called) or '(none)'}")
    bad = [n for n in result.tool_names_called if n in PLACEHOLDERS]
    if bad:
        print(f"WARNING: 占位工具被调用: {', '.join(bad)}", file=sys.stderr)
    if "query" not in result.tool_names_called:
        print("WARNING: 未调用 query", file=sys.stderr)
    print("---")
    print(result.reply)
    return 0


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="min_agent CLI")
    parser.add_argument("message", nargs="?", help="用户消息")
    parser.add_argument("--session-id", default=None)
    args = parser.parse_args(argv)
    if not args.message:
        parser.error("请提供用户消息，例如：min-agent \"睿德志行佣金审核通过了吗？\"")
    raise SystemExit(run_once(args.message, args.session_id))


if __name__ == "__main__":
    main()
