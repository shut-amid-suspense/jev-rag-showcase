"""Jev as a RAG step vs. conventional retrieval — a small, reproducible POC.

Question: can OpenRouter's Jev decisions model (~typesafe/jev-latest) pick the
passage that answers a question, and how does it compare with conventional
retrieval (BM25, embeddings) on accuracy and latency?

Pipelines, each scored on top-1 accuracy and per-query latency:
  bm25          local keyword search, no network
  embed         query embedding (OpenRouter) + cosine over pre-embedded corpus
  jev_all       Jev picks one passage from the whole corpus (<=255 choices)
  embed+jev     embeddings shortlist top-K, Jev picks one of them

Stdlib only. Key: $OPENROUTER_API_KEY, else the file /tmp/or.
Usage: python3 poc.py --probe     one call per endpoint, then stop
       python3 poc.py             full run, writes results.json
"""

import json
import math
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

JEV_MODEL = "~typesafe/jev-latest"
EMBED_MODEL = "openai/text-embedding-3-small"
# OPENROUTER_BASE_URL exists only to point a test run at a local fake service.
OPENROUTER = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai")
DECISIONS_URL = OPENROUTER + "/api/alpha/decisions"
EMBED_URL = OPENROUTER + "/api/v1/embeddings"
SHORTLIST_K = 20
N_QUESTIONS = 24


# ---------------------------------------------------------------- corpus

FIRST = ["Norvale", "Brightwater", "Kestrel", "Ashgrove", "Tamsin", "Oberlin",
         "Quillon", "Marrow", "Selby", "Vantor", "Hollis", "Dunmere",
         "Pellam", "Corvid", "Lindqvist", "Rowan", "Estrel", "Galloway",
         "Fenwick", "Irongate"]
SECOND = ["Labs", "Systems"]  # every first name appears twice -> near-duplicate decoys
CITIES = ["Leipzig", "Porto", "Tampere", "Graz", "Utrecht", "Brno", "Aarhus",
          "Ghent", "Bilbao", "Kraków"]
FOUNDERS = ["Ida Brandt", "Tomas Ek", "Lea Moreau", "Jonas Petrov", "Mira Solberg",
            "Arvid Lund", "Nora Keane", "Emil Vasquez", "Sara Okafor", "Felix Duarte",
            "Hanna Ribeiro", "Luca Novak"]
PRODUCTS = [
    ("a battery-management chip", "keeps lithium cells from overheating in e-bikes"),
    ("a translation earpiece", "renders speech into another language in real time"),
    ("a crop-monitoring drone", "maps soil moisture across large farms"),
    ("a payroll platform", "pays contractors in thirty currencies"),
    ("a hospital scheduling tool", "assigns nurses to shifts automatically"),
    ("a password vault", "stores team credentials with hardware keys"),
    ("an industrial 3D printer", "prints titanium parts for aircraft"),
    ("a water-filtration membrane", "removes microplastics from tap water"),
    ("a warehouse robot", "picks parcels from shelves at night"),
    ("a solar roof tile", "looks like slate but generates electricity"),
]


def build_corpus(seed=11):
    rnd = random.Random(seed)
    companies, chunks = [], []
    for first in FIRST:
        for second in SECOND:
            name = f"{first} {second}"
            product, does = rnd.choice(PRODUCTS)
            companies.append(dict(
                name=name, founder=rnd.choice(FOUNDERS), year=rnd.randint(1985, 2021),
                city=rnd.choice(CITIES), product=product, does=does,
                staff=rnd.choice([12, 40, 85, 150, 320, 700, 1400, 5200])))
    for c in companies:
        base = len(chunks)
        chunks.append(dict(id=f"c{base}", company=c["name"], kind="origin",
            text=f"{c['name']} was founded in {c['year']} by {c['founder']}, "
                 f"who had previously worked in {c['city']}."))
        chunks.append(dict(id=f"c{base+1}", company=c["name"], kind="product",
            text=f"The flagship offering of {c['name']} is {c['product']} that {c['does']}."))
        chunks.append(dict(id=f"c{base+2}", company=c["name"], kind="size",
            text=f"{c['name']} has {c['staff']} employees, most of them at its "
                 f"headquarters in {c['city']}."))
    return companies, chunks


# Paraphrased on purpose: the question avoids the passage's own wording.
QUESTION_TEMPLATES = {
    "origin": ["Who started {n}?", "When did {n} come into existence?"],
    "product": ["What does {n} sell?", "What is {n} best known for making?"],
    "size": ["How large is the workforce at {n}?", "Where is {n}'s main office?"],
}


def build_questions(chunks, n, seed=5):
    rnd = random.Random(seed)
    picked = rnd.sample(chunks, n)
    return [dict(q=rnd.choice(QUESTION_TEMPLATES[c["kind"]]).format(n=c["company"]),
                 gold=c["id"]) for c in picked]


# ---------------------------------------------------------------- http

def api_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key and os.path.exists("/tmp/or"):
        key = open("/tmp/or").read().strip()
    if not key:
        sys.exit("No key: set OPENROUTER_API_KEY or put it in /tmp/or")
    return key


RETRIES = Counter()  # dropped connections retried, per URL


class HTTPStatusError(RuntimeError):
    """The API answered with an HTTP error; .code is the status."""

    def __init__(self, url, code, body):
        super().__init__(f"{url} -> HTTP {code}: {body[:400]!r}")
        self.code = code


def post(url, body, key, attempts=3):
    """POST JSON; retry only dropped connections. Latency is the successful attempt."""
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "jev-rag-poc/0.1"})
    for attempt in range(attempts):
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read())
            return data, (time.perf_counter() - t0) * 1000
        except urllib.error.HTTPError as e:
            raise HTTPStatusError(url, e.code, e.read()) from None
        except (ConnectionError, urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
            RETRIES[url] += 1


def embed(texts, key):
    data, ms = post(EMBED_URL, {"model": EMBED_MODEL, "input": texts}, key)
    vecs = [d["embedding"] for d in sorted(data["data"], key=lambda d: d["index"])]
    return vecs, ms, data.get("usage", {})


def jev_pick(question, candidates, key):
    body = {
        "model": JEV_MODEL,
        "state": {"question": question},
        "questions": {"passage": {
            "type": "choice",
            "instructions": "Which single passage answers the question in state?",
            "criteria": {c["id"]: c["text"] for c in candidates},
        }},
    }
    data, ms = post(DECISIONS_URL, body, key)
    ans = data["answers"]["passage"]
    return ans["choice"], ans.get("confidence"), ms, data.get("usage", {})


# ---------------------------------------------------------------- local retrieval

def tokens(s):
    return re.findall(r"[a-z0-9]+", s.lower())


class BM25:
    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs = [tokens(d) for d in docs]
        self.avg = sum(map(len, self.docs)) / len(self.docs)
        df = Counter(t for d in self.docs for t in set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = [Counter(d) for d in self.docs]
        self.k1, self.b = k1, b

    def scores(self, q):
        out = []
        for tf, d in zip(self.tf, self.docs):
            s = 0.0
            for t in tokens(q):
                if t in tf:
                    f = tf[t]
                    s += self.idf[t] * f * (self.k1 + 1) / (
                        f + self.k1 * (1 - self.b + self.b * len(d) / self.avg))
            out.append(s)
        return out


def cosine_rank(qv, vecs):
    def cos(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        return dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)))
    return sorted(range(len(vecs)), key=lambda i: -cos(qv, vecs[i]))


# ---------------------------------------------------------------- run

def probe(key, chunks):
    vecs, ms, usage = embed([chunks[0]["text"]], key)
    print(f"embeddings ok: dim={len(vecs[0])} {ms:.0f} ms usage={usage}")
    choice, conf, ms, usage = jev_pick("Who started " + chunks[0]["company"] + "?",
                                       chunks[:5], key)
    print(f"jev ok: choice={choice} (gold {chunks[0]['id']}) conf={conf} {ms:.0f} ms usage={usage}")


def main():
    key = api_key()
    companies, chunks = build_corpus()
    assert len(chunks) <= 255, "Jev choice questions cap at 255 options"
    if "--probe" in sys.argv:
        return probe(key, chunks)

    questions = build_questions(chunks, N_QUESTIONS)
    print(f"corpus: {len(chunks)} passages, {len(questions)} questions")

    bm25 = BM25([c["text"] for c in chunks])
    corpus_vecs, index_ms, _ = embed([c["text"] for c in chunks], key)
    print(f"indexed corpus embeddings once: {index_ms:.0f} ms (not counted per query)")

    rows, cost = [], {"jev_all": 0.0, "embed+jev": 0.0}
    for i, item in enumerate(questions):
        q, gold = item["q"], item["gold"]
        row = {"q": q, "gold": gold}

        t0 = time.perf_counter()
        s = bm25.scores(q)
        row["bm25"] = {"pick": chunks[max(range(len(s)), key=s.__getitem__)]["id"],
                       "ms": (time.perf_counter() - t0) * 1000}

        (qv,), emb_ms, _ = embed([q], key)
        t0 = time.perf_counter()
        order = cosine_rank(qv, corpus_vecs)
        search_ms = (time.perf_counter() - t0) * 1000
        shortlist = [chunks[j] for j in order[:SHORTLIST_K]]
        row["embed"] = {"pick": chunks[order[0]]["id"], "ms": emb_ms + search_ms,
                        "gold_in_shortlist": gold in {c["id"] for c in shortlist}}

        pick, conf, ms, usage = jev_pick(q, chunks, key)
        row["jev_all"] = {"pick": pick, "conf": conf, "ms": ms}
        cost["jev_all"] += usage.get("cost", 0)

        pick, conf, ms, usage = jev_pick(q, shortlist, key)
        row["embed+jev"] = {"pick": pick, "conf": conf, "ms": emb_ms + search_ms + ms}
        cost["embed+jev"] += usage.get("cost", 0)

        rows.append(row)
        marks = " ".join(f"{p}={'✓' if row[p]['pick'] == gold else '✗'}"
                         for p in ("bm25", "embed", "jev_all", "embed+jev"))
        print(f"{i+1:2d}. {marks}  {q}")

    print("\npipeline     top-1   median ms   p90 ms")
    summary = {}
    for p in ("bm25", "embed", "jev_all", "embed+jev"):
        ok = sum(r[p]["pick"] == r["gold"] for r in rows)
        ms = sorted(r[p]["ms"] for r in rows)
        med, p90 = ms[len(ms) // 2], ms[int(len(ms) * 0.9) - 1]
        summary[p] = {"correct": ok, "of": len(rows), "median_ms": med, "p90_ms": p90}
        print(f"{p:<11} {ok:>2}/{len(rows)}   {med:>9.1f}   {p90:>6.1f}")
    recall = sum(r["embed"]["gold_in_shortlist"] for r in rows)
    print(f"\nembedding shortlist recall@{SHORTLIST_K}: {recall}/{len(rows)}")
    print(f"Jev cost: all={cost['jev_all']:.5f} USD, shortlist={cost['embed+jev']:.5f} USD")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results.json")
    with open(out, "w") as f:
        json.dump({"summary": summary, "jev_cost_usd": cost,
                   "shortlist_recall": recall, "rows": rows}, f, indent=2)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
