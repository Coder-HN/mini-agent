"""HTTP 服务入口：uvicorn 托管 agent_server.create_app。"""

from __future__ import annotations

import uvicorn

from agent_server.app import create_app
from min_agent.config import Settings


def main() -> None:
    settings = Settings.load()
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
