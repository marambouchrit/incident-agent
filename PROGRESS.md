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

Current day: **Day 2**  ·  Agent version: —  ·  Dev model: gemini-3.5-flash-lite (free tier: 15 RPM · 250K TPM · 500 RPD)  ·  Final model: —

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

### Day 1 — 2026-10-13 — Environment & first scenarios
- **Done:**
  - Target app "shopline" (api, worker, payments stub, load generator, PostgreSQL) runs in Docker Compose with JSON logs; own 10-commit git history (`2ca8b57`).
  - Capture tool records a live incident into `scenarios/<id>/` + `ground_truth/<id>.json`; 5 fault kits (`cd6f764`).
  - 5 scenarios recorded from the live app (`82487a9`): s01 missing migration (easy, dev), s02 wrong env var (easy, holdout), s03 OOM restart (easy, dev), s04 pool exhaustion (medium, holdout), s05 dropped index (medium, dev).
  - Automated review per scenario: cause and symptom in different files, timing lines up, 0 real giveaway hits. Log volume in range except the worker in s01 (1,490 lines) and s02 (1,483), just under the 1,500 minimum.
  - Fault map in `docs/TARGET_APP_BRIEF.md` §8.
- **TODO(human) gaps filled:** —
- **Learned:** (→ also in `docs/concepts.md`)
  - Cause and symptom are kept in different places because that is what makes an agent necessary; if they were together, the problem could be read off directly.
  - The log gives the mechanism, not the root cause (s04: the log says the pool is full; only the config and the commit say who shrank it and when).
- **Blocked / questions for Claude:**
  - The first s01 recording was lost (laptop went to sleep; worker crashed every 5 min from a query bug). Both fixed; recordings need the lid open.
  - s04 and s05 differ from the brief: s04 needed traffic bursts and a 1 s pool timeout; s05 drops the order_items(order_id) index, and the app gained an item count on the order history page (s01–s04 were recorded before that change).
  - `pytest` not installed yet, no `.venv`.
- **Next:** solve s02–s05 by hand (< 10 min each, s01 done), then Day 2: tools, guards, registry, unit tests.

### Day 2 — YYYY-MM-DD
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
