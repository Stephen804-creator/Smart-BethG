import unittest

from services.sniper_memory import SniperMemory


class TestSniperMemory(unittest.TestCase):
    def setUp(self):
        self.engine = SniperMemory(
            recent_turns=2,
            relevant_turns=2,
            max_context_chars=1800,
            max_scan_messages=200,
        )

    def test_keeps_latest_request_and_recent_turns(self):
        messages = [
            {"role": "user", "content": "We decided to use PostgreSQL for production."},
            {"role": "assistant", "content": "PostgreSQL is the production database."},
            {"role": "user", "content": "Now explain CSS grid."},
            {"role": "assistant", "content": "CSS grid lays out page content."},
            {"role": "user", "content": "What is responsive design?"},
        ]
        result = self.engine.compile(messages, "responsive design")
        contents = [item["content"] for item in result["messages"]]
        self.assertEqual(contents[-1], "What is responsive design?")
        self.assertIn("Now explain CSS grid.", contents)
        self.assertLessEqual(result["selected_chars"], 1800)

    def test_retrieves_relevant_older_turn(self):
        messages = [
            {"role": "user", "content": "Our production database decision is PostgreSQL."},
            {"role": "assistant", "content": "We will use PostgreSQL in production."},
            {"role": "user", "content": "Explain the difference between margin and padding in CSS."},
            {"role": "assistant", "content": "Margin is outside; padding is inside."},
            {"role": "user", "content": "What database did we choose for production?"},
        ]
        result = self.engine.compile(messages, "What database did we choose for production?")
        combined = "\n".join(item["content"] for item in result["messages"]).lower()
        self.assertIn("postgresql", combined)
        self.assertGreaterEqual(result["retrieved_older_turns"], 1)

    def test_does_not_send_entire_long_transcript(self):
        messages = []
        for index in range(80):
            messages.extend([
                {"role": "user", "content": f"Unrelated topic {index}: " + ("extra text " * 30)},
                {"role": "assistant", "content": f"Reply about topic {index}: " + ("answer " * 30)},
            ])
        messages.append({"role": "user", "content": "Tell me about topic 3."})
        result = self.engine.compile(messages, "Tell me about topic 3.")
        self.assertLess(result["selected_messages"], result["available_messages"])
        self.assertGreater(result["saved_chars"], 0)
        self.assertEqual(result["messages"][-1]["content"], "Tell me about topic 3.")

    def test_empty_history_is_safe(self):
        result = self.engine.compile([], "anything")
        self.assertEqual(result["messages"], [])
        self.assertEqual(result["saved_chars"], 0)

    def test_explicit_memory_ranking_prefers_matching_entries(self):
        entries = [
            {"id": 1, "content": "The project uses PostgreSQL."},
            {"id": 2, "content": "The UI uses CSS grid."},
        ]
        ranked = SniperMemory.rank_memories(entries, "database PostgreSQL", limit=1)
        self.assertEqual(ranked[0]["id"], 1)


if __name__ == "__main__":
    unittest.main()
