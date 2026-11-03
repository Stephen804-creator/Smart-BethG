# Memory Evaluation (v0.1)

Purpose: decide which memory approach to use (keyword search, embeddings, live file search, or a mix) by measuring, not guessing. Any retriever can be tested with the same cases.

## Files
- `memory_eval/cases.json`: a synthetic long project conversation (30 items) and 15 test questions, with thresholds.
- `memory_eval/run_eval.py`: the harness. Run `python design/memory_eval/run_eval.py` for the built-in baselines, or `--retriever mymodule:retrieve` for your own.

A retriever is a function `retrieve(query, corpus, k)` that returns a list of `(item_id, score)`. corpus items are `{id, t, text}` where `t` is time order. To test SniperMemory, write a small adapter that loads the corpus as memory for a test user, calls the context compiler, and returns the ids and scores.

## Case types
Keyword match, paraphrase (different words, same meaning), latest-wins (a decision was later changed, so the newer fact must rank above the old one), long-range recall, multi-fact questions, and no-answer (the system should return nothing, not guess).

## Metrics and starting thresholds
- recall@k at least 0.80 (every needed fact found in the top k)
- latest-wins 1.00
- abstain 1.00 (no answer means no result)
- Also report average context size, latency and cost.

## Baseline results (toy retrievers, not the real system)
| Retriever | recall@5 | MRR | latest-wins | abstain |
|---|---|---|---|---|
| recent only | 0.17 | 0.04 | 0.00 | 0.00 |
| keyword (BM25) | 0.83 | 0.92 | 0.00 | 1.00 |

Reading: keyword search finds most facts, but it does not know which version of a decision is newest. Any memory system needs a rule for superseded facts (mark old decisions as superseded, or prefer newer items on the same topic), whatever retrieval method it uses. Paraphrase questions are where embeddings might help. Test that before adding them.

## Decision rule
Adopt embeddings (for example pgvector) only if they improve paraphrase recall without hurting latest-wins, latency or cost on these cases plus a larger set from real usage.

## Still to add
Scale tests (thousands of items), a privacy test (one user can never retrieve another user's memory), staleness checks, and a cost measurement. Prompt caching (PR #6) lowers the cost of repeated prefixes. It is not memory and should be measured separately.
