"""Ask a large PDF — an agent searches the PDF and answers with the pages it used.

Three steps on one page: (1) an OpenRouter key — asked for up front when the
server has none, kept in the browser; (2) upload a PDF — indexed right away
(BM25 + embeddings) with live progress; (3) ask — a tool-calling agent (agent.py)
searches as often as it needs, each search a hybrid shortlist ranked by Jev, and
answers with the passages it relied on, or says the PDF doesn't cover the question.
Asking is locked until the PDF is ready.

Run:  .venv/bin/python app.py      (then open the printed local URL)
Key:  entered in the page, else $OPENROUTER_API_KEY, else the file /tmp/or.
"""

import collections
import os
import re
import time
import traceback
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

import gradio as gr
import pymupdf

from agent import AGENT_MODEL, body_text, run_agent
from poc import BM25, HTTPStatusError, embed
from squad_eval import unit

MAX_WORDS, MIN_WORDS, BATCH = 300, 25, 100
# Indexes live on the server, keyed by the uploaded file's path (Gradio names uploads by a
# hash of their content). Gradio deletes per-session state when the browser's connection
# drops, which silently lost the index while the page still said "ready".
INDEXES = collections.OrderedDict()
MAX_INDEXES = 3
POOL_EXEC = ThreadPoolExecutor(8)
HOW = "How it found this"
GUIDE = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "HOW_IT_WORKS.md")).read()


def friendly(e):
    """Plain-language message for a failure; the full error goes to the server log."""
    traceback.print_exception(e)
    if isinstance(e, HTTPStatusError):
        if e.code == 401:
            return "OpenRouter rejected the API key. Press “Change key” and enter a valid one."
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


def server_key():
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key and os.path.exists("/tmp/or"):
        key = open("/tmp/or").read().strip()
    return key


def get_key(saved):
    """The key saved in this browser wins; otherwise the server's own key."""
    return (saved or "").strip() or server_key()


def bar(done, total, width=20):
    filled = round(width * done / total) if total else 0
    return "█" * filled + "░" * (width - filled) + f" {round(100 * done / total) if total else 0}%"


# ---------------------------------------------------------------- step 1: the key

def key_view(saved):
    """(key step, key line, key-line row, pdf+ask steps) for the key currently in force."""
    shown, hidden = gr.update(visible=True), gr.update(visible=False)
    if (saved or "").strip():
        return hidden, "**1 · OpenRouter key:** yours, saved in this browser", shown, shown
    if server_key():
        return hidden, "**1 · OpenRouter key:** the server's", shown, shown
    return shown, "", hidden, hidden


def save_key(entered):
    """Check the key with one tiny request before keeping it."""
    entered = (entered or "").strip()
    if not entered:
        return gr.skip(), "Paste your key first.", *[gr.skip()] * 5
    try:
        embed(["key check"], entered)
    except HTTPStatusError as e:
        msg = ("OpenRouter rejected this key. Check it and try again." if e.code == 401
               else friendly(e))
        return gr.skip(), msg, *[gr.skip()] * 5
    except Exception as e:
        return gr.skip(), friendly(e), *[gr.skip()] * 5
    return entered, "", "", *key_view(entered)


# ---------------------------------------------------------------- step 2: the PDF

LOCKED = "Wait until the PDF is ready"


def ask_lock(ready, placeholder, has_pdf=True):
    """Question box, Ask button and Index again button: Ask only when the PDF is ready."""
    return (gr.update(interactive=ready, placeholder=placeholder),
            gr.update(interactive=ready), gr.update(visible=has_pdf))


def index_pdf(pdf_path, saved):
    """Generator: indexes the PDF, showing progress in the status line after every batch.
    Yields (status, answer, how, steps, history, earlier, question, ask, index again)."""
    cleared = ("", gr.update(label=HOW), "", [], "")
    if not pdf_path:
        gr.Warning("Upload a PDF first.")
        yield ("", *cleared, *ask_lock(False, "Upload a PDF first", has_pdf=False))
        return
    name = md_escape(os.path.basename(pdf_path))
    if pdf_path in INDEXES:
        INDEXES.move_to_end(pdf_path)
        index = INDEXES[pdf_path]
        yield (f"**{name}** · {index['pages']} pages · {len(index['chunks'])} passages · "
               f"**ready** (already indexed)", *cleared, *ask_lock(True, "Ask about your PDF"))
        return
    key = get_key(saved)
    if not key:
        yield (f"**{name}** · no OpenRouter key. Enter one in step 1.", *cleared,
               *ask_lock(False, LOCKED))
        return
    t0 = time.perf_counter()
    yield f"**{name}** · reading the PDF…", *cleared, *ask_lock(False, LOCKED)
    try:
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
            yield (f"**{name}** · no text found. This looks like a scanned PDF without a text "
                   f"layer, so it can't be searched.", *cleared,
                   *ask_lock(False, "This PDF can't be searched"))
            return
        total, done = len(chunks), 0
        batches = [chunks[i:i + BATCH] for i in range(0, total, BATCH)]
        futures = {POOL_EXEC.submit(embed, [c["text"] for c in b], key): n
                   for n, b in enumerate(batches)}
        results = [None] * len(batches)
        yield (f"**{name}** · indexing {bar(0, total)} 0 of {total} passages", *cleared,
               *ask_lock(False, LOCKED))
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result()
            done += len(batches[futures[fut]])
            yield (f"**{name}** · indexing {bar(done, total)} {done} of {total} passages · "
                   f"{time.perf_counter() - t0:.0f} s", *cleared, *ask_lock(False, LOCKED))
        vecs = [v for r in results for v in r[0]]
        cost = sum(r[2].get("cost", 0) for r in results)
        INDEXES[pdf_path] = {"name": name, "pages": len(doc), "chunks": chunks,
                             "bm25": BM25([c["text"] for c in chunks]),
                             "uvecs": [unit(v) for v in vecs]}
        while len(INDEXES) > MAX_INDEXES:
            INDEXES.popitem(last=False)
        yield (f"**{name}** · {len(doc)} pages · {total} passages · **ready** · indexed in "
               f"{time.perf_counter() - t0:.0f} s for ${cost:.4f}", *cleared,
               *ask_lock(True, "Ask about your PDF"))
    except Exception as e:
        yield (f"**{name}** · indexing failed. {friendly(e)} Then press **Index again**.",
               *cleared, *ask_lock(False, "Indexing failed. See the message above"))


def on_clear():
    return ("", "", gr.update(label=HOW), "", [], "",
            *ask_lock(False, "Upload a PDF first", has_pdf=False))


# ---------------------------------------------------------------- step 3: asking

def history_md(history):
    if not history:
        return ""
    lines = [f"- {md_escape(h['q'])} · {h['pages']}" for h in history]
    return "**Earlier questions**\n\n" + "\n".join(lines)


def steps_md(steps):
    lines = []
    for n, s in enumerate(steps, 1):
        if s["tool"] == "search":
            found = ", ".join(f"p. {r['page']} ({r['relevance']:.0%})" for r in s["results"]) or "nothing"
            lines.append(f"{n}. Searched “{md_escape(s['query'])}” → {found} · {s['ms'] / 1000:.1f} s")
        else:
            lines.append(f"{n}. Read page {s['page']} · {s['ms'] / 1000:.1f} s")
    return "\n".join(lines)


def ask(question, pdf_path, saved, history):
    """Generator: shows each agent step as it happens, then the answer and its sources."""
    history = history or []
    index = INDEXES.get(pdf_path) if pdf_path else None
    if not index:  # the button is locked until ready; this guards a stale page
        gr.Warning("The PDF isn't ready. Upload it again.")
        yield gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
        return
    if not (question or "").strip():
        gr.Warning("Type a question first.")
        yield gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
        return
    key = get_key(saved)
    steps, done = [], None
    yield ("### Answer\n*Searching the PDF…*", gr.update(label=f"{HOW} · working…"), "",
           gr.skip(), gr.skip())
    try:
        for kind, event in run_agent(question.strip(), index, key):
            if kind == "step":
                steps.append(event)
                yield (f"### Answer\n*Searching the PDF… step {len(steps)}*",
                       gr.update(label=f"{HOW} · working… {len(steps)} step(s) so far"),
                       steps_md(steps), gr.skip(), gr.skip())
            else:
                done = event
    except Exception as e:
        message = friendly(e)
        gr.Warning(message)
        yield (f"### Answer\nThe search stopped: {message}", gr.update(label=HOW),
               steps_md(steps), gr.skip(), gr.skip())
        return
    # Model-written Markdown is kept (bold, lists); brackets from the PDF stay literal.
    text = (done["answer"].strip() or "No answer: the search ran out of steps.")
    text = text.replace("[", "\\[").replace("]", "\\]")
    sources = done["sources"]
    if sources:
        blocks = [f"**Page {c['page']}**" + (f" · {md_escape(c['section'])}" if c["section"] else "")
                  + f"\n\n> {md_escape(body_text(c))}" for c in sources]
        sources_md = "\n\n#### Sources\n\n" + "\n\n".join(blocks)
    else:
        sources_md = "\n\n*No source passages were named.*"
    meta = (f"<small>{len(steps)} step(s) · {done['seconds']:.1f} s · ${done['cost']:.4f} · "
            f"agent {AGENT_MODEL}, passages ranked by Jev</small>")
    pages = ", ".join(f"p. {p}" for p in dict.fromkeys(c["page"] for c in sources)) or "no source"
    earlier = history_md(history)
    history = [{"q": question.strip(), "pages": pages}] + history
    yield (f"### Answer\n{text}{sources_md}\n\n{meta}", gr.update(label=f"{HOW} · {len(steps)} step(s)"),
           steps_md(steps), history, earlier)


# ---------------------------------------------------------------- UI

with gr.Blocks(title="Ask a large PDF") as demo:
    gr.Markdown("# Ask a large PDF\nUpload a PDF and ask questions about it. An agent searches "
                "the PDF as often as it needs and answers with the passages it used.")
    with gr.Accordion("How it works", open=False):
        gr.Markdown(GUIDE.split("\n", 1)[1])  # the file's own title is the accordion label
    # Kept in this browser's storage, so a reload doesn't ask for the key again.
    saved_key = gr.BrowserState("", storage_key="ask-large-pdf-openrouter-key",
                                secret="ask-large-pdf-local")
    history = gr.State([])

    with gr.Column(visible=False) as key_step:
        gr.Markdown("### 1 · Your OpenRouter key\nThe app uses OpenRouter to read the PDF and "
                    "answer. Paste an API key from your OpenRouter account (Keys page).")
        with gr.Row(equal_height=True):
            key_in = gr.Textbox(show_label=False, type="password", placeholder="sk-or-v1-…",
                                scale=5, min_width=200)
            save = gr.Button("Save key", variant="primary", scale=1, min_width=100)
        key_msg = gr.Markdown()
        cancel_key = gr.Button("Cancel", variant="secondary", size="sm", visible=False)
    with gr.Row(equal_height=True, visible=False) as key_row:
        key_line = gr.Markdown()
        change_key = gr.Button("Change key", variant="secondary", size="sm", scale=0,
                               min_width=110)

    with gr.Column(visible=False) as rest:
        gr.Markdown("### 2 · Your PDF")
        pdf = gr.File(show_label=False, file_types=[".pdf"], type="filepath")
        status = gr.Markdown()
        reindex = gr.Button("Index again", variant="secondary", size="sm", visible=False)
        gr.Markdown("### 3 · Ask")
        with gr.Row(equal_height=True):
            question = gr.Textbox(show_label=False, placeholder="Upload a PDF first",
                                  interactive=False, lines=1, max_lines=4, scale=5, min_width=200)
            go = gr.Button("Ask", variant="primary", interactive=False, scale=1, min_width=80)
        answer = gr.Markdown()
        with gr.Accordion(HOW, open=False) as how:
            steps = gr.Markdown()
        earlier = gr.Markdown()

    gr.Markdown("<small>Supported by [airabbit.blog](https://airabbit.blog)</small>")

    key_outputs = [key_step, key_line, key_row, rest]
    demo.load(key_view, [saved_key], key_outputs)
    save.click(save_key, [key_in], [saved_key, key_msg, key_in, *key_outputs])
    key_in.submit(save_key, [key_in], [saved_key, key_msg, key_in, *key_outputs])
    change_key.click(lambda: (gr.update(visible=True), "", gr.update(visible=True)), None,
                     [key_step, key_msg, cancel_key])
    cancel_key.click(lambda saved: ("", "", gr.update(visible=False), *key_view(saved)),
                     [saved_key], [key_in, key_msg, cancel_key, *key_outputs])

    pdf_outputs = [status, answer, how, steps, history, earlier, question, go, reindex]
    pdf.upload(index_pdf, [pdf, saved_key], pdf_outputs, show_progress="hidden")
    reindex.click(index_pdf, [pdf, saved_key], pdf_outputs, show_progress="hidden")
    pdf.clear(on_clear, None, pdf_outputs)
    ask_outputs = [answer, how, steps, history, earlier]
    go.click(ask, [question, pdf, saved_key, history], ask_outputs, show_progress="hidden")
    question.submit(ask, [question, pdf, saved_key, history], ask_outputs, show_progress="hidden")

if __name__ == "__main__":
    demo.launch()
