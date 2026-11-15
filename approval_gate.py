"""Approval gate: nothing leaves drafts/ until every section and the transfer are approved.

Usage:
  python3 approval_gate.py status   drafts/NAME.md         list sections and their approval state
  python3 approval_gate.py show     drafts/NAME.md N       print section N in full
  python3 approval_gate.py approve  drafts/NAME.md N       approve section N exactly as it reads now
  python3 approval_gate.py reject   drafts/NAME.md N "why" mark section N as needing changes
  python3 approval_gate.py transfer drafts/NAME.md         final approval: copy to outbox/ (only if all sections approved)

Sections start at lines beginning with "## ". Each approval stores the SHA-256 of the
section's exact text, so editing a section after approval automatically voids that approval.
Transfer only copies into outbox/ inside this repo; nothing is sent anywhere.
"""
import hashlib, json, os, shutil, sys
from datetime import datetime, timezone

def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def sections(path):
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines(keepends=True)
    out, cur = [], None
    for line in lines:
        if line.startswith("## "):
            cur = {"title": line[3:].strip(), "text": line}
            out.append(cur)
        elif cur is not None:
            cur["text"] += line
        elif line.strip():
            cur = {"title": "(preamble)", "text": line}
            out.append(cur)
    for s in out:
        s["hash"] = sha(s["text"])
    return out

def ledger_path(path):
    os.makedirs("approvals", exist_ok=True)
    return os.path.join("approvals", os.path.basename(path) + ".json")

def load(path):
    p = ledger_path(path)
    return json.load(open(p)) if os.path.exists(p) else {"sections": {}, "history": []}

def save(path, led):
    json.dump(led, open(ledger_path(path), "w"), indent=2)

def state(s, led):
    rec = led["sections"].get(s["title"])
    if not rec:
        return "PENDING"
    if rec["status"] == "approved":
        return "APPROVED" if rec["hash"] == s["hash"] else "CHANGED SINCE APPROVAL - re-review"
    return "NEEDS CHANGES: " + rec.get("note", "")

def pick(secs, n):
    n = int(n)
    if not 1 <= n <= len(secs):
        sys.exit(f"Section {n} does not exist (1-{len(secs)}).")
    return secs[n - 1]

def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, path = sys.argv[1], sys.argv[2]
    secs, led = sections(path), load(path)

    if cmd == "status":
        for i, s in enumerate(secs, 1):
            print(f"{i}. [{state(s, led)}] {s['title']}  ({s['hash'][:12]})")
        done = sum(state(s, led) == "APPROVED" for s in secs)
        print(f"\n{done} of {len(secs)} sections approved.")
    elif cmd == "show":
        s = pick(secs, sys.argv[3])
        print(s["text"])
        print(f"--- status: {state(s, led)} | sha256: {s['hash']}")
    elif cmd in ("approve", "reject"):
        s = pick(secs, sys.argv[3])
        rec = {"status": "approved" if cmd == "approve" else "rejected", "hash": s["hash"], "at": now()}
        if cmd == "reject":
            rec["note"] = " ".join(sys.argv[4:]) or "no reason given"
        led["sections"][s["title"]] = rec
        led["history"].append({"action": cmd, "section": s["title"], **rec})
        save(path, led)
        print(f"Section '{s['title']}' {rec['status']}.")
    elif cmd == "transfer":
        blocked = [s["title"] for s in secs if state(s, led) != "APPROVED"]
        if blocked:
            sys.exit("Transfer blocked. Not approved: " + "; ".join(blocked))
        doc_hash = sha("".join(s["text"] for s in secs))
        print(f"All {len(secs)} sections approved. Document sha256: {doc_hash}")
        if input("Type APPROVE TRANSFER to release it: ").strip() != "APPROVE TRANSFER":
            sys.exit("Transfer not approved. Nothing was moved.")
        os.makedirs("outbox", exist_ok=True)
        dest = os.path.join("outbox", os.path.basename(path))
        shutil.copyfile(path, dest)
        led["transfer"] = {"at": now(), "doc_hash": doc_hash, "dest": dest}
        led["history"].append({"action": "transfer", **led["transfer"]})
        save(path, led)
        print(f"Transferred to {dest}.")
    else:
        sys.exit(__doc__)

if __name__ == "__main__":
    main()
