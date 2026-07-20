"""agent_server：HTTP 入口（P0 为 POST /chat）。

装配依赖后委托 agent_core.loop；流式 SSE 留到 P1。
"""
