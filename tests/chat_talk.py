"""经 min_agent HTTP 测话术：本地截图 → POST /chat → talk_assistant → ai_crew。

联调脚本。需 min_agent :8001、ai_crew :8000 已启动。

用法（仓库根目录）:
  python tests/chat_talk.py --image tests/招商反馈pic.png 请分析这张微信聊天截图，给出对商家的推荐回复
  python tests/chat_talk.py --session-id <id> --image tests/招商反馈pic.png 再简短一点
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE = ROOT / "tests" / "招商反馈pic.png"
DEFAULT_BASE = "http://127.0.0.1:8001"


def image_to_data_url(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"图片不存在: {path}")
    mime, _ = mimetypes.guess_type(path.name)
    if not mime or not mime.startswith("image/"):
        mime = "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="话术 HTTP 测试：POST /chat")
    parser.add_argument("message", nargs="+", help="用户消息")
    parser.add_argument("--image", "-i", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--note", default="", help="补充说明（拼进 message）")
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--base-url", default=DEFAULT_BASE, help="min_agent 根地址")
    args = parser.parse_args(argv)

    image = args.image.resolve()
    message = " ".join(args.message).strip()
    if args.note.strip():
        message = f"{message}\n\n补充说明：{args.note.strip()}"

    payload: dict = {
        "message": message,
        "context": {"image_ref": image_to_data_url(image)},
    }
    if args.session_id:
        payload["session_id"] = args.session_id

    url = f"{args.base_url.rstrip('/')}/chat"
    print(f"POST {url}")
    print(f"image: {image} ({image.stat().st_size} bytes)")
    print("---")

    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:500]}", file=sys.stderr)
        raise SystemExit(1) from exc
    except urllib.error.URLError as exc:
        print(f"无法连接 {url}: {exc.reason}", file=sys.stderr)
        raise SystemExit(1) from exc

    tools = body.get("tool_names_called") or []
    print(f"session_id: {body.get('session_id') or ''}")
    print(f"tools: {', '.join(tools) or '(none)'}")
    print("---")
    print(body.get("reply") or "")


if __name__ == "__main__":
    main()
