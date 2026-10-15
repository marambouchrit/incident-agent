"""Run the agent on one scenario and save its trajectory.

    .venv/Scripts/python -m agent.run scenarios/s01
    .venv/Scripts/python -m agent.run s01 --max-steps 10
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent import trajectory as tr
from agent.loop import MAX_STEPS, run_agent
from agent.prompts import PROMPT_VERSION, SYSTEM_PROMPT

ROOT = Path(__file__).resolve().parents[1]


def resolve_scenario(arg: str) -> Path:
    """Accept 's01' or 'scenarios/s01'."""
    path = Path(arg)
    if not path.is_dir():
        path = ROOT / "scenarios" / arg
    if not (path / "incident.txt").is_file():
        sys.exit(f"Not a scenario folder (no incident.txt): {arg}")
    return path


def print_summary(traj: dict, saved: Path) -> None:
    print(f"\n=== {traj['scenario']} | {traj['model']} | prompt {traj['agent_version']} ===")
    for step in traj["steps"]:
        mark = " (forced)" if step["forced"] else ""
        print(f"[{step['step']:>2}]{mark} {(step['hypothesis'] or '-').strip()[:110]}")
        for c in step["tool_calls"]:
            err = "  ERROR" if c["is_error"] else ""
            print(f"      -> {c['tool']}({c['args']}){err}")
    print(f"\nstop: {traj['stop_reason']}")
    if traj.get("error"):
        print(f"error: {traj['error']}")
    report = traj["report"]
    if report:
        print(f"report: {report.get('status')} | {report.get('root_cause_category')} "
              f"| confidence {report.get('confidence')}")
        print(f"  {report.get('summary')}")
    t = traj["totals"]
    print(f"\n{t['steps']} steps | {t['tool_calls']} tool calls ({t['tool_errors']} errors) | "
          f"{t['input_tokens']} in / {t['output_tokens']} out tokens | {t['latency_ms'] / 1000:.1f}s LLM")
    print(f"saved: {saved.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the incident agent on one scenario.")
    parser.add_argument("scenario", help="scenario id (s01) or folder (scenarios/s01)")
    parser.add_argument("--max-steps", type=int, default=MAX_STEPS)
    args = parser.parse_args()

    scenario_dir = resolve_scenario(args.scenario)
    traj = run_agent(scenario_dir, SYSTEM_PROMPT, max_steps=args.max_steps)
    traj["agent_version"] = PROMPT_VERSION
    print_summary(traj, tr.save(traj))


if __name__ == "__main__":
    main()
