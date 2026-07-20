"""P2 验收：max_steps=2 软收口 + 落库文案检查（联调脚本，需 .env + Postgres）。

用法（仓库根目录）:
  python tests/accept_max_steps.py
"""

from __future__ import annotations

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


def main() -> None:
    settings = Settings.load()
    if not settings.openai_api_key or not settings.postgres_dsn:
        print("缺少 OPENAI_API_KEY 或 POSTGRES_DSN", file=sys.stderr)
        raise SystemExit(2)

    agents, tools = assemble()
    agent = agents.get("min_agent")
    agent.max_steps = 2  # 验收：压低步数，强制第二轮软收口

    store = Store(settings.postgres_dsn)
    llm = LLMClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url or None,
    )
    session = store.get_or_create_session(
        None, agent="min_agent", model=settings.openai_model
    )
    result = run_agent(
        store=store,
        llm=llm,
        tool_registry=tools,
        agent_registry=agents,
        session=session,
        user_input="睿德志行佣金审核通过了吗？请先查再答。",
        agent_name="min_agent",
        compaction=settings.compaction_config(),
    )
    print(f"session_id: {result.session_id}")
    print(f"tools: {', '.join(result.tool_names_called) or '(none)'}")
    print(f"max_steps: {agent.max_steps}")
    print("---")
    print(result.reply)
    print("---")

    if not result.reply.strip():
        print("FAIL: reply 为空", file=sys.stderr)
        raise SystemExit(1)
    if "处理超时" in result.reply:
        print("FAIL: reply 含假超时文案", file=sys.stderr)
        raise SystemExit(1)

    history = store.load_history(session.id)
    last = next((h for h in reversed(history) if h["role"] == "assistant"), None)
    if not last or "处理超时" in (last.get("content") or ""):
        print("FAIL: PG assistant 行为异常", file=sys.stderr)
        raise SystemExit(1)
    print("OK: soft-close acceptance passed")


if __name__ == "__main__":
    main()
