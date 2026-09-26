"""Ask a large PDF — searches the PDF and answers with the pages it used.

Three steps on one page: (1) the keys, kept in the browser; (2) upload a PDF,
indexed right away (BM25 + embeddings) with live progress; (3) ask, with an
optional screenshot, by one of three searches: Standard (keywords.py: the model
writes search terms, Jev keeps the best passages), Fast (classic.py: one search)
or Thorough (agent.py: a tool-calling agent searches until sure). Each answers
with the passages it relied on, or says the PDF doesn't cover the question.
Asking is locked until the PDF is ready.

Run:  .venv/bin/python app.py      (then open the printed local URL)
Keys: only the ones entered in the page, kept in that browser and removable there.
      The server never supplies a key of its own.
"""

import base64
import collections
import mimetypes
import os
import re
import time
import traceback
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import gradio as gr
import pymupdf

from agent import CEREBRAS, PROVIDERS, body_text, run_agent
from classic import run_classic
from keywords import run_keywords
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


CEREBRAS_MODELS_URL = CEREBRAS + "/v1/models"


def cerebras_key(saved=None):
    """The Cerebras key saved in this browser; the server never supplies one."""
    return (saved or "").strip()


def model_choices(saved_cb=None):
    """Agent models on offer: Gemini always; Qwen only when a Cerebras key is set."""
    ids = ["gemini"] + (["qwen"] if cerebras_key(saved_cb) else [])
    return [(PROVIDERS[i]["label"], i) for i in ids]


def check_cerebras(key):
    """One tiny request to see whether Cerebras accepts the key."""
    req = urllib.request.Request(CEREBRAS_MODELS_URL, headers={
        "Authorization": f"Bearer {key}", "User-Agent": "jev-rag-poc/0.1"})
    try:
        urllib.request.urlopen(req, timeout=30).read()
    except urllib.error.HTTPError as e:
        raise HTTPStatusError(CEREBRAS_MODELS_URL, e.code, e.read()) from None


MAX_IMAGE_MB = 5
IMAGE_ONLY_QUESTION = "What is shown in this image, and what does the document say about it?"


def image_data_url(path):
    """The attached image as a data URL, or raises ValueError with a plain message."""
    if os.path.getsize(path) > MAX_IMAGE_MB * 1024 * 1024:
        raise ValueError(f"The image is larger than {MAX_IMAGE_MB} MB. Attach a smaller one.")
    mime = mimetypes.guess_type(path)[0] or "image/png"
    return f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode()


def get_key(saved):
    """The OpenRouter key saved in this browser; the server never supplies one."""
    return (saved or "").strip()


def bar(done, total, width=20):
    filled = round(width * done / total) if total else 0
    return "█" * filled + "░" * (width - filled) + f" {round(100 * done / total) if total else 0}%"


# ---------------------------------------------------------------- step 1: the keys

def key_view(saved_or, saved_cb, model_value=None):
    """Step 1 shows either the keys line or the keys panel, never both.
    Returns (keys panel, keys line, keys-line row, steps 2-3, cancel button, model choice,
    model choice's wrapper, model note). With only one model there is nothing to choose, so a line names it."""
    shown, hidden = gr.update(visible=True), gr.update(visible=False)
    choices = model_choices(saved_cb)
    ids = [c[1] for c in choices]
    model = gr.update(choices=choices, value=model_value if model_value in ids else "gemini")
    # The Radio ignores visible= in this update (Gradio 6.28), so its wrapper is toggled.
    note = (gr.update(visible=len(ids) > 1), gr.update(visible=len(ids) == 1))
    if not (saved_or or "").strip():
        return shown, "", hidden, hidden, hidden, model, *note
    cb = "saved" if (saved_cb or "").strip() else "not added, so only Gemini is available"
    line = f"**1 · Keys** (kept in this browser): OpenRouter saved · Cerebras {cb}"
    return hidden, line, shown, shown, hidden, model, *note


def save_keys(or_in, cb_in, saved_or, saved_cb, model_value):
    """Check each key entered with one tiny request before keeping it; an empty field keeps
    the current key. Returns (saved OpenRouter, saved Cerebras, message, the two fields,
    *key_view)."""
    or_in, cb_in = (or_in or "").strip(), (cb_in or "").strip()
    keep = [gr.skip()] * 10

    def refuse(msg):
        return gr.skip(), gr.skip(), msg, *keep
    if not or_in and not cb_in:
        return refuse("Paste a key first.")
    if or_in:
        try:
            embed(["key check"], or_in)
        except HTTPStatusError as e:
            return refuse("OpenRouter rejected this key. Check it and try again." if e.code == 401
                          else friendly(e))
        except Exception as e:
            return refuse(friendly(e))
    elif not get_key(saved_or):
        return refuse("Paste your OpenRouter key too. Every question needs it.")
    if cb_in:
        try:
            check_cerebras(cb_in)
        except HTTPStatusError as e:
            return refuse("Cerebras rejected this key. Check it and try again."
                          if e.code in (401, 403) else f"Cerebras returned an error ({e.code}).")
        except Exception as e:
            return refuse(friendly(e).replace("OpenRouter", "Cerebras"))
    new_or = or_in or saved_or
    new_cb = cb_in or saved_cb
    return new_or, new_cb, "", "", "", *key_view(new_or, new_cb, model_value)


def remove_keys(model_value):
    """Delete both keys from this browser's storage; the page asks for keys again."""
    gr.Info("Keys removed from this browser.")
    return "", "", "", "", "", *key_view("", "", model_value)


def open_keys():
    """Change keys: the panel takes the place of the keys line."""
    return (gr.update(visible=True), "Leave a field empty to keep its current key.",
            gr.update(visible=True), gr.update(visible=False))


# ---------------------------------------------------------------- step 2: the PDF

LOCKED = "Wait until the PDF is ready"
READY = "Ask about the PDF. Attach a screenshot with 📎 if it helps."


def ask_lock(ready, placeholder, has_pdf=True):
    """Question box (with its Ask button) and Index again: asking only when the PDF is ready."""
    return gr.update(interactive=ready, placeholder=placeholder), gr.update(visible=has_pdf)


def index_pdf(pdf_path, saved):
    """Generator: indexes the PDF, showing progress in the status line after every batch.
    Yields (status, answer, how, steps, history, earlier, question, index again)."""
    cleared = ("", gr.update(label=HOW, visible=False), "", [], "")
    if not pdf_path:
        gr.Warning("Upload a PDF first.")
        yield ("", *cleared, *ask_lock(False, "Upload a PDF first", has_pdf=False))
        return
    name = md_escape(os.path.basename(pdf_path))
    if pdf_path in INDEXES:
        INDEXES.move_to_end(pdf_path)
        index = INDEXES[pdf_path]
        yield (f"**{name}** · {index['pages']} pages · {len(index['chunks'])} passages · "
               f"**ready** (already indexed)", *cleared, *ask_lock(True, READY))
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
               *ask_lock(True, READY))
    except Exception as e:
        yield (f"**{name}** · indexing failed. {friendly(e)} Then press **Index again**.",
               *cleared, *ask_lock(False, "Indexing failed. See the message above"))


def on_clear():
    return ("", "", gr.update(label=HOW, visible=False), "", [], "",
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
        if s["tool"] == "terms":
            terms = ", ".join(f"“{md_escape(t)}”" for t in s["terms"]) or "none"
            lines.append(f"{n}. Wrote search terms: {terms} · {s['ms'] / 1000:.1f} s")
        elif s["tool"] == "pool":
            lines.append(f"{n}. Ran {s['queries']} searches → {s['found']} passages · "
                         f"{s['ms'] / 1000:.1f} s")
        elif s["tool"] in ("search", "pick"):
            found = ", ".join(f"p. {r['page']}" + (f" ({r['relevance']:.0%})" if r.get("relevance")
                                                    is not None else "")
                              for r in s["results"]) or "nothing"
            what = (f"Jev kept the best of {s['from']}" if s["tool"] == "pick"
                    else f"Searched “{md_escape(s['query'])}”")
            lines.append(f"{n}. {what} → {found} · {s['ms'] / 1000:.1f} s")
        else:
            lines.append(f"{n}. Read page {s['page']} · {s['ms'] / 1000:.1f} s")
    return "\n".join(lines)


METHODS = {"classic": ("Fast: one search", run_classic),
           "keywords": ("Standard: writes search terms, keeps the best passages", run_keywords),
           "agent": ("Thorough: keeps searching until sure (slowest)", run_agent)}


def options_label(method, model):
    """The Options accordion names the current choice, so it can stay closed."""
    name = METHODS.get(method, METHODS["keywords"])[0].split(":")[0]
    return f"Options: {name} search · {PROVIDERS.get(model, PROVIDERS['gemini'])['label'].split(' · ')[0]}"


def ask(box, method, model, pdf_path, saved, saved_cb, history):
    """Generator: shows each search step as it happens, then the answer and its sources."""
    history = history or []
    box = box or {}
    question, files = box.get("text"), box.get("files") or []
    image_path = files[0] if files else None
    if isinstance(image_path, dict):
        image_path = image_path.get("path")
    index = INDEXES.get(pdf_path) if pdf_path else None
    if not index:  # the button is locked until ready; this guards a stale page
        gr.Warning("The PDF isn't ready. Upload it again.")
        yield gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
        return
    question = (question or "").strip()
    if not question and not image_path:
        gr.Warning("Type a question or attach an image first.")
        yield gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
        return
    image = None
    if image_path:
        try:
            image = image_data_url(image_path)
        except ValueError as e:
            gr.Warning(str(e))
            yield gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
            return
    question = question or IMAGE_ONLY_QUESTION
    model = model if model in PROVIDERS else "gemini"
    agent_key = cerebras_key(saved_cb) if PROVIDERS[model]["key"] == "cerebras" else None
    if PROVIDERS[model]["key"] == "cerebras" and not agent_key:
        gr.Warning("No Cerebras key is set up, so Qwen isn't available. Add one with "
                   "“Change keys”, or choose Gemini.")
        yield gr.skip(), gr.skip(), gr.skip(), gr.skip(), gr.skip()
        return
    key = get_key(saved)
    steps, done = [], None
    yield ("### Answer\n*Searching the PDF…*", gr.update(label=f"{HOW} · working…", visible=True), "",
           gr.skip(), gr.skip())
    try:
        runner = METHODS.get(method, METHODS["keywords"])[1]
        for kind, event in runner(question, index, key, image=image, provider=model,
                                  agent_key=agent_key):
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
    estimate = " (estimated)" if PROVIDERS[model]["price"] else ""
    meta = (f"<small>{len(steps)} step(s) · {done['seconds']:.1f} s · ${done['cost']:.4f}{estimate} · "
            f"{PROVIDERS[model]['label']}{' · with your image' if image else ''} · "
            + METHODS.get(method, METHODS["keywords"])[0].split(":")[0] + " search</small>")
    pages = ", ".join(f"p. {p}" for p in dict.fromkeys(c["page"] for c in sources)) or "no source"
    earlier = history_md(history)
    history = [{"q": question + (" (with image)" if image else ""), "pages": pages}] + history
    yield (f"### Answer\n{meta}\n\n{text}{sources_md}", gr.update(label=f"{HOW} · {len(steps)} step(s)"),
           steps_md(steps), history, earlier)


# ---------------------------------------------------------------- UI

# A readable column on wide screens; each search choice on its own full-width line.
CSS = """
.gradio-container { max-width: 760px !important; margin: 0 auto !important; }
.stacked-choice .wrap { flex-direction: column; }
.stacked-choice .wrap label { width: 100%; }
"""

with gr.Blocks(title="Ask a large PDF") as demo:
    gr.Markdown("# Ask a large PDF\nUpload a PDF and ask questions about it. Every answer shows "
                "the passages it is based on.")
    with gr.Accordion("How it works", open=False):
        gr.Markdown(GUIDE.split("\n", 1)[1])  # the file's own title is the accordion label
    # Kept in this browser's storage, so a reload doesn't ask for the keys again.
    saved_key = gr.BrowserState("", storage_key="ask-large-pdf-openrouter-key",
                                secret="ask-large-pdf-local")
    saved_cb = gr.BrowserState("", storage_key="ask-large-pdf-cerebras-key",
                               secret="ask-large-pdf-local")
    history = gr.State([])

    # Step 1 is either this one line or the panel below it, never both.
    with gr.Column(visible=False) as key_row:
        key_line = gr.Markdown()
        with gr.Row():
            change_key = gr.Button("Change keys", variant="secondary", size="md", scale=0,
                                   min_width=120)
            forget_keys = gr.Button("Remove keys", variant="secondary", size="md", scale=0,
                                    min_width=120)
    with gr.Column(visible=False) as key_step:
        gr.Markdown("### 1 · Your keys\nThe app uses OpenRouter to read the PDF and answer. "
                    "Paste an API key from your [OpenRouter keys page]"
                    "(https://openrouter.ai/settings/keys). A [Cerebras](https://cloud.cerebras.ai) "
                    "key is optional and adds the faster Qwen model. Keys are kept only in this "
                    "browser; **Remove keys** deletes them.")
        key_in = gr.Textbox(label="OpenRouter key", type="password", placeholder="sk-or-v1-…")
        cb_in = gr.Textbox(label="Cerebras key (optional)", type="password", placeholder="csk-…")
        key_msg = gr.Markdown()
        with gr.Row():
            save = gr.Button("Save keys", variant="primary", scale=0, min_width=120)
            cancel_key = gr.Button("Cancel", variant="secondary", scale=0, min_width=100,
                                   visible=False)

    with gr.Column(visible=False) as rest:
        gr.Markdown("### 2 · Your PDF")
        pdf = gr.File(show_label=False, file_types=[".pdf"], type="filepath", height=120)
        with gr.Row(equal_height=True):
            status = gr.Markdown()
            reindex = gr.Button("Index again", variant="secondary", size="md", visible=False,
                                scale=0, min_width=120)
        gr.Markdown("### 3 · Ask")
        # One box: the question, an optional screenshot (📎 or paste) and the Ask button.
        question = gr.MultimodalTextbox(label="Question", show_label=False, placeholder="Upload a PDF first",
                                        interactive=False, file_types=["image"],
                                        file_count="single", sources=["upload"],
                                        submit_btn="Ask", lines=2, max_lines=6)
        with gr.Accordion(options_label("keywords", "gemini"), open=False) as options:
            method = gr.Radio([(label, key) for key, (label, _) in METHODS.items()],
                              value="keywords", label="Search", elem_classes="stacked-choice")
            with gr.Column() as model_box:
                model = gr.Radio(model_choices(), value="gemini", label="Model",
                                 elem_classes="stacked-choice")
            model_note = gr.Markdown("**Model:** Gemini 3.7 Flash. Add a Cerebras key in step 1 "
                                     "to use Qwen.", visible=False)
        answer = gr.Markdown()
        with gr.Accordion(HOW, open=False, visible=False) as how:
            steps = gr.Markdown()
        earlier = gr.Markdown()

    gr.Markdown("<small>Supported by [airabbit.blog](https://airabbit.blog)</small>")

    key_outputs = [key_step, key_line, key_row, rest, cancel_key, model, model_box, model_note]
    demo.load(key_view, [saved_key, saved_cb, model], key_outputs)
    # A visibility change sent while Options is closed can be lost (Gradio 6.28: the page
    # still showed the one-choice model list after loading), so it is sent again on opening.
    options.expand(lambda o, c, m: key_view(o, c, m)[-2:], [saved_key, saved_cb, model],
                   [model_box, model_note])
    save_inputs = [key_in, cb_in, saved_key, saved_cb, model]
    save_outputs = [saved_key, saved_cb, key_msg, key_in, cb_in, *key_outputs]
    save.click(save_keys, save_inputs, save_outputs)
    key_in.submit(save_keys, save_inputs, save_outputs)
    cb_in.submit(save_keys, save_inputs, save_outputs)
    change_key.click(open_keys, None, [key_step, key_msg, cancel_key, key_row])
    # Gradio's BrowserState only writes non-empty values, so setting the keys to "" would
    # leave the old ones in storage. Delete the stored entries in the browser directly.
    forget_keys.click(remove_keys, [model], save_outputs, js=(
        "(m) => { localStorage.removeItem('ask-large-pdf-openrouter-key'); "
        "localStorage.removeItem('ask-large-pdf-cerebras-key'); return m; }"))
    cancel_key.click(lambda o, c, m: ("", "", "", *key_view(o, c, m)), [saved_key, saved_cb, model],
                     [key_in, cb_in, key_msg, *key_outputs])

    pdf_outputs = [status, answer, how, steps, history, earlier, question, reindex]
    pdf.upload(index_pdf, [pdf, saved_key], pdf_outputs, show_progress="hidden")
    reindex.click(index_pdf, [pdf, saved_key], pdf_outputs, show_progress="hidden")
    pdf.clear(on_clear, None, pdf_outputs)
    ask_outputs = [answer, how, steps, history, earlier]
    ask_inputs = [question, method, model, pdf, saved_key, saved_cb, history]
    question.submit(ask, ask_inputs, ask_outputs, show_progress="hidden")
    for choice in (method, model):
        choice.change(lambda a, b: gr.update(label=options_label(a, b)), [method, model], options)

if __name__ == "__main__":
    demo.launch(css=CSS, footer_links=[])
