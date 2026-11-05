"""Make gap-fill (cloze) questions from a learner's own Python code. No AI model needed.

For each call to a known function, hide the function name and offer the right
answer plus look-alike distractors from the same category. A distractor is kept
only if running the code with it gives DIFFERENT output, so exactly one answer
is correct. Usage: python make_cloze.py script.py
"""
import ast
import json
import random
import subprocess
import sys

# Starter categories. The Learning Library owns the real, reviewed lists.
CATEGORIES = {
    "summary": ["sum", "max", "min", "len"],
    "convert": ["int", "str", "float", "bool"],
    "order": ["sorted", "reversed", "list", "set"],
}
LOOKUP = {name: cat for cat, names in CATEGORIES.items() for name in names}


def run(code):
    try:
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=3)
        return r.returncode, r.stdout
    except subprocess.TimeoutExpired:
        return -1, ""


def make_questions(source, seed=0, max_options=4):
    rng = random.Random(seed)
    base_code, base_out = run(source)
    if base_code != 0:
        raise SystemExit("The script must run cleanly first.")
    lines = source.split("\n")
    questions = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        answer = node.func.id
        if answer not in LOOKUP:
            continue
        row, col = node.func.lineno - 1, node.func.col_offset
        end = col + len(answer)
        gapped = lines[:]
        gapped[row] = lines[row][:col] + "____" + lines[row][end:]
        options = [answer]
        others = [n for n in CATEGORIES[LOOKUP[answer]] if n != answer]
        rng.shuffle(others)
        for wrong in others:
            trial = lines[:]
            trial[row] = lines[row][:col] + wrong + lines[row][end:]
            code, out = run("\n".join(trial))
            if code != 0 or out != base_out:  # distractor must give a different result
                options.append(wrong)
            if len(options) == max_options:
                break
        if len(options) < 3:
            continue  # ambiguous or too easy, skip
        rng.shuffle(options)
        questions.append({
            "type": "cloze",
            "line": row + 1,
            "code": "\n".join(gapped),
            "options": options,
            "answer": answer,
            "expected_output": base_out.strip(),
        })
    return questions


if __name__ == "__main__":
    src = open(sys.argv[1]).read()
    print(json.dumps(make_questions(src), indent=2))
