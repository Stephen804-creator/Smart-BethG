# Smart BethG Clean Code Rules (v0.1)

Inject with the Core Rules whenever the AI writes or edits code. The Quality Gate (QUALITY_GATE.md) enforces these automatically, so they are not optional hints. The numbers are sensible starting values to tune with real data.

## Stay in your lane (scope discipline)
1. Change only what was asked. No unrelated edits, renames or reformatting of other files.
2. Do not add features, libraries or files the user did not ask for. Ask first.
3. Match the project's existing style, structure and naming.
4. For a big change (more than about 3 files or 100 lines), explain the plan and ask first.
5. Finish with a short summary of exactly what changed and why.

## Never cross these lines
- Never delete, skip or weaken a test to make it pass.
- Never hard-code secrets, keys or passwords. Read them from environment variables.
- Never swallow errors silently (no empty except or catch). Handle them or report them.
- Never build SQL by joining strings with user input. Use parameterized queries.
- Never trust user input. Validate and sanitize it on the server.
- Never leave debug flags, stray print statements or commented-out code in finished work.
- Never copy-paste the same block three times. Make a function.
- Never invent a library function. If unsure, check the official docs or say so.

## Shape of good code (limits)
- One job per function. Target under about 30 lines, hard limit 50.
- Nesting at most 3 levels deep. Return early to flatten.
- Complexity at most 10 per function.
- Files under about 300 lines. Split by responsibility.
- Names say what things are or do. No data1, tmp or x (except tiny loops). Booleans read like questions (is_valid).
- No magic numbers. Name your constants.
- Comments explain WHY, not WHAT. Public functions get a one-line docstring.
- Handle the empty, missing, too-large and failure cases.
- Keep side effects at the edges. Prefer small functions that return a value.
- Add or update a test for every behavior you add or fix.
- Use the project's formatter. Do not hand-format.

## When unsure
Stop and ask one clear question instead of guessing. Say what you assumed.

## Teach & build link
Every rule has a Learning Library card. When you avoid or fix a violation, name the rule and say why in one sentence, so the learner learns what makes code bad even when it works.
