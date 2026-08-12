"""会话可见范围：本人 / 全部数据权限。"""

from __future__ import annotations

import unittest

from agent_core.store import session_visible


class SessionVisibilityTests(unittest.TestCase):
    def test_all_scope_sees_others(self) -> None:
        self.assertTrue(
            session_visible("2", viewer_user_id="1", data_scope="1")
        )

    def test_self_only_own(self) -> None:
        self.assertTrue(
            session_visible("3", viewer_user_id="3", data_scope="5")
        )

    def test_self_only_deny_other(self) -> None:
        self.assertFalse(
            session_visible("2", viewer_user_id="3", data_scope="5")
        )

    def test_legacy_empty_owner_needs_all(self) -> None:
        self.assertFalse(
            session_visible("", viewer_user_id="3", data_scope="5")
        )
        self.assertTrue(
            session_visible("", viewer_user_id="1", data_scope="1")
        )


if __name__ == "__main__":
    unittest.main()
