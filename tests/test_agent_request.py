import unittest

from agent.request import AgentRequest


class TestAgentRequest(unittest.TestCase):
    def test_valid_request_constructs(self):
        req = AgentRequest(text="hello", user={"id": 1, "role": "user"})
        self.assertEqual(req.workspace, "default")

    def test_blank_text_rejected(self):
        with self.assertRaises(ValueError):
            AgentRequest(text="   ", user={"id": 1})

    def test_blank_workspace_rejected(self):
        with self.assertRaises(ValueError):
            AgentRequest(text="hi", user={"id": 1}, workspace="  ")

    def test_user_without_id_rejected(self):
        with self.assertRaises(ValueError):
            AgentRequest(text="hi", user={"role": "user"})


if __name__ == "__main__":
    unittest.main()
