# capture

`capture/capture.sh <id> <fault>` (run from Git Bash) records one incident:

1. Resets the shop repo to its base commit and starts the healthy shop.
2. Starts log recording and traffic.
3. Runs the fault's scripts at their minutes (default: `inject.sh` at minute 18 of 35).
4. Writes `scenarios/<id>/` and `ground_truth/<id>.json`.
5. Runs `reset.sh` and stops the shop.

Useful options: `--healthy-min`, `--total-min`, `--force`, `--out-root <dir>` (write somewhere else, for trials).

## What a fault folder contains (`faults/<fault>/`)

| File | Purpose |
|---|---|
| `inject.sh` | Makes the change: edit files in the shop repo, commit, deploy. Calls `mark_culprit` after the culprit commit. |
| `reset.sh` | Undoes anything outside git (database schema, data). Must be safe to run on a healthy shop. |
| `incident.txt` | The symptom report. Placeholders are filled at capture time. |
| `ground_truth.json` | The answer, in the format of `docs/SCENARIO_SPEC.md` §3. Same placeholders. |
| `timeline.txt` (optional) | Lines of `<minute> <script>` to run several scripts, e.g. unrelated commits before the culprit. |

Scripts run with the shop repo as working directory, with `$WORK` and `$FAULTS_DIR` set. Shared helpers: `source "$FAULTS_DIR/lib.sh"`.

Placeholders: `{{ID}}`, `{{CULPRIT_COMMIT}}`, `{{INJECT_TS}}`, `{{INJECT_TIME}}` (HH:MM UTC), `{{FIRST_ERROR_TS}}`, `{{FIRST_ERROR_TIME}}`, `{{FIRST_CRASH_TS}}`, `{{FIRST_CRASH_TIME}}` (first out-of-memory kill).

The word scan at the end is a first filter only. `/review-scenario` and a manual read are still required.
