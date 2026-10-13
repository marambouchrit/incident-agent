---
name: log-day
description: End-of-day wrap-up. Draft today's PROGRESS.md entry from what actually happened in the repo, check pace against the next checkpoint, and prompt my concepts journal. Use when I say I'm done for the day or run /log-day.
argument-hint: "[optional: notes, blockers, what I learned]"
disable-model-invocation: true
---

Wrap up today. My notes (may be empty): $ARGUMENTS

1. **Gather facts:** `git log --since="18 hours ago" --oneline`, `git status`, `pytest -q`, open gaps (`grep -rn "TODO(human)" agent baseline eval`), and today's section in `ROADMAP.md`.
2. **Draft the entry** in `PROGRESS.md` using the existing template (Done · TODO(human) gaps filled · Learned · Blocked · Next). Use facts, not effort ("tools return capped output, 9 tests green", not "worked on tools"). Use my notes for Learned/Blocked. Don't invent learnings.
3. **Update the status block:** tick a checkpoint only if its "Done when" condition is actually met; advance "Current day" only if today's deliverable is met.
4. **Pace check (2–3 lines):** on track / behind for the next checkpoint. If behind, propose one concrete cut.
5. **Journal prompt:** name the 1–2 concepts from today worth a paragraph in `docs/concepts.md`, and ask me to write them in my own words. Do NOT write them for me.
6. Show me the diff of `PROGRESS.md` and ask before saving it.
