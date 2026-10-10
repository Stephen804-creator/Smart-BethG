"""
Smart BethG - Intent Detection (T0402)

A short list of regex triggers, nothing more. This is NOT natural
language understanding, and it deliberately only recognizes intents it
can fulfill with zero unreliable argument extraction:

- git.read needs no arguments beyond the workspace, which the request
  already carries.
- memory.write's "argument" is just whatever text follows the trigger
  phrase, stored verbatim - there's no guessing involved, unlike a file
  path or a shell command.
- filesystem.read needs a file path. extract_file_path() only returns
  one when it's unambiguous (quoted/backticked, or a bare token that
  actually looks like a filename). When it can't find one confidently,
  the executor asks the user which file they mean instead of guessing -
  see agent/planner.py's "clarify" step kind. This is the one
  intentional exception to "don't recognize an intent you can't
  reliably fill the arguments for": the fallback here isn't a guess,
  it's a question.

terminal.execute (needs a program AND arguments, and actually runs
something) is still NOT recognized here - a wrong guess at a shell
command is a materially different risk than asking "which file?" again.

Everything unrecognized falls through to plain chat, which is always a
safe default.
"""
import re

_GIT_STATUS_PATTERN = re.compile(
    r"\bgit status\b|\brepository status\b|\brepo status\b|\bcheck (my |the )?repo(sitory)?\b",
    re.IGNORECASE,
)

_GIT_BRANCHES_PATTERN = re.compile(
    r"\blist (the )?branches\b|\bshow (me )?(the )?branches\b|\bwhat branches\b|\bgit branch(es)?\b",
    re.IGNORECASE,
)

_GIT_CHECKOUT_PATTERN = re.compile(
    r"\b(checkout|check out|switch to)\s+(branch\s+)?(?P<branch>[\w./-]+)\b",
    re.IGNORECASE,
)

# Anchored to require an explicit "explain"/"analyze" instruction so a
# bare "what changed" (ambiguous - could mean the repo, a file, anything)
# doesn't get swept in here.
_GIT_CHANGE_ANALYSIS_PATTERN = re.compile(
    r"\b(explain|analyze|summarize|walk me through) (the )?(diff|changes?)\b",
    re.IGNORECASE,
)

_GIT_DIFF_PATTERN = re.compile(
    r"\bgit diff\b|\bshow (me )?(the )?diff\b|\bwhat changed\b|\bwhat('s| is) different\b",
    re.IGNORECASE,
)

_GIT_COMMIT_MESSAGE_PATTERN = re.compile(
    r"\b(write|draft|suggest|generate) (a |me a )?commit message\b",
    re.IGNORECASE,
)

# Anchored at the start on purpose: "remember that I prefer X" is a
# write instruction; "do you remember what I said?" (a question, not
# imperative, "remember" not at the start) correctly falls through to
# chat instead - a real AI reply is the right way to answer a recall
# question, not a regex.
_REMEMBER_PATTERN = re.compile(
    r"^\s*(please\s+)?remember(\s*:\s*|\s+that\s+|\s+)(?P<content>.+)$", re.IGNORECASE
)

_FILE_READ_TRIGGER_PATTERN = re.compile(
    r"\bread (the )?file\b|\bshow (me )?(the )?(contents of|file)\b|"
    r"\bopen (the )?file\b|\bwhat'?s in (the )?file\b|\bcat\s",
    re.IGNORECASE,
)

_CODE_EXPLAIN_TRIGGER_PATTERN = re.compile(
    r"\bexplain (the )?(code (in|for|of) )?(the )?file\b|"
    r"\bexplain (what )?(this )?(code|file) does\b|"
    r"\bwalk me through (the )?(code in )?(the )?file\b",
    re.IGNORECASE,
)

_CODE_REVIEW_TRIGGER_PATTERN = re.compile(
    r"\breview (the )?(code (in|for) )?(the )?file\b|"
    r"\b(check|find) (bugs|issues|problems) (in|with) (the )?file\b|"
    r"\bdebug (the )?file\b",
    re.IGNORECASE,
)

# Anchored at the start, same reasoning as _REMEMBER_PATTERN: "research
# quantum computing" is an instruction; "I did some research on this
# yesterday" (not at the start) should fall through to chat.
_RESEARCH_PATTERN = re.compile(
    r"^\s*(please\s+)?(research|look up|search (the web )?for|find (information|info) (on|about))"
    r"(\s*:\s*|\s+)?(?P<query>.*)$",
    re.IGNORECASE,
)

# A path in quotes/backticks - unambiguous regardless of shape.
_QUOTED_PATH_PATTERN = re.compile(r"[\"'`]([^\"'`]+)[\"'`]")

# A bare token that looks like a filename: no spaces, has a real
# extension (1-6 word characters after a dot). Deliberately narrow -
# this is the only case where a bare (unquoted) token is trusted.
_BARE_PATH_PATTERN = re.compile(r"\b([\w./-]+\.[A-Za-z0-9]{1,6})\b")

CHAT = "chat"
GIT_READ = "git.read"
MEMORY_WRITE = "memory.write"
FILESYSTEM_READ = "filesystem.read"
RESEARCH = "research"
CODE_EXPLAIN = "code.explain"
CODE_REVIEW = "code.review"
GIT_BRANCHES = "git.branches"
GIT_DIFF = "git.diff"
GIT_CHECKOUT = "git.checkout"
GIT_ANALYZE_CHANGES = "git.analyze_changes"
GIT_COMMIT_MESSAGE = "git.commit_message"


def classify_intent(text: str) -> str:
    text = text or ""
    if _REMEMBER_PATTERN.match(text):
        return MEMORY_WRITE
    if _RESEARCH_PATTERN.match(text):
        return RESEARCH
    if _GIT_COMMIT_MESSAGE_PATTERN.search(text):
        return GIT_COMMIT_MESSAGE
    if _GIT_CHANGE_ANALYSIS_PATTERN.search(text):
        return GIT_ANALYZE_CHANGES
    if _GIT_CHECKOUT_PATTERN.search(text):
        return GIT_CHECKOUT
    if _GIT_BRANCHES_PATTERN.search(text):
        return GIT_BRANCHES
    if _GIT_DIFF_PATTERN.search(text):
        return GIT_DIFF
    if _GIT_STATUS_PATTERN.search(text):
        return GIT_READ
    if _CODE_REVIEW_TRIGGER_PATTERN.search(text):
        return CODE_REVIEW
    if _CODE_EXPLAIN_TRIGGER_PATTERN.search(text):
        return CODE_EXPLAIN
    if _FILE_READ_TRIGGER_PATTERN.search(text):
        return FILESYSTEM_READ
    return CHAT


def extract_memory_content(text: str) -> str:
    """Only meaningful when classify_intent(text) == MEMORY_WRITE."""
    match = _REMEMBER_PATTERN.match(text or "")
    return match.group("content").strip() if match else ""


def extract_research_query(text: str) -> str:
    """Only meaningful when classify_intent(text) == RESEARCH."""
    match = _RESEARCH_PATTERN.match(text or "")
    return match.group("query").strip() if match else ""


def extract_file_path(text: str):
    """
    Returns a file path string if one can be confidently identified, or
    None if not - callers must treat None as "ask, don't guess", not as
    a fallback to try harder.
    """
    text = text or ""
    quoted = _QUOTED_PATH_PATTERN.search(text)
    if quoted:
        return quoted.group(1).strip()

    bare = _BARE_PATH_PATTERN.search(text)
    if bare:
        return bare.group(1).strip()

    return None


def extract_branch_name(text: str):
    """Only meaningful when classify_intent(text) == GIT_CHECKOUT."""
    match = _GIT_CHECKOUT_PATTERN.search(text or "")
    return match.group("branch").strip() if match else None
