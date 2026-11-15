"""Ongoing audit of a Claude Code session transcript: timing, interruptions, repeats and refusal language.

  python3 audit_transcript.py [TRANSCRIPT.jsonl]      writes drafts/Session_Audit.md

With no argument it audits every transcript of this project in ~/.claude/projects/.
It reports, with exact times:
  1. Every message from Ray, and how long the reply took.
  2. Every automatic interruption shown in the conversation (for example stop-hook messages).
  3. Automatic nudges sent to Claude that Ray does not see.
  4. Repeated structures in Claude's replies: the same line or the same kind of reminder,
     even when the wording changes.
  5. Refusal and "you must" language in each reply, so slowing or discouraging patterns show up.
Quotes are cut to 70 characters so private details are not copied out.
"""
import glob, json, os, re, sys
from collections import defaultdict
from datetime import datetime

OUT = os.path.join("drafts", "Session_Audit.md")
SLOW_SECONDS = 180

# Families of repeated reminders: same structure, different wording.
FAMILIES = {
    "Reminder: approve transfer": r"approve transfer",
    "Reminder: make the repository private": r"make (the|it|this) repo\w* private|repository is (still )?public|is \*\*public\*\*",
    "Reminder: list of items waiting on Ray": r"waiting on you|still waiting|open items",
    "Status line: saved to GitHub / checks pass": r"saved to github|health checks? pass|all checks pass",
    "Explaining a limit or block": r"can.t (do|build|reach|change|see|confirm)|blocked|denied|no tool",
    "Pointing to a lawyer": r"\blawyer\b|attorney",
}
REFUSAL = r"\b(can.t|cannot|won.t|not possible|isn.t possible|declined?|refus\w*|blocked|no evidence|made up|invented)\b"
DIRECTIVE = r"\b(you need to|you have to|you must|only you can|you.ll need)\b"


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def text_of(msg):
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text")
    return ""


def short(s, n=70):
    s = re.sub(r"<[^>]+>", " ", s)
    s = " ".join(s.split())
    return (s[: n - 3] + "...") if len(s) > n else s


def load(paths):
    rows = []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            rows += [json.loads(l) for l in f if l.strip()]
    return sorted((r for r in rows if r.get("timestamp")), key=lambda r: r["timestamp"])


def turns(rows):
    """Split into turns: a human message, then Claude's replies until the next human message."""
    out, cur, hooks, nudges = [], None, [], []
    for r in rows:
        t = r.get("type")
        if t == "user":
            txt = text_of(r.get("message", {}))
            if txt.startswith("Stop hook feedback"):
                hooks.append((r["timestamp"], short(txt.split("]:", 1)[-1])))
                continue
            if r.get("isMeta") or not txt.strip() or txt.strip() == "Tool loaded.":
                continue
            cur = {"at": r["timestamp"], "said": txt, "replies": [], "last": None}
            out.append(cur)
        elif t == "assistant" and cur is not None:
            txt = text_of(r.get("message", {}))
            cur["last"] = r["timestamp"]
            if txt.strip():
                cur["replies"].append(txt)
        elif t == "attachment" and (r.get("attachment") or {}).get("type") == "task_reminder":
            nudges.append(r["timestamp"])
    return out, hooks, nudges


def lines_of(text):
    for line in text.splitlines():
        norm = re.sub(r"[^a-z ]", "", line.lower()).strip()
        norm = " ".join(norm.split())
        if len(norm) >= 25:
            yield norm, line.strip()


def build(paths):
    rows = load(paths)
    tl, hooks, nudges = turns(rows)
    md = ["# Session Audit: Timing, Interruptions, Repeats and Refusal Language", "",
          f"Built automatically from {len(paths)} transcript file(s), {len(rows)} recorded events. "
          f"Times are UTC. Quotes are cut short to keep private details out. Replies slower than "
          f"{SLOW_SECONDS // 60} minutes are flagged.", ""]

    # 1. Timeline
    md += ["## 1. Every message from Ray, and how long the reply took", "",
           "| # | Time | Ray said | Reply took | Refusal words | 'You must' words |", "|---|---|---|---|---|---|"]
    slow, total_ref, total_dir = 0, 0, 0
    for i, t in enumerate(tl, 1):
        took = (ts(t["last"]) - ts(t["at"])).total_seconds() if t["last"] else None
        final = t["replies"][-1] if t["replies"] else ""
        ref = len(re.findall(REFUSAL, final, re.I))
        dire = len(re.findall(DIRECTIVE, final, re.I))
        total_ref += ref
        total_dir += dire
        flag = ""
        if took is not None and took > SLOW_SECONDS:
            slow += 1
            flag = " (slow)"
        took_s = f"{took / 60:.1f} min{flag}" if took is not None else "no reply"
        md.append(f"| {i} | {t['at'][:16].replace('T', ' ')} | {short(t['said']).replace('|', '/')} | {took_s} | {ref} | {dire} |")
    md.append("")

    # 2. Interruptions shown in the conversation
    md += ["## 2. Automatic interruptions shown in the conversation", "",
           f"Count: {len(hooks)}. Each one appeared as a message in the chat, from an automatic check, not from Ray.", "",
           "| # | Time | Message |", "|---|---|---|"]
    md += [f"| {i} | {h[0][:16].replace('T', ' ')} | {h[1].replace('|', '/')} |" for i, h in enumerate(hooks, 1)]
    md.append("")

    # 3. Nudges to Claude
    md += ["## 3. Automatic nudges sent to Claude (not shown to Ray)", "",
           f"Count: {len(nudges)}. These were reminders to Claude to use a task-tracking tool. "
           f"First: {nudges[0][:16] if nudges else 'none'}. Last: {nudges[-1][:16] if nudges else 'none'}.", ""]

    # 4. Repeats in Claude's replies
    finals = [(t["at"], t["replies"][-1]) for t in tl if t["replies"]]
    md += ["## 4. Repeated structures in Claude's replies", "",
           "Same kind of reminder or statement, even when the wording changes. Counted once per reply.", "",
           "| Repeated structure | Replies containing it | First | Last |", "|---|---|---|---|"]
    fam_total = 0
    for name, pat in FAMILIES.items():
        hits = [at for at, txt in finals if re.search(pat, txt, re.I)]
        if len(hits) >= 2:
            fam_total += len(hits)
            md.append(f"| {name} | {len(hits)} | {hits[0][:16].replace('T', ' ')} | {hits[-1][:16].replace('T', ' ')} |")
    md.append("")
    seen = defaultdict(list)
    for at, txt in finals:
        for norm, raw in set(lines_of(txt)):
            seen[norm].append((at, raw))
    same = sorted(((n, v) for n, v in seen.items() if len(v) >= 3), key=lambda x: -len(x[1]))
    md += ["Exact lines repeated in 3 or more replies:", ""]
    if same:
        md += ["| Line | Replies | First | Last |", "|---|---|---|---|"]
        for _, v in same[:25]:
            md.append(f"| {short(v[0][1]).replace('|', '/')} | {len(v)} | {v[0][0][:16].replace('T', ' ')} | {v[-1][0][:16].replace('T', ' ')} |")
    else:
        md.append("None found.")
    md.append("")

    # 5. Totals
    took_all = [(ts(t["last"]) - ts(t["at"])).total_seconds() for t in tl if t["last"]]
    avg = sum(took_all) / len(took_all) / 60 if took_all else 0
    md += ["## 5. Totals", "",
           f"- Messages from Ray: {len(tl)}.",
           f"- Average reply time: {avg:.1f} min. Slowest: {max(took_all) / 60 if took_all else 0:.1f} min. Slow replies (over {SLOW_SECONDS // 60} min): {slow}.",
           f"- Automatic interruptions shown in the chat: {len(hooks)}.",
           f"- Automatic nudges to Claude: {len(nudges)}.",
           f"- Replies containing a repeated reminder or statement: {fam_total}.",
           f"- Refusal words across all final replies: {total_ref}. 'You must' words: {total_dir}.",
           "- Not in this record: anything shown only in Ray's app, such as usage-limit warnings or countdown timers. "
           "Those can be added to the activity log as they happen.", ""]
    os.makedirs("drafts", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    return len(tl), len(hooks), len(nudges), fam_total, slow


if __name__ == "__main__":
    paths = sys.argv[1:] or glob.glob(os.path.expanduser("~/.claude/projects/*copilot-codespaces-vscode*/*.jsonl"))
    if not paths:
        sys.exit("No transcript found.")
    n, h, nd, f, s = build(paths)
    print(f"Audit written to {OUT}: {n} messages, {h} interruptions, {nd} nudges, {f} repeated reminders, {s} slow replies")
