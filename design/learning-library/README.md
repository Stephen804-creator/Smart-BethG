# Learning Library (v0.1)

A prepared, reviewed library of programming ideas, plus tools that turn the learner's OWN code into practice, without calling an AI model every time. Part of the Learning Engine (see LEARNING_ENGINE_CORE.md).

## Three layers
1. **Global Library (shared, never contains user code).** Concept cards, question templates and an error catalog, per language, from beginner to advanced.
2. **Project Teaching Map (per learner, derived from their code).** For each file: which constructs appear, on which lines, how often. It is stored as data next to the project. Teaching comments are NOT written into the learner's real code (professional code stays clean). A commented view can be rendered on demand.
3. **Practice engine.** Picks questions from the banks, makes gap-fill questions from the learner's own code, and grades by running code and tests. The AI model is used only for new or unusual ideas and for feedback on open-ended answers.

## Flow
1. **Parse** the learner's code with a real parser (not the AI) and list the distinct constructs used. A 1,000-line project may use only about 150 distinct ones.
2. **Map** each construct to a library card.
3. **Teach each construct once**, most frequent and most basic first, skipping what the learner already mastered. Do not walk through every line.
4. **Practice** in this order: gap-fill, predict the output, spot the error, debug a broken block, then battle (a helper version with hints, then a blank version).
5. Skipping lessons is always allowed. Build only mode never touches this.

## Rules
- Every example in a card must run. Record the language version it was checked on.
- Every generated gap-fill must have exactly one correct answer, verified by running the code (see tools/make_cloze.py).
- Randomize variants with code (names, values, order), not with the model.
- Match real error messages from the learner's own runs against the error catalog for an instant explanation, before asking any model.
- Missing construct: generate the card once, verify its examples by running them, remove all user-specific content, mark it `reviewed: false`, and add it to the shared library so the cost is paid once. An experienced developer then reviews it.
- Cards go beyond the usual tutorial: each has a "Going deeper" section.
- Hint ladder in battle mode: hint, bigger hint, solution. Using help marks the attempt assisted.
- Write original text. Link to official documentation. Do not copy text from MDN, freeCodeCamp or other courses without a checked license.
- Privacy: the Teaching Map is the user's data. The global library stores no user code.

## Files
- `_TEMPLATE.md`: the card format.
- `python/range.md`, `python/indentation.md`: sample cards (examples verified on Python 3.12.3).
- `tools/make_cloze.py`: makes gap-fill questions from Python code with no model, keeping only distractors that change the output. Usage: `python make_cloze.py script.py`.
