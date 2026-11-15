"""Activity log: a tamper-evident record of every request, delay and block.

Each entry stores the SHA-256 of the entry before it (a hash chain, like a ledger).
Changing or deleting any past entry breaks the chain, and `verify` shows exactly where.

Run:
  python3 activity_log.py add "what was asked" OUTCOME CAUSE "what happened" [minutes] [doc ...]
  python3 activity_log.py note KIND "Ray's exact words" "how it was read / what each side said"
  python3 activity_log.py repeat CAUSED_BY COUNT "what repeated" "why"   (CAUSED_BY: ray | system | claude)
  python3 activity_log.py report      totals by outcome and cause, plus document word counts
  python3 activity_log.py verify      check that no entry has been changed or removed

KIND (note):
  unclear           wording that could mean more than one thing, and how it was read
  interpretation    a reading Claude chose, so it can be checked
  debate            a disagreement, with each side's position and how it ended
  direction-change  the plan changed, and why
(add entries are KIND "request".)

OUTCOME: done | delayed | blocked
CAUSE (why it was not instant):
  none          worked first time
  broken        a bug in the code; fixed by changing the code
  access        an account or permission setting (for example GitHub access)
  safety-rule   a protection that stops an action on purpose, with the reason given
  waiting-on-ray  needs Ray's decision or approval
  outside       an outside service or tool problem (for example a package that would not install)
"""
import hashlib, json, os, sys
from collections import Counter
from datetime import datetime, timezone

LOG = "activity_log.jsonl"
OUTCOMES = {"done", "delayed", "blocked"}
CAUSES = {"none", "broken", "access", "safety-rule", "waiting-on-ray", "outside"}
KINDS = {"unclear", "interpretation", "debate", "direction-change"}
REPEAT_BY = {"ray", "system", "claude"}
GENESIS = "0" * 64


def entry_hash(e):
    return hashlib.sha256(json.dumps({k: v for k, v in e.items() if k != "hash"},
                                     sort_keys=True).encode()).hexdigest()


def read():
    if not os.path.exists(LOG):
        return []
    with open(LOG, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def words(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return len(f.read().split())


def add(asked, outcome, cause, detail, minutes=None, docs=(), at=None):
    if outcome not in OUTCOMES or cause not in CAUSES:
        sys.exit(f"OUTCOME must be one of {sorted(OUTCOMES)}; CAUSE one of {sorted(CAUSES)}")
    append({"kind": "request", "at": at, "asked": asked, "outcome": outcome, "cause": cause, "detail": detail,
         "minutes": float(minutes) if minutes not in (None, "") else None,
         "docs": {d: words(d) for d in docs if os.path.exists(d)}})


def note(kind, wording, detail, at=None):
    if kind not in KINDS:
        sys.exit(f"KIND must be one of {sorted(KINDS)}")
    append({"kind": kind, "at": at, "wording": wording, "detail": detail})


def repeat(by, count, what, detail, at=None):
    if by not in REPEAT_BY:
        sys.exit(f"CAUSED_BY must be one of {sorted(REPEAT_BY)}")
    append({"kind": "repeat", "at": at, "caused_by": by, "count": int(count),
            "wording": what, "detail": detail})


def append(fields):
    log = read()
    now = datetime.now(timezone.utc).isoformat(timespec="minutes")
    e = {"n": len(log) + 1, **fields, "at": fields.get("at") or now, "logged": now,
         "prev": log[-1]["hash"] if log else GENESIS}
    e["hash"] = entry_hash(e)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"Logged #{e['n']}: {e['kind']}" + (f" {e['outcome']} ({e['cause']})" if "outcome" in e else ""))
    try:  # keep the law book continuous
        import law_book
        law_book.build()
    except Exception as err:
        print(f"(law book not rebuilt: {err})")


def verify(quiet=False):
    prev = GENESIS
    for i, e in enumerate(read(), 1):
        if e.get("n") != i or e.get("prev") != prev or entry_hash(e) != e.get("hash"):
            print(f"BROKEN CHAIN at entry {i}: it was changed, removed or reordered.")
            return False
        prev = e["hash"]
    if not quiet:
        print(f"Chain intact: {len(read())} entries, none changed or removed.")
    return True


def report():
    everything = read()
    ok = verify()
    log = [e for e in everything if e.get("kind", "request") == "request"]
    notes = [e for e in everything if e.get("kind", "request") != "request"]
    print(f"\nEntries: {len(everything)}  (requests {len(log)}, other notes {len(notes)})")
    print("\nBy kind:")
    for k, v in Counter(e.get("kind", "request") for e in everything).most_common():
        print(f"  {k:17} {v:3}")
    for label, field in (("By outcome", "outcome"), ("By cause", "cause")):
        print(f"\n{label}:")
        for k, v in Counter(e[field] for e in log).most_common():
            mins = sum(e["minutes"] or 0 for e in log if e[field] == k)
            print(f"  {k:15} {v:3}" + (f"   {mins:g} min" if mins else ""))
    print("\nNot instant, and why:")
    for e in log:
        if e["cause"] != "none":
            t = f" ({e['minutes']:g} min)" if e["minutes"] else ""
            print(f"  #{e['n']} {e['at'][:16]} [{e['outcome']}/{e['cause']}]{t} {e['asked']}: {e['detail']}")
    for kind in ("unclear", "interpretation", "debate", "direction-change"):
        items = [e for e in notes if e["kind"] == kind]
        if items:
            print(f"\n{kind.upper()}:")
            for e in items:
                print(f"  #{e['n']} {e['at'][:16]} Ray: \"{e['wording']}\"\n      -> {e['detail']}")
    docs = {}
    for e in log:
        docs.update(e["docs"])
    if docs:
        print("\nDocument word counts (at time logged):")
        for d, w in docs.items():
            print(f"  {d}: {w} words")
    return ok


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["add"] and len(a) >= 5:
        add(a[1], a[2], a[3], a[4], a[5] if len(a) > 5 else None, a[6:])
    elif a[:1] == ["repeat"] and len(a) == 5:
        repeat(a[1], a[2], a[3], a[4])
    elif a[:1] == ["note"] and len(a) == 4:
        note(a[1], a[2], a[3])
    elif a == ["report"]:
        sys.exit(0 if report() else 1)
    elif a == ["verify"]:
        sys.exit(0 if verify() else 1)
    else:
        sys.exit(__doc__)
