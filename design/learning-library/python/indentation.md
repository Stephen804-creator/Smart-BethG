---
id: python.indentation
language: python
level: beginner
prerequisites: []
tags: [syntax, blocks, errors]
reviewed: false
last_checked: 2026-11-05
checked_on: Python 3.12.3
reference: https://docs.python.org/3/reference/lexical_analysis.html#indentation
---

# Indentation

## The idea in plain words
In Python, the empty space at the start of a line tells the computer which lines belong together. A line that ends with a colon (`:`) opens a group of lines, called a block. Every line in that block must be pushed in by the same amount. Python does not use curly brackets for this, so the spaces ARE the structure.

## When to use it
Always, after any line that ends with a colon: `if`, `for`, `while`, `def`, `class`, `try`, `else`, and so on.

## When not to use it
Do not indent a line that is not inside a block. Extra indentation on a normal line is an error.

## Rules and conventions
- Use 4 spaces for each level (the Python style guide, PEP 8).
- Every line in the same block uses the same amount.
- Do not mix tabs and spaces. Set your editor to insert 4 spaces when you press Tab.
- When you paste code, check that it sits at the right depth. Pasted lines that are 4 spaces too shallow or too deep cause errors.

## Common mistakes
| Broken code | Error message (Python 3.12) | Why | Fix |
|---|---|---|---|
| `if True:` then an unindented `print('hi')` | `IndentationError: expected an indented block after 'if' statement on line 1` | the block after the colon is empty | push the next line in by 4 spaces |
| second line of a block indented less than the first | `IndentationError: unindent does not match any outer indentation level` | lines in one block must match | use the same indentation for each line |
| one line indented with a tab, the next with spaces | `TabError: inconsistent use of tabs and spaces in indentation` | tabs and spaces were mixed | use only spaces |

## Examples (each ran on Python 3.12.3)
```python
for i in range(3):
    print(i)
```
Output: 0, 1, 2 on separate lines.

Same idea, different place. Indentation changes what happens:
```python
total = 0
for n in [1, 2, 3]:
    total = total + n
print(total)        # prints 6 (after the loop)
```
```python
total = 0
for n in [1, 2, 3]:
    total = total + n
    print(total)    # prints 1, then 3, then 6 (inside the loop)
```

## Going deeper
- Indentation can change what a program does without causing any error, as in the second example. This is why it is a bug that hides.
- A line that continues inside brackets, like a long list, may be indented freely. The block rules apply to statements, not to lines inside brackets.
- Formatters such as `ruff format` or `black` fix indentation style for you.

## Other languages
JavaScript, Java and C use curly brackets `{ }` to mark blocks, so indentation is only for readability there. In Python it is part of the grammar.

## Questions (templates, graded by running code)
- type: spot_error
  prompt: This code crashes. What is wrong?
  code: |
    if True:
    print('hi')
  answer: "The line after the colon is not indented."
- type: predict
  prompt: What does this print? Look at where the print line sits.
  code: |
    total = 0
    for n in [1, 2, 3]:
        total = total + n
    print(total)
  answer: "6"
- type: debug
  prompt: Make this print only the final total, once.
  code: |
    total = 0
    for n in [1, 2, 3]:
        total = total + n
        print(total)
  answer: "Move print(total) out of the loop (remove its 4 extra spaces)."
- type: battle
  prompt: Write a loop that adds 1, 2 and 3 into total and then prints total once.
  tests: ["output equals 6"]
  hints: ["Where should the print line start?", "The print line should not be indented."]
