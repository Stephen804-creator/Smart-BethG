import unittest

from security.role_permissions import build_security_context, permissions_for_role


class TestRolePermissions(unittest.TestCase):
    def test_user_role_gets_only_low_risk_permissions(self):
        perms = permissions_for_role("user")
        self.assertIn("filesystem.read", perms)
        self.assertIn("git.read", perms)
        self.assertNotIn("terminal.execute", perms)
        self.assertNotIn("docker.run", perms)

    def test_admin_role_gets_everything(self):
        perms = permissions_for_role("admin")
        self.assertIn("terminal.execute", perms)
        self.assertIn("docker.run", perms)
        self.assertIn("network.request", perms)

    def test_unknown_role_fails_closed_to_user_permissions(self):
        perms = permissions_for_role("some_made_up_role")
        self.assertEqual(perms, permissions_for_role("user"))

    def test_build_security_context_carries_user_id_and_role_permissions(self):
        ctx = build_security_context({"id": 7, "role": "admin"}, workspace="proj")
        self.assertEqual(ctx.user_id, "7")
        self.assertEqual(ctx.workspace, "proj")
        self.assertTrue(ctx.has_permission("terminal.execute"))

    def test_build_security_context_defaults_to_user_role_if_missing(self):
        ctx = build_security_context({"id": 3}, workspace="default")
        self.assertFalse(ctx.has_permission("terminal.execute"))
        self.assertTrue(ctx.has_permission("filesystem.read"))


if __name__ == "__main__":
    unittest.main()
