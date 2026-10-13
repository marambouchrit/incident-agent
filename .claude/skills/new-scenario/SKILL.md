---
name: new-scenario
description: Generate one incident scenario (fault scripts, capture, scenario folder, ground truth) following docs/SCENARIO_SPEC.md.
argument-hint: "<fault> <easy|medium|hard> [extra idea]"
disable-model-invocation: true
---

Create a new scenario. Arguments: $ARGUMENTS (fault, difficulty, optional idea).

This is generated work. You write it fully; I review it.

1. Read `docs/SCENARIO_SPEC.md` and `ls scenarios ground_truth` to pick the next neutral ID (`sNN`). Check the current dev/holdout ratio and assign `split` to keep it near 60/40.
2. Propose the design in ≤ 10 lines and wait for my OK:
   - symptom (what `incident.txt` will say) and where it shows up
   - the cause and where it lives (must be a different place)
   - the culprit commit's realistic, intent-describing message
   - unrelated commits and red herrings (counts per difficulty table)
   - timeline: healthy period → change → first error
3. After my OK, implement it: `faults/<fault>/inject.sh` + `reset.sh` (reuse existing ones if the fault exists), run it via the capture flow, and produce `scenarios/sNN/` and `ground_truth/sNN.json`.
   If Docker isn't available, say so and stop. Don't hand-fake the logs unless I explicitly allow a synthetic scenario.
4. Run the `review-scenario` checks on the result and fix any failure before reporting.
5. Report: ID, difficulty, split, one-line summary, and anything I should manually double-check. Remind me to solve it by hand (< 10 min) before marking it ready.
