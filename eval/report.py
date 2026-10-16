"""Turn a folder of trajectories into a markdown results table.

    .venv/Scripts/python -m eval.report runs/2026-10-16/agent
    .venv/Scripts/python -m eval.report runs/s0*_v1_20261015T22*.json   # loose files work too

Prints the table and writes it to results/<folder-date>_<system>.md.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path

from agent.llm import load_env
from eval.metrics import (calibration_buckets, load_ground_truth, load_trajectory,
                          not_identified_rate, score_run)

ROOT = Path(__file__).resolve().parents[1]


def _price(name: str) -> float:
    """USD per 1M tokens from .env (LLM_PRICE_IN / LLM_PRICE_OUT); 0 when unset (free tier)."""
    try:
        return float(os.environ.get(name, "0") or 0)
    except ValueError:
        return 0.0


def score_paths(paths: list[Path]) -> list[dict]:
    load_env()
    p_in, p_out = _price("LLM_PRICE_IN"), _price("LLM_PRICE_OUT")
    rows = []
    for p in sorted(paths):
        traj = load_trajectory(p)
        t = traj.get("totals") or {}
        truth = load_ground_truth(traj["scenario"])
        r = score_run(traj)
        r.update({
            "path": p, "difficulty": truth.get("difficulty", "?"), "split": truth.get("split", "?"),
            "steps": t.get("steps", 0),
            "tokens_in": t.get("input_tokens", 0), "tokens_out": t.get("output_tokens", 0),
            "cost": (t.get("input_tokens", 0) * p_in + t.get("output_tokens", 0) * p_out) / 1e6,
            # wall_s is written by eval/run_all.py; older runs only have LLM time
            "latency_s": traj.get("wall_s", t.get("latency_ms", 0) / 1000),
        })
        rows.append(r)
    return rows


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _fmt(x: float | None, spec: str = ".2f") -> str:
    return "-" if x is None else format(x, spec)


def _evidence(rows: list[dict]) -> tuple[int, int]:
    found = sum(r["evidence"]["found"] for r in rows)
    total = sum(r["evidence"]["total"] for r in rows)
    return found, total


def _frac(k: int, n: int) -> str:
    return f"{k}/{n}" if n else "-"


PROVIDER_FAILURES = {"llm_error"}   # the provider failed, not the agent: never scored


def render(rows: list[dict], title: str) -> str:
    out = [f"# {title}", ""]
    lost = [r for r in rows if r["stop_reason"] in PROVIDER_FAILURES]
    rows = [r for r in rows if r["stop_reason"] not in PROVIDER_FAILURES]
    if lost:
        out += [f"> {len(lost)} run(s) lost to provider errors, not scored: "
                + ", ".join(sorted(r["path"].name for r in lost)), ""]
    by_id: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_id[r["scenario"]].append(r)

    out += ["## Per scenario", "",
            "| id | diff | split | runs | correct | category | judge | evidence | not_id | "
            "steps | tokens | latency s | cost $ |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for sid in sorted(by_id):
        rs = by_id[sid]
        f, t = _evidence(rs)
        out.append(
            f"| {sid} | {rs[0]['difficulty']} | {rs[0]['split']} | {len(rs)} "
            f"| {_frac(sum(r['correct'] for r in rs), len(rs))} "
            f"| {_frac(sum(r['category_match'] for r in rs), len(rs))} "
            f"| {sum(r['needs_judge'] for r in rs)} | {_frac(f, t)} "
            f"| {sum(not r['identified'] for r in rs)} "
            f"| {_fmt(_mean([r['steps'] for r in rs]), '.1f')} "
            f"| {_fmt(_mean([r['tokens_in'] + r['tokens_out'] for r in rs]), ',.0f')} "
            f"| {_fmt(_mean([r['latency_s'] for r in rs]), '.1f')} "
            f"| {_fmt(_mean([r['cost'] for r in rs]), '.4f')} |")

    n = len(rows)
    f, t = _evidence(rows)
    acc = {d: [r for r in rows if r["difficulty"] == d] for d in ("easy", "medium", "hard")}
    acc_s = ", ".join(f"{d} {_frac(sum(r['correct'] for r in v), len(v))}" for d, v in acc.items())
    out += ["", "## Aggregate", "",
            f"- Runs: {n} ({len(by_id)} scenarios)",
            f"- Correct (cause found): {_frac(sum(r['correct'] for r in rows), n)}"
            f" (by difficulty: {acc_s})",
            f"- Category match: {_frac(sum(r['category_match'] for r in rows), n)}",
            f"- Needs judge: {sum(r['needs_judge'] for r in rows)}",
            f"- Evidence precision: {_frac(f, t)} ({_fmt(f / t if t else None)})",
            f"- not_identified rate: {_fmt(not_identified_rate(rows))}",
            f"- Stop reasons: " + ", ".join(
                f"{k} {v}" for k, v in sorted(_count(r["stop_reason"] for r in rows).items())),
            f"- Avg steps {_fmt(_mean([r['steps'] for r in rows]), '.1f')}"
            f" | avg tokens {_fmt(_mean([r['tokens_in'] + r['tokens_out'] for r in rows]), ',.0f')}"
            f" | avg latency {_fmt(_mean([r['latency_s'] for r in rows]), '.1f')} s"
            f" | avg cost ${_fmt(_mean([r['cost'] for r in rows]), '.4f')}"]

    out += ["", "## Calibration (identified runs)", "",
            "| confidence | n | avg confidence | accuracy |", "|---|---|---|---|"]
    for b in calibration_buckets(rows):
        out.append(f"| {b['range']} | {b['n']} | {b['avg_confidence']:.2f} | {b['accuracy']:.2f} |")

    missing = [(r["scenario"], q) for r in rows for q in r["evidence"]["missing"]]
    if missing:
        out += ["", "## Quotes not seen in any tool output", ""]
        out += [f"- {sid}: `{q[:100]}`" for sid, q in missing]
    return "\n".join(out) + "\n"


def _count(items) -> dict:
    c: dict = defaultdict(int)
    for x in items:
        c[x] += 1
    return c


def collect(args: list[str]) -> list[Path]:
    paths: list[Path] = []
    for a in args:
        p = Path(a)
        paths += sorted(p.glob("*.json")) if p.is_dir() else [p]
    return paths


def main(argv: list[str]) -> Path | None:
    paths = collect(argv)
    if not paths:
        sys.exit("No trajectories found. Give a folder (runs/<date>/agent) or .json files.")
    first = Path(argv[0])
    # runs/<date>/<system>  ->  results/<date>_<system>.md ; loose files -> results/adhoc.md
    name = f"{first.parent.name}_{first.name}" if first.is_dir() else "adhoc"
    text = render(score_paths(paths), f"Results - {name}")
    print(text)
    out = ROOT / "results" / f"{name}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"written: {out.relative_to(ROOT).as_posix()}")
    return out


if __name__ == "__main__":
    main(sys.argv[1:])
