"""Run the agent on N scenarios x K runs, then print the results table.

    .venv/Scripts/python -m eval.run_all                    # s01..s05 x 3
    .venv/Scripts/python -m eval.run_all s02 s04 --runs 1
    .venv/Scripts/python -m eval.run_all --dry-run          # show the plan, no LLM call

Trajectories go to runs/<today>/agent/, the table to results/<today>_agent.md.
Re-score without re-running: python -m eval.report runs/<date>/agent
"""

from __future__ import annotations

import argparse
import time
from datetime import date
from pathlib import Path

from agent import trajectory as tr
from agent.loop import run_agent
from agent.prompts import PROMPT_VERSION, SYSTEM_PROMPT
from agent.run import resolve_scenario
from eval import report

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ["s01", "s02", "s03", "s04", "s05"]
MAX_LLM_ERRORS_IN_A_ROW = 2   # quota gone or provider down: stop instead of burning the list


def main() -> None:
    ap = argparse.ArgumentParser(description="N scenarios x K runs, then the results table.")
    ap.add_argument("scenarios", nargs="*", default=DEFAULT)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", default=str(ROOT / "runs" / date.today().isoformat() / "agent"))
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    out = Path(a.out)
    plan = [(sid, k) for k in range(1, a.runs + 1) for sid in a.scenarios]  # round-robin
    print(f"{len(plan)} runs ({len(a.scenarios)} scenarios x {a.runs}) -> {out}")
    if a.dry_run:
        return

    errors_in_a_row = 0
    for i, (sid, k) in enumerate(plan, 1):
        t0 = time.monotonic()
        traj = run_agent(resolve_scenario(sid), SYSTEM_PROMPT)
        traj["agent_version"] = PROMPT_VERSION
        traj["wall_s"] = round(time.monotonic() - t0, 1)
        traj["run_index"] = k
        saved = tr.save(traj, out)
        rep = traj["report"] or {}
        print(f"[{i:>2}/{len(plan)}] {sid} run {k}: {traj['stop_reason']} | "
              f"{rep.get('root_cause_category', '-')} | {traj['totals']['steps']} steps | "
              f"{traj['wall_s']}s -> {saved.name}")

        errors_in_a_row = errors_in_a_row + 1 if traj["stop_reason"] == "llm_error" else 0
        if errors_in_a_row >= MAX_LLM_ERRORS_IN_A_ROW:
            print(f"Stopping: {errors_in_a_row} LLM errors in a row ({traj.get('error')}).")
            break

    report.main([str(out)])


if __name__ == "__main__":
    main()
