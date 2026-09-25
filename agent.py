"""Agentic retrieval over one indexed PDF: a tool-calling model searches, Jev selects.

The agent (Gemini 3.7 Flash on OpenRouter) gets three tools:
  search(query)            hybrid BM25 + embeddings shortlist of 20 passages, ranked
                           by Jev; returns the top 3 with Jev's probability
  read_page(page)          the full text of one page, for surrounding context
  final_answer(answer, passage_ids)
                           ends the run; the ids name the passages the answer uses
It may search as often as it needs (up to MAX_STEPS model turns), rephrasing
queries into the document's own terms, and must say when the PDF lacks the answer.

run_agent() is a generator of events so a UI can show each step as it happens.
"""

import json
import time

from poc import DECISIONS_URL, JEV_MODEL, embed, post
from ableton_eval import rrf
from squad_eval import CHAT_URL, top_k

AGENT_MODEL = "google/gemini-3.7-flash"
MAX_STEPS = 6
SHORTLIST, POOL, TOP = 20, 50, 3

SYSTEM = """You answer questions about one PDF document, using only its text.

Use the search tool to find passages. Write search queries in the terms the document
itself would use, not only the user's words. If the results do not answer the
question, search again with different terms. If the question has several parts,
search for each part. Use read_page when a passage is cut off or you need the rest
of its page.

Finish by calling final_answer with a brief answer and the ids of the passages it
is based on. If the document does not answer the question after searching, say so
in final_answer and pass no ids. Never answer from your own knowledge."""

TOOLS = [
    {"type": "function", "function": {
        "name": "search",
        "description": "Search the PDF. Returns the 3 most relevant passages with id, page, "
                       "section, relevance (0-1) and text.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                       "required": ["query"]}}},
    {"type": "function", "function": {
        "name": "read_page",
        "description": "Return all passages on one page of the PDF.",
        "parameters": {"type": "object", "properties": {"page": {"type": "integer"}},
                       "required": ["page"]}}},
    {"type": "function", "function": {
        "name": "final_answer",
        "description": "Give the final answer and the ids of the passages it is based on.",
        "parameters": {"type": "object", "properties": {
            "answer": {"type": "string"},
            "passage_ids": {"type": "array", "items": {"type": "string"}}},
            "required": ["answer", "passage_ids"]}}},
]


def body_text(c):
    return c["text"][len(c["label"]):]


def search(query, index, key):
    """Hybrid shortlist, then Jev ranks it. Returns (top passages, ms, cost)."""
    t0 = time.perf_counter()
    chunks = index["chunks"]
    s = index["bm25"].scores(query)
    bm_order = sorted(range(len(s)), key=lambda i: -s[i])[:POOL]
    (qv,), _, usage = embed([query], key)
    em_order = top_k(qv, index["uvecs"], POOL)
    cands = [chunks[i] for i in rrf(bm_order, em_order)[:SHORTLIST]]
    body = {"model": JEV_MODEL, "state": {"question": query},
            "questions": {"pick": {"type": "choice",
                                   "instructions": "Which single passage answers the question in state?",
                                   "criteria": {c["id"]: c["text"] for c in cands}}}}
    data, _ = post(DECISIONS_URL, body, key)
    probs = data["answers"]["pick"].get("probabilities") or {data["answers"]["pick"]["choice"]: 1}
    by_id = {c["id"]: c for c in cands}
    ranked = sorted(by_id, key=lambda i: -probs.get(i, 0))[:TOP]
    top = [{"id": i, "page": by_id[i]["page"], "section": by_id[i]["section"],
            "relevance": round(probs.get(i, 0), 2), "text": body_text(by_id[i])} for i in ranked]
    cost = usage.get("cost", 0) + data.get("usage", {}).get("cost", 0)
    return top, (time.perf_counter() - t0) * 1000, cost


def read_page(page, index):
    return [{"id": c["id"], "page": c["page"], "section": c["section"], "text": body_text(c)}
            for c in index["chunks"] if c["page"] == page]


def run_agent(question, index, key):
    """Yields ("step", dict) for each tool call, then ("done", dict)."""
    t_start = time.perf_counter()
    by_id = {c["id"]: c for c in index["chunks"]}
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    cost = 0.0
    for turn in range(MAX_STEPS):
        last = turn == MAX_STEPS - 1
        body = {"model": AGENT_MODEL, "temperature": 0, "messages": messages,
                "tools": TOOLS if not last else TOOLS[2:],
                "tool_choice": "required"}
        data, model_ms = post(CHAT_URL, body, key)
        cost += data.get("usage", {}).get("cost", 0)
        msg = data["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        messages.append({"role": "assistant", "content": msg.get("content") or "",
                         "tool_calls": calls})
        if not calls:  # a plain-text reply despite tool_choice=required: treat as the answer
            yield "done", {"answer": msg.get("content") or "", "sources": [], "cost": cost,
                           "seconds": time.perf_counter() - t_start, "turns": turn + 1}
            return
        for call in calls:
            name = call["function"]["name"]
            args = json.loads(call["function"].get("arguments") or "{}")
            if name == "final_answer":
                ids = [i for i in args.get("passage_ids", []) if i in by_id]
                yield "done", {"answer": args.get("answer", ""),
                               "sources": [by_id[i] for i in dict.fromkeys(ids)], "cost": cost,
                               "seconds": time.perf_counter() - t_start, "turns": turn + 1}
                return
            if name == "search":
                top, ms, c = search(args.get("query", ""), index, key)
                cost += c
                result = top
                yield "step", {"tool": "search", "query": args.get("query", ""), "results": top,
                               "ms": ms + model_ms}
            elif name == "read_page":
                result = read_page(int(args.get("page", 0)), index)
                yield "step", {"tool": "read_page", "page": args.get("page"),
                               "results": result, "ms": model_ms}
            else:
                result = {"error": f"unknown tool {name}"}
            model_ms = 0  # the model's time counts once per turn, not once per call
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result)})
    yield "done", {"answer": "", "sources": [], "cost": cost, "turns": MAX_STEPS,
                   "seconds": time.perf_counter() - t_start}
