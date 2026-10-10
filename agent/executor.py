"""
Smart BethG - Agent Executor (T0404, now genuinely multi-step for research)

Ties the pieces together:

    AgentRequest -> classify_intent -> build_plan -> run every step in
    order -> return an honest, structured outcome.

Most plans are still exactly one step (git.read, memory.write,
filesystem.read - see agent/planner.py for why). RESEARCH and the code
intents (code.explain / code.review) are real multi-step plans: an
earlier step (a web search, or a filesystem.read) runs first and its
real output becomes context injected into the following "chat" step,
which is what synthesizes a grounded answer. If any earlier step fails,
is denied, or needs approval, the plan stops there and reports exactly
that - it never proceeds to synthesize an answer from nothing.

Step kinds: "chat" (the AI provider, with recalled memory + any
accumulated search context injected), "tool" (the security-governed
system-level tools in services/tool_service.py), "memory" (writing a
new memory entry - bypasses ToolService/PolicyEngine entirely, since
storing a stated preference isn't a security-sensitive system action),
"search" (real web search via services/search_service.py, also outside
ToolService since it can't touch the user's system - only the final
synthesis step, not the search step, is user-facing on success), and
"clarify" (ask instead of guessing).

Both /tasks and /api/chat route through this (see routes/chat.py).
"""
from agent.intent import (
    classify_intent, MEMORY_WRITE, RESEARCH, CODE_EXPLAIN, CODE_REVIEW,
    GIT_ANALYZE_CHANGES, GIT_COMMIT_MESSAGE, extract_memory_content,
)
from agent.planner import build_plan
from agent.request import AgentRequest
from services.tool_service import ToolService
from services.chat_service import ChatService
from services.memory_service import MemoryService
from services.search_service import SearchService
from logging_setup import get_logger

logger = get_logger("task")


class AgentExecutor:
    def __init__(self, tool_service=None, chat_service=None, memory_service=None, search_service=None):
        self.tool_service = tool_service or ToolService()
        self.chat_service = chat_service or ChatService()
        self.memory_service = memory_service or MemoryService()
        self.search_service = search_service or SearchService()

    def run(self, agent_request: AgentRequest) -> dict:
        intent = classify_intent(agent_request.text)
        plan = build_plan(intent, agent_request.text)

        logger.info(
            "Agent request: user=%s intent=%s workspace=%s steps=%d",
            agent_request.user["id"], intent, agent_request.workspace, len(plan.steps),
        )

        context_parts = []  # accumulated from earlier non-terminal steps (search results, file contents, ...)

        for index, step in enumerate(plan.steps):
            is_last = index == len(plan.steps) - 1

            if step.kind == "chat":
                chat_result = self.chat_service.send(
                    agent_request.user["id"], agent_request.text,
                    agent_request.conversation_id, agent_request.selection,
                    agent_request.workspace,
                    extra_context="\n\n".join(context_parts) if context_parts else None,
                )
                return {
                    "intent": intent,
                    "status": "completed" if chat_result.get("provider_configured") else "no_provider",
                    "result": chat_result,
                }

            if step.kind == "memory":
                return self._run_memory_write(agent_request)

            if step.kind == "clarify":
                chat_result = self._persist_synthesized_exchange(agent_request, step.question)
                return {"intent": step.action, "status": "needs_clarification", "result": chat_result}

            if step.kind == "search":
                context, failure = self._run_search_step(agent_request, step)
                if failure:
                    return failure
                context_parts.append(context)
                continue  # proceed to the next step (expected: the synthesis chat step)

            # kind == "tool"
            tool_result = self.tool_service.execute(
                agent_request.user, step.action, workspace=agent_request.workspace, **step.args,
            )

            tool_succeeded = tool_result.get("success") and tool_result.get("status") == "executed"
            if is_last or not tool_succeeded:
                # Either a standalone tool intent (git.read, filesystem.read), or
                # a chained tool that failed / was denied / needs approval - in
                # both cases the plan ends here and reports what actually
                # happened. A chained plan never proceeds to synthesize an
                # answer from a tool step that didn't succeed.
                chat_result = self._record_tool_exchange(agent_request, step.action, tool_result)
                return {
                    "intent": step.action,
                    "status": tool_result.get("status"),
                    "result": {**chat_result, "tool_result": tool_result},
                }

            context_parts.append(self._format_tool_result_as_context(step.action, tool_result))
            if intent == CODE_EXPLAIN:
                context_parts.append(
                    "Explain what the code above does: its purpose, its key logic, and "
                    "anything notable. Only describe what is actually in the file."
                )
            elif intent == CODE_REVIEW:
                context_parts.append(
                    "Review the code above for bugs, error-handling gaps, and "
                    "improvements. Point to specific lines or functions. If you don't "
                    "see a real problem, say so instead of inventing one."
                )
            elif intent == GIT_ANALYZE_CHANGES:
                context_parts.append(
                    "Explain what the diff above actually changes and why it likely "
                    "matters. Only describe changes that are actually present in the diff."
                )
            elif intent == GIT_COMMIT_MESSAGE:
                context_parts.append(
                    "Based only on the diff above, write a concise, conventional-style "
                    "commit message (a short summary line, plus a body if genuinely "
                    "needed). If the diff is empty, say there's nothing to commit."
                )
            continue

        # Every branch above returns; reaching here means build_plan produced
        # a plan whose last step doesn't terminate - a planning bug, not a
        # runtime condition to paper over.
        raise RuntimeError(f"Plan for intent {intent!r} did not produce a terminal outcome.")

    @staticmethod
    def _format_tool_result_as_context(action: str, tool_result: dict) -> str:
        """Turns a successful chained tool result into context for the next step."""
        result = tool_result.get("result", {})
        if action == "filesystem.read":
            return f"Contents of {result.get('path')}:\n\n{result.get('content', '')}"
        if action == "git.read" and tool_result.get("operation") == "diff":
            output = (result.get("stdout") or "").strip()
            return f"Git diff:\n\n{output}" if output else "Git diff: no changes (empty diff)."
        return f"Result of {action}: {result}"

    def _run_search_step(self, agent_request: AgentRequest, step) -> tuple:
        """
        Returns (grounded_context_or_None, terminal_outcome_or_None).
        Exactly one of the two is non-None - a real result to carry into
        the next step, or a terminal failure to return immediately
        (search failing does not fall through to a synthesis step that
        would have nothing real to synthesize from).
        """
        query = step.args.get("query", "")
        try:
            results = self.search_service.search(query)
        except Exception as exc:
            logger.error("Search failed: user=%s query=%r error=%s", agent_request.user["id"], query, exc)
            chat_result = self._persist_synthesized_exchange(
                agent_request, f"I couldn't search the web for that: {exc}"
            )
            return None, {"intent": RESEARCH, "status": "search_failed", "result": chat_result}

        if not results:
            chat_result = self._persist_synthesized_exchange(
                agent_request, f'I searched for "{query}" but found no results.'
            )
            return None, {"intent": RESEARCH, "status": "no_results", "result": chat_result}

        context_lines = "\n".join(f"- {r['title']}: {r['snippet']} ({r['url']})" for r in results)
        context = (
            f'Web search results for "{query}":\n{context_lines}\n\n'
            "Answer the user's question using only the information above. "
            "Cite the specific URL(s) that support each claim. If the "
            "results don't contain enough information to answer "
            "confidently, say so honestly instead of guessing."
        )
        return context, None

    def _run_memory_write(self, agent_request: AgentRequest) -> dict:
        content = extract_memory_content(agent_request.text)
        try:
            entry = self.memory_service.remember(
                agent_request.user["id"], content, scope="user", source="chat",
            )
            reply = f"Got it, I'll remember that: \"{content}\""
            status = "executed"
        except ValueError as exc:
            entry = None
            reply = f"I couldn't store that: {exc}"
            status = "failed"

        chat_result = self._persist_synthesized_exchange(agent_request, reply)
        return {
            "intent": MEMORY_WRITE,
            "status": status,
            "result": {**chat_result, "memory_entry": entry},
        }

    def _record_tool_exchange(self, agent_request: AgentRequest, action: str, tool_result: dict) -> dict:
        """
        Persists the user's text and a synthesized, honest summary of
        what the tool actually did into the conversation, so a
        tool-triggered exchange shows up in history the same way a
        normal chat reply does - and so the existing chat UI can render
        it with zero special-casing (it just displays `reply`).
        """
        reply = self._summarize_tool_result(action, tool_result)
        return self._persist_synthesized_exchange(agent_request, reply)

    def _persist_synthesized_exchange(self, agent_request: AgentRequest, reply: str) -> dict:
        conversation_id, is_new = self.chat_service.get_or_create_conversation(
            agent_request.user["id"], agent_request.conversation_id
        )
        self.chat_service.repo.add_message(conversation_id, "user", agent_request.text)
        if is_new:
            self.chat_service.repo.set_title(conversation_id, agent_request.text[:60])
        self.chat_service.repo.add_message(conversation_id, "assistant", reply, provider="agent")
        self.chat_service.repo.touch(conversation_id)
        return {"conversation_id": conversation_id, "reply": reply, "provider_configured": True}

    @staticmethod
    def _summarize_tool_result(action: str, tool_result: dict) -> str:
        status = tool_result.get("status")
        if status == "approval_required":
            return (
                f"That requires approval before I can do it (action: {action}). "
                f"Approval ID: {tool_result.get('approval_id')}. "
                "An approval with this ID needs to be approved before I can proceed."
            )
        if status == "denied":
            return f"I don't have permission to do that with your current role. ({tool_result.get('reason')})"
        if not tool_result.get("success"):
            return f"That didn't succeed: {tool_result.get('reason', 'unknown error')}"

        result = tool_result.get("result", {})
        if action == "git.read":
            output = (result.get("stdout") or "").strip()
            operation = tool_result.get("operation", "status")
            label = {"status": "Repository status", "diff": "Git diff", "branches": "Branches"}.get(operation, "Result")
            return f"{label}:\n\n{output}" if output else f"{label}: nothing to report."
        if action == "git.write" and tool_result.get("operation") == "checkout":
            output = (result.get("stdout") or "").strip()
            return f"Switched branch.\n\n{output}" if output else "Switched branch."
        if action == "filesystem.read":
            content = result.get("content", "")
            truncated = content if len(content) <= 4000 else content[:4000] + "\n\n[...truncated]"
            return f"Contents of {result.get('path')}:\n\n{truncated}"

        return f"Done ({action})."
