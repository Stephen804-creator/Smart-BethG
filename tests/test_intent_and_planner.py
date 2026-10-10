import unittest

from agent.intent import classify_intent, CHAT, GIT_READ, MEMORY_WRITE, FILESYSTEM_READ, RESEARCH, CODE_EXPLAIN, CODE_REVIEW, extract_memory_content, extract_file_path, extract_research_query
from agent.planner import build_plan


class TestIntentClassification(unittest.TestCase):
    def test_git_status_phrases_recognized(self):
        for text in [
            "git status",
            "what's the repository status?",
            "check my repo",
            "Check the repository please",
            "repo status",
        ]:
            self.assertEqual(classify_intent(text), GIT_READ, msg=text)

    def test_remember_phrases_recognized(self):
        for text in [
            "remember that I prefer Python",
            "Remember: I use FastAPI",
            "please remember I like concise answers",
        ]:
            self.assertEqual(classify_intent(text), MEMORY_WRITE, msg=text)

    def test_remember_question_is_not_a_write(self):
        """
        "remember" not at the start (a question about past context, not
        an instruction to store something new) must fall through to
        chat - a real AI reply is the right way to answer that, not a
        regex guessing at recall.
        """
        self.assertEqual(classify_intent("do you remember what I told you earlier?"), CHAT)

    def test_extract_memory_content_strips_trigger_phrase(self):
        self.assertEqual(extract_memory_content("remember that I prefer Python"), "I prefer Python")
        self.assertEqual(extract_memory_content("Remember: I use FastAPI"), "I use FastAPI")
        self.assertEqual(extract_memory_content("please remember I like concise answers"), "I like concise answers")

    def test_unrelated_text_falls_back_to_chat(self):
        for text in [
            "what's the capital of France?",
            "run this script",
            "hello there",
        ]:
            self.assertEqual(classify_intent(text), CHAT, msg=text)

    def test_file_read_phrases_recognized(self):
        for text in [
            "read the file config.py",
            "show me the contents of notes.txt",
            "open the file readme.md",
            "what's in the file app.py",
            "cat main.py",
        ]:
            self.assertEqual(classify_intent(text), FILESYSTEM_READ, msg=text)

    def test_file_path_extraction_prefers_quoted_paths(self):
        self.assertEqual(extract_file_path('read the file "src/main.py"'), "src/main.py")
        self.assertEqual(extract_file_path("show me the contents of 'notes.txt'"), "notes.txt")
        self.assertEqual(extract_file_path("open the file `config.yaml`"), "config.yaml")

    def test_file_path_extraction_finds_bare_filename(self):
        self.assertEqual(extract_file_path("read the file config.py"), "config.py")

    def test_file_path_extraction_returns_none_when_ambiguous(self):
        """
        "read the file" with nothing identifiable as a path must return
        None - the executor asks a clarifying question rather than
        guessing, see agent/planner.py's "clarify" step.
        """
        self.assertIsNone(extract_file_path("read the file"))
        self.assertIsNone(extract_file_path("can you read that file for me"))

    def test_research_phrases_recognized(self):
        for text in [
            "research quantum computing",
            "look up the latest news on AI regulation",
            "search for the best pizza places",
            "find information about black holes",
            "find info on FastAPI",
        ]:
            self.assertEqual(classify_intent(text), RESEARCH, msg=text)

    def test_research_mention_not_at_start_falls_back_to_chat(self):
        self.assertEqual(classify_intent("I did some research on this yesterday"), CHAT)
        self.assertEqual(classify_intent("can you research this for me"), CHAT)

    def test_research_with_no_topic_still_classified_for_clarification(self):
        """
        Unlike a random unmatched phrase, a bare "research" with nothing
        after it must still be recognized as the RESEARCH intent (with
        an empty query) so the planner's clarify path can fire - if this
        fell through to plain CHAT instead, the user would just get an
        AI reply guessing at what to research instead of being asked.
        """
        self.assertEqual(classify_intent("please research"), RESEARCH)
        self.assertEqual(extract_research_query("please research"), "")

    def test_extract_research_query(self):
        self.assertEqual(extract_research_query("research quantum computing"), "quantum computing")
        self.assertEqual(extract_research_query("look up the weather in Lagos"), "the weather in Lagos")

    def test_empty_text_is_chat(self):
        self.assertEqual(classify_intent(""), CHAT)
        self.assertEqual(classify_intent(None), CHAT)


class TestPlanner(unittest.TestCase):
    def test_chat_intent_produces_single_chat_step(self):
        plan = build_plan(CHAT)
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].kind, "chat")

    def test_tool_intent_produces_single_tool_step(self):
        plan = build_plan(GIT_READ)
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].kind, "tool")
        self.assertEqual(plan.steps[0].action, GIT_READ)

    def test_memory_write_intent_produces_memory_step(self):
        plan = build_plan(MEMORY_WRITE)
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].kind, "memory")
        self.assertEqual(plan.steps[0].action, MEMORY_WRITE)

    def test_filesystem_read_with_clear_path_produces_tool_step_with_args(self):
        plan = build_plan(FILESYSTEM_READ, 'read the file "notes.txt"')
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].kind, "tool")
        self.assertEqual(plan.steps[0].action, FILESYSTEM_READ)
        self.assertEqual(plan.steps[0].args, {"path": "notes.txt"})

    def test_filesystem_read_without_clear_path_produces_clarify_step(self):
        plan = build_plan(FILESYSTEM_READ, "read the file")
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].kind, "clarify")
        self.assertIsNotNone(plan.steps[0].question)

    def test_research_with_query_produces_two_step_plan(self):
        plan = build_plan(RESEARCH, "research quantum computing")
        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(plan.steps[0].kind, "search")
        self.assertEqual(plan.steps[0].args, {"query": "quantum computing"})
        self.assertEqual(plan.steps[1].kind, "chat")

    def test_research_without_query_produces_clarify_step(self):
        plan = build_plan(RESEARCH, "please research")
        self.assertEqual(len(plan.steps), 1)
        self.assertEqual(plan.steps[0].kind, "clarify")


if __name__ == "__main__":
    unittest.main()


class TestCodeIntents(unittest.TestCase):
    def test_code_explain_phrases(self):
        for text in [
            "explain the file main.py",
            "explain what this code does in app.py",
            "walk me through the file server.py",
        ]:
            self.assertEqual(classify_intent(text), CODE_EXPLAIN, msg=text)

    def test_code_review_phrases(self):
        for text in [
            "review the file utils.py",
            "debug the file server.py",
            "check bugs in file api.py",
        ]:
            self.assertEqual(classify_intent(text), CODE_REVIEW, msg=text)

    def test_plain_read_is_not_mistaken_for_code_intent(self):
        self.assertEqual(classify_intent("read the file config.py"), FILESYSTEM_READ)

    def test_explain_with_path_plans_read_then_chat(self):
        plan = build_plan(CODE_EXPLAIN, 'explain the file "main.py"')
        self.assertEqual([s.kind for s in plan.steps], ["tool", "chat"])
        self.assertEqual(plan.steps[0].action, "filesystem.read")
        self.assertEqual(plan.steps[0].args, {"path": "main.py"})

    def test_review_without_path_plans_clarify(self):
        plan = build_plan(CODE_REVIEW, "review the file")
        self.assertEqual([s.kind for s in plan.steps], ["clarify"])
