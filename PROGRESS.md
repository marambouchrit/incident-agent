# Progress Log — Incident Investigation Agent

> Companion to `ROADMAP.md`. One entry per working day. Keep it short and honest.

## Status

| Checkpoint | Target day | Status | Notes |
|---|---|---|---|
| CP0 — Setup (CLAUDE.md, Learning style, spec, skills) | 0 | ✅ | 2026-10-13 |
| CP1 — E2E on 5 scenarios | 4 | ✅ | 2026-10-15 · 5/5 submitted, right commit 5/5, right category 2/5 |
| CP2 — One-command eval on ~12 | 7 | ✅ | 2026-10-18 · 11 × 3, prompt v2: cause 28/33 (holdout 15/15), category 22/33 |
| CP3 — Agent vs. baseline, full set | 10 | ⬜ | |
| CP4 — Repo, viewer, demo | 13 | ⬜ | |

Current day: **Day 8**  ·  Agent version: v2 (system prompt v2)  ·  Dev model: gemini-3.5-flash-lite (free tier: 15 RPM · 250K TPM · 500 RPD)  ·  Final model: —

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

### Day 2 — 2026-10-15 — Tools
- **Done:**
  - Hand-solved s02–s05 (Day 1 "done when" now met for all 5).
  - `.venv` (pydantic 2.14, pytest 9.1), `requirements.txt`, `pytest.ini`.
  - `agent/tools/`: guards (`safe_path`, `cap_output` + footer, `run_with_timeout`), parsing (jsonl, Postgres log with DETAIL/STATEMENT folded, diffs, pg_dump schema, containers), 7 tools + `submit_report` schema (Pydantic), registry (`tool_specs`, `run_tool`: validate → timeout → cap).
  - 89 tests green (1 skipped: symlink test needs Windows Developer Mode). `ground_truth/` proven unreachable from every scenario; every tool output ≤ 100 lines on s01–s05; error messages list valid options.
  - `scripts/try_tools.py <id>` prints what the model sees for each tool.
  - `log_stats` checked on all 5 scenarios: each fault has a visible signal (s01 first errors 14:06 + deploy 45b232b; s02 connection refused on POST /checkout; s03 19 worker restarts; s04 `QueuePool limit of size 2`; s05 p95 160 → 768 ms on GET /orders, zero errors).
- **TODO(human) gaps filled:** truncation footer, `format_stats` (log_stats output), tool descriptions — all three written by Claude at my request.
- **Learned:** (→ also in `docs/concepts.md` #4–6)
  - Cutting output can hide the error (line 200 vs. cap 100) → filter before cutting, summarize with `log_stats`, footer tells the model what's missing.
  - A summary can erase evidence: masking all numbers turned "size 2" into "size N" in s04. Tests checked shape, not content; reading the real output caught it.
  - Some faults have no errors at all (s03, s05): an errors-only summary would make them invisible.
- **Blocked / questions for Claude:**
  - `cap_output` counts lines, not characters: a db log line holds a full SQL statement. Watch token size on Day 3.
  - Pydantic `Optional` args become `anyOf` in the JSON schema; check the Gemini provider accepts it on Day 3.
- **Next:** Day 3 — `agent/llm.py` wrapper, the loop (system prompt, dispatch, 15-step limit, forced report), first autonomous run on s01.

### Day 3 — 2026-10-15 — The loop (first autonomous run)
- **Done:**
  - `agent/llm.py`: Gemini REST wrapper (stdlib only), neutral message format, `llm_call(messages, tools, tool_choice)` → (msg, usage). Retries on 429/5xx, RPM throttle (`LLM_RPM=14`), tokens + latency per call. Ping OK: 1,598 input tokens for 8 tool specs + 2 short messages.
  - `agent/loop.py`: loops until a valid `submit_report` or 15 steps. Tool errors go back as results; a text-only answer gets a nudge (costs a step); `submit_report` is forced at the limit (`not_identified` allowed); `llm_error` stops but keeps the trajectory.
  - `agent/prompts.py` (system prompt v1), `agent/trajectory.py` (full tool results per step → `runs/`), `agent/run.py` CLI.
  - 101 tests green (1 skipped): offline LLM conversion, loop with a scripted fake LLM (submit, unknown tool/bad args, step limit, text-only, provider failure), prompt giveaway check.
  - First autonomous run on s01 (`e82f4f4`): correct `missing_migration` in 5 steps (log_stats → list_commits → show_commit 45b232b → get_db_schema orders → submit_report), 18,861 in / 656 out tokens, 34.7 s LLM time. Ignored the payments-503 red herring.
  - Cleanup (`4471f9f`): removed dead `NotImplementedError` paths in `run.py` and the skip in `test_loop.py`.
- **TODO(human) gaps filled:** loop control logic, system prompt v1. Both written by Claude at my request. No open gaps.
- **Learned:** (→ also in `docs/concepts.md` #7–10, #24 and `docs/journal.md` Day 3)
  - System prompt = fixed rules (same for every scenario); user prompt = the incident ticket (symptom only).
  - The provider name stays inside `llm.py`; the loop only knows `llm_call`, so changing provider means changing one file.
  - The model chooses every step, including when to call `submit_report`. Code checks the report's *form* (Pydantic); only the eval checks whether it's *right*.
  - The agent picks each tool from the previous result (hash from `log_stats` → `show_commit`; table from the diff → `get_db_schema`). It fixes bad calls from error messages, but never fixes the app (read-only).
  - Holdout (s02, s04): run them for CP1, never tune on what they show.
  - Silent faults: s03 has 0 errors (signal = 19 restarts), s05 has 0 errors (signal = p95 160 → 768 ms). Connection pool = a few DB connections kept open and shared; s04 shrank it from 10 to 2.
- **Blocked / questions for Claude:**
  - s01 report has `confidence: 1`: overconfident (calibration, Day 5).
  - Steps 1 and 5 have no `Hypothesis:` line (3/5 followed). Option for later: a required `hypothesis` argument on tools.
  - Input tokens per turn doubled in 5 steps (2,354 → 4,735). Watch on 15-step runs.
  - Day 2 question answered: Gemini accepts Pydantic's `anyOf` through `parametersJsonSchema`.
- **Next:** Day 4 — report validation (1 retry max), duplicate-call detection, run all 5 scenarios, one failure note per scenario → CP1.

### Day 4 — 2026-10-15 — Structured report + ✅ CP1
- **Done:**
  - Invalid `submit_report`: 1 retry for the whole run (forced final call included), then stop with `invalid_report`; exact Pydantic error sent back + "NOT recorded" + tries left. `traj["invalid_reports"]`.
  - Duplicate-call detection: same tool + same args (key order and `None` ignored) → tool not re-run, model gets a 5-line preview of the first result + "try a different angle". Counts as a step. `traj["duplicate_calls"]`, `duplicate: true` per call.
  - `scripts/run_all.py`: runs s01–s05, prints a summary table (no grading).
  - 108 tests green (1 skipped).
  - Real run, gemini-3.5-flash-lite, prompt v1, 1 run each: **5/5 `submitted`**, 6–9 steps, 26–39K tokens, 0 duplicates, 0 invalid reports.
- **Failure notes (1 run each, compared by hand to `ground_truth/`):**

  | id | Right commit | Category (agent → truth) | Note |
  |---|---|---|---|
  | s01 | ✅ 45b232b | ✅ missing_migration | **Hallucinated evidence**: quote `column_name \| character varying \| 40 \| yes` from `db/schema` appears in no tool output. Right answer, fake proof. |
  | s02 | ✅ 0f782bf | ✅ bad_config | Clean: 6 steps, both quotes real. |
  | s03 | ✅ 7cca109 | ❌ resource_exhaustion → infra_crash | Cause found (OOM, `.all()`), but 9 steps with **no hypothesis written** at all; third quote ("requeued interrupted jobs") is real but doesn't prove the OOM. |
  | s04 | ✅ a0f1bed | ❌ bad_config → resource_exhaustion | Cause found (pool 10 → 2). Category is the trigger (config) instead of the effect (exhausted pool). |
  | s05 | ✅ de45f63 | ❌ code_bug → performance_regression | Cause found (dropped index on order_items.order_id). Zero errors in the logs and still found. |

  Across all 5: `confidence: 1` every time (no calibration signal); many steps with no hypothesis text.
- **TODO(human) gaps filled:** `on_invalid_report`, `on_duplicate`, failure notes — written by Claude at my request.
- **Learned:** (→ `docs/concepts.md` #11–13)
  - "Submitted" means the mechanics work, not that the answer is right: the s01 fake quote passed every check we have today.
  - The categories overlap (OOM = crash or exhaustion? pool shrunk by config = config or exhaustion?). 3/5 "wrong" categories with 5/5 right commits says the label set is ambiguous, not that the agent is lost.
- **Blocked / questions for Claude:**
  - Correctness rule for Day 5: grade on category, on key detail/commit, or both? The category set may need clearer definitions (or the rule should accept the key detail).
  - Duplicate detection and report retry never fired on real runs; only unit tests cover them so far.
- **Next:** Day 5 — eval harness v0: correctness rule, verbatim evidence check (would catch s01), calibration, 3 runs per scenario.

### Day 5 — 2026-10-16 — Evaluation harness v0
- **Done:**
  - `eval/metrics.py`: verbatim evidence check (`quote_found`: whitespace-insensitive, `...` may skip text, no fuzzy match; `submit_report` results excluded so an echoed quote can't find itself), correctness signals + `grade` (correct = culprit commit AND a key alias in summary/fix; category scored separately; half-specific → `needs_judge`), `calibration_buckets` (3 buckets, identified runs only), `not_identified_rate`.
  - `eval/run_all.py` (N scenarios × K runs, round-robin, wall-clock per run, stops after 2 provider errors in a row) and `eval/report.py` (markdown table per scenario + aggregate → `results/<date>_agent.md`; `llm_error` runs listed, not scored).
  - 126 tests green (1 skipped). "Done when" met: the fake-trajectory test catches a fabricated quote, and the real s01 Day 4 run flags `column_name | character varying | 40 | yes`.
  - Real eval (`3f440b2`), gemini-3.5-flash-lite, prompt v1: 14 scored runs (s02 has 2; 4 runs lost to HTTP 503, 3 re-run). Cause found **14/14**, category **7/14**, evidence **32/38 (0.84)**, not_identified 0 %, all confidence 1.00. 6.9 steps, ~31K tokens, ~98 s per run.
- **TODO(human) gaps filled:** `quote_found`, `grade`, `calibration_buckets`. All three written by Claude at my request.
- **Learned:** (→ `docs/concepts.md` #25–27, `docs/journal.md` Day 5)
  - Running costs quota and scoring is free, so they are kept separate: a rule change re-scores every saved run without new LLM calls.
  - Facts (`correctness_signals`) vs. rule (`grade`): two scores show the investigation works (14/14) while the labels don't (7/14, same mistakes each run on s03 and s04).
  - A provider outage is not an agent failure: before the fix, 2 empty runs counted as wrong and `not_identified`.
  - The 6 unseen quotes are 3 kinds: 3 real faults (s01 rewritten as a fake log line; s03 ×2 diff sign inverted, `-` instead of `+`), 1 borderline (s02 non-adjacent lines glued), 2 false alarms (s04, s05: `+` diff prefix dropped).
- **Blocked / questions for Claude:**
  - Evidence rule: allow omitting a diff's `+`/`-` prefix but not writing the wrong one? Decide with a before/after number (Day 6/7).
  - Category definitions: s03 (`resource_exhaustion` vs `infra_crash`) and s04 (`bad_config` vs `resource_exhaustion`) are wrong the same way every run.
  - Calibration has no signal yet (14/14 in one bucket at 1.00); needs hard scenarios.
  - Gemini free tier is unstable (503 "high demand"): 4/18 runs lost today.
- **Next:** Day 6 — ~7 more scenarios (first hard ones), dev/holdout tags, eval on dev set, failure taxonomy with counts.

### Day 6 — 2026-10-16 → 2026-10-18 — More scenarios + failure analysis
- **Done:**
  - 6 new scenarios recorded live (`9489cd0`): s06 payments provider down (medium, dev, no culprit commit), s07 Decimal×float pricing bug (medium, holdout), s08 Postgres statement_timeout 30s→250ms (medium, dev), s10 N+1 in an "orders repository" refactor, pool look-alike of s04 (hard, holdout), s11 payments timeout 3→0.07 s hidden in a "tune HTTP client" commit (hard, dev), s12 jobs.priority column without migration, crash-loop look-alike of s03 (hard, holdout). Set: **11 scenarios**, 6 dev / 5 holdout, 3 easy / 5 medium / 3 hard. Every recording checked: error count, first_error_ts, log volume.
  - s09 (worker takes all Postgres connections) recorded twice, 1 api error each time: not reproducible → deleted with its kit.
  - `capture/dry_run.sh` (kit on a throwaway clone with a fake docker, ~10 s), `capture/record_batch.sh` (sequential recording, failures skipped), `scripts/summarize_runs.py` (one page per trajectory, holdout skipped).
  - Grading: no culprit commit → `commit_match = None` and the category takes its place (`"" in text` was always True); generic alias `payments` removed from s06; `eval/run_all.py` defaults to every scenario folder. 182 tests green (1 skipped).
  - Dev eval (`f801346`), 6 × 3 = 18 runs, all submitted: cause found **12/18** (easy 6/6, medium 3/9, hard 3/3), category **6/18**, evidence **45/55 (0.82)**, confidence 0.99 vs. accuracy 0.67, 7.2 steps, ~35K tokens, ~31 s per run.
  - "Done when" met: top 2 failure modes named with trajectories (table below).
  - `docs/journal.md` is now git-ignored (local study notes).
- **TODO(human) gaps filled:** no-culprit grading rule, failure taxonomy. Both by Claude at my request.
- **Learned:** (→ `docs/concepts.md` #28–30)
  - #1 anchoring (6/18): s08 blames the "popularity" commit 3/3 (search slow since 20:38, broken only at 20:49, 4 s after the timeout reload) and never reads postgres.conf or db.log; s06 spends steps 2–8 on the decoy config commit before checking containers.
  - #2 wrong category / misread evidence (12/18): s03, s05 label overlap; s06 reads exit_code=137 as OOM although oom_killed=False.
  - Designed difficulty ≠ difficulty for the agent: hard s11 3/3 (culprit = last commit), medium s08 0/3 (last visible commit is the decoy).
  - 7 of 10 "unseen" quotes are diff lines without their `+`/`-`: the check is too strict there.
  - A dry-run proves the scripts run, not that the incident happens (s09). Performance assumptions need a measurement on the real machine (s08 EXPLAIN ANALYZE: 550–745 ms → timeout lowered from 500 ms to 250 ms).
- **Blocked / questions for Claude:**
  - Day 5 journal is still in the GitHub history (`3f440b2`); removing it needs a force-push.
  - Recording took ~5 h 20 instead of ~4 h (PC sleep +34 min, s09 retry +36 min).
  - Gemini quota (500 RPD) can't fit 2 × dev + full eval in one day: reuse today's dev eval as the "before" run.
- **Next:** Day 7 — mitigations for #1 (verify timing + state before submit_report, a requirement not a tool order) and #2 (clearer category definitions), evidence rule for diff prefixes, before/after on dev, then one-command eval on all 11 × 3 → CP2.

### Day 7 — 2026-10-18 — Targeted mitigations + ✅ CP2
- **Done:**
  - Evidence rule (`eval/metrics.py`): a diff line may be quoted without its `+`/`-`; a wrong sign still fails (quote matched against the original text or a prefix-stripped copy, never a mix). Day 6 runs re-scored with 0 LLM calls: **45/55 → 52/55**; the 3 left are real faults (s03 ×2 inverted sign, s05 paraphrase).
  - Tool level (`agent/tools/descriptions.py`): `get_container_status` said *"Exit code 137 … means it ran out of memory"* (wrong since Day 2) → now "137 = killed; `oom_killed` says whether memory was the reason". `submit_report` now defines each category, following `docs/SCENARIO_SPEC.md` §6.
  - Prompt **v2** (`agent/prompts.py`): "Before you conclude" requires timing (first error vs. every change), state (config/schema/containers) and one ruled-out alternative, in any order (no fixed tool sequence).
  - Leak fixed: v1's evidence example was `"git/45b232b"`, s01's real culprit commit (since Day 3). New test: no ground-truth culprit commit in the prompt or any tool description.
  - 186 tests green (1 skipped).
  - Before/after on dev (6 × 3, both with the new evidence rule): cause **12/18 → 13/18**, category **6/18 → 11/18**, evidence 52/55 → 50/55, confidence/accuracy 0.99/0.67 → 1.00/0.72, tokens 34.9K → 38.5K (+10 %).
  - CP2: holdout 5 × 3 added to the same `runs/2026-10-18/agent_v2/` → full 11 × 3 with v2 (`results/2026-10-18_agent_v2.md`): cause **28/33** (dev 13/18, holdout **15/15**), category 22/33, evidence 93/98 (0.95), confidence 1.00 vs. accuracy 0.85. `python -m eval.run_all` runs all 11 × 3 in one command; today it ran in two parts (dev, then holdout) to save quota.
  - Commit `d6bd927`.
- **TODO(human) gaps filled:** evidence rule, tool description fix + category definitions, prompt v2. All by Claude at my request.
- **Learned:** (→ `docs/concepts.md` #31–32)
  - Fix the observation before adding a rule: the s06 "137 = OOM" misread came from our own tool description.
  - Category definitions fixed the label problem: s03 0/3 → 3/3, s05 0/3 → 2/3.
  - Anchoring only partly fixed: on s08 the agent now opens the config commit `2ef2fad` 2/3 times (0/3 in v1), but still doesn't compare the times (20:49:30 change, 20:49:35 first error) and keeps the 20:38 commit as the main cause (1/3 correct).
  - s06 stays 0/3 for a label reason: 2/3 runs find "payments container exited, `oom_killed=False`" but say `infra_crash`; nothing in the snapshot shows `payments` is external (same compose file). Not tuned further (would overfit dev).
  - Holdout > dev (15/15 vs 13/18) means the fixes didn't overfit; it doesn't mean the agent is perfect (the agent-hard cases s06/s08 happen to be dev; 15 runs is small). Holdout misses on category: s04 1/3, s10 1/3 (pool look-alikes). Numbers only, holdout runs not read.
  - Tool + prompt changed together: the gain is measured for the set, not per change.
- **Blocked / questions for Claude:**
  - Overconfidence unchanged (confidence ~1.00 on every run): no calibration signal yet.
  - New fabricated quote in s06 v2 run 1 (`PAYMENTS_URL=http://paymnts:8080`), caught by the evidence check.
  - `docs/concepts.md` is tracked in git although my rule is "don't push concepts"; left out of `d6bd927`, decide (commit or untrack).
  - Day 8 asks for 15–20 scenarios; recording 6 took ~5 h 20 on Day 6.
- **Next:** Day 8 — one-shot baseline (`baseline/`, same `submit_report` schema, fixed token budget), `eval --system baseline`, cost estimate; scenario count decision.

<!-- copy the block above for each day -->

---

## Failure taxonomy (from Day 6)

| Failure mode | Count (dev) | Example trajectory | Fix tried | Effect |
|---|---|---|---|---|
| **#1 Anchoring on the first suspicious commit** (blames/chases the commit just before the errors, never checks timing or state) | **6/18** (s08 3/3 wrong answer; s06 3/3 spent steps 2–8 on the decoy config commit before checking containers) | runs/2026-10-18/agent/s08_v1_20261018T180917.json · runs/2026-10-18/agent/s06_v1_20261018T180847.json | Prompt v2 "Before you conclude" (timing, state, alternatives) | Partial: s08 opens `2ef2fad` 0/3 → 2/3, correct 0/3 → 1/3; still no timing comparison |
| **#2 Wrong category / misread evidence** | **12/18** category wrong (s03 3/3, s05 3/3 label overlap; s06 3/3 reads `exit_code=137` as OOM although `oom_killed=False`; s08 3/3 code_bug) | runs/2026-10-18/agent/s06_v1_20261018T181143.json | Category definitions in `submit_report`; 137 description fixed | Dev category 6/18 → 11/18 (s03 0 → 3, s05 0 → 2); s06 0/3 remains (label ambiguity) |
| Overconfidence | 18/18 runs at confidence ≥ 0.95; accuracy 0.67 | results/2026-10-18_agent.md (calibration) | — | v2 full set: 33/33 at ~1.00, accuracy 0.85 |
| Hallucinated evidence | 3/18 v1 (s03 ×2 inverted sign, s05 paraphrase); v2 dev 5 quotes incl. 1 invented diff (s06) | runs/2026-10-18/agent_v2/s06_v2_20261018T190030.json | Evidence rule (diff prefix) | False alarms gone (45 → 52/55); real fakes still caught |
| Wrong tool / bad args | 0 | — | — | |
| Context drowning | 0 (max 66K tokens, s06 run 3) | — | — | |
| Gave up too early | 0 (0 not_identified) | — | — | |
| Looping | 1 duplicate call (s06 run 3) | runs/2026-10-18/agent/s06_v1_20261018T181500.json | duplicate detection (Day 4) | blocked, agent moved on |
| Hallucinated evidence | Day 5: 4 runs. Day 6: 3 quotes (s03 ×2 rebuilt diff lines, s05 paraphrase with `->`) | runs/2026-10-16/agent/s03_v1_20261016T154505.json | verbatim evidence check (Day 5) | detected, not prevented |
| Evidence check false alarm (diff `+`/`-` stripped by the agent) | 7 of 10 "not seen" quotes on Day 6 (s08 ×3, s11 ×2, s05 ×2) | runs/2026-10-18/agent/s11_v1_20261018T180938.json | — (Day 7: accept missing diff prefix) | |

---

## Results snapshots

| Date | System | Model | Scenarios × runs | Acc. (E/M/H) | Evidence prec. | Avg steps | Avg cost | Avg latency |
|---|---|---|---|---|---|---|---|---|
| 2026-10-16 | agent v1 | gemini-3.5-flash-lite | 5 × 3 (14 scored) | 8/8 · 6/6 · – | 0.84 | 6.9 | $0 (free) | 98 s |
| 2026-10-18 | agent v1 (dev set) | gemini-3.5-flash-lite | 6 × 3 (18 scored) | 6/6 · 3/9 · 3/3 | 0.82 | 7.2 | $0 (free) | 31 s |

---

## Future work (ideas parked to protect scope)

-
