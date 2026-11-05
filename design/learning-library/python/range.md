---
id: python.range
language: python
level: beginner
prerequisites: [python.for-loop, python.function-call]
tags: [loops, sequences, numbers]
reviewed: false
last_checked: 2026-11-05
checked_on: Python 3.12.3
reference: https://docs.python.org/3/tutorial/controlflow.html#the-range-function
---

# range()

## The idea in plain words
`range()` makes a counting sequence of whole numbers. It is most often used to repeat something a set number of times. `range(5)` counts 0, 1, 2, 3, 4. It stops BEFORE the number you give it.

## When to use it
- To repeat an action a fixed number of times: `for i in range(3):`.
- To count from a start number to an end number, or to count in steps (every 2nd number, or backwards).

## When not to use it
- To go through the items of a list. Loop over the list directly (`for item in items:`) or use `enumerate(items)` if you also need the position. `range(len(items))` works but is usually harder to read.

## Rules and conventions
- Three forms: `range(stop)`, `range(start, stop)`, `range(start, stop, step)`.
- The start number is included. The stop number is NOT included.
- The numbers must be whole numbers (integers).
- `range` does not build a full list in memory. Use `list(range(...))` when you want to see the numbers.

## Common mistakes
| Broken code | Error message | Why | Fix |
|---|---|---|---|
| `list(range(0, 10, 0))` | `ValueError: range() arg 3 must not be zero` | a step of 0 would never move | use a step such as 1 or 2 |
| `list(range(2.5))` | `TypeError: 'float' object cannot be interpreted as an integer` | range needs whole numbers | use `int(2.5)` or a whole number |
| `range(1, 5)` expected to include 5 | no error, only 1 to 4 | the stop number is not included | use `range(1, 6)` |
| `range(5, 2)` gives nothing | no error, empty result | counting up from 5 can never reach 2 | use a negative step: `range(5, 2, -1)` |

## Examples (each ran on Python 3.12.3)
```python
print(list(range(5)))          # [0, 1, 2, 3, 4]
print(list(range(2, 6)))       # [2, 3, 4, 5]
print(list(range(10, 0, -3)))  # [10, 7, 4, 1]
print(list(range(5, 2)))       # []
print(len(range(2, 10, 3)))    # 3
```

## Going deeper
- `len(range(...))` works without creating the numbers, so even huge ranges are cheap.
- A negative step counts down. The start must then be larger than the stop.
- `range` is not a list. You can index it (`range(10)[3]` is 3) and slice it, but you cannot change it.

## Other languages
JavaScript has no built-in range. People write `for (let i = 0; i < 5; i++)`. In that form the stop number is also excluded, which is the same off-by-one idea.

## Questions (templates, graded by running code)
- type: cloze
  prompt: Fill the gap so the loop prints 0, 1, 2.
  code: |
    for i in ____(3):
        print(i)
  answer: range
  options: [range, len, list, sum]
- type: predict
  prompt: What does this print?
  code: print(list(range(2, 6)))
  answer: "[2, 3, 4, 5]"
- type: spot_error
  prompt: Why does this crash?
  code: print(list(range(0, 10, 0)))
  answer: "ValueError: the step cannot be 0"
- type: battle
  prompt: Write a loop that prints the numbers 1 to 5, one per line.
  tests: ["output equals 1\n2\n3\n4\n5"]
  hints: ["The stop number is not included.", "Try range(1, 6)."]
  solution: |
    for i in range(1, 6):
        print(i)
