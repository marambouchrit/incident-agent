# Progress Log — Incident Investigation Agent

> Companion to `ROADMAP.md`. One entry per working day. Keep it short and honest.

## Status

| Checkpoint | Target day | Status | Notes |
|---|---|---|---|
| CP0 — Setup (CLAUDE.md, Learning style, spec, skills) | 0 | ✅ | 2026-10-13 |
| CP1 — E2E on 5 scenarios | 4 | ⬜ | |
| CP2 — One-command eval on ~12 | 7 | ⬜ | |
| CP3 — Agent vs. baseline, full set | 10 | ⬜ | |
| CP4 — Repo, viewer, demo | 13 | ⬜ | |

Current day: **Day 1**  ·  Agent version: —  ·  Dev model: gemini-3.5-flash-lite (free tier: 15 RPM · 250K TPM · 500 RPD)  ·  Final model: —

---

## Daily entries

### Day 0 — 2026-10-13 — Setup checklist (see `SETUP.md`)
- [x] Repo created, setup files committed (`591ec95`, 13 files, remote `origin` set)
- [x] Claude Code: CLAUDE.md recognized · Learning style active · `/next` answers "Day 0"
- [x] Dev model chosen, `.env` filled (`gemini` / `gemini-3.5-flash-lite`; `.env` is git-ignored)
- [x] `/log-day` run, CP0 ticked
- **Learned:**
- **Open / not verified:**
  - API key not tested yet (no call made); first proof is the Day 3 run.
  - Free-tier limits seen in AI Studio on 2026-10-13: Flash models (3.8, 3.7) 5 RPM / 20 RPD, too low for an agent; Flash-Lite models (3.5, 3.1) 15 RPM / 500 RPD. Switched dev model from `gemini-3.8-flash` to `gemini-3.5-flash-lite`.
  - Final (stronger) model for Day 12 is undecided: 20 RPD on free Flash cannot run a full eval.
  - `pytest` is not installed (system Python 3.12, no `.venv` yet); needed by Day 2.
- **Next:** Day 1 — target app, capture script, 5 scenarios (3 easy + 2 medium) + ground truth; manual giveaway review.

### Day 1 — YYYY-MM-DD
- **Done:**
- **TODO(human) gaps filled:**
- **Learned:** (→ also in `docs/concepts.md`)
- **Blocked / questions for Claude:**
- **Next:**

<!-- copy the block above for each day -->

---

## Failure taxonomy (from Day 6)

| Failure mode | Count (dev) | Example trajectory | Fix tried | Effect |
|---|---|---|---|---|
| Anchoring on first hypothesis | | | | |
| Wrong tool / bad args | | | | |
| Context drowning | | | | |
| Gave up too early | | | | |
| Looping | | | | |
| Hallucinated evidence | | | | |

---

## Results snapshots

| Date | System | Model | Scenarios × runs | Acc. (E/M/H) | Evidence prec. | Avg steps | Avg cost | Avg latency |
|---|---|---|---|---|---|---|---|---|

---

## Future work (ideas parked to protect scope)

-
