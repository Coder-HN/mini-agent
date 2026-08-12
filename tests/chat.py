"""向 min_agent Agent 发一条用户消息，打印回复（联调脚本，需 .env + Postgres）。

用法（仓库根目录）:
  python tests/chat.py 示例门店甲的审批通过了吗？
  python tests/chat.py --session-id <id> 刚才那两笔是哪个渠道？
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "packages", ROOT / "apps"):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

from agent_core.loop import run_agent
from agent_core.store import Store
from agent_llm.client import LLMClient
from min_agent.agent import assemble
from min_agent.config import Settings


def ask(message: str, session_id: str | None = None) -> None:
    settings = Settings.load()
    if not settings.openai_api_key:
        print("缺少 OPENAI_API_KEY，请检查 .env", file=sys.stderr)
        raise SystemExit(2)
    if not settings.postgres_dsn:
        print("缺少 POSTGRES_DSN，请检查 .env", file=sys.stderr)
        raise SystemExit(2)

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
    print(f"tools: {', '.join(result.tool_names_called) or '(none)'}")
    print("---")
    print(result.reply)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="向 min_agent 发消息并打印回答")
    parser.add_argument("message", nargs="+", help="用户消息")
    parser.add_argument("--session-id", default=None, help="续聊时传入上次 session_id")
    args = parser.parse_args(argv)
    ask(" ".join(args.message), args.session_id)


if __name__ == "__main__":
    main()
