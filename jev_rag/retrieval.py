"""Local keyword ranking, vector similarity and reciprocal-rank fusion.

This module has no provider, UI or experiment dependencies.
"""
import math
import re
from collections import Counter

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

def unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]

def top_k(qv, unit_vecs, k):
    qv = unit(qv)
    scores = [sum(a * b for a, b in zip(qv, v)) for v in unit_vecs]
    return sorted(range(len(scores)), key=lambda i: -scores[i])[:k]

def rrf(*rankings, k=60):
    score = {}
    for ranking in rankings:
        for r, i in enumerate(ranking):
            score[i] = score.get(i, 0) + 1 / (k + r + 1)
    return sorted(score, key=lambda i: -score[i])
