"""Print one compact page per trajectory, for failure analysis.

    .venv/Scripts/python scripts/summarize_runs.py runs/2026-10-16/agent            # dev runs only
    .venv/Scripts/python scripts/summarize_runs.py runs/2026-10-16/agent s03        # one scenario
    .venv/Scripts/python scripts/summarize_runs.py runs/2026-10-16/agent > notes.md

Per step: the hypothesis the model wrote, each tool call with its args, how many lines came back
and the first line. Then the report, each evidence quote marked found / NOT FOUND, and the grade.
Holdout scenarios are skipped unless --allow-holdout (don't read them before Day 9).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.metrics import load_ground_truth, load_trajectory, quote_found, score_run, tool_texts  # noqa: E402


def short(text: str, width: int = 110) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[: width - 1] + "…"


def summarize(path: Path) -> str:
    traj = load_trajectory(path)
    if traj.get("stop_reason") == "llm_error":
        return f"## {path.name}\n\nprovider error, not scored\n"
    truth = load_ground_truth(traj["scenario"])
    score = score_run(traj)
    totals = traj.get("totals") or {}
    out = [
        f"## {traj['scenario']} · run {traj.get('run_index', '?')} · {path.name}",
        "",
        f"stop: {traj.get('stop_reason')} · steps: {len(traj['steps'])} · "
        f"tokens in/out: {totals.get('input_tokens', '?')}/{totals.get('output_tokens', '?')} · "
        f"tool errors: {totals.get('tool_errors', '?')} · {traj.get('wall_s', '?')} s · "
        f"duplicates: {traj.get('duplicate_calls', 0)} · invalid reports: {traj.get('invalid_reports', 0)}",
        "",
    ]
    for step in traj["steps"]:
        flag = " (forced)" if step.get("forced") else ""
        hyp = step.get("hypothesis")
        out.append(f"**{step['step']}{flag}** hyp: {short(hyp) if hyp else '—'}")
        for call in step["tool_calls"]:
            if call["tool"] == "submit_report":
                out.append("  - submit_report")
                continue
            args = json.dumps(call.get("args", {}), ensure_ascii=False)
            result = call.get("result", "")
            lines = result.count("\n") + 1 if result else 0
            dup = " DUP" if call.get("duplicate") else ""
            out.append(f"  - {call['tool']} {short(args, 70)} → {lines} lines{dup} | {short(result.splitlines()[0] if result else '', 80)}")
    report = traj.get("report") or {}
    out += ["", f"**Report** · category: {report.get('root_cause_category')} (truth: {truth['category']}) · "
                f"confidence: {report.get('confidence')}",
            f"summary: {short(report.get('summary', ''), 300)}"]
    texts = tool_texts(traj)
    for ev in report.get("evidence", []):
        mark = "found" if quote_found(ev["quote"], texts) else "**NOT FOUND**"
        out.append(f"  - [{mark}] {ev.get('source', '?')}: `{short(ev['quote'], 120)}`")
    out += ["", f"**Grade** · correct: {score['correct']} · commit: {score['commit_match']} · "
                f"category: {score['category_match']} · aliases: {score['alias_hits']} · "
                f"evidence: {score['evidence']['found']}/{score['evidence']['total']}",
            f"truth: {short(truth['key_detail'], 200)}", ""]
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", type=Path)
    parser.add_argument("scenarios", nargs="*", help="only these ids, e.g. s01 s03")
    parser.add_argument("--allow-holdout", action="store_true")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8")
    for path in sorted(args.folder.glob("*.json")):
        sid = path.name.split("_")[0]
        if args.scenarios and sid not in args.scenarios:
            continue
        if load_ground_truth(sid).get("split") == "holdout" and not args.allow_holdout:
            continue
        print(summarize(path))


if __name__ == "__main__":
    main()
