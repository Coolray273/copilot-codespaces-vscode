"""Health check: proves the whole system is working and gives it an ID ("DNA").

Run:  python3 health_check.py

Checks:
  1. Files       every core file is present
  2. Code        every script compiles without errors
  3. Storage     manifest files exist and none are duplicates
  4. Approvals   every recorded approval has a valid signature and matches the current text
  5. GitHub      no unsaved changes, and nothing waiting to be pushed
Then it computes the system fingerprint: one SHA-256 over every tracked file.
If any file changes, the fingerprint changes. Each run is logged in health_log.json,
so you can see when the system last checked out clean and whether anything changed since.
"""
import glob, hashlib, json, os, subprocess
from datetime import datetime, timezone

CORE = ["generate_exports.py", "storage_guard.py", "family_tree.py", "approval_gate.py",
        "requirements.txt", "CLAUDE.md", "drafts/Legal_Reference.md", "keys/approver_public.key"]
MANIFEST = ["R1_Master_Manifest.txt", "R1_Master_Manifest.docx", "R1_Master_Manifest.pdf"]
LOG = "health_log.json"


def sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()


def check_files():
    missing = [p for p in CORE if not os.path.exists(p)]
    return not missing, "all present" if not missing else "missing: " + ", ".join(missing)


def check_code():
    bad = []
    for p in glob.glob("*.py"):
        try:
            compile(open(p, encoding="utf-8").read(), p, "exec")
        except SyntaxError as e:
            bad.append(f"{p} line {e.lineno}: {e.msg}")
    return not bad, "all scripts compile" if not bad else "errors: " + "; ".join(bad)


def check_storage():
    missing = [p for p in MANIFEST if not os.path.exists(p)]
    if missing:
        return False, "missing: " + ", ".join(missing)
    hashes = [sha_file(p) for p in MANIFEST]
    if len(set(hashes)) != len(hashes):
        return False, "duplicate files found"
    return True, f"{len(MANIFEST)} files, no duplicates"


def check_approvals():
    try:
        import approval_gate as g
    except ImportError as e:
        return False, f"cannot load approval gate ({e}); run: pip install -r requirements.txt"
    problems, total = [], 0
    for ledger in glob.glob("approvals/*.json"):
        doc = os.path.join("drafts", os.path.basename(ledger)[:-5])
        if not os.path.exists(doc):
            problems.append(f"{doc} missing")
            continue
        led = g.load(doc)
        for s in g.sections(doc):
            if s["title"] in led["sections"]:
                total += 1
                st = g.state(s, led)
                if st != "APPROVED" and not st.startswith("NEEDS CHANGES"):
                    problems.append(f"{os.path.basename(doc)} '{s['title']}': {st}")
    if problems:
        return False, "; ".join(problems) + " -> run approval_gate.py repair"
    return True, f"{total} approvals, all signatures valid"


def check_github():
    if git("status", "--porcelain", "--", ".", ":!health_log.json"):
        return False, "unsaved changes (not committed)"
    ahead = git("rev-list", "--count", "@{u}..HEAD")
    if ahead and ahead != "0":
        return False, f"{ahead} commit(s) not pushed to GitHub"
    return True, "everything saved and pushed"


def fingerprint():
    h = hashlib.sha256()
    for p in sorted(git("ls-files").splitlines()):
        if p != LOG and os.path.exists(p):
            h.update(p.encode() + b"\0" + sha_file(p).encode() + b"\n")
    return h.hexdigest()


def main():
    checks = [("Files", check_files), ("Code", check_code), ("Storage", check_storage),
              ("Approvals", check_approvals), ("GitHub", check_github)]
    results = []
    for name, fn in checks:
        ok, detail = fn()
        results.append({"check": name, "ok": ok, "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    dna = fingerprint()
    log = json.load(open(LOG)) if os.path.exists(LOG) else []
    last = log[-1] if log else None
    all_ok = all(r["ok"] for r in results)
    print(f"\nSystem fingerprint: {dna[:16]}...")
    if last:
        print("Since last check: " + ("no changes" if last["fingerprint"] == dna else "files have changed"))
    print("OVERALL: " + ("WORKING - all checks passed" if all_ok else "ATTENTION NEEDED - see FAIL lines above"))

    log.append({"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "fingerprint": dna, "ok": all_ok, "results": results})
    with open(LOG, "w") as f:
        json.dump(log[-100:], f, indent=2)
    raise SystemExit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
