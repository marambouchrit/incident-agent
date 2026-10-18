from pathlib import Path

import pytest

from eval.metrics import evidence_check, load_trajectory, quote_found

ROOT = Path(__file__).resolve().parents[1]

REAL_LINE = "worker: state=running restarts=17 exit_code=137 oom_killed=True mem_limit_mb=256"
FAKE_QUOTE = "column_name | character varying | 40 | yes"


def fake_trajectory(quotes: list[str]) -> dict:
    """A tiny run: one real tool output, then a report quoting `quotes`."""
    return {
        "steps": [
            {"tool_calls": [{"tool": "get_container_status", "args": {},
                             "result": REAL_LINE + "\napi: state=running restarts=0",
                             "is_error": False, "duplicate": False}]},
            {"tool_calls": [{"tool": "submit_report", "args": {},
                             # a validation error echoing the fake quote must not count
                             "result": f"Invalid report: input_value='{FAKE_QUOTE}'",
                             "is_error": True, "duplicate": False}]},
        ],
        "report": {"evidence": [{"source": "containers", "quote": q} for q in quotes]},
    }


def test_exact_quote_is_found():
    assert quote_found("exit_code=137 oom_killed=True", [REAL_LINE])


def test_fabricated_quote_is_caught():
    assert not quote_found(FAKE_QUOTE, [REAL_LINE])


def test_precision_counts_real_and_fake():
    r = evidence_check(fake_trajectory([REAL_LINE, FAKE_QUOTE]))
    assert r["precision"] == 0.5
    assert r["missing"] == [FAKE_QUOTE]


def test_submit_report_echo_does_not_count():
    r = evidence_check(fake_trajectory([FAKE_QUOTE]))
    assert r["precision"] == 0.0


def test_no_evidence_is_not_scored():
    traj = fake_trajectory([])
    assert evidence_check(traj)["precision"] is None
    traj["report"] = None
    assert evidence_check(traj)["precision"] is None


S01_RUN = ROOT / "runs" / "s01_v1_20261015T223236.json"


@pytest.mark.skipif(not S01_RUN.exists(), reason="Day 4 s01 run not present")
def test_real_s01_run_flags_the_invented_schema_quote():
    r = evidence_check(load_trajectory(S01_RUN))
    assert r["total"] == 4
    assert r["missing"] == [FAKE_QUOTE]


# --- correctness -------------------------------------------------------------

from eval.metrics import correctness_signals, grade  # noqa: E402

TRUTH = {"category": "missing_migration", "culprit_commit": "45b232b",
         "key_detail_aliases": ["discount_code", "orders.discount_code"]}


def report(category="missing_migration", summary="", status="identified") -> dict:
    return {"status": status, "root_cause_category": category, "summary": summary,
            "suggested_fix": "", "evidence": [], "confidence": 0.8}


def test_signals_read_summary_not_quotes():
    r = report(summary="Commit 45B232B added discount_code without a migration.")
    r["evidence"] = [{"source": "x", "quote": "orders.discount_code"}]
    sig = correctness_signals(r, TRUTH)
    assert sig["category_match"] and sig["commit_match"] and sig["identified"]
    assert sig["alias_hits"] == ["discount_code"]


def test_everything_right_is_correct():
    sig = correctness_signals(report(summary="45b232b added discount_code, no migration"), TRUTH)
    assert grade(sig)["correct"] is True


def test_everything_wrong_is_incorrect():
    sig = correctness_signals(report("code_bug", summary="a typo in the payments client"), TRUTH)
    assert grade(sig)["correct"] is False


def test_not_identified_is_never_correct():
    sig = correctness_signals(report("unknown", summary="45b232b discount_code?",
                                     status="not_identified"), TRUTH)
    assert grade(sig)["correct"] is False


def test_no_report_is_incorrect():
    assert grade(correctness_signals(None, TRUTH))["correct"] is False


NO_COMMIT = {"category": "dependency_failure", "culprit_commit": "",
             "key_detail_aliases": ["payment provider", "payments container", "exited"]}


def test_no_culprit_commit_is_not_a_free_match():
    sig = correctness_signals(report("dependency_failure", summary="something broke"), NO_COMMIT)
    assert sig["commit_match"] is None


def test_no_culprit_commit_needs_category_and_alias():
    right = correctness_signals(
        report("dependency_failure", summary="the payments container exited; provider down"), NO_COMMIT)
    assert grade(right) == {"correct": True, "needs_judge": False}
    decoy = correctness_signals(
        report("bad_config", summary="commit 72e66c2 changed api.env; payments container unreachable"),
        NO_COMMIT)
    assert grade(decoy) == {"correct": False, "needs_judge": True}
    vague = correctness_signals(report("bad_config", summary="checkout fails"), NO_COMMIT)
    assert grade(vague)["correct"] is False


def test_half_specific_goes_to_judge_and_category_breaks_the_tie():
    commit_only = correctness_signals(report(summary="commit 45b232b broke it"), TRUTH)
    assert grade(commit_only) == {"correct": True, "needs_judge": True}
    wrong_label = correctness_signals(report("code_bug", summary="commit 45b232b broke it"), TRUTH)
    assert grade(wrong_label) == {"correct": False, "needs_judge": True}


# --- calibration -------------------------------------------------------------

from eval.metrics import calibration_buckets, not_identified_rate  # noqa: E402


def row(conf, correct, identified=True) -> dict:
    return {"confidence": conf, "correct": correct, "identified": identified}


def test_not_identified_rate():
    rows = [row(0.9, True), row(0.2, False, identified=False), row(None, False, identified=False)]
    assert not_identified_rate(rows) == 2 / 3
    assert not_identified_rate([]) is None


def test_overconfident_runs_show_up_as_a_gap():
    rows = [row(1.0, False)] * 3 + [row(1.0, True)]
    [top] = calibration_buckets(rows)
    assert top["n"] == 4 and top["avg_confidence"] == 1.0 and top["accuracy"] == 0.25


def test_every_scored_run_lands_in_exactly_one_bucket():
    confs = [0.0, 0.1, 0.33, 0.5, 0.5, 0.66, 0.8, 0.95, 1.0]
    buckets = calibration_buckets([row(c, i % 2 == 0) for i, c in enumerate(confs)])
    assert sum(b["n"] for b in buckets) == len(confs)
    assert all(b["n"] > 0 and 0 <= b["accuracy"] <= 1 for b in buckets)


def test_runs_without_report_are_skipped():
    assert calibration_buckets([row(None, False, identified=False)]) == []
