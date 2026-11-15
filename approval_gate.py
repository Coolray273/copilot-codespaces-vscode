"""Approval gate with four-step verification. Nothing leaves drafts/ until all four pass.

  Step 1  Fingerprint   Every section gets a SHA-256 fingerprint of its exact text.
  Step 2  Your review   You read the whole document and approve it (all at once or by section).
  Step 3  Signature     Each approval is signed with your ML-DSA-65 key (post-quantum).
                        Without your private key, no one can fake or change an approval.
  Step 4  Transfer      Every fingerprint and signature is re-checked, then you give a
                        separate final approval. Only then is the file copied to outbox/.

Usage:
  python3 approval_gate.py keygen                      make your signing key (once)
  python3 approval_gate.py review   drafts/NAME.md     show the whole document and decide
  python3 approval_gate.py status   drafts/NAME.md     where each section stands
  python3 approval_gate.py transfer drafts/NAME.md     final checks and final approval

At the review prompt:  APPROVE ALL  |  APPROVE 1 2 3  |  CHANGE 6 <what to change>  |  Enter = no decision
Editing a section after it is approved voids that approval automatically.
Transfer only copies into outbox/ inside this repo; nothing is sent anywhere.
"""
import hashlib, json, os, shutil, sys
from datetime import datetime, timezone
from dilithium_py.ml_dsa import ML_DSA_65 as MLDSA

SECRET_KEY = os.path.expanduser("~/.approval_gate/ml_dsa_secret.key")  # never in the repo
PUBLIC_KEY = os.path.join("keys", "approver_public.key")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canon(rec):
    """The exact bytes that get signed: every field except the signature itself."""
    return json.dumps({k: v for k, v in rec.items() if k != "sig"}, sort_keys=True).encode()


def keygen():
    if os.path.exists(SECRET_KEY):
        sys.exit(f"A key already exists at {SECRET_KEY}. Not overwriting it.")
    pk, sk = MLDSA.keygen()
    os.makedirs(os.path.dirname(SECRET_KEY), exist_ok=True)
    with open(SECRET_KEY, "w") as f:
        f.write(sk.hex())
    os.chmod(SECRET_KEY, 0o600)
    os.makedirs("keys", exist_ok=True)
    with open(PUBLIC_KEY, "w") as f:
        f.write(pk.hex())
    print(f"Private key: {SECRET_KEY} (keep it secret, back it up)")
    print(f"Public key:  {PUBLIC_KEY} (safe to share; used to check signatures)")


def sign(rec):
    if not os.path.exists(SECRET_KEY):
        sys.exit("No signing key. Run: python3 approval_gate.py keygen")
    rec["sig"] = MLDSA.sign(bytes.fromhex(open(SECRET_KEY).read()), canon(rec)).hex()
    return rec


def sig_ok(rec):
    if not os.path.exists(PUBLIC_KEY) or "sig" not in rec:
        return False
    return MLDSA.verify(bytes.fromhex(open(PUBLIC_KEY).read()), canon(rec), bytes.fromhex(rec["sig"]))


def sections(path):
    out, cur = [], None
    with open(path, encoding="utf-8") as f:
        for line in f.read().splitlines(keepends=True):
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
    with open(ledger_path(path), "w") as f:
        json.dump(led, f, indent=2)


def state(s, led):
    rec = led["sections"].get(s["title"])
    if not rec:
        return "PENDING"
    if not sig_ok(rec):
        return "SIGNATURE INVALID - re-review"
    if rec["status"] == "approved":
        return "APPROVED" if rec["hash"] == s["hash"] else "CHANGED SINCE APPROVAL - re-review"
    return "NEEDS CHANGES: " + rec.get("note", "")


def record(path, led, s, status, note=None):
    rec = {"section": s["title"], "status": status, "hash": s["hash"], "at": now()}
    if note:
        rec["note"] = note
    sign(rec)
    led["sections"][s["title"]] = rec
    led["history"].append(rec)
    save(path, led)


def status(path):
    secs, led = sections(path), load(path)
    for i, s in enumerate(secs, 1):
        print(f"{i}. [{state(s, led)}] {s['title']}")
    done = sum(state(s, led) == "APPROVED" for s in secs)
    print(f"\n{done} of {len(secs)} sections approved.")
    return secs, led


def review(path):
    secs, led = sections(path), load(path)
    print("=" * 60)
    for i, s in enumerate(secs, 1):
        print(f"[Section {i} - {state(s, led)}]\n{s['text'].rstrip()}\n")
    print("=" * 60)
    answer = input("APPROVE ALL | APPROVE 1 2 3 | CHANGE N <what> | Enter = no decision: ").strip()
    words = answer.split()
    if not words:
        print("No decision recorded.")
    elif answer.upper() == "APPROVE ALL":
        for s in secs:
            record(path, led, s, "approved")
        print(f"All {len(secs)} sections approved and signed.")
    elif words[0].upper() == "APPROVE" and all(w.isdigit() and 1 <= int(w) <= len(secs) for w in words[1:]) and words[1:]:
        for w in words[1:]:
            record(path, led, secs[int(w) - 1], "approved")
        print("Approved and signed: sections " + ", ".join(words[1:]))
    elif words[0].upper() == "CHANGE" and len(words) > 2 and words[1].isdigit() and 1 <= int(words[1]) <= len(secs):
        record(path, led, secs[int(words[1]) - 1], "rejected", " ".join(words[2:]))
        print(f"Section {words[1]} marked for changes.")
    else:
        sys.exit("Not understood. Nothing was recorded.")
    print()
    status(path)


def transfer(path):
    secs, led = sections(path), load(path)
    print("Step 1 + 3 re-check: fingerprints and signatures")
    blocked = []
    for i, s in enumerate(secs, 1):
        st = state(s, led)
        print(f"  {i}. {st}")
        if st != "APPROVED":
            blocked.append(str(i))
    if blocked:
        sys.exit("Transfer blocked. Not approved: sections " + ", ".join(blocked))
    doc_hash = sha("".join(s["text"] for s in secs))
    print(f"Step 2 confirmed: all {len(secs)} sections approved by you.")
    print(f"Document fingerprint: {doc_hash}")
    if input("Step 4: type APPROVE TRANSFER to release it: ").strip() != "APPROVE TRANSFER":
        sys.exit("Transfer not approved. Nothing was moved.")
    os.makedirs("outbox", exist_ok=True)
    dest = os.path.join("outbox", os.path.basename(path))
    shutil.copyfile(path, dest)
    if sha(open(dest, encoding="utf-8").read()) != sha(open(path, encoding="utf-8").read()):
        os.remove(dest)
        sys.exit("Copy did not match the original. Transfer cancelled.")
    rec = sign({"action": "transfer", "doc_hash": doc_hash, "dest": dest, "at": now()})
    led["transfer"] = rec
    led["history"].append(rec)
    save(path, led)
    print(f"All four steps passed. Transferred to {dest}.")


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "keygen":
        return keygen()
    if len(sys.argv) != 3 or sys.argv[1] not in ("review", "status", "transfer"):
        sys.exit(__doc__)
    {"review": review, "status": status, "transfer": transfer}[sys.argv[1]](sys.argv[2])


if __name__ == "__main__":
    main()
