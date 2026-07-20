"""跨请求会话 Store（PostgreSQL）。

与本轮内存 transcript 分离：这里只持久化续聊需要的 user / 最终 assistant。
中途 tool 轨迹 P0 可不落库。连接串来自 POSTGRES_DSN。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import psycopg
from psycopg.rows import DictRow, dict_row


@dataclass
class Session:
    """会话元数据；model 可空，首次跑时由调用方补写。"""

    id: str
    agent: str
    model: str
    created_at: datetime


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
            conn.commit()

    def create_session(self, agent: str, model: str = "") -> Session:
        """新建会话行并返回；id 使用 UUID 字符串便于前后端传递。"""
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_sessions (id, agent, model, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (session_id, agent, model, now),
            )
            conn.commit()
        return Session(id=session_id, agent=agent, model=model, created_at=now)

    def get_session(self, session_id: str) -> Session | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, agent, model, created_at FROM agent_sessions WHERE id = %s",
                (session_id,),
            ).fetchone()
        if not row:
            return None
        return Session(
            id=row["id"],
            agent=row["agent"],
            model=row["model"] or "",
            created_at=row["created_at"],
        )

    def get_or_create_session(
        self, session_id: str | None, agent: str, model: str = ""
    ) -> Session:
        """请求未带 session_id、或 id 不存在时新建；存在则复用并尽量补 model。"""
        if session_id:
            existing = self.get_session(session_id)
            if existing:
                if model and not existing.model:
                    with self._connect() as conn:
                        conn.execute(
                            "UPDATE agent_sessions SET model = %s WHERE id = %s",
                            (model, session_id),
                        )
                        conn.commit()
                    existing.model = model
                return existing
        return self.create_session(agent=agent, model=model)

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
