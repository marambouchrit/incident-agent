"""Run the agent on several scenarios, one after another, and print a summary table.

    .venv/Scripts/python scripts/run_all.py              # s01..s05
    .venv/Scripts/python scripts/run_all.py s02 s04

No grading here (that is eval/, Day 5): this only produces trajectories to read.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import trajectory as tr  # noqa: E402
from agent.loop import run_agent  # noqa: E402
from agent.prompts import PROMPT_VERSION, SYSTEM_PROMPT  # noqa: E402
from agent.run import ROOT, print_summary, resolve_scenario  # noqa: E402

DEFAULT = ["s01", "s02", "s03", "s04", "s05"]


def main() -> None:
    ids = sys.argv[1:] or DEFAULT
    rows = []
    for sid in ids:
        traj = run_agent(resolve_scenario(sid), SYSTEM_PROMPT)
        traj["agent_version"] = PROMPT_VERSION
        saved = tr.save(traj)
        print_summary(traj, saved)
        report, t = traj["report"] or {}, traj["totals"]
        rows.append((sid, traj["stop_reason"], report.get("status", "-"), report.get("root_cause_category", "-"),
                     report.get("confidence", "-"), t["steps"], traj.get("duplicate_calls", 0),
                     traj.get("invalid_reports", 0), t["input_tokens"] + t["output_tokens"],
                     saved.relative_to(ROOT).as_posix()))

    head = ("id", "stop", "status", "category", "conf", "steps", "dup", "bad_rep", "tokens", "trajectory")
    print("\n" + " | ".join(head))
    for r in rows:
        print(" | ".join(str(x) for x in r))


if __name__ == "__main__":
    main()
