"""Representative retrieval test on SQuAD v2 (dev set) — Jev vs. conventional.

Corpus: all 1,204 real Wikipedia paragraphs of the SQuAD v2 dev set (median
113 words). Questions: a seeded sample of answerable questions (gold = the
paragraph the question was written from) plus unanswerable ones (gold = none;
SQuAD v2 marks them is_impossible — no paragraph contains the answer).

Pipelines, all scored top-1 against the gold paragraph:
  bm25            local keyword search over the whole corpus
  embed           query embedding + cosine over the whole corpus
  embed>jev       embeddings shortlist top-K, Jev picks one or "none"
  embed>llm       embeddings shortlist top-K, a fast chat model picks one or
                  "none" — the conventional LLM-reranker baseline

Jev cannot take the whole corpus: a choice question caps at 255 options and
the model's context is ~32k tokens, so it always needs a shortlist here.

Usage: python3 squad_eval.py --probe       one question through every pipeline
       python3 squad_eval.py               full run, writes squad-results.json
Data:  data/squad-dev-v2.0.json from rajpurkar.github.io/SQuAD-explorer
"""

import json
import math
import os
import random
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from poc import BM25, JEV_MODEL, DECISIONS_URL, EMBED_MODEL, RETRIES, api_key, embed, post

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "squad-dev-v2.0.json")
EMB_CACHE = os.path.join(HERE, "data", "corpus-embeddings.json")
CHAT_URL = "https://openrouter.ai/api/v1/chat/completions"
LLM_MODEL = "google/gemini-3.5-flash-lite"
K = 20
N_ANSWERABLE = 200
N_UNANSWERABLE = 50
WORKERS = 4
NONE = "none"


def load():
    data = json.load(open(DATA))["data"]
    paras, qs = [], []
    for art in data:
        for p in art["paragraphs"]:
            pid = f"p{len(paras)}"
            paras.append({"id": pid, "title": art["title"], "text": p["context"]})
            for qa in p["qas"]:
                qs.append({"q": qa["question"], "gold": NONE if qa["is_impossible"] else pid})
    rnd = random.Random(2026)
    ans = rnd.sample([q for q in qs if q["gold"] != NONE], N_ANSWERABLE)
    una = rnd.sample([q for q in qs if q["gold"] == NONE], N_UNANSWERABLE)
    return paras, ans + una


def corpus_vectors(key, paras):
    if os.path.exists(EMB_CACHE):
        cached = json.load(open(EMB_CACHE))
        if cached["model"] == EMBED_MODEL and len(cached["vecs"]) == len(paras):
            return cached["vecs"]
    vecs = []
    for i in range(0, len(paras), 100):
        v, _, _ = embed([p["text"] for p in paras[i:i + 100]], key)
        vecs += v
    json.dump({"model": EMBED_MODEL, "vecs": vecs}, open(EMB_CACHE, "w"))
    return vecs


def unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


def top_k(qv, unit_vecs, k):
    qv = unit(qv)
    scores = [sum(a * b for a, b in zip(qv, v)) for v in unit_vecs]
    return sorted(range(len(scores)), key=lambda i: -scores[i])[:k]


def jev_pick(q, cands, key):
    criteria = {c["id"]: c["text"] for c in cands}
    criteria[NONE] = "None of the passages contains the answer to the question."
    body = {"model": JEV_MODEL, "state": {"question": q},
            "questions": {"passage": {
                "type": "choice",
                "instructions": "Which single passage contains the answer to the question "
                                "in state? Choose none if no passage contains it.",
                "criteria": criteria}}}
    data, ms = post(DECISIONS_URL, body, key)
    a = data["answers"]["passage"]
    return a["choice"], ms, data.get("usage", {}).get("cost", 0)


def llm_pick(q, cands, key):
    listing = "\n\n".join(f"[{c['id']}] {c['text']}" for c in cands)
    prompt = (f"Question: {q}\n\nPassages:\n\n{listing}\n\n"
              f"Reply with only the id of the single passage that contains the answer "
              f"(for example {cands[0]['id']}), or {NONE} if no passage contains it.")
    body = {"model": LLM_MODEL, "max_tokens": 20, "temperature": 0,
            "messages": [{"role": "user", "content": prompt}]}
    data, ms = post(CHAT_URL, body, key)
    text = (data["choices"][0]["message"].get("content") or "").strip().lower()
    m = re.search(r"\bp\d+\b|\bnone\b", text)
    return (m.group(0) if m else f"unparsed:{text[:30]}"), ms, data.get("usage", {}).get("cost", 0)


def run_one(item, paras, bm25, unit_vecs, key):
    q, row = item["q"], {"q": item["q"], "gold": item["gold"]}

    t0 = time.perf_counter()
    s = bm25.scores(q)
    row["bm25"] = {"pick": paras[max(range(len(s)), key=s.__getitem__)]["id"],
                   "ms": (time.perf_counter() - t0) * 1000}

    (qv,), emb_ms, _ = embed([q], key)
    t0 = time.perf_counter()
    order = top_k(qv, unit_vecs, K)
    search_ms = (time.perf_counter() - t0) * 1000
    cands = [paras[i] for i in order]
    row["recall_at_k"] = item["gold"] in {c["id"] for c in cands}
    row["embed"] = {"pick": cands[0]["id"], "ms": emb_ms, "search_ms": search_ms}

    pick, ms, cost = jev_pick(q, cands, key)
    row["embed>jev"] = {"pick": pick, "ms": emb_ms + ms, "rerank_ms": ms, "cost": cost}

    pick, ms, cost = llm_pick(q, cands, key)
    row["embed>llm"] = {"pick": pick, "ms": emb_ms + ms, "rerank_ms": ms, "cost": cost}
    return row


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p))]


def main():
    key = api_key()
    paras, items = load()
    print(f"corpus {len(paras)} paragraphs; {N_ANSWERABLE} answerable + "
          f"{N_UNANSWERABLE} unanswerable questions; shortlist K={K}")
    bm25 = BM25([p["text"] for p in paras])
    unit_vecs = [unit(v) for v in corpus_vectors(key, paras)]

    if "--probe" in sys.argv:
        row = run_one(items[0], paras, bm25, unit_vecs, key)
        print(json.dumps(row, indent=2))
        return

    rows, done = [], 0
    with ThreadPoolExecutor(WORKERS) as pool:
        for row in pool.map(lambda it: run_one(it, paras, bm25, unit_vecs, key), items):
            rows.append(row)
            done += 1
            if done % 25 == 0:
                print(f"  {done}/{len(items)}", flush=True)

    ans = [r for r in rows if r["gold"] != NONE]
    una = [r for r in rows if r["gold"] == NONE]
    pipes = ("bm25", "embed", "embed>jev", "embed>llm")
    summary = {}
    print(f"\nembedding recall@{K} (ceiling for the rerankers): "
          f"{sum(r['recall_at_k'] for r in ans)}/{len(ans)}")
    print(f"\n{'pipeline':<10} {'answerable':>11} {'said none':>10} {'unanswerable':>13}"
          f" {'median ms':>10} {'p90 ms':>7} {'cost $':>8}")
    for p in pipes:
        ok = sum(r[p]["pick"] == r["gold"] for r in ans)
        false_none = sum(r[p]["pick"] == NONE for r in ans)
        abstain = sum(r[p]["pick"] == NONE for r in una)
        ms = [r[p]["ms"] for r in rows]
        cost = sum(r[p].get("cost", 0) for r in rows)
        summary[p] = {"answerable_correct": ok, "answerable_said_none": false_none,
                      "unanswerable_said_none": abstain, "median_ms": pct(ms, .5),
                      "p90_ms": pct(ms, .9), "cost_usd": cost}
        print(f"{p:<10} {ok:>7}/{len(ans)} {false_none:>10} {abstain:>9}/{len(una)}"
              f" {pct(ms, .5):>10.0f} {pct(ms, .9):>7.0f} {cost:>8.4f}")
    for p in ("embed>jev", "embed>llm"):
        rr = [r[p]["rerank_ms"] for r in rows]
        print(f"{p} rerank call alone: median {pct(rr, .5):.0f} ms, p90 {pct(rr, .9):.0f} ms")
    print(f"local cosine search (pure Python, 1,204 vectors): median "
          f"{pct([r['embed']['search_ms'] for r in rows], .5):.0f} ms — excluded above")
    unparsed = sum(r["embed>llm"]["pick"].startswith("unparsed") for r in rows)
    print(f"llm replies that were not an id or none: {unparsed}")
    print(f"dropped connections retried: {dict(RETRIES) or 0}")

    out = os.path.join(HERE, "squad-results.json")
    json.dump({"config": {"K": K, "llm": LLM_MODEL, "jev": JEV_MODEL, "embed": EMBED_MODEL,
                          "workers": WORKERS}, "summary": summary, "rows": rows},
              open(out, "w"), indent=2)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
