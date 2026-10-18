"""Metrics computed from one saved trajectory (runs/*.json).

Day 5 starts with the evidence check: every quote in the final report must come
from a tool result the agent actually received in that same run.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def load_trajectory(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def tool_texts(traj: dict) -> list[str]:
    """Every tool result the model saw, in order.

    submit_report results are excluded: a validation error echoes the report's
    own input back, so a fabricated quote would "find itself" there.
    Duplicate previews and error messages stay in: the model did see them.
    """
    return [
        call["result"]
        for step in traj["steps"]
        for call in step["tool_calls"]
        if call["tool"] != "submit_report"
    ]


def _squash(s: str) -> str:
    return " ".join(s.split())


def quote_found(quote: str, texts: list[str]) -> bool:
    # Rule: verbatim up to whitespace; "..." may skip text; case and characters must match
    # exactly (no fuzzy match, so a one-character typo counts as not seen).
    pieces = [_squash(p) for p in quote.replace("…", "...").split("...")]
    pieces = [p for p in pieces if p]
    if not pieces:
        return False
    for text in map(_squash, texts):
        pos = 0
        for p in pieces:
            pos = text.find(p, pos)
            if pos < 0:
                break
            pos += len(p)
        else:
            return True
    return False


def evidence_check(traj: dict) -> dict:
    """Score the report's evidence against what the agent saw.

    Returns precision = found / total, or None when there is nothing to score
    (no report, or a report with no evidence items).
    """
    report = traj.get("report") or {}
    quotes = [e["quote"] for e in report.get("evidence", [])]
    if not quotes:
        return {"precision": None, "total": 0, "found": 0, "missing": []}
    texts = tool_texts(traj)
    missing = [q for q in quotes if not quote_found(q, texts)]
    found = len(quotes) - len(missing)
    return {"precision": found / len(quotes), "total": len(quotes), "found": found,
            "missing": missing}


GROUND_TRUTH = Path(__file__).resolve().parents[1] / "ground_truth"


def load_ground_truth(scenario: str) -> dict:
    return json.loads((GROUND_TRUTH / f"{scenario}.json").read_text(encoding="utf-8"))


def correctness_signals(report: dict | None, truth: dict) -> dict:
    """Raw facts comparing a report to the ground truth. No verdict here.

    Text matching uses summary + suggested_fix only, not the evidence quotes:
    quotes are copied from the logs, which name the symptom (e.g. "QueuePool")
    even when the agent never understood the cause.
    """
    if not report:
        return {"identified": False, "category_match": False, "commit_match": False,
                "alias_hits": [], "category": None}
    text = _squash(f"{report.get('summary', '')} {report.get('suggested_fix', '')}").lower()
    culprit = truth["culprit_commit"][:7].lower()
    return {
        "identified": report.get("status") == "identified",
        "category": report.get("root_cause_category"),
        "category_match": report.get("root_cause_category") == truth["category"],
        # None = no culprit commit (e.g. a provider outage): `"" in text` would always be True
        "commit_match": (culprit in text) if culprit else None,
        "alias_hits": [a for a in truth["key_detail_aliases"] if _squash(a).lower() in text],
    }


def grade(sig: dict) -> dict:
    # Rule: correct = the specific cause is named (culprit commit AND a key alias).
    # The category is scored separately (category_match): the labels overlap, so a
    # neighbour label must not hide a found cause. Half-specific reports go to a judge;
    # meanwhile the category breaks the tie.
    # No culprit commit: the category takes the commit's place. It is what separates
    # "the provider is down" (dependency_failure) from the decoy "a config commit broke it".
    if not sig["identified"]:
        return {"correct": False, "needs_judge": False}
    first = sig["category_match"] if sig["commit_match"] is None else sig["commit_match"]
    specifics = int(first) + int(bool(sig["alias_hits"]))
    if specifics == 2:
        return {"correct": True, "needs_judge": False}
    if specifics == 0:
        return {"correct": False, "needs_judge": False}
    return {"correct": sig["category_match"], "needs_judge": True}


def score_run(traj: dict) -> dict:
    report = traj.get("report") or {}
    sig = correctness_signals(traj.get("report"), load_ground_truth(traj["scenario"]))
    return {"scenario": traj["scenario"], "stop_reason": traj.get("stop_reason"),
            "confidence": report.get("confidence"),
            **sig, **grade(sig), "evidence": evidence_check(traj)}


# --- across runs ---------------------------------------------------------------

def not_identified_rate(rows: list[dict]) -> float | None:
    """Share of runs that ended without naming a cause (not_identified or no report)."""
    if not rows:
        return None
    return sum(not r["identified"] for r in rows) / len(rows)


def calibration_buckets(rows: list[dict]) -> list[dict]:
    """Group scored runs by stated confidence; compare it to how often they were right.

    rows: score_run() outputs. Runs with no report (confidence None) are skipped:
    they never stated a confidence. Each bucket is
    {"range": "0.8-1.0", "n": int, "avg_confidence": float, "accuracy": float}.
    """
    # Rule: 3 buckets [0, 0.5) [0.5, 0.8) [0.8, 1.0], top edge inclusive. Only identified
    # runs: a not_identified confidence means "sure it's unknown", not "sure of my cause".
    edges = [(0.0, 0.5), (0.5, 0.8), (0.8, 1.0)]
    scored = [r for r in rows if r["identified"] and r["confidence"] is not None]
    buckets = []
    for lo, hi in edges:
        inside = [r for r in scored
                  if lo <= r["confidence"] < hi or (hi == 1.0 and r["confidence"] == 1.0)]
        if inside:
            buckets.append({
                "range": f"{lo:.1f}-{hi:.1f}",
                "n": len(inside),
                "avg_confidence": sum(r["confidence"] for r in inside) / len(inside),
                "accuracy": sum(r["correct"] for r in inside) / len(inside),
            })
    return buckets


if __name__ == "__main__":
    # python -m eval.metrics runs/s01_*.json ...
    for p in sys.argv[1:]:
        traj = load_trajectory(p)
        r = evidence_check(traj)
        prec = "-" if r["precision"] is None else f"{r['precision']:.2f}"
        print(f"{Path(p).name}: evidence {r['found']}/{r['total']} ({prec})")
        for q in r["missing"]:
            print(f"    NOT SEEN: {q[:100]!r}")
        sig = correctness_signals(traj.get("report"), load_ground_truth(traj["scenario"]))
        print(f"    signals: category={sig['category']} match={sig['category_match']} "
              f"commit={sig['commit_match']} aliases={sig['alias_hits']}")
        try:
            print(f"    verdict: {grade(sig)}")
        except NotImplementedError:
            print("    verdict: (grade() not written yet)")
