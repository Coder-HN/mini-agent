"""FastAPI 应用工厂：装配 Store / LLM / Agent 后暴露 /chat。

路由写在 create_app 内，避免 P0 多文件跳转；SSE 中间件留给 P1。
"""

from __future__ import annotations

from importlib.metadata import metadata

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from agent_core.loop import run_agent
from agent_core.store import Store
from agent_llm.client import LLMClient
from min_agent.agent import assemble
from min_agent.config import Settings


class ChatRequest(BaseModel):
    """POST /chat 入参。session_id 缺省则新建会话。"""

    message: str
    session_id: str | None = None
    context: dict | None = None


class ChatResponse(BaseModel):
    """出参。tool_names_called 便于联调验收，前端可忽略。"""

    session_id: str
    reply: str
    tool_names_called: list[str] = Field(default_factory=list)


def _owner_from_context(context: dict | None) -> str:
    if not context:
        return ""
    return str(context.get("owner_user_id") or context.get("user_id") or "").strip()


def create_app(settings: Settings | None = None) -> FastAPI:
    """创建已注入依赖的 FastAPI app；settings 可注入便于测试。"""
    settings = settings or Settings.load()
    agent_registry, tool_registry = assemble()
    store = Store(settings.postgres_dsn)
    llm = LLMClient(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url or None,
    )

    # name/version 来自 pyproject.toml（需已 pip install）
    pkg = metadata("min-agent")
    app = FastAPI(title=pkg["Name"], version=pkg["Version"])
    app.state.settings = settings
    app.state.store = store
    app.state.llm = llm
    app.state.agent_registry = agent_registry
    app.state.tool_registry = tool_registry

    @app.get("/health")
    def health():
        return {"ok": True}

    @app.get("/sessions/{session_id}/trail")
    def session_trail(
        session_id: str,
        viewer_user_id: str = Query(default=""),
        data_scope: str = Query(default=""),
    ):
        """按 session 返回工具审计轨迹；按数据权限过滤可见性。"""
        session = store.get_session(session_id)
        if session is None:
            return {"session_id": session_id, "events": []}
        if not store.can_access_session(
            session,
            viewer_user_id=viewer_user_id,
            data_scope=data_scope,
        ):
            raise HTTPException(
                status_code=403,
                detail="无权查看该会话轨迹（仅本人或数据权限全部）",
            )
        return {"session_id": session_id, "events": store.list_tool_events(session_id)}

    @app.post("/chat", response_model=ChatResponse)
    def chat(body: ChatRequest):
        owner = _owner_from_context(body.context)
        scope = ""
        if body.context:
            scope = str(body.context.get("data_scope") or "").strip()
        if body.session_id:
            existing = store.get_session(body.session_id)
            if existing is not None and existing.owner_user_id:
                if not store.can_access_session(
                    existing,
                    viewer_user_id=owner,
                    data_scope=scope,
                ):
                    raise HTTPException(status_code=403, detail="无权续聊他人会话")
        session = store.get_or_create_session(
            body.session_id,
            agent="min_agent",
            model=settings.openai_model,
            owner_user_id=owner,
        )
        result = run_agent(
            store=store,
            llm=llm,
            tool_registry=tool_registry,
            agent_registry=agent_registry,
            session=session,
            user_input=body.message,
            agent_name="min_agent",
            context=body.context,
            compaction=settings.compaction_config(),
        )
        return ChatResponse(
            session_id=result.session_id,
            reply=result.reply,
            tool_names_called=result.tool_names_called,
        )

    return app
