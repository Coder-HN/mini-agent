"""gateway 只读工具：Mock HTTP，覆盖无 token / 403 / 成功。"""

from __future__ import annotations

import json
import unittest
from io import BytesIO
from unittest.mock import patch

from min_agent.gateway import route_query


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


class GatewayJwtTests(unittest.TestCase):
    def test_missing_token(self) -> None:
        out = route_query("users", {}, ctx={})
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("error"), "missing_token")

    def test_permission_denied_403(self) -> None:
        import urllib.error

        err = urllib.error.HTTPError(
            url="http://127.0.0.1:8000/api/v1/sys-user",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=BytesIO('{"code":403,"msg":"无权"}'.encode()),
        )
        with patch("min_agent.gateway.urllib.request.urlopen", side_effect=err):
            out = route_query(
                "users",
                {},
                ctx={"context": {"access_token": "t"}},
            )
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("error"), "permission_denied")
        self.assertIn("无权", out.get("message", ""))

    def test_users_ok(self) -> None:
        payload = json.dumps(
            {"code": 200, "data": {"list": [{"username": "admin"}], "count": 1}}
        ).encode()
        with patch(
            "min_agent.gateway.urllib.request.urlopen",
            return_value=_FakeResp(200, payload),
        ):
            out = route_query(
                "users",
                {"pageSize": 10},
                ctx={"context": {"access_token": "t"}},
            )
        self.assertTrue(out.get("ok"))
        self.assertEqual(out.get("data_type"), "users")
        self.assertEqual(out["data"]["code"], 200)

    def test_commission_retired(self) -> None:
        out = route_query("commission", {}, ctx={"context": {"access_token": "t"}})
        self.assertFalse(out.get("ok"))
        self.assertEqual(out.get("error"), "retired")


if __name__ == "__main__":
    unittest.main()
