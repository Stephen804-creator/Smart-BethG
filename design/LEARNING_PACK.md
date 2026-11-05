# Learning Pack (v0.1)

The Learning Pack is a hidden document the AI writes ONCE per stage from the learner's own code. After that, plain code plays it in a pop-up Learning Panel. No model call is needed while the learner studies. This refines learning-library/README.md: the library gives the AI reliable reference material and cuts cost, but the Pack itself is made from the learner's code.

## What is in a Pack
1. **Reading parts:** short parts (about 80 to 150 words), each pointing at real line numbers in the learner's code, each with a mini quiz.
2. **Quiz bank:** verified questions with answers (gap-fill, predict the output, spot the error), shuffled at play time.
3. **Debug levels:** levels 1 to 20 of planted bugs in a practice copy, with hints and the expected fix.
4. **Battle tasks:** a helper version (with a hint ladder) and a blank version, both graded by tests.
5. **Error explanations** and references to Learning Library cards.

## How it is made (one model call per stage)
- Input: the stage's code (small) plus the relevant library cards.
- Output: JSON that the engine validates against a schema.
- Automatic checks before the Pack is accepted:
  - every code snippet runs;
  - every quiz answer is verified by running the code, and has exactly one correct option;
  - every planted bug makes at least one test fail, and the reference fix makes all tests pass;
  - reading text only refers to line numbers that exist;
  - explanations agree with library cards where a card exists.
- If a check fails, regenerate once. If it still fails, fall back to library-only content and say so.
- Rough cost per stage (assumption, measure it): about 3,000 to 5,000 output tokens, about $0.015 to $0.025 on a fast model at list price, or $0.045 to $0.075 on a strong model.
- If the learner edits their code later, regenerate only the changed parts (compare hashes).

## The Learning Panel (no model calls)
A pop-up sheet over the chat, opened from the stage card ("Learn this stage"). Tabs: Read, Quiz, Debug, Battle.
- **Read:** one part at a time with "Continue reading", a mini quiz per part, and "Skip to practice" always available. A small "Report a mistake" link on every part.
- **Quiz:** random questions from the bank, labelled "Quiz from your code".
- **Debug:** levels 1 to 20. Bugs are planted in a practice copy of a small unit (a function or file), never in the learner's real project or GitHub, and never 1,000 lines at once. The learner taps the line they suspect, edits, and runs tests. Passing a level unlocks the next.
- **Battle:** Helper or Blank. Blank hides the code, turns paste and copy off and grades by tests. Help (hint, bigger hint, solution) marks the attempt assisted.

## Bug planting
Done by code, not by the model: remove a colon, change indentation, rename a variable, flip an operator or boundary, change a return value. Early levels use syntax and indentation errors, then wrong names, then logic errors (such as off-by-one), then several bugs, then bugs across functions. The error catalog supplies the explanations.

## AI notice
Under the LATEST AI message only, show: "Smart BethG is AI and can make mistakes. Check important things." It moves to the newest message when one arrives, so older messages do not repeat it. Wording to be reviewed.

## Honest limits
- Model-written explanations can be wrong. Verification, library cross-checks, the Report a mistake link, and expert review of sampled Packs reduce this but do not remove it.
- Fixed banks can be shared between learners. That is fine for learning, not for ranked competition.
- A Pack contains the learner's code details, so it is the learner's data under the privacy policy. Nothing from a Pack goes into the shared library without removing user-specific content.
