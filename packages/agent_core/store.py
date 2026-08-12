"""跨请求会话 Store（PostgreSQL）。

与本轮内存 transcript 分离：续聊落 user / 最终 assistant；
工具审计落独立表 agent_tool_events。连接串来自 POSTGRES_DSN。
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import psycopg
from psycopg.rows import DictRow, dict_row


def session_visible(
    owner_user_id: str,
    *,
    viewer_user_id: str,
    data_scope: str,
) -> bool:
    """数据权限：datascope=1 全部；否则仅本人。无归属旧会话仅全部可看。"""
    scope = str(data_scope or "").strip()
    if scope == "1":
        return True
    viewer = str(viewer_user_id or "").strip()
    owner = str(owner_user_id or "").strip()
    if not viewer or not owner:
        return False
    return viewer == owner


@dataclass
class Session:
    """会话元数据；model 可空；owner_user_id 用于轨迹可见范围。"""

    id: str
    agent: str
    model: str
    created_at: datetime
    owner_user_id: str = ""


class Store:
    """agent_sessions / agent_messages 的读写与建表。"""

    def __init__(self, dsn: str):
        self.dsn = dsn
        self._ensure_schema()

    def _connect(self) -> psycopg.Connection[DictRow]:
        return psycopg.Connection[DictRow].connect(self.dsn, row_factory=dict_row)

    def _ensure_schema(self) -> None:
        """幂等建表。

        本地可能已有旧表缺 model 列，故额外 ADD COLUMN IF NOT EXISTS，
        避免 CREATE TABLE IF NOT EXISTS 在旧结构上静默跳过导致插入失败。
        """
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_sessions (
                    id TEXT PRIMARY KEY,
                    agent TEXT NOT NULL,
                    model TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                """
                ALTER TABLE agent_sessions
                ADD COLUMN IF NOT EXISTS model TEXT NOT NULL DEFAULT ''
                """
            )
            conn.execute(
                """
                ALTER TABLE agent_sessions
                ADD COLUMN IF NOT EXISTS owner_user_id TEXT NOT NULL DEFAULT ''
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_sessions_owner
                ON agent_sessions(owner_user_id)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES agent_sessions(id),
                    role TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    tool_call_id TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_messages_session
                ON agent_messages(session_id, created_at)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_tool_events (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES agent_sessions(id),
                    tool_call_id TEXT,
                    tool_name TEXT NOT NULL,
                    arguments TEXT NOT NULL DEFAULT '{}',
                    result_summary TEXT NOT NULL DEFAULT '',
                    permission_denied BOOLEAN NOT NULL DEFAULT FALSE,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_agent_tool_events_session
                ON agent_tool_events(session_id, created_at)
                """
            )
            conn.commit()

    def create_session(
        self, agent: str, model: str = "", owner_user_id: str = ""
    ) -> Session:
        """新建会话行并返回；id 使用 UUID 字符串便于前后端传递。"""
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        owner = str(owner_user_id or "").strip()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_sessions (id, agent, model, owner_user_id, created_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (session_id, agent, model, owner, now),
            )
            conn.commit()
        return Session(
            id=session_id,
            agent=agent,
            model=model,
            created_at=now,
            owner_user_id=owner,
        )

    def get_session(self, session_id: str) -> Session | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, agent, model, created_at, owner_user_id
                FROM agent_sessions WHERE id = %s
                """,
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return Session(
            id=row["id"],
            agent=row["agent"],
            model=row["model"] or "",
            created_at=row["created_at"],
            owner_user_id=str(row.get("owner_user_id") or ""),
        )

    def get_or_create_session(
        self,
        session_id: str | None,
        agent: str,
        model: str = "",
        owner_user_id: str = "",
    ) -> Session:
        """请求未带 session_id、或 id 不存在时新建；存在则复用并尽量补 model/owner。"""
        owner = str(owner_user_id or "").strip()
        if session_id:
            existing = self.get_session(session_id)
            if existing:
                with self._connect() as conn:
                    if model and not existing.model:
                        conn.execute(
                            "UPDATE agent_sessions SET model = %s WHERE id = %s",
                            (model, session_id),
                        )
                        existing.model = model
                    if owner and not existing.owner_user_id:
                        conn.execute(
                            "UPDATE agent_sessions SET owner_user_id = %s WHERE id = %s",
                            (owner, session_id),
                        )
                        existing.owner_user_id = owner
                    conn.commit()
                return existing
        return self.create_session(agent=agent, model=model, owner_user_id=owner)

    def can_access_session(
        self,
        session: Session | None,
        *,
        viewer_user_id: str,
        data_scope: str,
    ) -> bool:
        if session is None:
            return False
        return session_visible(
            session.owner_user_id,
            viewer_user_id=viewer_user_id,
            data_scope=data_scope,
        )

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_call_id: str | None = None,
    ) -> str:
        """追加一条消息，返回消息 id。"""
        msg_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_messages
                    (id, session_id, role, content, tool_call_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    msg_id,
                    session_id,
                    role,
                    content or "",
                    tool_call_id,
                    datetime.now(timezone.utc),
                ),
            )
            conn.commit()
        return msg_id

    def load_history(self, session_id: str) -> list[dict]:
        """加载续聊历史。

        故意只取 user/assistant：中途 tool 行若未来落库，也不应直接塞回 OpenAI
        messages（缺配对会报错）；本轮 tool 由 loop 内存维护。
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, tool_call_id
                FROM agent_messages
                WHERE session_id = %s
                  AND role IN ('user', 'assistant')
                ORDER BY created_at ASC, id ASC
                """,
                (session_id,),
            ).fetchall()
        return [
            {"role": r["role"], "content": r["content"] or ""}
            for r in rows
        ]

    def append_tool_event(
        self,
        session_id: str,
        *,
        tool_name: str,
        arguments: dict | str,
        result_summary: str,
        permission_denied: bool = False,
        duration_ms: int = 0,
        tool_call_id: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> str:
        """写入一条工具审计事件，返回事件 id。"""
        event_id = str(uuid.uuid4())
        if isinstance(arguments, dict):
            args_text = json.dumps(arguments, ensure_ascii=False)
        else:
            args_text = arguments or "{}"
        summary = result_summary or ""
        if len(summary) > 8192:
            summary = summary[:8192] + "…(truncated)"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_tool_events (
                    id, session_id, tool_call_id, tool_name, arguments,
                    result_summary, permission_denied, duration_ms,
                    prompt_tokens, completion_tokens, total_tokens, created_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s
                )
                """,
                (
                    event_id,
                    session_id,
                    tool_call_id,
                    tool_name,
                    args_text,
                    summary,
                    permission_denied,
                    int(duration_ms),
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    datetime.now(timezone.utc),
                ),
            )
            conn.commit()
        return event_id

    def list_tool_events(self, session_id: str) -> list[dict]:
        """按时间序返回会话工具轨迹（供 trail API）。"""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, session_id, tool_call_id, tool_name, arguments,
                       result_summary, permission_denied, duration_ms,
                       prompt_tokens, completion_tokens, total_tokens, created_at
                FROM agent_tool_events
                WHERE session_id = %s
                ORDER BY created_at ASC, id ASC
                """,
                (session_id,),
            ).fetchall()
        out: list[dict] = []
        for r in rows:
            created = r["created_at"]
            out.append(
                {
                    "id": r["id"],
                    "session_id": r["session_id"],
                    "tool_call_id": r["tool_call_id"],
                    "tool_name": r["tool_name"],
                    "arguments": r["arguments"],
                    "result_summary": r["result_summary"],
                    "permission_denied": bool(r["permission_denied"]),
                    "duration_ms": r["duration_ms"],
                    "prompt_tokens": r["prompt_tokens"],
                    "completion_tokens": r["completion_tokens"],
                    "total_tokens": r["total_tokens"],
                    "created_at": created.isoformat() if created else None,
                }
            )
        return out
