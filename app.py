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
    return [(PROVIDERS[i]["label"].split(" · ")[0], i) for i in ids]


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
READY = "Ask about the PDF, e.g. “I don’t hear anything when I play a note”"


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

def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "s")


def readable(text):
    """Table-of-contents dot leaders ("Audio........41") shown as one ellipsis."""
    return re.sub(r"(?:\s*[.…]){4,}\s*", " … ", text)


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
            what = (f"Kept the best of {s['from']} passages (ranked by Jev)" if s["tool"] == "pick"
                    else f"Searched “{md_escape(s['query'])}”")
            lines.append(f"{n}. {what} → {found} · {s['ms'] / 1000:.1f} s")
        else:
            lines.append(f"{n}. Read page {s['page']} · {s['ms'] / 1000:.1f} s")
    return "\n".join(lines)


# The three searches: (name on the switch, the one line shown under it, runner).
METHODS = {"classic": ("Fast", "One search with your words. Fastest, but can miss details.",
                       run_classic),
           "keywords": ("Standard", "Writes search terms from your question and screenshot, then "
                                    "keeps the best passages.", run_keywords),
           "agent": ("Thorough", "Keeps searching until it is sure. Slowest.", run_agent)}


def method_help(method):
    name, text, _ = METHODS.get(method, METHODS["keywords"])
    return f"**{name}:** {text}"


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
        runner = METHODS.get(method, METHODS["keywords"])[2]
        for kind, event in runner(question, index, key, image=image, provider=model,
                                  agent_key=agent_key):
            if kind == "step":
                steps.append(event)
                yield (f"### Answer\n*Searching the PDF… step {len(steps)}*",
                       gr.update(label=f"{HOW} · working… {plural(len(steps), 'step')} so far"),
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
                  + f"\n\n> {md_escape(readable(body_text(c)))}" for c in sources]
        sources_md = "\n\n#### Sources\n\n" + "\n\n".join(blocks)
    else:
        sources_md = "\n\n*No source passages were named.*"
    estimate = " (estimated)" if PROVIDERS[model]["price"] else ""
    cost = done["cost"]
    cost = f"${cost:.4f}" if cost >= 0.0001 else "<$0.0001" if cost > 0 else "$0"
    meta = (f'<span class="meta">{plural(len(steps), "step")} · {done["seconds"]:.1f} s · '
            f"{cost}{estimate} · {PROVIDERS[model]['label']}"
            f"{' · with your image' if image else ''} · "
            + METHODS.get(method, METHODS["keywords"])[0] + " search</span>")
    pages = ", ".join(f"p. {p}" for p in dict.fromkeys(c["page"] for c in sources)) or "no source"
    earlier = history_md(history)
    history = [{"q": question + (" (with image)" if image else ""), "pages": pages}] + history
    yield (f"### Answer\n{meta}\n\n{text}{sources_md}", gr.update(label=f"{HOW} · {plural(len(steps), 'step')}"),
           steps_md(steps), history, earlier)


# ---------------------------------------------------------------- UI

# A readable column on wide screens; each search choice on its own full-width line.
# A readable column on wide screens; the two choices as compact switches with 44px targets;
# a clear primary Ask button. Colours come from the theme, so dark mode follows.
CSS = """
.gradio-container { max-width: 760px !important; margin: 0 auto !important; }
.settings { gap: 12px 28px !important; align-items: flex-start; }
.settings > * { flex: 0 0 auto !important; min-width: 0 !important; }
.settings .form { background: transparent !important; border: 0 !important;
       box-shadow: none !important; }
.seg { border: 0 !important; padding: 0 !important; background: transparent !important;
       box-shadow: none !important; display: flex !important; flex-wrap: wrap;
       align-items: center; gap: 8px; }
.seg > [data-testid="block-info"] { margin: 0 !important; font-size: 13px; font-weight: 600;
       color: var(--body-text-color) !important; }
.seg > .wrap:not([data-testid]) { display: inline-flex !important; flex-wrap: nowrap !important; gap: 2px !important;
       padding: 3px; border-radius: 10px; background: var(--background-fill-secondary); }
.seg > .wrap:not([data-testid]) label { position: relative; min-height: 44px; margin: 0 !important;
       padding: 0 16px !important; display: flex; align-items: center; border: 0 !important;
       border-radius: 8px !important; background: transparent !important;
       box-shadow: none !important; color: var(--body-text-color) !important; cursor: pointer; }
.seg > .wrap:not([data-testid]) label input { position: absolute; inset: 0; width: 100%; height: 100%; margin: 0;
       opacity: 0; cursor: pointer; }
.seg > .wrap:not([data-testid]) label span { margin: 0 !important; }
.seg > .wrap:not([data-testid]) label.selected { background: var(--background-fill-primary) !important;
       font-weight: 600; box-shadow: 0 1px 3px rgba(0, 0, 0, .18) !important; }
.seg > .wrap:not([data-testid]) label:has(input:focus-visible) { outline: 2px solid #2563eb; outline-offset: 1px; }
.help, .model-note { font-size: 13px; }
.help p, .model-note p { margin: 4px 0 0 !important; }
.multimodal-textbox .submit-button { min-width: 76px; min-height: 44px; border-radius: 8px !important;
       background: #c2410c !important; color: #fff !important; font-weight: 600; }
.multimodal-textbox .submit-button:disabled { opacity: .45; }
.multimodal-textbox .thumbnail-image { cursor: zoom-in; }
.multimodal-textbox .upload-button { min-width: 44px; min-height: 44px; }
/* The thumbnail opens the screenshot; removing it is a visible badge on its corner, so a tap
   on the picture can never remove it. The badge's hit area reaches 40px outside the image. */
.multimodal-textbox .thumbnail-wrapper, .multimodal-textbox .thumbnail-item,
.multimodal-textbox .thumbnails { overflow: visible !important; }
.multimodal-textbox .thumbnail-item { position: relative; width: 72px !important;
       height: 52px !important; }
.multimodal-textbox .thumbnail-image { width: 72px !important; height: 52px !important;
       object-fit: cover; border-radius: 6px; }
.multimodal-textbox .delete-button { position: absolute !important; top: -9px !important;
       right: -9px !important; left: auto !important; bottom: auto !important;
       width: 22px !important; height: 22px !important; padding: 5px !important;
       opacity: 1 !important; border-radius: 50% !important; background: #374151 !important;
       color: #fff !important; }
.multimodal-textbox .delete-button::after { content: ""; position: absolute; inset: -9px; }
.multimodal-textbox .thumbnails { padding: 10px 10px 0 0 !important; }
.seg > [data-testid="block-info"] { min-width: 52px; }
.meta { font-size: 14px; color: #5f5f67; }
.dark .meta { color: #a1a1aa; }
#shot-view { border: 0; padding: 0; background: transparent; max-width: 96vw; max-height: 96vh; }
#shot-view::backdrop { background: rgba(0, 0, 0, .8); }
#shot-view img { display: block; max-width: 96vw; max-height: 90vh; border-radius: 8px; }
#shot-view button { position: fixed; top: 12px; right: 12px; min-width: 44px; min-height: 44px;
       border: 0; border-radius: 8px; background: rgba(255, 255, 255, .9); color: #111;
       font-size: 15px; cursor: pointer; }
"""

# The attached screenshot opens full size: click (or Enter on) its thumbnail. A native
# <dialog> keeps focus inside, closes on Esc, the Close button or a click outside the
# image, and gives focus back to the thumbnail. The answer is announced when it changes.
HEAD = """
<script>
(() => {
  function dialog() {
    let d = document.getElementById("shot-view");
    if (d) return d;
    d = document.createElement("dialog");
    d.id = "shot-view";
    d.setAttribute("aria-label", "Screenshot, full size");
    d.innerHTML = '<button type="button">Close</button><img alt="Attached screenshot, full size">';
    d.querySelector("button").onclick = () => d.close();
    d.addEventListener("click", (e) => { if (e.target === d) d.close(); });
    document.body.appendChild(d);
    return d;
  }
  function open(img) {
    const d = dialog();
    d.querySelector("img").src = img.src;
    img.focus();  // the dialog gives focus back to whatever had it when it opened
    d.showModal();
    d.querySelector("button").focus();
  }
  const thumb = (e) => e.target.closest && e.target.closest(".multimodal-textbox .thumbnail-image");
  // Capture phase: the text box stops clicks on its thumbnails before they bubble up.
  document.addEventListener("click", (e) => {
    const t = thumb(e);
    if (t) { e.preventDefault(); e.stopPropagation(); open(t); }
  }, true);
  document.addEventListener("keydown", (e) => {
    const t = thumb(e);
    if (t && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); e.stopPropagation(); open(t); }
  }, true);
  new MutationObserver(() => {
    document.querySelectorAll(".multimodal-textbox .thumbnail-image:not([tabindex])").forEach((t) => {
      t.tabIndex = 0;
      t.setAttribute("role", "button");
      t.setAttribute("aria-label", "View screenshot full size");
      t.title = "View full size";
    });
    document.querySelectorAll(".multimodal-textbox .submit-button[aria-label='Submit']")
      .forEach((b) => b.setAttribute("aria-label", "Ask"));
    const a = document.getElementById("answer");
    if (a && !a.hasAttribute("aria-live")) a.setAttribute("aria-live", "polite");
  }).observe(document.documentElement, { childList: true, subtree: true });
})();
</script>
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
        with gr.Row(elem_classes="settings"):
            method = gr.Radio([(name, key) for key, (name, _, _) in METHODS.items()],
                              value="keywords", label="Search", elem_classes="seg")
            with gr.Column() as model_box:
                model = gr.Radio(model_choices(), value="gemini", label="Model", elem_classes="seg")
            model_note = gr.Markdown("**Model:** Gemini 3.7 Flash. Add a Cerebras key in step 1 "
                                     "to use Qwen.", visible=False, elem_classes="model-note")
        # Below both switches: a help line that wraps must not move the Model switch.
        help_line = gr.Markdown(method_help("keywords"), elem_classes="help")
        answer = gr.Markdown(elem_id="answer")
        with gr.Accordion(HOW, open=False, visible=False) as how:
            steps = gr.Markdown()
        earlier = gr.Markdown()

    gr.Markdown("<small>Supported by [airabbit.blog](https://airabbit.blog)</small>")

    key_outputs = [key_step, key_line, key_row, rest, cancel_key, model, model_box, model_note]
    demo.load(key_view, [saved_key, saved_cb, model], key_outputs)
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
    # The box and the switches are locked while a question runs: no second Ask on top of it,
    # and the answer's line names the search and model that were really used.
    lock = [question, method, model]
    # The answer area keeps its height while the next answer runs, so the page doesn't jump.
    question.submit(lambda: [gr.update(interactive=False)] * 3, None, lock, js=(
        "() => { const a = document.getElementById('answer');"
        " if (a) a.style.minHeight = a.offsetHeight + 'px'; }")).then(
        ask, ask_inputs, ask_outputs, show_progress="hidden").then(
        lambda: [gr.update(interactive=True)] * 3, None, lock, js=(
            "() => { const a = document.getElementById('answer'); if (a) a.style.minHeight = ''; }"))
    method.change(method_help, method, help_line)

if __name__ == "__main__":
    demo.launch(css=CSS, head=HEAD, footer_links=[])
