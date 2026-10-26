"""Saved indexes: a PDF is indexed once per content, and stays indexed across restarts.

An index is keyed by the SHA-256 of the PDF's bytes, so the same file is found again
whatever it is called, and a changed file (different bytes) is indexed fresh. Each
index is one file in data/indexes/ (git-ignored): the passages and their unit
embedding vectors. The keyword index is rebuilt from the passages when loading.
Only the MAX_SAVED most recently used indexes are kept.

The files are pickles written by this app into its own folder; nothing else writes there.
"""

import array
import hashlib
import os
import pickle

from poc import BM25

# ASK_PDF_INDEX_DIR exists only so a test run against a fake service keeps its (fake)
# indexes apart from the real ones.
DIR = os.environ.get("ASK_PDF_INDEX_DIR") or os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "indexes")
MAX_SAVED = 10
VERSION = 1  # bump when the chunking or the embedding model changes: old files are ignored


def fingerprint(path):
    """SHA-256 of the file's bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _path(fp):
    return os.path.join(DIR, f"{fp}.pkl")


def save(fp, index):
    """Write the index (atomically), then drop the least recently used ones over MAX_SAVED."""
    os.makedirs(DIR, exist_ok=True)
    vecs = index["uvecs"]
    record = {"version": VERSION, "name": index["name"], "pages": index["pages"],
              "chunks": index["chunks"], "dim": len(vecs[0]) if vecs else 0,
              "vecs": array.array("d", (x for v in vecs for x in v)).tobytes()}
    tmp = _path(fp) + ".tmp"
    with open(tmp, "wb") as f:
        pickle.dump(record, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, _path(fp))
    saved = sorted((os.path.join(DIR, n) for n in os.listdir(DIR) if n.endswith(".pkl")),
                   key=os.path.getmtime, reverse=True)
    for old in saved[MAX_SAVED:]:
        os.remove(old)


def load(fp):
    """The saved index for this fingerprint, or None (missing, old version or unreadable)."""
    try:
        with open(_path(fp), "rb") as f:
            record = pickle.load(f)
    except (OSError, pickle.UnpicklingError, EOFError):
        return None
    if record.get("version") != VERSION:
        return None
    os.utime(_path(fp))  # most recently used
    flat, dim = array.array("d"), record["dim"]
    flat.frombytes(record["vecs"])
    uvecs = [flat[i:i + dim].tolist() for i in range(0, len(flat), dim)]
    chunks = record["chunks"]
    return {"name": record["name"], "pages": record["pages"], "chunks": chunks,
            "bm25": BM25([c["text"] for c in chunks]), "uvecs": uvecs}
