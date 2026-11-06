# Smart BethG Teaching Style Guide: How the AI Explains Code

Draft v0.1. The AI must read this before it writes any reading part, quiz explanation or hint in a Learning Pack. Every claim about what code does must be checked by running it.

## 1. Why this exists

A thin explanation leaves a beginner with more questions than they started with. Take this one: "A route connects a web address to a function. Line 7 says `@app.post("/api/problems")`." A beginner immediately asks:

- What is a web address? What is a function?
- How does this line connect the two? What is `@app`?
- Why `.post`? Why the slash, `api` and `problems`? Must it be in quotes?
- What happens if I remove the line, or forget the slash?
- How will I know when to use it, and when not to?

This guide makes the AI answer those questions before the learner has to ask them.

## 2. The rules

1. **Start at the real beginning.** List what the learner must already know (a "Before this you need" ladder) and teach any missing step first. Build up in order: web address, request, function, then the line itself.
2. **Define every term before using it,** in plain words with one example. No word may appear undefined. If a term will be explained later, say exactly where ("explained in Stage 5").
3. **Take the line apart.** Show it piece by piece and label each piece: Fixed (must be exactly this), Your choice (you pick the name), Convention (customary, not required) or Required punctuation. Say why each piece exists.
4. **Show the mechanism.** Build a tiny runnable model (5 to 15 lines) of what the line does behind the scenes, run it and show the output.
5. **Tell the story in order.** "You press Submit. The browser sends a message to this address. The app looks the address up. It finds the function and runs it."
6. **What if I remove it? What if I change it?** For every piece, say what happens, from a real run, with the exact message or behavior.
7. **Why this and not another?** Compare with the alternatives (for example `post` and `get`).
8. **Is it a must?** Answer every "must it be...?" question (quotes, slash, name, order).
9. **Common mistakes,** with the exact error message and the fix.
10. **When to use it, and when it does NOT fit.** Include cases where the construct does not belong in the learner's design.
11. **Connect to the learner's design.** After the learner sketches their plan in plain words or pseudocode, ask which pieces they would use and why, before showing code.
12. **Check understanding three ways:** predict, what-if, and explain-back (say it in your own words).
13. **Question audit.** Before publishing, write the 15 questions a beginner is most likely to ask about this part. Each must be answered, or deferred in writing with where it will be answered.
14. **Chunk, do not cut.** There is no limit on total depth. Split into parts. Each part answers one main question, ends with a quick check and offers "Continue reading". Never drop steps just to be short. Offer "Explain it simpler".
15. **Be honest.** Verify every claim by running it, state the language and framework version, and label anything not run as "not verified". Keep the "Report a mistake" link.
16. **Tone:** friendly, short sentences, the learner's own names and lines, no jargon, no shame.

## 3. Reading part template

Title as a question. Before this you need. Plain words. The line in pieces (a table of: piece, what it is, fixed or your choice or convention, what happens if removed or changed). See it work (tiny model and output). The step-by-step story. What if. Why this and not that. When it does not fit. Common mistakes. Check: predict, what-if, explain-back. Continue reading.

## 4. Worked example: the route line

**Part 1. Before this: three words you need**

- **Web address.** The text that says where to go, like `https://mysite.com/api/problems`. The part after the site name, `/api/problems`, is the **path**. Think of the site as a building and the path as the room number.
- **Request.** When you press Submit, your browser sends a message to that address. A request has a kind. **GET** means "give me something". **POST** means "here is new data, please save it".
- **Function.** A named block of code that does one job. `add_problem` saves a problem.

Your app needs a way to decide which function handles which request. That decision is called a **route**.

**Part 2. The line, piece by piece:** `@app.post("/api/problems")`

| Piece | What it is | Type | If removed or changed |
|---|---|---|---|
| `@` | Attaches what follows to the function below it (Python calls this a decorator) | Fixed | The function is never connected to an address |
| `app` | Your app object, created earlier on the line `app = FastAPI()` | Your choice, but it must match the earlier line | Python stops: name not found |
| `.post` | "Handle POST requests", the kind a form sends to save data | Fixed (frameworks offer `get`, `post`, `put`, `delete`) | Another name means another kind of request |
| `( )` | Hold the address | Required punctuation | Syntax error |
| `" "` | Quotes mean "this is text, not code" | Required punctuation | `SyntaxError: invalid syntax` |
| `/api/problems` | The path to match | Your choice, but it must exactly match the address the form sends to | Requests get "404 Not Found" |

Conventions: the path starts with `/`; `api` marks "this is for programs, not a page people see"; `problems` names what is handled, usually plural.

**Part 3. See the mechanism.** This is a tiny model, not the real framework, but it shows the idea. It ran on Python 3.12.3.

```python
routes = {}

class App:
    def post(self, address):
        def register(function):
            routes[("POST", address)] = function
            return function
        return register

app = App()

@app.post("/api/problems")
def add_problem():
    return "saved"

def handle(method, address):
    function = routes.get((method, address))
    if function is None:
        return "404 Not Found"
    return function()

print(list(routes))
print(handle("POST", "/api/problems"))
```

Output: `[('POST', '/api/problems')]` then `saved`. The `@` line wrote an entry in a lookup list (`routes`). When a request arrives, the app looks it up, finds `add_problem` and runs it.

**Part 4. What if...?** (each result is from running the model above)

| Change | Result |
|---|---|
| Delete the `@app.post(...)` line | `routes` is empty, so every request gets `404 Not Found` |
| Change the path by one letter (`/api/problem`) | `404 Not Found` |
| Ask with GET instead of POST | `404 Not Found`, because only POST was registered |
| Remove the quotes | `SyntaxError: invalid syntax` |
| Write `api/problems` with no leading slash | It registers, but browsers always send addresses starting with `/`, so nothing matches and requests get `404 Not Found` |

In the real framework, some of these may show a different error message. The generator must run the real code in the sandbox and report the real message. The toy model has not been checked against the real framework.

**Part 5. Why `post` and not `get`?** Rule of thumb: GET reads, POST sends something new to be saved. A form that saves a problem uses POST.

**Part 6. When it does NOT fit.** A helper function that is only called by other code, like `save(data)`, has no route and no `@` line. A route is only for functions that web requests should reach.

**Part 7. Check yourself**

- **Predict:** if the form sends to `/api/problem` (no `s`), what does the user get?
- **What if:** you delete the `@` line. What breaks, and what still works?
- **Explain back:** say in your own words what `.post("/api/problems")` tells the app.

## 5. Automatic checks on every explanation

- A glossary check finds any word that is not defined and not in the learner's known-terms list.
- Every "what if" row carries a recorded run result.
- Every piece of the line appears in the pieces table with a type.
- The question audit list exists and every item is answered or deferred in writing.
- Every line number mentioned exists.
- Every part ends with a quick check.
- If a check fails, regenerate once, then fall back to library-only content.

## 6. Where it fits

This guide is an input to the Learning Pack generator, together with the Core Rules, the Clean Code Rules and the Learning Library cards (see LEARNING_PACK.md).

## 7. Limits

- Longer explanations cost more tokens, so measure the cost per stage.
- Over-explaining can overwhelm. The learner can skip, and the engine should shorten depth when the learner passes checks alone.
- A toy model shows the idea, but real framework behavior must be run in the sandbox before it is stated as fact.
