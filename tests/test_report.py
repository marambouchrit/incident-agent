from pathlib import Path

import pytest

from eval.report import render, score_paths

DAY4 = sorted((Path(__file__).resolve().parents[1] / "runs").glob("s0*_v1_20261015T22*.json"))


@pytest.mark.skipif(len(DAY4) != 5, reason="Day 4 runs not present")
def test_report_on_day4_runs():
    text = render(score_paths(DAY4), "t")
    assert "| s01 | easy | dev | 1 | 1/1 |" in text
    assert "Evidence precision: 13/15" in text
    assert "column_name | character varying" in text   # the fabricated quote is listed


@pytest.mark.skipif(len(DAY4) != 5, reason="Day 4 runs not present")
def test_provider_errors_are_not_scored():
    rows = score_paths(DAY4)
    lost = dict(rows[0], stop_reason="llm_error", identified=False, correct=False)
    text = render(rows + [lost], "t")
    assert "1 run(s) lost to provider errors" in text
    assert "Runs: 5 (5 scenarios)" in text
    assert "not_identified rate: 0.00" in text
