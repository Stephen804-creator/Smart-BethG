"""Memory retrieval evaluation harness for Smart BethG.

Usage:
  python design/memory_eval/run_eval.py                    # built-in baselines
  python design/memory_eval/run_eval.py --retriever mymod:retrieve

A retriever is a function retrieve(query, corpus, k) -> list of (item_id, score).
corpus is a list of {"id", "t", "text"} dicts; t is time order (bigger = newer).
Exit code is 1 when a threshold in cases.json is not met, so CI can gate on it.
"""
import argparse
import importlib
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STOP = set("a an and are as at be by did do does for from how in is it of on or our so that the this to us was we what when where which who why with".split())


def tokens(text):
    return [w for w in re.findall(r"[a-z0-9_]+", text.lower()) if w not in STOP]


def recent_only(query, corpus, k):
    newest = sorted(corpus, key=lambda d: d["t"], reverse=True)[:k]
    return [(d["id"], 1.0) for d in newest]


def bm25(query, corpus, k, k1=1.5, b=0.75):
    docs = [tokens(d["text"]) for d in corpus]
    avg = sum(len(x) for x in docs) / len(docs)
    df = {}
    for toks in docs:
        for w in set(toks):
            df[w] = df.get(w, 0) + 1
    n = len(docs)
    q = tokens(query)
    scored = []
    for d, toks in zip(corpus, docs):
        s = 0.0
        for w in q:
            f = toks.count(w)
            if not f:
                continue
            idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
            s += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * len(toks) / avg))
        if s > 0:
            scored.append((d["id"], s))
    return sorted(scored, key=lambda x: -x[1])[:k]


BASELINES = {"recent_only": recent_only, "bm25": bm25}


def evaluate(retrieve, data, k=5, abstain_below=0.0):
    corpus = data["corpus"]
    text = {d["id"]: d["text"] for d in corpus}
    rows = []
    for c in data["cases"]:
        got = retrieve(c["query"], corpus, k)
        ids = [i for i, _ in got]
        row = {"id": c["id"], "kind": c["kind"], "chars": sum(len(text[i]) for i in ids)}
        if c["kind"] == "no_answer":
            row["pass"] = (not got) or max(s for _, s in got) <= abstain_below
        elif c["kind"] == "latest_wins":
            new, old = c["relevant"][0], c["stale"]
            row["pass"] = new in ids and (old not in ids or ids.index(new) < ids.index(old))
        else:
            rel = set(c["relevant"])
            row["recall"] = len(rel & set(ids)) / len(rel)
            row["rr"] = next((1 / (n + 1) for n, i in enumerate(ids) if i in rel), 0.0)
            row["pass"] = row["recall"] == 1.0
        rows.append(row)
    return rows


def summarize(rows, thresholds):
    ret = [r for r in rows if "recall" in r]
    lw = [r for r in rows if r["kind"] == "latest_wins"]
    na = [r for r in rows if r["kind"] == "no_answer"]
    rate = lambda xs: sum(r["pass"] for r in xs) / len(xs) if xs else 1.0
    s = {
        "recall_at_k": sum(r["recall"] for r in ret) / len(ret),
        "mrr": sum(r["rr"] for r in ret) / len(ret),
        "latest_wins": rate(lw),
        "abstain": rate(na),
        "avg_context_chars": sum(r["chars"] for r in rows) / len(rows),
        "cases_passed": sum(r["pass"] for r in rows),
        "cases_total": len(rows),
    }
    s["meets_thresholds"] = (
        s["recall_at_k"] >= thresholds["recall_at_k"]
        and s["latest_wins"] >= thresholds["latest_wins"]
        and s["abstain"] >= thresholds["abstain"]
    )
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--retriever", help="module:function to test; default runs the built-in baselines")
    ap.add_argument("--cases", default=os.path.join(HERE, "cases.json"))
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--abstain-below", type=float, default=0.0)
    args = ap.parse_args()
    data = json.load(open(args.cases))
    targets = dict(BASELINES)
    if args.retriever:
        mod, fn = args.retriever.split(":")
        targets = {args.retriever: getattr(importlib.import_module(mod), fn)}
    ok = True
    for name, fn in targets.items():
        s = summarize(evaluate(fn, data, args.k, args.abstain_below), data["thresholds"])
        print(f"{name}: recall@{args.k}={s['recall_at_k']:.2f} mrr={s['mrr']:.2f} "
              f"latest_wins={s['latest_wins']:.2f} abstain={s['abstain']:.2f} "
              f"avg_context_chars={s['avg_context_chars']:.0f} "
              f"passed={s['cases_passed']}/{s['cases_total']} thresholds={'MET' if s['meets_thresholds'] else 'NOT MET'}")
        ok = ok and s["meets_thresholds"]
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
