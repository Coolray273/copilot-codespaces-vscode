# Read this first: project state and how to work with Ray

## How Ray wants to work
- Keep answers short: what's good, what's better, and why. No long lessons.
- Never just say no. Always give a solution or a clear reason.
- Fix problems and keep work moving without asking each time.
- Approvals are the exception: record one only when Ray says yes to that specific thing.
- His rule: bring work back for review, approve each section, then approve the transfer separately.
- Be honest: R1, R2 and the "Genius Federation" exist here only as text in these files. Don't claim powers that don't exist.

## What's here (branch: claude/anti-relay-firewall-pj2ko2)
- `generate_exports.py`: writes the manifest as TXT, DOCX, PDF and an email draft (`R1_Master_Manifest.*`).
- `storage_guard.py`: SHA-256 duplicate check on the manifest files.
- `family_tree.py`: writes the hierarchy tree to `R1_Family_Tree.txt`.
- `approval_gate.py`: four-step gate (fingerprint, review, ML-DSA signature, final transfer) plus `repair` for self-correction. Run with no arguments for usage.
- `drafts/Legal_Reference.md`: plain-language guide to computer-access and stored-email laws. Not legal advice.
- `health_check.py`: run first in any session. Checks files, code, storage, approval signatures and GitHub sync, and prints a system fingerprint.
- `activity_log.py`: hash-chained log of every request, delay and block, with cause and word counts. Add an entry for every request (`add`), especially any delay or block, with its real cause. `report` for totals.
- Setup: `pip install -r requirements.txt`

## Where things stand (updated 2026-11-15)
- Legal reference: all 7 sections approved by Ray in chat on 2026-11-15, recorded and signed by Claude (see `keys/approver_label.txt`).
- International reference (`drafts/International_Reference.md`, UK/Canada/Australia/Switzerland/Singapore): 6 sections, waiting for Ray's review.
- **Waiting on Ray: step 4, the final transfer of the legal reference.** Do not run it until he says "approve transfer".
- The signing key lived in the old session's home folder and is gone in a new session. Existing approvals still verify with `keys/approver_public.key`. Running `keygen` again would replace the public key and void those signatures, so ask Ray first.
- Next after transfer: the document is for a lawyer or an ic3.gov report. Suggested: Maryland Volunteer Lawyers Service.

## Ideas Ray has raised (not built)
- Offline/rural continuity: a local AI on his own computer (for example Ollama), and off-grid radio messaging (for example Meshtastic LoRa radios). Needs his own hardware.
