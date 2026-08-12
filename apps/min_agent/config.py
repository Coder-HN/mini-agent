"""环境配置：LLM / Postgres / go-admin 上游。"""

from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from agent_core.compaction import CompactionConfig


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "openai_api_key"),
    )
    openai_api_base: str = Field(
        default="",
        validation_alias=AliasChoices(
            "OPENAI_API_BASE", "OPENAI_BASE_URL", "openai_api_base"
        ),
    )
    openai_model_name: str = Field(
        default="",
        validation_alias=AliasChoices(
            "OPENAI_MODEL_NAME", "OPENAI_MODEL", "openai_model_name"
        ),
    )
    go_gateway_url: str = Field(
        default="http://127.0.0.1:8000",
        validation_alias=AliasChoices("GO_GATEWAY_URL", "go_gateway_url"),
    )
    postgres_dsn: str = Field(
        default="",
        validation_alias=AliasChoices("POSTGRES_DSN", "postgres_dsn"),
    )
    # 上下文压缩：触发为 用量 ≥ MODEL_CONTEXT_TOKENS − CONTEXT_RESERVED_TOKENS
    model_context_tokens: int | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "MODEL_CONTEXT_TOKENS", "model_context_tokens"
        ),
    )
    context_reserved_tokens: int = Field(
        default=10_000,
        validation_alias=AliasChoices(
            "CONTEXT_RESERVED_TOKENS", "context_reserved_tokens"
        ),
    )
    context_keep_recent_messages: int = Field(
        default=12,
        validation_alias=AliasChoices(
            "CONTEXT_KEEP_RECENT_MESSAGES", "context_keep_recent_messages"
        ),
    )
    context_compact_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "CONTEXT_COMPACT_ENABLED", "context_compact_enabled"
        ),
    )
    host: str = "127.0.0.1"
    port: int = 8001

    @property
    def openai_base_url(self) -> str:
        return self.openai_api_base

    @property
    def openai_model(self) -> str:
        return self.openai_model_name

    def compaction_config(self) -> CompactionConfig:
        """供 run_agent 使用的压缩配置；未配 MODEL_CONTEXT_TOKENS 时不触发。"""
        return CompactionConfig(
            enabled=self.context_compact_enabled,
            model_context_tokens=self.model_context_tokens,
            reserved_tokens=self.context_reserved_tokens,
            keep_recent_messages=self.context_keep_recent_messages,
        )

    @classmethod
    def load(cls) -> "Settings":
        """从环境变量与 .env 加载；勿在日志中打印 api_key。"""
        return cls()
