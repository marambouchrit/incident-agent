"""Export trajectories + grades + ground truth as static JSON for the viewer in ui/.

    .venv/Scripts/python scripts/export_ui_data.py runs/2026-10-22/agent_v3 runs/2026-10-22/agent_v3_holdout

Writes ui/public/data/index.json (one row per run) and ui/public/data/runs/<file>.json
(trajectory + score + ground truth + where each evidence quote was found).
The grade comes from eval.metrics.score_run, so the viewer never re-implements scoring.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eval.metrics import load_ground_truth, load_trajectory, quote_found, score_run  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "ui" / "public" / "data"


def verdict(score: dict) -> str:
    # Same counting as results/*.md: a needs_judge run keeps its category tie-break
    # (shown as a badge in the UI). "unclear" = the agent named no cause at all.
    if not score["identified"]:
        return "unclear"
    return "correct" if score["correct"] else "wrong"


def quote_locations(traj: dict) -> list[list[dict]]:
    """For each evidence quote, the (step, call) results that contain it. Empty = not seen."""
    report = traj.get("report") or {}
    out = []
    for ev in report.get("evidence", []):
        hits = []
        for step in traj["steps"]:
            for i, call in enumerate(step["tool_calls"]):
                if call["tool"] != "submit_report" and quote_found(ev["quote"], [call["result"]]):
                    hits.append({"step": step["step"], "call": i})
        out.append(hits)
    return out


def export_run(path: Path) -> tuple[dict, dict]:
    traj = load_trajectory(path)
    score = score_run(traj)
    truth = load_ground_truth(traj["scenario"])
    run_id = path.stem
    detail = {"id": run_id, "trajectory": traj, "score": score, "verdict": verdict(score),
              "truth": truth, "quote_locations": quote_locations(traj)}
    report = traj.get("report") or {}
    row = {"id": run_id, "scenario": traj["scenario"], "run_index": traj.get("run_index"),
           "split": truth.get("split"), "difficulty": truth.get("difficulty"),
           "agent_version": traj.get("agent_version"), "model": traj.get("model"),
           "verdict": verdict(score), "needs_judge": score["needs_judge"],
           "category_match": score["category_match"],
           "category": report.get("root_cause_category"), "confidence": report.get("confidence"),
           "steps": traj["totals"]["steps"], "stop_reason": traj.get("stop_reason"),
           "evidence_found": score["evidence"]["found"], "evidence_total": score["evidence"]["total"]}
    return row, detail


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dirs", nargs="+", type=Path, help="folders of trajectory JSON files")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    if args.out.exists():
        shutil.rmtree(args.out)
    (args.out / "runs").mkdir(parents=True)

    rows = []
    for d in args.dirs:
        for path in sorted(d.glob("*.json")):
            row, detail = export_run(path)
            (args.out / "runs" / f"{row['id']}.json").write_text(
                json.dumps(detail, ensure_ascii=False), encoding="utf-8")
            rows.append(row)
    rows.sort(key=lambda r: (r["scenario"], r["run_index"] or 0))
    (args.out / "index.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"exported {len(rows)} runs to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
