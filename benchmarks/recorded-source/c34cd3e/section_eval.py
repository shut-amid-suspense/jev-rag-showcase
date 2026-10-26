"""Does cutting the PDF by table-of-contents section beat cutting it by page?

Same document (Ableton Live 11 manual, pages 23–856) and the same 149 questions as
ableton_eval.py, three ways of cutting the text:
  page          each page split into pieces of <=300 words (what the app does today)
  section+page  cut at every table-of-contents heading and at every page break, so
                each piece is one section on one page (<=300 words)
  section       cut at every heading only; long sections split into <=300 words,
                pieces may span two pages

All are scored the same way, by page: a pick is a hit when the piece covers the
page the question was written from. "section" pieces can span two pages, an
advantage under this scoring; "section+page" removes it and is the fair comparison.

Run: .venv/bin/python section_eval.py      (writes section-results.json)
"""

import json
import os
import re
import subprocess
import time

from ableton_eval import FIRST_PAGE, LAST_PAGE, MAX_WORDS, MIN_WORDS, PDF, QUESTIONS, jev_choice, outline, rrf
from poc import BM25, api_key, embed
from squad_eval import pct, top_k, unit

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "data", "section-embeddings.json")
CACHE_SP = os.path.join(HERE, "data", "section-page-embeddings.json")
PAGE_CACHE = os.path.join(HERE, "data", "ableton-embeddings.json")
K, POOL = 20, 50
PICK = "Which single passage answers the question in state?"


def page_texts():
    out = subprocess.run(["pdftotext", "-layout", PDF, "-"], capture_output=True,
                         text=True, errors="replace").stdout
    return out.split("\f")


def split_even(words, pages):
    """Split a word list (with a parallel page list) into even pieces of <=MAX_WORDS."""
    n = max(1, -(-len(words) // MAX_WORDS))
    size = -(-len(words) // n)
    for i in range(n):
        w, p = words[i * size:(i + 1) * size], pages[i * size:(i + 1) * size]
        if len(w) >= MIN_WORDS:
            yield w, p


def page_chunks(pages):
    items = outline()
    chunks = []
    for pno in range(FIRST_PAGE, LAST_PAGE + 1):
        section = [i for i in items if i["page"] <= pno][-1]["title"]
        words = pages[pno - 1].split()
        for w, p in split_even(words, [pno] * len(words)):
            chunks.append({"id": f"p{len(chunks)}", "pages": [pno],
                           "text": f"[{section}, p. {pno}] " + " ".join(w)})
    return chunks


def section_chunks(pages, cut_pages=False, prefix="s"):
    """Cut at each heading's position (and, with cut_pages, at every page break);
    returns (chunks, headings found, total)."""
    items = [i for i in outline() if FIRST_PAGE <= i["page"] <= LAST_PAGE]
    words, word_pages = [], []
    page_start = {}
    for pno in range(FIRST_PAGE, LAST_PAGE + 1):
        page_start[pno] = len(words)
        w = pages[pno - 1].split()
        words += w
        word_pages += [pno] * len(w)
    # Find where each heading starts: its words, in order, on or after its page start.
    cuts, found = [], 0
    for item in items:
        title = item["title"].split()
        lo = max(page_start[item["page"]], cuts[-1][0] if cuts else 0)
        hi = page_start.get(item["page"] + 1, len(words))
        pos = None
        for j in range(lo, max(lo, hi - len(title) + 1)):
            if words[j:j + len(title)] == title:
                pos = j
                break
        if pos is None:
            pos = max(page_start[item["page"]], lo)  # not found: cut at its page start
        else:
            found += 1
        cuts.append((pos, item["title"]))
    if cut_pages:  # page breaks become cuts too, keeping the section title in force
        titled = sorted(cuts)
        for pno, start in page_start.items():
            current = [t for pos, t in titled if pos <= start]
            if current:
                cuts.append((start, current[-1]))
        cuts = sorted(set(cuts), key=lambda c: c[0])
        cuts = [c for i, c in enumerate(cuts) if i == 0 or c[0] != cuts[i - 1][0]]
    cuts.append((len(words), None))
    chunks = []
    for (start, title), (end, _) in zip(cuts, cuts[1:]):
        for w, p in split_even(words[start:end], word_pages[start:end]):
            span = f"p. {p[0]}" if p[0] == p[-1] else f"pp. {p[0]}–{p[-1]}"
            chunks.append({"id": f"{prefix}{len(chunks)}", "pages": sorted(set(p)),
                           "text": f"[{title}, {span}] " + " ".join(w)})
    return chunks, found, len(items)


def vectors(chunks, key, cache):
    if os.path.exists(cache):
        v = json.load(open(cache))
        if len(v) == len(chunks):
            return v
    v = []
    for i in range(0, len(chunks), 100):
        v += embed([c["text"] for c in chunks[i:i + 100]], key)[0]
    json.dump(v, open(cache, "w"))
    return v


def evaluate(name, chunks, uvecs, questions, key):
    bm25 = BM25([c["text"] for c in chunks])
    by_id = {c["id"]: c for c in chunks}
    hits = {"bm25": 0, "embed": 0, "hybrid": 0, "hybrid>jev": 0}
    recall, jev_ms, cost = 0, [], 0.0
    for q in questions:
        s = bm25.scores(q["q"])
        bm = sorted(range(len(s)), key=lambda i: -s[i])[:POOL]
        (qv,), _, usage = embed([q["q"]], key)
        cost += usage.get("cost", 0)
        em = top_k(qv, uvecs, POOL)
        cands = [chunks[i] for i in rrf(bm, em)[:K]]
        hit = lambda c: q["page"] in c["pages"]
        hits["bm25"] += hit(chunks[bm[0]])
        hits["embed"] += hit(chunks[em[0]])
        hits["hybrid"] += hit(cands[0])
        recall += any(hit(c) for c in cands)
        pick, ms, c = jev_choice(q["q"], {c["id"]: c["text"] for c in cands}, PICK, key)
        jev_ms.append(ms)
        cost += c
        hits["hybrid>jev"] += bool(pick in by_id and hit(by_id[pick]))
    words = sorted(len(c["text"].split()) for c in chunks)
    return {"chunks": len(chunks), "median_words": words[len(words) // 2],
            "avg_pages_per_chunk": round(sum(len(c["pages"]) for c in chunks) / len(chunks), 2),
            "hits": hits, "shortlist_recall": recall, "of": len(questions),
            "jev_median_ms": round(pct(jev_ms, .5)), "cost_usd": round(cost, 4)}


def main():
    key = api_key()
    pages = page_texts()
    questions = json.load(open(QUESTIONS))
    pc = page_chunks(pages)
    sc, found, total = section_chunks(pages)
    spc, _, _ = section_chunks(pages, cut_pages=True, prefix="sp")
    print(f"headings located in the text: {found}/{total}")
    results = {}
    names = ("page", "section+page", "section")
    for name, chunks, cache in (("page", pc, PAGE_CACHE), ("section+page", spc, CACHE_SP),
                                ("section", sc, CACHE)):
        t0 = time.perf_counter()
        uvecs = [unit(v) for v in vectors(chunks, key, cache)]
        results[name] = evaluate(name, chunks, uvecs, questions, key)
        print(f"{name}: done in {time.perf_counter() - t0:.0f} s", flush=True)
    n = results["page"]["of"]
    row = lambda label, f: print(f"{label:<22}" + "".join(f"{f(results[k]):>16}" for k in names))
    print("\n" + " " * 22 + "".join(f"{k:>16}" for k in names))
    row("pieces", lambda r: r["chunks"])
    row("median words", lambda r: r["median_words"])
    row("avg pages per piece", lambda r: r["avg_pages_per_chunk"])
    for m in ("bm25", "embed", "hybrid", "hybrid>jev"):
        row(m, lambda r: f"{r['hits'][m]}/{n}")
    row("shortlist recall@20", lambda r: f"{r['shortlist_recall']}/{n}")
    row("Jev median ms", lambda r: r["jev_median_ms"])
    row("cost $", lambda r: r["cost_usd"])
    json.dump({"headings_found": found, "headings_total": total, "results": results},
              open(os.path.join(HERE, "section-results.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
