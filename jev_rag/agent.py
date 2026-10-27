"""Agentic retrieval over one indexed PDF: a tool-calling model searches, Jev selects.

The agent (Gemini 3.8 Flash on OpenRouter) gets three tools:
  search(query)            hybrid BM25 + embeddings shortlist of 20 passages, ranked
                           by Jev; returns the top 3 with Jev's probability
  read_page(page)          the full text of one page, for surrounding context
  final_answer(answer, passage_ids)
                           ends the run; the ids name the passages the answer uses
It may search as often as it needs (up to MAX_STEPS model turns), rephrasing
queries into the document's own terms, and must say when the PDF lacks the answer.

run_agent() is a generator of events so a UI can show each step as it happens:
("stage", text) names what it is doing now, ("step", dict) reports a finished tool
call, ("done", dict) ends the run.
"""

import json
import os
import time

from .api import CHAT_URL, DECISIONS_URL, JEV_MODEL, HTTPStatusError, embed, post
from .retrieval import rrf, top_k

# CEREBRAS_BASE_URL exists only to point a test run at a local fake service.
CEREBRAS = os.environ.get("CEREBRAS_BASE_URL", "https://api.cerebras.ai")

# Models that can drive the agent. Search (embeddings + Jev) always runs on OpenRouter.
# Cerebras returns no cost, so its cost is estimated from tokens at its published price.
PROVIDERS = {
    "gemini": {"label": "Gemini 3.8 Flash · OpenRouter", "url": CHAT_URL,
               "model": "google/gemini-3.8-flash", "key": "openrouter", "price": None},
    "qwen": {"label": "Qwen 3.8 27B · Cerebras", "url": CEREBRAS + "/v1/chat/completions",
             "model": "qwen-3.8-27b", "key": "cerebras", "price": (0.99, 1.49)},  # $ per M tokens in, out
}
AGENT_MODEL = PROVIDERS["gemini"]["model"]
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
in final_answer and pass no ids. Never answer from your own knowledge.

The user may attach an image, such as a screenshot of what they see. Use it to
understand their situation and to choose search terms, but answer only from the
document."""

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


def turn_cost(data, provider):
    usage = data.get("usage", {})
    if "cost" in usage or not provider["price"]:
        return usage.get("cost", 0)
    p_in, p_out = provider["price"]
    return (usage.get("prompt_tokens", 0) * p_in + usage.get("completion_tokens", 0) * p_out) / 1e6


def run_agent(question, index, key, image=None, provider="gemini", agent_key=None):
    """Yields ("step", dict) for each tool call, then ("done", dict).
    key: OpenRouter key (search). agent_key: key for the agent's provider (defaults to key).
    image: optional data URL of an image the user attached."""
    t_start = time.perf_counter()
    prov = PROVIDERS[provider]
    by_id = {c["id"]: c for c in index["chunks"]}
    content = question if not image else [{"type": "text", "text": question},
                                           {"type": "image_url", "image_url": {"url": image}}]
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}]
    cost, retries = 0.0, 0
    for turn in range(MAX_STEPS):
        last = turn == MAX_STEPS - 1
        yield "stage", ("Writing the answer…" if last else
                        "Deciding what to search…" if turn == 0 else "Deciding the next step…")
        body = {"model": prov["model"], "temperature": 0, "messages": messages,
                "tools": TOOLS if not last else TOOLS[2:],
                "tool_choice": "required"}
        # Cerebras sometimes fails to produce a valid tool call and answers 400 (seen at the
        # final step with an image in the conversation). At temperature 0 the same request
        # fails the same way every time; a retry at temperature 0.7 succeeded 3/3 in tests.
        for attempt in range(3):
            try:
                data, model_ms = post(prov["url"], body, agent_key or key)
                break
            except HTTPStatusError as e:
                if e.code != 400 or attempt == 2:
                    raise
                retries += 1
                body = {**body, "temperature": 0.7}
        cost += turn_cost(data, prov)
        msg = data["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        messages.append({"role": "assistant", "content": msg.get("content") or "",
                         "tool_calls": calls})
        if not calls:  # a plain-text reply despite tool_choice=required: treat as the answer
            yield "done", {"answer": msg.get("content") or "", "sources": [], "cost": cost,
                           "seconds": time.perf_counter() - t_start, "turns": turn + 1, "retries": retries}
            return
        for call in calls:
            name = call["function"]["name"]
            args = json.loads(call["function"].get("arguments") or "{}")
            if name == "final_answer":
                ids = [i for i in args.get("passage_ids", []) if i in by_id]
                yield "done", {"answer": args.get("answer", ""),
                               "sources": [by_id[i] for i in dict.fromkeys(ids)], "cost": cost,
                               "seconds": time.perf_counter() - t_start, "turns": turn + 1, "retries": retries}
                return
            if name == "search":
                yield "stage", f"Searching the PDF for “{args.get('query', '')}”…"
                top, ms, c = search(args.get("query", ""), index, key)
                cost += c
                result = top
                yield "step", {"tool": "search", "query": args.get("query", ""), "results": top,
                               "ms": ms + model_ms}
            elif name == "read_page":
                yield "stage", f"Reading page {args.get('page')}…"
                result = read_page(int(args.get("page", 0)), index)
                yield "step", {"tool": "read_page", "page": args.get("page"),
                               "results": result, "ms": model_ms}
            else:
                result = {"error": f"unknown tool {name}"}
            model_ms = 0  # the model's time counts once per turn, not once per call
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": json.dumps(result)})
    yield "done", {"answer": "", "sources": [], "cost": cost, "turns": MAX_STEPS,
                   "seconds": time.perf_counter() - t_start, "retries": retries}
