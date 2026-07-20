"""agent_llm：OpenAI 兼容 Chat Completions 薄封装。

仅负责发起一次 create；不编排 FC 循环（循环在 agent_core.loop）。
"""
