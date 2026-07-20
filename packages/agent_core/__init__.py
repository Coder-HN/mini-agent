"""agent_core 包：FC 运行时内核（Store / Loop / Turn）。

负责会话持久化、Agent 定义、工具注册表与主循环；不负责具体业务工具实现
（业务工具在 apps/min_agent）。主入口见 loop.run_agent。
"""
