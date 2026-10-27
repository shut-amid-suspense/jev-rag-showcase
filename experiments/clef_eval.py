"""Cloudflare Clef and Clef-flash vs. Jev on the Decisions API — accuracy and speed.

Both models take the same request on /api/alpha/decisions, so every item is sent
to every model, rotating who goes first, so network drift hits all alike.
The first call to each model is a warm-up and is not counted.

Tasks
  intent    40 hand-labelled support messages -> one of 6 intents
  passage   POC corpus: pick the passage that answers a question, 10 candidates
            (the company's 3 passages, its near-twin's 3, and 4 others)
  passage_all  same questions against all 120 passages — a long request, which
            the Clef model card says Workers AI may truncate

Key: $OPENROUTER_API_KEY. Usage: python3 -m experiments.clef_eval  (writes clef-results.json)
"""

import json
import random

from . import poc
from jev_rag.paths import EXPERIMENT_RESULTS

MODELS = {"jev": "~typesafe/jev-latest", "clef": "cloudflare/clef",
          "flash": "cloudflare/clef-flash"}

INTENTS = {
    "billing": "Charges, invoices, refunds, payment methods, pricing",
    "bug": "Something in the product is broken, crashing or behaving wrongly",
    "account": "Login, password, 2FA, email change, deleting or locking the account",
    "feature": "Asking for something the product does not do yet",
    "shipping": "Where a physical order is, delivery delays, wrong address, returns of goods",
    "praise": "Thanks or compliments with no request",
}

INTENT_ITEMS = [
    ("I was charged twice for the same month, please fix it.", "billing"),
    ("Can I pay by bank transfer instead of card?", "billing"),
    ("Your invoice is missing our VAT number.", "billing"),
    ("I cancelled last week but still got billed. Refund please.", "billing"),
    ("Why did my plan price go up from 9 to 12 euros?", "billing"),
    ("The app crashes every time I open the settings page.", "bug"),
    ("Export to CSV produces an empty file.", "bug"),
    ("Dark mode text is invisible on the dashboard.", "bug"),
    ("Since the update, notifications arrive twice.", "bug"),
    ("Search returns results from other workspaces, that looks wrong.", "bug"),
    ("I can't log in, it says my password is wrong but I just reset it.", "account"),
    ("How do I turn on two-factor authentication?", "account"),
    ("Please delete my account and all my data.", "account"),
    ("I need to change the email address on my profile.", "account"),
    ("My account got locked after too many attempts.", "account"),
    ("It would be great if you supported Markdown in comments.", "feature"),
    ("Any plans for a Linux desktop app?", "feature"),
    ("Please add an option to schedule reports weekly.", "feature"),
    ("Could you integrate with Jira?", "feature"),
    ("I wish I could set a custom domain for shared pages.", "feature"),
    ("My package was supposed to arrive Monday and it's Thursday.", "shipping"),
    ("Tracking hasn't updated in five days.", "shipping"),
    ("I typed the wrong street, can you redirect the parcel?", "shipping"),
    ("The box arrived crushed, how do I send it back?", "shipping"),
    ("Do you ship to Norway?", "shipping"),
    ("Just wanted to say your support team is fantastic.", "praise"),
    ("Love the new design, great work!", "praise"),
    ("Thanks, that fixed it. You're the best.", "praise"),
    ("Been using this for three years, still my favourite tool.", "praise"),
    ("Huge thanks to Maria for the quick help yesterday.", "praise"),
    # harder: mixed signals, the label is the actual request
    ("Great app, but I was billed after my trial ended without warning.", "billing"),
    ("Love it! Only thing missing is an offline mode.", "feature"),
    ("After I changed my password the mobile app keeps crashing on start.", "bug"),
    ("The order confirmation email never came, but the card was charged and nothing shipped.", "shipping"),
    ("I can't find where to download my receipts.", "billing"),
    ("Password reset link gives a 404 page.", "bug"),
    ("Would you consider a student discount?", "billing"),
    ("Is there a way to log in with Google?", "feature"),
    ("Can you merge my two accounts into one?", "account"),
    ("Thanks for the fast delivery, arrived a day early!", "praise"),
]


def decide(model, state, qname, instructions, criteria, key):
    body = {"model": model, "state": state, "questions": {qname: {
        "type": "choice", "instructions": instructions, "criteria": criteria}}}
    data, ms = poc.post(poc.DECISIONS_URL, body, key)
    ans = data["answers"][qname]
    return ans["choice"], ans.get("confidence"), ms, data.get("usage", {})


def intent_cases():
    return [dict(state={"message": m}, gold=g, label=m) for m, g in INTENT_ITEMS]


def passage_cases(chunks, n, all_passages, seed=5):
    rnd = random.Random(seed)
    qs = poc.build_questions(chunks, n, seed=seed)
    by_id = {c["id"]: c for c in chunks}
    cases = []
    for q in qs:
        gold = by_id[q["gold"]]
        if all_passages:
            cands = chunks
        else:
            first = gold["company"].split()[0]
            near = [c for c in chunks if c["company"].split()[0] == first]  # own 3 + twin's 3
            rest = rnd.sample([c for c in chunks if c not in near], 4)
            cands = near + rest
            rnd.shuffle(cands)
        cases.append(dict(state={"question": q["q"]}, gold=q["gold"], label=q["q"],
                          criteria={c["id"]: c["text"] for c in cands}))
    return cases


TASKS = {
    "intent": ("intent", "Which intent best describes the customer's request in state?",
               lambda: [dict(c, criteria=INTENTS) for c in intent_cases()]),
    "passage": ("passage", "Which single passage answers the question in state?",
                lambda: passage_cases(poc.build_corpus()[1], 30, False)),
    "passage_all": ("passage", "Which single passage answers the question in state?",
                    lambda: passage_cases(poc.build_corpus()[1], 12, True)),
}


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]


def run_task(name, key):
    qname, instructions, make = TASKS[name]
    cases = make()
    rows = []
    print(f"\n== {name}: {len(cases)} items")
    # warm-up: one uncounted call per model
    for model in MODELS.values():
        decide(model, cases[0]["state"], qname, instructions, cases[0]["criteria"], key)
    for i, c in enumerate(cases):
        row = {"item": c["label"], "gold": c["gold"]}
        items = list(MODELS.items())
        order = items[i % len(items):] + items[:i % len(items)]  # rotate who goes first
        for short, model in order:
            try:
                pick, conf, ms, usage = decide(model, c["state"], qname, instructions,
                                               c["criteria"], key)
                row[short] = {"pick": pick, "conf": conf, "ms": ms,
                              "cost": usage.get("cost", 0),
                              "in_tokens": usage.get("input_tokens")}
            except Exception as e:  # count, don't crash the run
                row[short] = {"error": str(e)[:300]}
        rows.append(row)
        marks = " ".join(f"{s}={'✓' if row[s].get('pick') == c['gold'] else '✗'}" for s in MODELS)
        print(f"{i+1:2d}. {marks}  {c['label'][:70]}")
    return rows


def summarize(rows):
    out = {}
    for s in MODELS:
        ok = [r[s] for r in rows if "error" not in r[s]]
        ms = [r["ms"] for r in ok]
        out[s] = {
            "correct": sum(r[s].get("pick") == r["gold"] for r in rows),
            "of": len(rows), "errors": len(rows) - len(ok),
            "median_ms": pct(ms, 0.5) if ms else None, "p90_ms": pct(ms, 0.9) if ms else None,
            "cost_usd": sum(r["cost"] for r in ok),
            "mean_conf_right": _mean([r[s]["conf"] for r in rows
                                      if r[s].get("pick") == r["gold"]]),
            "mean_conf_wrong": _mean([r[s]["conf"] for r in rows
                                      if "error" not in r[s] and r[s]["pick"] != r["gold"]]),
        }
    return out


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 3) if xs else None


def main():
    key = poc.api_key()
    results = {"models": MODELS, "tasks": {}}
    for name in TASKS:
        rows = run_task(name, key)
        results["tasks"][name] = {"summary": summarize(rows), "rows": rows}
    print("\ntask         model  correct   median ms   p90 ms   errors   cost USD")
    for name, t in results["tasks"].items():
        for s, v in t["summary"].items():
            med = f"{v['median_ms']:.0f}" if v["median_ms"] else "-"
            p90 = f"{v['p90_ms']:.0f}" if v["p90_ms"] else "-"
            print(f"{name:<12} {s:<5}  {v['correct']:>2}/{v['of']:<4}  {med:>9}   {p90:>6}"
                  f"   {v['errors']:>6}   {v['cost_usd']:.5f}")
    out = str(EXPERIMENT_RESULTS / "clef-results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
