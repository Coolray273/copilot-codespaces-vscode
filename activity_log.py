"""Activity log: a tamper-evident record of every request, delay and block.

Each entry stores the SHA-256 of the entry before it (a hash chain, like a ledger).
Changing or deleting any past entry breaks the chain, and `verify` shows exactly where.

Run:
  python3 activity_log.py add "what was asked" OUTCOME CAUSE "what happened" [minutes] [doc ...]
  python3 activity_log.py report      totals by outcome and cause, plus document word counts
  python3 activity_log.py verify      check that no entry has been changed or removed

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
    log = read()
    e = {"n": len(log) + 1,
         "at": at or datetime.now(timezone.utc).isoformat(timespec="minutes"),
         "asked": asked, "outcome": outcome, "cause": cause, "detail": detail,
         "minutes": float(minutes) if minutes not in (None, "") else None,
         "docs": {d: words(d) for d in docs if os.path.exists(d)},
         "prev": log[-1]["hash"] if log else GENESIS}
    e["hash"] = entry_hash(e)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"Logged #{e['n']}: {outcome} ({cause})")


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
    log = read()
    ok = verify()
    print(f"\nRequests logged: {len(log)}")
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
    elif a == ["report"]:
        sys.exit(0 if report() else 1)
    elif a == ["verify"]:
        sys.exit(0 if verify() else 1)
    else:
        sys.exit(__doc__)
