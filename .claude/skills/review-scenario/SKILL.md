---
name: review-scenario
description: Check a scenario for giveaways, symptom/cause separation, noise, red herrings, timing and solvability against docs/SCENARIO_SPEC.md.
argument-hint: "<scenario id, e.g. s03, or 'all'>"
disable-model-invocation: true
---

Review scenario(s): $ARGUMENTS

For each scenario, read `docs/SCENARIO_SPEC.md`, the folder `scenarios/<id>/` and `ground_truth/<id>.json`, then check:

1. **Format:** all required files exist; log lines parse as JSON with the required fields; ≥ 8 commits; neutral folder ID.
2. **Leak scan:** grep the whole scenario folder (case-insensitive) for: the `fault` value, `ground_truth`, `inject`, `scenario`, `fault`, `bug`, `oops`, `hack`, `break`, `temporar`, `TODO`, `FIXME`. Show every hit with its file and line.
3. **Giveaway checklist** (§6 of the spec), item by item: ✅ / ❌ + one-line reason.
4. **Separation:** the first visible symptom's file ≠ the cause location in the ground truth.
5. **Timing:** the culprit change happens before `first_error_ts`; a healthy period exists before it; red herrings fit their described timing.
6. **Noise & difficulty:** line counts per service, WARNING/ERROR in the healthy period, and red herring count vs. the difficulty table.
7. **Solvability:** quote the exact lines (file + content) a human would use as evidence. If you can't find them verbatim, it's a ❌.

Output a short table per scenario (check → ✅/❌ → note), then a verdict: **ready** or **fix needed** (with the fixes listed). Don't modify anything unless I ask.
This automated review does not replace my manual check (solving it by hand).
