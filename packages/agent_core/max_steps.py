"""步数软收口常量（对齐 OpenCode max-steps / isLastStep）。"""

from __future__ import annotations

# 未配置 max_steps / max_turns 时的硬保险，防止空转打爆账单
HARD_MAX_TURNS = 64

# 最后一步注入：禁工具，要求文本总结（语义对齐 OpenCode MAX_STEPS_PROMPT）
# 以 role=user 注入（D5-B），避免连续 assistant 触发部分兼容 API 挑剔
MAX_STEPS_PROMPT = (
    "已达到本轮最大步数，工具已全部禁用，禁止再发起任何工具调用。"
    "请用简洁中文总结：已完成事项、未完成事项、建议的下一步。"
)

# 最后一步仍要调工具时的回灌说明（不 execute）
TOOLS_DISABLED_RESULT = "Tools are disabled after the maximum agent steps"

# 补救轮仍无文本时的兜底（禁止「处理超时」措辞）
MAX_STEPS_FALLBACK = "已达最大步数且未能生成总结，请缩小问题后重试。"
