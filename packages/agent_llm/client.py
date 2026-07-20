"""OpenAI 兼容 LLM 客户端。

只封装一次 chat.completions.create；tool_choice 默认 auto，由 Loop 控制轮次。
model / base_url 必须由调用方从 .env（OPENAI_MODEL_NAME / OPENAI_API_BASE）传入，
代码内不写死国外厂商默认模型名。
"""

from __future__ import annotations

from typing import Any

from openai import OpenAI


class LLMClient:
    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        if not model or not model.strip():
            raise ValueError("model 不能为空，请配置 OPENAI_MODEL_NAME")
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model.strip()

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        tool_choice: str = "auto",
    ) -> Any:
        """发起单次非流式 completion；流式留给 P1。

        tools 为 None 或 [] 时不向 provider 传 tools（无可执行工具）。
        tool_choice 支持 \"auto\" / \"none\"（最后一步软收口用 none）。
        """
        use_model = (model or self.model).strip()
        if not use_model:
            raise ValueError("model 不能为空，请配置 OPENAI_MODEL_NAME")
        kwargs: dict[str, Any] = {
            "model": use_model,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice
        elif tool_choice == "none":
            # 无 tools 时仍声明 none，避免部分模型擅自造 tool_calls
            kwargs["tool_choice"] = "none"
        return self.client.chat.completions.create(**kwargs)
