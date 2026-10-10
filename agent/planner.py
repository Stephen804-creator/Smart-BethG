"""
Smart BethG - Planning Engine (T0403)

Most intents still map to exactly one step - git.read, memory.write,
and filesystem.read genuinely only need one action, so a longer plan
for them would be theater. RESEARCH is the first genuinely multi-step
plan: search, then a chat step that synthesizes an answer grounded in
what the search actually returned - a single step could search OR
answer, not search-then-answer-using-the-results. Real multi-step
decomposition beyond this (e.g. planning several different search
queries, or a plan whose later steps depend on branching on an earlier
result) is still not implemented - this executes a fixed, hand-written
two-step shape for research, not a general planner that can construct
arbitrary step sequences.

Planning here also includes argument binding for filesystem.read: if no
confident file path can be extracted from the text, the plan is a
"clarify" step (ask the user which file, rather than guess and read the
wrong one or crash). Same treatment for research with no query.
"""
from dataclasses import dataclass, field
from typing import List, Optional

from agent.intent import (
    CHAT, MEMORY_WRITE, FILESYSTEM_READ, RESEARCH, CODE_EXPLAIN, CODE_REVIEW,
    GIT_READ, GIT_BRANCHES, GIT_DIFF, GIT_CHECKOUT, GIT_ANALYZE_CHANGES, GIT_COMMIT_MESSAGE,
    extract_file_path, extract_research_query, extract_branch_name,
)


@dataclass
class PlanStep:
    kind: str  # "chat", "tool", "memory", "clarify", or "search"
    action: Optional[str] = None  # e.g. "git.read"/"memory.write", set when kind != "chat"
    args: dict = field(default_factory=dict)  # extracted arguments for a "tool"/"search" step
    question: Optional[str] = None  # the question to show the user, set when kind == "clarify"


@dataclass
class Plan:
    steps: List[PlanStep] = field(default_factory=list)


def build_plan(intent: str, text: str = "") -> Plan:
    if intent == CHAT:
        return Plan(steps=[PlanStep(kind="chat")])

    if intent == MEMORY_WRITE:
        return Plan(steps=[PlanStep(kind="memory", action=intent)])

    if intent == FILESYSTEM_READ:
        path = extract_file_path(text)
        if path is None:
            return Plan(steps=[PlanStep(
                kind="clarify", action=intent,
                question="Which file would you like me to read? Please give me the exact path.",
            )])
        return Plan(steps=[PlanStep(kind="tool", action=intent, args={"path": path})])

    if intent == RESEARCH:
        query = extract_research_query(text)
        if not query:
            return Plan(steps=[PlanStep(
                kind="clarify", action=intent,
                question="What would you like me to research?",
            )])
        # Genuinely two steps: search, then a chat step that synthesizes
        # an answer grounded in what the search actually returned. This
        # is the real reason multi-step plans exist - a single-step plan
        # could search OR answer, not search-then-answer-from-results.
        return Plan(steps=[
            PlanStep(kind="search", action=intent, args={"query": query}),
            PlanStep(kind="chat"),
        ])

    if intent in (CODE_EXPLAIN, CODE_REVIEW):
        path = extract_file_path(text)
        if path is None:
            verb = "explain" if intent == CODE_EXPLAIN else "review"
            return Plan(steps=[PlanStep(
                kind="clarify", action=intent,
                question=f"Which file would you like me to {verb}? Please give me the exact path.",
            )])
        # Read the file for real (through the same permission-checked,
        # workspace-confined tool as a plain filesystem.read), then a
        # chat step that receives the actual file contents - so the AI
        # explains/reviews what's really in the file, not what it
        # guesses a file with that name might contain.
        return Plan(steps=[
            PlanStep(kind="tool", action="filesystem.read", args={"path": path}),
            PlanStep(kind="chat"),
        ])

    if intent == GIT_BRANCHES:
        return Plan(steps=[PlanStep(kind="tool", action=GIT_READ, args={"operation": "branches"})])

    if intent == GIT_DIFF:
        return Plan(steps=[PlanStep(kind="tool", action=GIT_READ, args={"operation": "diff"})])

    if intent == GIT_CHECKOUT:
        branch = extract_branch_name(text)
        if not branch:
            return Plan(steps=[PlanStep(
                kind="clarify", action=intent,
                question="Which branch would you like me to switch to?",
            )])
        return Plan(steps=[PlanStep(
            kind="tool", action="git.write", args={"operation": "checkout", "branch": branch},
        )])

    if intent in (GIT_ANALYZE_CHANGES, GIT_COMMIT_MESSAGE):
        # Same shape as code.explain/review: a real diff first, then a
        # chat step that receives the actual diff text - the AI never
        # analyzes or drafts a message for changes it wasn't shown.
        return Plan(steps=[
            PlanStep(kind="tool", action=GIT_READ, args={"operation": "diff"}),
            PlanStep(kind="chat"),
        ])

    return Plan(steps=[PlanStep(kind="tool", action=intent)])
