"""Builds the Law Book Challenge from the activity log. Re-run anytime; the log also rebuilds it on every new entry.

  python3 law_book.py        writes drafts/Law_Book_Challenge.md

Part One: the case file (every logged event as a numbered exhibit, labels removed).
Part Two: the challenge (what students look for and how they score).
Part Three: the inventory (answer key and totals), at the back.
"""
import json, os, re
from collections import Counter

LOG = "activity_log.jsonl"
OUT = os.path.join("drafts", "Law_Book_Challenge.md")

CATEGORIES = {
    "WORKED": "Worked as directed (not a finding)",
    "BUG": "Broken: a bug in the code, then fixed",
    "CD-ACCESS": "Blocked: a missing permission",
    "CD-NOT-FOUND": "Could not: the thing does not exist where searched",
    "CD-OUTSIDE": "Delayed: an outside tool or service problem",
    "CD-SYSTEM-BLOCK": "Blocked by the automatic safety check",
    "CD-CHOICE": "Declined by Claude, with a stated reason",
    "CD-HONESTY": "Declined because it would mean stating something unknown as fact",
    "WAITING": "Waiting on Ray's decision",
    "UNCLEAR": "Unclear wording, and how it was read",
    "INTERPRETATION": "An interpretation Claude chose",
    "DEBATE": "A disagreement between Ray and Claude",
    "DIRECTION": "A change of direction",
    "CORRECTION": "A mistake that was found and corrected",
    "REPEAT": "Something that had to be repeated",
}


def classify(e):
    kind, d = e.get("kind", "request"), e.get("detail", "")
    if kind != "request":
        if "(log correction)" in e.get("wording", "") or d.startswith("Correction:"):
            return "CORRECTION"
        if kind == "repeat":
            return "REPEAT"
        return {"unclear": "UNCLEAR", "interpretation": "INTERPRETATION",
                "debate": "DEBATE", "direction-change": "DIRECTION"}[kind]
    m = re.match(r"(CD-[A-Z-]+)", d)
    if m:
        return m.group(1)
    return {"none": "WORKED", "broken": "BUG", "access": "CD-ACCESS",
            "waiting-on-ray": "WAITING",
            "outside": "CD-NOT-FOUND" if "not found" in d.lower() else "CD-OUTSIDE",
            "safety-rule": "CD-SYSTEM-BLOCK" if "safety check" in d.lower() else "CD-CHOICE",
            }[e["cause"]]


def strip_code(text):
    return re.sub(r"^CD-[A-Z-]+:\s*", "", text)


def build():
    log = [json.loads(l) for l in open(LOG, encoding="utf-8") if l.strip()]
    rows = [(e, classify(e)) for e in log]
    findings = [(e, c) for e, c in rows if c != "WORKED"]
    head = log[-1]["hash"][:16] if log else "none"

    out = ["# The Genius Federation Law Book Challenge",
           "",
           f"Built automatically from the activity log: {len(log)} exhibits, log seal {head}. "
           "The log is hash-chained, so these exhibits match the original record exactly. "
           "General information for study, not legal advice.",
           "",
           "## Part One: The Case File",
           "",
           "Each exhibit is one logged event, in order. Labels have been removed. Read every exhibit; "
           "some show the system working exactly as directed, and those are not findings.",
           ""]
    for e, _ in rows:
        said = e.get("wording") or e.get("asked", "")
        if e.get("kind") == "repeat":
            said += f" (repeated {e['count']} times)"
        out.append(f"**Exhibit {e['n']}** ({e['at'][:10]}). Asked or said: \"{said}\"  ")
        out.append(f"What happened: {strip_code(e.get('detail', ''))}")
        out.append("")

    out += ["## Part Two: The Challenge",
            "",
            "Find every exhibit where the system did not act 100% as directed, or where the direction changed. That means:",
            "every refusal, block, delay, bug, mistake, unclear wording, interpretation, debate, change of direction and repeat.",
            "For a repeat, also name who caused it: Ray, the company or system, or Claude. (1 extra point)",
            "",
            "For each one you find, write down:",
            "1. The exhibit number. (1 point)",
            "2. Its category, from the list below. (1 point)",
            "3. Your judgment: was the stated reason true, and was the action lawful and proper? Give your evidence. (1 point, awarded by the judges)",
            "",
            "Categories:",
            ""]
    out += [f"- {k}: {v}" for k, v in CATEGORIES.items() if k != "WORKED"]
    out += ["",
            "Penalty: minus 1 point for listing an exhibit where the system worked as directed.",
            f"Maximum score: {len(findings) * 3 + sum(1 for _, c in findings if c == 'REPEAT')} points "
            f"({len(findings)} findings x 3, plus 1 per repeat for naming who caused it).",
            "The student with the most points wins. Ties go to the student with the strongest evidence in step 3.",
            "",
            "## Part Three: The Inventory (Answer Key)",
            "",
            "For judges only. Keep this part separate from the student copies.",
            "",
            "| Exhibit | Category | Code | Summary |",
            "|---|---|---|---|"]
    for e, c in findings:
        summary = (e.get("asked") or e.get("wording", "")).replace("|", "/")
        if len(summary) > 80:
            summary = summary[:77] + "..."
        out.append(f"| {e['n']} | {CATEGORIES[c]} | {c} | {summary} |")
    counts = Counter(c for _, c in rows)
    out += ["",
            "### Totals",
            "",
            "| Category | Count | Share of all exhibits |",
            "|---|---|---|"]
    for k in CATEGORIES:
        if counts.get(k):
            out.append(f"| {CATEGORIES[k]} | {counts[k]} | {counts[k] / len(rows):.1%} |")
    reps = [e for e, c in rows if c == "REPEAT"]
    if reps:
        by = Counter()
        for e in reps:
            by[e["caused_by"]] += e["count"]
        total = sum(by.values())
        out += [f"| **All exhibits** | **{len(rows)}** | **100%** |", "",
                "### Repeats, by who caused them", "",
                "| Caused by | Times repeated | Share |", "|---|---|---|"]
        names = {"ray": "Ray", "system": "Company or system", "claude": "Claude"}
        for k, v in by.most_common():
            out.append(f"| {names[k]} | {v} | {v / total:.1%} |")
        out += [f"| **All repeats** | **{total}** | **100%** |", ""]
    else:
        out += [f"| **All exhibits** | **{len(rows)}** | **100%** |"]
    out += [
            f"Findings for students: {len(findings)}. Worked as directed: {counts.get('WORKED', 0)}. "
            "No exhibit records a legal order or outside party stopping the work.",
            ""]
    os.makedirs("drafts", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    return len(log), len(findings)


if __name__ == "__main__":
    n, f = build()
    print(f"Law book rebuilt: {n} exhibits, {f} findings -> {OUT}")
