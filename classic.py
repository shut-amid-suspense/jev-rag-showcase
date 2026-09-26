"""Classic RAG: one search, one answer. The baseline next to the agent in agent.py.

One hybrid search (BM25 + embeddings, merged) takes the top TOP_K passages, with no
Jev ranking and no further searches. One model call then writes the answer from
those passages and names the ones it used (the agent's final_answer tool, so the
page shows sources the same way). Works with either provider and an optional image.

run_classic() yields the same events as agent.run_agent(): one ("step", ...) for
the search, then ("done", ...).
"""

import json
import time

from ableton_eval import rrf
from agent import PROVIDERS, TOOLS, body_text, turn_cost
from poc import HTTPStatusError, embed, post
from squad_eval import top_k

TOP_K, POOL = 5, 50
FINAL_ANSWER = [t for t in TOOLS if t["function"]["name"] == "final_answer"]

SYSTEM = """You answer a question about one PDF document using only the passages given
with the question. Call final_answer with a brief answer and the ids of the passages it
is based on. If the passages do not answer the question, say so and pass no ids.
Never answer from your own knowledge.

The user may attach an image, such as a screenshot of what they see. Use it to
understand their situation, but answer only from the passages."""


def run_classic(question, index, key, image=None, provider="gemini", agent_key=None):
    """Yields ("step", dict) for the one search, then ("done", dict) like run_agent."""
    t_start = time.perf_counter()
    prov = PROVIDERS[provider]
    chunks = index["chunks"]

    s = index["bm25"].scores(question)
    bm_order = sorted(range(len(s)), key=lambda i: -s[i])[:POOL]
    (qv,), _, usage = embed([question], key)
    em_order = top_k(qv, index["uvecs"], POOL)
    passages = [chunks[i] for i in rrf(bm_order, em_order)[:TOP_K]]
    cost = usage.get("cost", 0)
    yield "step", {"tool": "search", "query": question, "ms": (time.perf_counter() - t_start) * 1000,
                   "results": [{"id": c["id"], "page": c["page"], "section": c["section"],
                                "relevance": None, "text": body_text(c)} for c in passages]}

    listing = "\n\n".join(f"[{c['id']}] (page {c['page']}"
                          + (f", {c['section']}" if c["section"] else "") + f")\n{body_text(c)}"
                          for c in passages)
    text = f"Question: {question}\n\nPassages:\n\n{listing}"
    content = text if not image else [{"type": "text", "text": text},
                                      {"type": "image_url", "image_url": {"url": image}}]
    body = {"model": prov["model"], "temperature": 0, "tools": FINAL_ANSWER,
            "tool_choice": "required",
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}]}
    retries = 0
    t_model = time.perf_counter()
    # Same as the agent: Cerebras sometimes answers 400 when it fails to produce a tool
    # call; a retry at temperature 0.7 has succeeded where temperature 0 kept failing.
    for attempt in range(3):
        try:
            data, _ = post(prov["url"], body, agent_key or key)
            break
        except HTTPStatusError as e:
            if e.code != 400 or attempt == 2:
                raise
            retries += 1
            body = {**body, "temperature": 0.7}
    cost += turn_cost(data, prov)
    msg = data["choices"][0]["message"]
    calls = msg.get("tool_calls") or []
    answer, ids = msg.get("content") or "", []
    if calls:
        args = json.loads(calls[0]["function"].get("arguments") or "{}")
        answer, ids = args.get("answer", ""), args.get("passage_ids", [])
    by_id = {c["id"]: c for c in passages}
    sources = [by_id[i] for i in dict.fromkeys(ids) if i in by_id]
    yield "done", {"answer": answer, "sources": sources, "cost": cost, "retries": retries,
                   "turns": 1, "seconds": time.perf_counter() - t_start,
                   "model_ms": (time.perf_counter() - t_model) * 1000}
