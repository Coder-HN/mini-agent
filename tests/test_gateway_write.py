"""gateway 写工具：未确认不写；确认后 method/path；无 token / 403。"""

from __future__ import annotations

import json
import unittest
from io import BytesIO
from unittest.mock import patch

from min_agent.gateway import route_write


class _FakeResp:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResp":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class GatewayWriteTests(unittest.TestCase):
    def test_create_preview_no_http(self) -> None:
        with patch("min_agent.gateway.urllib.request.urlopen") as mock_open:
            out = route_write(
                "create_user",
                {
                    "username": "zhangsan",
                    "nickName": "张三",
                    "phone": "13900000001",
                    "email": "zs@example.com",
                },
                confirmed=False,
                ctx={"context": {"access_token": "t"}},
            )
        mock_open.assert_not_called()
        self.assertTrue(out.get("ok"))
        self.assertTrue(out.get("needs_confirm"))
        self.assertEqual(out["impact"][0]["username"], "zhangsan")

    def test_create_confirmed_posts(self) -> None:
        payload = json.dumps({"code": 200, "data": 99, "msg": "创建成功"}).encode()
        with patch(
            "min_agent.gateway.urllib.request.urlopen",
            return_value=_FakeResp(200, payload),
        ) as mock_open:
            out = route_write(
                "create_user",
                {
                    "username": "zhangsan",
                    "nickName": "张三",
                    "phone": "13900000001",
                    "email": "zs@example.com",
                },
                confirmed=True,
                ctx={"context": {"access_token": "t"}},
            )
        self.assertTrue(out.get("ok"))
        self.assertFalse(out.get("needs_confirm"))
        req = mock_open.call_args[0][0]
        self.assertEqual(req.get_method(), "POST")
        self.assertIn("/api/v1/sys-user", req.full_url)

    def test_create_confirmed_missing_token(self) -> None:
        out = route_write(
            "create_user",
            {
                "username": "zhangsan",
                "nickName": "张三",
                "phone": "13900000001",
                "email": "zs@example.com",
            },
            confirmed=True,
            ctx={},
        )
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("error"), "missing_token")

    def test_disable_confirmed_403(self) -> None:
        import urllib.error

        err = urllib.error.HTTPError(
            url="http://127.0.0.1:8000/api/v1/user/status",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=BytesIO(b'{"code":403}'),
        )
        get_payload = json.dumps(
            {
                "code": 200,
                "data": {
                    "userId": 3,
                    "username": "selfonly",
                    "nickName": "普通员工",
                    "status": "2",
                },
            }
        ).encode()

        def _side_effect(req, timeout=30):  # noqa: ANN001
            if req.get_method() == "GET":
                return _FakeResp(200, get_payload)
            raise err

        with patch("min_agent.gateway.urllib.request.urlopen", side_effect=_side_effect):
            out = route_write(
                "disable_user",
                {"userId": 3},
                confirmed=True,
                ctx={"context": {"access_token": "t"}},
            )
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("error"), "permission_denied")
        self.assertIn("无权", out.get("message", ""))

    def test_disable_preview_and_put_path(self) -> None:
        get_payload = json.dumps(
            {
                "code": 200,
                "data": {
                    "userId": 3,
                    "username": "selfonly",
                    "nickName": "普通员工",
                    "status": "2",
                },
            }
        ).encode()
        put_payload = json.dumps({"code": 200, "data": 3, "msg": "更新成功"}).encode()

        def _side_effect(req, timeout=30):  # noqa: ANN001
            if req.get_method() == "GET":
                return _FakeResp(200, get_payload)
            return _FakeResp(200, put_payload)

        with patch(
            "min_agent.gateway.urllib.request.urlopen", side_effect=_side_effect
        ) as mock_open:
            preview = route_write(
                "disable_user",
                {"userId": 3},
                confirmed=False,
                ctx={"context": {"access_token": "t"}},
            )
            done = route_write(
                "disable_user",
                {"userId": 3},
                confirmed=True,
                ctx={"context": {"access_token": "t"}},
            )
        self.assertTrue(preview.get("needs_confirm"))
        self.assertEqual(preview["impact"][0]["username"], "selfonly")
        self.assertTrue(done.get("ok"))
        put_req = mock_open.call_args_list[-1][0][0]
        self.assertEqual(put_req.get_method(), "PUT")
        self.assertIn("/api/v1/user/status", put_req.full_url)


if __name__ == "__main__":
    unittest.main()
