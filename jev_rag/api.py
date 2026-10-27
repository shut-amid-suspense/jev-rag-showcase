"""Provider endpoints and HTTP helpers shared by runtime and experiments."""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from collections import Counter

JEV_MODEL = "~typesafe/jev-latest"
EMBED_MODEL = "openai/text-embedding-3-small"
# Overrides allow offline integration tests to use a local fake provider.
OPENROUTER = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai")
DECISIONS_URL = OPENROUTER + "/api/alpha/decisions"
EMBED_URL = OPENROUTER + "/api/v1/embeddings"
CHAT_URL = OPENROUTER + "/api/v1/chat/completions"
RETRIES = Counter()

def api_key():
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("No key: set OPENROUTER_API_KEY in the environment")
    return key

class HTTPStatusError(RuntimeError):
    """The API answered with an HTTP error; .code is the status."""

    def __init__(self, url, code, body):
        # Provider error bodies can echo submitted text or credentials.
        # Keep them out of exceptions, terminal logs and benchmark failure reports.
        super().__init__(f"{url} -> HTTP {code}")
        self.code = code

def post(url, body, key, attempts=3):
    """POST JSON; retry only dropped connections. Latency is the successful attempt."""
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": "jev-rag-poc/0.1"})
    for attempt in range(attempts):
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read())
            return data, (time.perf_counter() - t0) * 1000
        except urllib.error.HTTPError as e:
            raise HTTPStatusError(url, e.code, e.read()) from None
        except (ConnectionError, urllib.error.URLError, TimeoutError):
            if attempt == attempts - 1:
                raise
            RETRIES[url] += 1

def embed(texts, key):
    data, ms = post(EMBED_URL, {"model": EMBED_MODEL, "input": texts}, key)
    vecs = [d["embedding"] for d in sorted(data["data"], key=lambda d: d["index"])]
    return vecs, ms, data.get("usage", {})
