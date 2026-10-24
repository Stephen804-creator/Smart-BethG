import unittest
from services.capability_registry import CapabilityRegistry
from services.policy_engine import PolicyEngine

class TestCapabilityRegistry(unittest.TestCase):
    def setUp(self): self.registry=CapabilityRegistry()
    def test_known_action_validates_and_is_typed(self):
        spec=self.registry.validate_arguments("github","issues.create",{"repository":"owner/repo","title":"Fix bug"})
        self.assertEqual(spec.risk,"write"); self.assertTrue(spec.side_effecting)
    def test_unknown_action_fails_closed(self):
        with self.assertRaises(ValueError): self.registry.validate_arguments("github","shell.run",{})
    def test_unknown_and_bad_arguments_are_rejected(self):
        with self.assertRaises(ValueError): self.registry.validate_arguments("github","issues.create",{"repository":"a/b","title":42})
        with self.assertRaises(ValueError): self.registry.validate_arguments("github","issues.create",{"repository":"a/b","title":"ok","force":True})
    def test_write_action_requires_approval(self):
        spec=self.registry.get("github","issues.create")
        decision=PolicyEngine().evaluate(spec,{"user_id":7,"connector_key":"github","status":"connected","granted_permissions":["github.issues.create"]},7)
        self.assertEqual(decision.decision,"approval_required"); self.assertTrue(decision.requires_approval)
    def test_unconnected_connector_is_denied(self):
        spec=self.registry.get("github","issues.list")
        decision=PolicyEngine().evaluate(spec,{"user_id":7,"connector_key":"github","status":"disconnected","granted_permissions":["github.issues.list"]},7)
        self.assertEqual(decision.decision,"deny")

if __name__=="__main__": unittest.main()
