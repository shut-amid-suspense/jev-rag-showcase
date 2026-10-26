"""RAG retrieval methods measured on a real, large PDF: the Ableton Live 11 manual.

Document: data/live11-manual-en.pdf (867 pages, ~201k words), from
cdn-resources.ableton.com. Content pages 23–856; the index (857+) is excluded.

Steps (each writes a file in data/, so later steps are repeatable and cheap):
  ingest     pdftotext per page -> chunks of <=300 words, each prefixed with its
             table-of-contents section; outline from pdftohtml -> data/chunks.json
  questions  a model writes one question per sampled chunk, told not to reuse
             the chunk's wording; that chunk is the gold -> data/questions.json
  probe      one question through every method
  run        every question through every method, sequentially (one request
             at a time, so latencies are not inflated) -> ableton-results.json

Scoring: "chunk" = picked the exact gold chunk; "page" = picked any chunk on
the gold chunk's page (the manual often says the same thing twice in a page).
"""

import json
import os
import random
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from poc import BM25, DECISIONS_URL, EMBED_MODEL, JEV_MODEL, RETRIES, api_key, embed, post
from squad_eval import CHAT_URL, LLM_MODEL, pct, top_k, unit

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "data")
PDF = os.path.join(D, "live11-manual-en.pdf")
CHUNKS = os.path.join(D, "chunks.json")
QUESTIONS = os.path.join(D, "questions.json")
EMB_CACHE = os.path.join(D, "ableton-embeddings.json")
FIRST_PAGE, LAST_PAGE = 23, 856
MAX_WORDS, MIN_WORDS = 300, 25
QGEN_MODEL = "anthropic/claude-haiku-4.5"
N_SAMPLE = 150
K = 20
POOL = 50


# ---------------------------------------------------------------- ingest

def outline():
    xml = subprocess.run(["pdftohtml", "-xml", "-i", "-stdout", "-f", "1", "-l", "1", PDF],
                         capture_output=True, text=True, errors="replace").stdout
    root = ET.fromstring(xml[xml.index("<outline>"):xml.rindex("</outline>") + 10])
    items = []

    def walk(node, depth):
        for el in node:
            if el.tag == "item":
                items.append({"level": depth, "page": int(el.get("page")),
                              "title": (el.text or "").strip()})
            elif el.tag == "outline":
                walk(el, depth + 1)
    walk(root, 1)
    return items


def ingest():
    items = outline()
    pages = subprocess.run(["pdftotext", "-layout", PDF, "-"], capture_output=True,
                           text=True, errors="replace").stdout.split("\f")
    chunks = []
    for pno in range(FIRST_PAGE, LAST_PAGE + 1):
        section = [i for i in items if i["page"] <= pno][-1]["title"]
        words = pages[pno - 1].split()
        n_parts = max(1, -(-len(words) // MAX_WORDS))
        size = -(-len(words) // n_parts)
        for part in range(n_parts):
            w = words[part * size:(part + 1) * size]
            if len(w) < MIN_WORDS:
                continue
            chunks.append({"id": f"c{len(chunks)}", "page": pno, "section": section,
                           "text": f"[{section}, p. {pno}] " + " ".join(w)})
    json.dump({"outline": items, "chunks": chunks}, open(CHUNKS, "w"))
    wc = sorted(len(c["text"].split()) for c in chunks)
    print(f"{len(chunks)} chunks from pages {FIRST_PAGE}-{LAST_PAGE}; words/chunk "
          f"median {wc[len(wc) // 2]}, max {wc[-1]}; outline {len(items)} entries")


# ---------------------------------------------------------------- questions

QGEN_PROMPT = """Below is one passage from the Ableton Live 11 reference manual.

Write ONE question that a Live user might realistically type into a help search,
which this passage answers. Rules:
- Use your own everyday words; do not copy distinctive phrases from the passage.
- The question must make sense on its own, without seeing the passage.
- If the passage has no concrete, answerable information (only a heading,
  a list of names, or a figure caption), reply with exactly: SKIP

Reply with only the question, or SKIP.

Passage:
{text}"""


def questions():
    key = api_key()
    chunks = json.load(open(CHUNKS))["chunks"]
    rnd = random.Random(2026)
    pool = [c for c in chunks if len(c["text"].split()) >= 80]
    sample = rnd.sample(pool, N_SAMPLE)
    out, skipped = [], 0
    for c in sample:
        data, _ = post(CHAT_URL, {"model": QGEN_MODEL, "temperature": 0, "max_tokens": 80,
                                  "messages": [{"role": "user",
                                                "content": QGEN_PROMPT.format(text=c["text"])}]},
                       key)
        q = (data["choices"][0]["message"].get("content") or "").strip()
        if not q or q.upper().startswith("SKIP"):
            skipped += 1
            continue
        out.append({"q": q, "gold": c["id"], "page": c["page"]})
    json.dump(out, open(QUESTIONS, "w"), indent=1)
    print(f"{len(out)} questions written, {skipped} passages skipped -> {QUESTIONS}")


# ---------------------------------------------------------------- methods

def jev_choice(state_q, criteria, instructions, key):
    body = {"model": JEV_MODEL, "state": {"question": state_q},
            "questions": {"pick": {"type": "choice", "instructions": instructions,
                                   "criteria": criteria}}}
    data, ms = post(DECISIONS_URL, body, key)
    return data["answers"]["pick"]["choice"], ms, data.get("usage", {}).get("cost", 0)


def llm_pick(q, cands, key):
    listing = "\n\n".join(f"[{c['id']}] {c['text']}" for c in cands)
    prompt = (f"Question: {q}\n\nPassages:\n\n{listing}\n\nReply with only the id of the "
              f"single passage that best answers the question (for example {cands[0]['id']}).")
    data, ms = post(CHAT_URL, {"model": LLM_MODEL, "max_tokens": 20, "temperature": 0,
                               "messages": [{"role": "user", "content": prompt}]}, key)
    text = (data["choices"][0]["message"].get("content") or "").strip().lower()
    m = re.search(r"\bc\d+\b", text)
    return (m.group(0) if m else f"unparsed:{text[:30]}"), ms, data.get("usage", {}).get("cost", 0)


def rrf(*rankings, k=60):
    score = {}
    for ranking in rankings:
        for r, i in enumerate(ranking):
            score[i] = score.get(i, 0) + 1 / (k + r + 1)
    return sorted(score, key=lambda i: -score[i])


class Toc:
    """Jev navigates the table of contents: chapter -> section -> chunk. No embeddings."""

    def __init__(self, items, chunks, last_page=LAST_PAGE):
        self.last_page = last_page
        self.items = [dict(i, idx=n) for n, i in enumerate(items) if i["page"] <= last_page]
        self.chunks = chunks
        self.chapters = [i for i in self.items if i["level"] == 1]

    def _end_page(self, item):
        later = [i["page"] for i in self.items[item["idx"] + 1:] if i["level"] <= item["level"]]
        return later[0] if later else self.last_page

    def pick(self, q, key):
        total_ms = total_cost = 0
        crit = {f"ch{n}": f"{c['title']} (pages {c['page']}-{self._end_page(c)})"
                for n, c in enumerate(self.chapters)}
        ch, ms, cost = jev_choice(q, crit, "Which chapter of the Ableton Live manual answers "
                                           "the question in state?", key)
        total_ms += ms
        total_cost += cost
        chapter = self.chapters[int(ch[2:])]
        end = self._end_page(chapter)
        nxt = self._next_chapter_idx(chapter)
        secs = [i for i in self.items if chapter["idx"] < i["idx"] < nxt][:255]
        if secs:
            crit = {f"s{n}": s["title"] for n, s in enumerate(secs)}
            s, ms, cost = jev_choice(q, crit, "Which section answers the question in state?", key)
            total_ms += ms
            total_cost += cost
            sec = secs[int(s[1:])]
            lo, hi = sec["page"], self._end_page(sec)
        else:
            lo, hi = chapter["page"], end
        cands = [c for c in self.chunks if lo <= c["page"] <= hi][:254]
        crit = {c["id"]: c["text"] for c in cands}
        pick, ms, cost = jev_choice(q, crit, "Which single passage answers the question in "
                                             "state?", key)
        return pick, total_ms + ms, total_cost + cost, len(cands)

    def _next_chapter_idx(self, chapter):
        later = [c["idx"] for c in self.chapters if c["idx"] > chapter["idx"]]
        return later[0] if later else len(self.items) + 1


# ---------------------------------------------------------------- run

METHODS = ("bm25", "embed", "hybrid", "hybrid>jev", "hybrid>llm", "toc>jev")


def setup(key):
    data = json.load(open(CHUNKS))
    chunks = data["chunks"]
    bm25 = BM25([c["text"] for c in chunks])
    if os.path.exists(EMB_CACHE) and len(json.load(open(EMB_CACHE))) == len(chunks):
        vecs = json.load(open(EMB_CACHE))
    else:
        vecs = []
        for i in range(0, len(chunks), 100):
            vecs += embed([c["text"] for c in chunks[i:i + 100]], key)[0]
        json.dump(vecs, open(EMB_CACHE, "w"))
    return chunks, bm25, [unit(v) for v in vecs], Toc(data["outline"], chunks)


def run_one(item, chunks, bm25, uvecs, toc, key):
    q, row = item["q"], {"q": item["q"], "gold": item["gold"], "page": item["page"]}

    t0 = time.perf_counter()
    s = bm25.scores(q)
    bm_order = sorted(range(len(s)), key=lambda i: -s[i])[:POOL]
    bm_ms = (time.perf_counter() - t0) * 1000
    row["bm25"] = {"pick": chunks[bm_order[0]]["id"], "ms": bm_ms}

    (qv,), emb_ms, _ = embed([q], key)
    t0 = time.perf_counter()
    em_order = top_k(qv, uvecs, POOL)
    search_ms = (time.perf_counter() - t0) * 1000
    row["embed"] = {"pick": chunks[em_order[0]]["id"], "ms": emb_ms, "search_ms": search_ms}

    fused = rrf(bm_order, em_order)
    cands = [chunks[i] for i in fused[:K]]
    row["recall_at_k"] = item["gold"] in {c["id"] for c in cands}
    row["hybrid"] = {"pick": cands[0]["id"], "ms": emb_ms + bm_ms}

    pick, ms, cost = jev_choice(q, {c["id"]: c["text"] for c in cands},
                                "Which single passage answers the question in state?", key)
    row["hybrid>jev"] = {"pick": pick, "ms": emb_ms + bm_ms + ms, "step_ms": ms, "cost": cost}

    pick, ms, cost = llm_pick(q, cands, key)
    row["hybrid>llm"] = {"pick": pick, "ms": emb_ms + bm_ms + ms, "step_ms": ms, "cost": cost}

    pick, ms, cost, n = toc.pick(q, key)
    row["toc>jev"] = {"pick": pick, "ms": ms, "cost": cost, "last_step_candidates": n}
    return row


def run(probe=False):
    key = api_key()
    chunks, bm25, uvecs, toc = setup(key)
    page_of = {c["id"]: c["page"] for c in chunks}
    items = json.load(open(QUESTIONS))
    if probe:
        print(json.dumps(run_one(items[0], chunks, bm25, uvecs, toc, key), indent=2))
        return
    rows = []
    for n, it in enumerate(items, 1):
        rows.append(run_one(it, chunks, bm25, uvecs, toc, key))
        if n % 20 == 0:
            print(f"  {n}/{len(items)}", flush=True)

    print(f"\n{len(chunks)} chunks, {len(rows)} questions, sequential requests")
    print(f"hybrid recall@{K} (ceiling for hybrid>jev / hybrid>llm): "
          f"{sum(r['recall_at_k'] for r in rows)}/{len(rows)}")
    print(f"\n{'method':<11} {'chunk':>8} {'page':>8} {'median ms':>10} {'p90 ms':>7} {'cost $':>8}")
    summary = {}
    for m in METHODS:
        chunk_ok = sum(r[m]["pick"] == r["gold"] for r in rows)
        page_ok = sum(page_of.get(r[m]["pick"]) == r["page"] for r in rows)
        ms = [r[m]["ms"] for r in rows]
        cost = sum(r[m].get("cost", 0) for r in rows)
        summary[m] = {"chunk": chunk_ok, "page": page_ok, "of": len(rows),
                      "median_ms": pct(ms, .5), "p90_ms": pct(ms, .9), "cost_usd": cost}
        print(f"{m:<11} {chunk_ok:>4}/{len(rows)} {page_ok:>4}/{len(rows)} "
              f"{pct(ms, .5):>10.0f} {pct(ms, .9):>7.0f} {cost:>8.4f}")
    for m in ("hybrid>jev", "hybrid>llm"):
        st = [r[m]["step_ms"] for r in rows]
        print(f"{m} picking step alone: median {pct(st, .5):.0f} ms, p90 {pct(st, .9):.0f} ms")
    print(f"embedding call alone: median {pct([r['embed']['ms'] for r in rows], .5):.0f} ms; "
          f"cosine search (pure Python): median "
          f"{pct([r['embed']['search_ms'] for r in rows], .5):.0f} ms, not counted above")
    print(f"llm unparsed replies: {sum(r['hybrid>llm']['pick'].startswith('unparsed') for r in rows)}")
    print(f"dropped connections retried: {dict(RETRIES) or 0}")
    out = os.path.join(HERE, "ableton-results.json")
    json.dump({"config": {"K": K, "pool": POOL, "jev": JEV_MODEL, "llm": LLM_MODEL,
                          "embed": EMBED_MODEL, "qgen": QGEN_MODEL},
               "summary": summary, "rows": rows}, open(out, "w"), indent=1)
    print(f"wrote {out}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    {"ingest": ingest, "questions": questions, "probe": lambda: run(True), "run": run}[cmd]()
