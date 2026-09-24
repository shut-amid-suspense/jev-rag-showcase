"""Ask a large PDF — answers from a large PDF, with a live comparison of RAG methods.

Upload a PDF and it is indexed right away. Ask a question: the answer comes from
the Hybrid → Jev method (BM25 + embeddings shortlist 20 passages, Jev picks one,
a small chat model writes the answer from that one passage) and is shown as soon
as it is ready. The other five methods keep running and fill the "Compare
methods" panel when they finish.

Run:  .venv/bin/python app.py      (then open the printed local URL)
Key:  Settings → OpenRouter key, else $OPENROUTER_API_KEY, else the file /tmp/or.
"""

import os
import re
import time
import traceback
import urllib.error
from concurrent.futures import ThreadPoolExecutor

import gradio as gr
import pymupdf

from ableton_eval import Toc, jev_choice, llm_pick, rrf
from poc import BM25, HTTPStatusError, embed, post
from squad_eval import CHAT_URL, LLM_MODEL, top_k, unit

MAX_WORDS, MIN_WORDS, K, POOL = 300, 25, 20, 50
PICK = "Which single passage answers the question in state?"
M_BM25, EMB, HYB = "BM25", "Embeddings", "Hybrid"
JEV, LLM, TOC = "Hybrid → Jev", "Hybrid → Gemini", "Jev via contents"
ORDER = (M_BM25, EMB, HYB, JEV, LLM, TOC)
USED = JEV  # the method whose passage the answer is written from
POOL_EXEC = ThreadPoolExecutor(8)


def friendly(e):
    """Plain-language message for a failure; the full error goes to the server log."""
    traceback.print_exception(e)
    if isinstance(e, HTTPStatusError):
        if e.code == 401:
            return "OpenRouter rejected the API key. Check it under Settings."
        if e.code == 402:
            return "Your OpenRouter account is out of credit."
        if e.code == 429:
            return "OpenRouter is rate-limiting requests. Wait a moment and try again."
        return f"OpenRouter returned an error ({e.code}). Try again."
    if isinstance(e, (ConnectionError, urllib.error.URLError, TimeoutError)):
        return "Couldn't reach OpenRouter. Check your connection and try again."
    return f"Something went wrong ({type(e).__name__}). Try again."


def md_escape(text):
    """Show source text literally: brackets, asterisks etc. must not become Markdown."""
    return re.sub(r"([\\`*_{}\[\]<>#|~])", r"\\\1", text)


def get_key(field):
    key = (field or "").strip() or os.environ.get("OPENROUTER_API_KEY", "")
    if not key and os.path.exists("/tmp/or"):
        key = open("/tmp/or").read().strip()
    return key


# ---------------------------------------------------------------- indexing

def build_index(pdf_path, key_field, progress=gr.Progress()):
    """Returns (index or None, status markdown). Never raises: failures become a status."""
    if not pdf_path:
        gr.Warning("Upload a PDF first.")
        return None, ""
    name = os.path.basename(pdf_path)
    key = get_key(key_field)
    if not key:
        return None, f"**{name}** · no OpenRouter key — enter one under Settings, then press **Index again**."
    try:
        t0 = time.perf_counter()
        progress(0, desc="Reading the PDF…")
        doc = pymupdf.open(pdf_path)
        outline = [{"level": lvl, "title": " ".join(title.split()), "page": page}
                   for lvl, title, page in doc.get_toc() if page >= 1]
        chunks = []
        for pno, page in enumerate(doc, 1):
            words = page.get_text().split()
            before = [i for i in outline if i["page"] <= pno]
            section = before[-1]["title"] if before else ""
            label = f"[{section}, p. {pno}] " if section else f"[p. {pno}] "
            n_parts = max(1, -(-len(words) // MAX_WORDS))
            size = -(-len(words) // n_parts)
            for part in range(n_parts):
                w = words[part * size:(part + 1) * size]
                if len(w) >= MIN_WORDS:
                    chunks.append({"id": f"c{len(chunks)}", "page": pno, "section": section,
                                   "label": label, "text": label + " ".join(w)})
        if not chunks:
            return None, (f"**{name}** · no text found. This looks like a scanned PDF "
                          f"without a text layer, so it can't be searched.")
        progress(0.2, desc=f"Indexing {len(chunks)} passages…")
        batches = [chunks[i:i + 100] for i in range(0, len(chunks), 100)]
        results = list(POOL_EXEC.map(lambda b: embed([c["text"] for c in b], key), batches))
        vecs = [v for r in results for v in r[0]]
        cost = sum(r[2].get("cost", 0) for r in results)
        index = {"name": name, "chunks": chunks, "bm25": BM25([c["text"] for c in chunks]),
                 "uvecs": [unit(v) for v in vecs],
                 "toc": Toc(outline, chunks, last_page=len(doc)) if outline else None,
                 "chapters": sum(1 for i in outline if i["level"] == 1)}
        return index, (f"**{name}** · {len(doc)} pages · {len(chunks)} passages · "
                       f"**ready** · indexed in {time.perf_counter() - t0:.0f} s for ${cost:.4f}")
    except Exception as e:
        return None, f"**{name}** · indexing failed. {friendly(e)} Then press **Index again**."


# ---------------------------------------------------------------- asking

def history_md(history):
    if not history:
        return ""
    lines = [f"- {md_escape(h['q'])} · p. {h['page']}" for h in history]
    return "**Earlier questions**\n\n" + "\n".join(lines)


def ask(question, index, key_field, history):
    """Generator: yields the answer as soon as Jev's path is done, then the comparison."""
    history = history or []
    if not index:
        gr.Warning("The PDF isn't ready yet. Upload one, or wait until it says “ready”.")
        yield gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
        return
    if not (question or "").strip():
        gr.Warning("Type a question first.")
        yield gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
        return
    key = get_key(key_field)
    t_start = time.perf_counter()
    chunks, by_id = index["chunks"], {c["id"]: c for c in index["chunks"]}
    res = {}
    try:
        t0 = time.perf_counter()
        s = index["bm25"].scores(question)
        bm_order = sorted(range(len(s)), key=lambda i: -s[i])[:POOL]
        bm_ms = (time.perf_counter() - t0) * 1000
        res[M_BM25] = (chunks[bm_order[0]]["id"], bm_ms, 0.0)
        (qv,), emb_ms, usage = embed([question], key)
    except Exception as e:
        gr.Warning(friendly(e))
        yield gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
        return
    emb_cost = usage.get("cost", 0)
    t0 = time.perf_counter()
    em_order = top_k(qv, index["uvecs"], POOL)
    search_ms = (time.perf_counter() - t0) * 1000
    res[EMB] = (chunks[em_order[0]]["id"], emb_ms + search_ms, emb_cost)
    cands = [chunks[i] for i in rrf(bm_order, em_order)[:K]]
    base_ms = bm_ms + emb_ms + search_ms
    res[HYB] = (cands[0]["id"], base_ms, emb_cost)

    def run_jev():
        pick, ms, cost = jev_choice(question, {c["id"]: c["text"] for c in cands}, PICK, key)
        return pick, base_ms + ms, emb_cost + cost

    def run_llm():
        pick, ms, cost = llm_pick(question, cands, key)
        return pick, base_ms + ms, emb_cost + cost

    def run_toc():
        if not index["toc"] or not index["chapters"]:
            raise LookupError("this PDF has no table of contents")
        if index["chapters"] > 255:
            raise LookupError("more than 255 chapters")
        pick, ms, cost, _ = index["toc"].pick(question, key)
        return pick, ms, cost

    futures = {JEV: POOL_EXEC.submit(run_jev), LLM: POOL_EXEC.submit(run_llm),
               TOC: POOL_EXEC.submit(run_toc)}

    def result(name):
        try:
            return futures[name].result()
        except LookupError as e:  # an expected "can't run here", shown as-is
            return (f"not available: {e}", 0.0, 0.0)
        except Exception as e:
            return (f"failed: {friendly(e)}", 0.0, 0.0)

    # 1) The answer, from the passage Jev picked — shown without waiting for the others.
    res[JEV] = result(JEV)
    jev_pick = res[JEV][0]
    p = by_id.get(jev_pick)
    if p:
        prompt = (f"Answer the question using only this passage. If the passage does not "
                  f"answer it, say so. Be brief.\n\nPassage (page {p['page']}):\n{p['text']}"
                  f"\n\nQuestion: {question}")
        try:
            data, ans_ms = post(CHAT_URL, {"model": LLM_MODEL, "max_tokens": 300, "temperature": 0,
                                           "messages": [{"role": "user", "content": prompt}]}, key)
            text = (data["choices"][0]["message"].get("content") or "").strip()
            ans_cost = data.get("usage", {}).get("cost", 0)
        except Exception as e:
            text, ans_ms, ans_cost = f"Couldn't write the answer: {friendly(e)}", 0, 0
        wall = time.perf_counter() - t_start
        quote = p["text"][len(p["label"]):]
        quote = md_escape(quote[:600]) + ("…" if len(quote) > 600 else "")
        where = f"Page {p['page']}" + (f" · {p['section']}" if p["section"] else "")
        answer_md = (f"### Answer\n{text}\n\n**{where}**\n\n> {quote}\n\n"
                     f"<small>Found by **{USED}** · answer in {wall:.1f} s · "
                     f"cost ${res[JEV][2] + ans_cost:.4f}</small>")
    else:
        answer_md = f"### Answer\nNo answer: {USED} couldn't pick a passage ({jev_pick})."
    yield (answer_md, gr.update(label="Compare methods · still running…"), [],
           "", gr.skip(), gr.skip())

    # 2) The comparison, once every method has finished.
    res[LLM], res[TOC] = result(LLM), result(TOC)
    used_page = p["page"] if p else None
    rows, details, agree = [], [], 0
    for name in ORDER:
        pick, ms, cost = res[name]
        c = by_id.get(pick)
        agree += bool(c and used_page and c["page"] == used_page)
        label = f"{name} ✓ used for answer" if name == USED else name
        rows.append([label if c else f"{name} — {pick}", c["page"] if c else "—",
                     round(ms), f"{cost * 1000:.2f}"])
        if c:
            where = f"page {c['page']}" + (f" · {c['section']}" if c["section"] else "")
            details.append(f"**{name}** — {where}\n\n> {md_escape(c['text'][len(c['label']):][:800])}\n")
    summary = (f"Compare methods · {agree} of {len(ORDER)} picked page {used_page}"
               if used_page else "Compare methods")
    earlier = history_md(history)
    history = [{"q": question.strip(), "page": used_page or "—"}] + history
    yield (gr.skip(), gr.update(label=summary), rows,
           "**Passage each method picked**\n\n" + "\n---\n".join(details), history, earlier)


def on_new_pdf(pdf_path, key_field, progress=gr.Progress()):
    index, status = build_index(pdf_path, key_field, progress)
    return index, status, "", gr.update(label="Compare methods"), [], "", [], ""


def indexing_notice(pdf_path):
    """Shown the moment a PDF arrives, so the wait is visible before indexing starts."""
    if not pdf_path:
        return None, "", "", gr.update(label="Compare methods"), [], "", [], ""
    name = os.path.basename(pdf_path)
    return (None, f"**{name}** · indexing… (large PDFs take up to a minute)", "",
            gr.update(label="Compare methods"), [], "", [], "")


def on_clear():
    return None, "", "", gr.update(label="Compare methods"), [], "", [], ""


# ---------------------------------------------------------------- UI

with gr.Blocks(title="Ask a large PDF") as demo:
    gr.Markdown("# Ask a large PDF\nUpload a PDF and ask questions about it. Answers "
                "quote the page they come from.")
    index = gr.State(None)
    history = gr.State([])
    pdf = gr.File(label="PDF", file_types=[".pdf"], type="filepath")
    status = gr.Markdown()
    with gr.Accordion("Settings", open=False):
        key = gr.Textbox(label="OpenRouter API key", type="password",
                         placeholder="sk-or-… (leave empty to use the server's key)")
        reindex = gr.Button("Index again", variant="secondary")
    with gr.Row(equal_height=True):
        question = gr.Textbox(show_label=False, placeholder="Ask about your PDF",
                              lines=1, max_lines=4, scale=5, min_width=200)
        go = gr.Button("Ask", variant="primary", scale=1, min_width=80)
    answer = gr.Markdown()
    with gr.Accordion("Compare methods", open=False) as compare:
        gr.Markdown("Every question also runs through five other retrieval methods. "
                    "*Hybrid* merges BM25 and embeddings; its top 20 passages go to Jev or "
                    "Gemini, which pick one. ms = time for this question, $ / 1k = cost "
                    "per 1,000 questions.")
        table = gr.Dataframe(headers=["Method", "Page", "ms", "$ / 1k"], interactive=False,
                             wrap=True, column_widths=["43%", "19%", "18%", "20%"])
        passages = gr.Markdown()
    earlier = gr.Markdown()

    reset_outputs = [index, status, answer, compare, table, passages, history, earlier]
    pdf.upload(indexing_notice, [pdf], reset_outputs).then(on_new_pdf, [pdf, key], reset_outputs)
    pdf.clear(on_clear, None, reset_outputs)
    reindex.click(indexing_notice, [pdf], reset_outputs).then(on_new_pdf, [pdf, key], reset_outputs)
    ask_outputs = [answer, compare, table, passages, history, earlier]
    go.click(ask, [question, index, key, history], ask_outputs)
    question.submit(ask, [question, index, key, history], ask_outputs)

if __name__ == "__main__":
    demo.launch()
