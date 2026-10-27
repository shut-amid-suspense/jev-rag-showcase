"""Keywords RAG: the model writes search terms, each is searched, Jev picks, the model answers.

1. One model call reads the question (and the attached image, if any) and returns a few
   search terms in the document's likely wording, e.g. the names of controls it sees.
2. Each term, plus the question itself, runs a hybrid search (BM25 + embeddings, merged).
   All hits are merged into one pool of at most POOL passages.
3. One Jev call ranks the pool against the question and the terms; the TOP passages with
   the highest probability are kept.
4. One model call answers from those passages (classic.answer_from), naming its sources.

A fixed three calls plus one Jev call, unlike the agent's open-ended loop.
run_keywords() yields the same events as agent.run_agent(): ("stage", text) before each
stage, ("step", dict) after it, then ("done", dict).
"""

import json
import time

from .retrieval import rrf, top_k
from .agent import PROVIDERS, body_text, turn_cost
from .classic import answer_from, call_model
from .api import DECISIONS_URL, JEV_MODEL, embed, post

MAX_TERMS, PER_TERM, POOL, TOP = 6, 20, 40, 5

TERMS_TOOL = [{"type": "function", "function": {
    "name": "search_terms",
    "description": "Search terms to look up in the document.",
    "parameters": {"type": "object", "properties": {
        "terms": {"type": "array", "items": {"type": "string"}}}, "required": ["terms"]}}}]

TERMS_SYSTEM = f"""You help search one PDF document. Given the user's question, and a
screenshot if they attached one, call search_terms with 2 to {MAX_TERMS} short search
terms in the wording the document itself would likely use. Include the names of
controls, panels, settings, messages or other items the question or the screenshot
refers to, and the task the user is trying to do. Do not answer the question."""


def run_keywords(question, index, key, image=None, provider="gemini", agent_key=None):
    """Yields ("step", dict) for the terms, each search and Jev's pick, then ("done", dict)."""
    t_start = time.perf_counter()
    prov = PROVIDERS[provider]
    chunks = index["chunks"]

    content = question if not image else [{"type": "text", "text": question},
                                           {"type": "image_url", "image_url": {"url": image}}]
    body = {"model": prov["model"], "temperature": 0, "tools": TERMS_TOOL,
            "tool_choice": "required",
            "messages": [{"role": "system", "content": TERMS_SYSTEM},
                         {"role": "user", "content": content}]}
    yield "stage", "Writing search terms…"
    t0 = time.perf_counter()
    data, retries = call_model(prov, body, agent_key or key)
    cost = turn_cost(data, prov)
    calls = data["choices"][0]["message"].get("tool_calls") or []
    terms = json.loads(calls[0]["function"].get("arguments") or "{}").get("terms", []) if calls else []
    terms = [t.strip() for t in terms if isinstance(t, str) and t.strip()][:MAX_TERMS]
    yield "step", {"tool": "terms", "terms": terms, "ms": (time.perf_counter() - t0) * 1000}

    yield "stage", "Searching the PDF for " + ", ".join(f"“{t}”" for t in terms) + "…"
    t0 = time.perf_counter()
    queries = list(dict.fromkeys([question] + terms))
    vecs, _, usage = embed(queries, key)  # one request for every query
    cost += usage.get("cost", 0)
    lists = []
    for q, qv in zip(queries, vecs):
        s = index["bm25"].scores(q)
        bm_order = sorted(range(len(s)), key=lambda i: -s[i])[:PER_TERM]
        lists.append(rrf(bm_order, top_k(qv, index["uvecs"], PER_TERM))[:PER_TERM])
    # Round-robin over the lists so every term contributes its best hits to the pool.
    pool = []
    for rank in range(PER_TERM):
        for order in lists:
            if rank < len(order) and order[rank] not in pool:
                pool.append(order[rank])
    pool = [chunks[i] for i in pool[:POOL]]
    yield "step", {"tool": "pool", "queries": len(queries), "found": len(pool),
                   "ms": (time.perf_counter() - t0) * 1000}

    yield "stage", f"Picking the best of {len(pool)} passages…"
    t0 = time.perf_counter()
    jev = {"model": JEV_MODEL, "state": {"question": question, "search_terms": terms},
           "questions": {"pick": {"type": "choice",
                                  "instructions": "Which single passage best helps answer the "
                                                  "question in state?",
                                  "criteria": {c["id"]: c["text"] for c in pool}}}}
    data, _ = post(DECISIONS_URL, jev, key)
    cost += data.get("usage", {}).get("cost", 0)
    pick = data["answers"]["pick"]
    probs = pick.get("probabilities") or {pick["choice"]: 1}
    by_id = {c["id"]: c for c in pool}
    ranked = sorted(by_id, key=lambda i: -probs.get(i, 0))[:TOP]
    passages = [by_id[i] for i in ranked]
    yield "step", {"tool": "pick", "from": len(pool),
                   "ms": (time.perf_counter() - t0) * 1000,
                   "results": [{"id": c["id"], "page": c["page"], "section": c["section"],
                                "relevance": round(probs.get(c["id"], 0), 2),
                                "text": body_text(c)} for c in passages]}

    yield "stage", "Writing the answer…"
    t0 = time.perf_counter()
    answer, sources, c, r = answer_from(question, passages, image, prov, agent_key or key)
    yield "done", {"answer": answer, "sources": sources, "cost": cost + c,
                   "retries": retries + r, "turns": 2, "terms": terms,
                   "seconds": time.perf_counter() - t_start,
                   "model_ms": (time.perf_counter() - t0) * 1000}
