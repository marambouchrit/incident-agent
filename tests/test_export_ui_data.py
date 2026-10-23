import json
from pathlib import Path

from scripts.export_ui_data import main, quote_locations

REAL_LINE = "worker: state=running restarts=17 exit_code=137 oom_killed=True"


def test_quote_locations_points_to_the_call_that_returned_the_quote() -> None:
    traj = {
        "steps": [
            {"step": 1, "tool_calls": [{"tool": "list_commits", "result": "abc123 something"}]},
            {"step": 2, "tool_calls": [{"tool": "get_container_status", "result": REAL_LINE}]},
            {"step": 3, "tool_calls": [{"tool": "submit_report", "result": REAL_LINE}]},
        ],
        "report": {"evidence": [{"quote": "exit_code=137"}, {"quote": "never seen"}]},
    }
    assert quote_locations(traj) == [[{"step": 2, "call": 0}], []]


def test_export_writes_index_and_one_file_per_run(tmp_path: Path) -> None:
    run = {
        "scenario": "s01", "agent_version": "v3", "model": "m", "run_index": 1,
        "steps": [{"step": 1, "tool_calls": [{"tool": "read_logs", "result": "discount_code missing"}]}],
        "report": {"root_cause_category": "missing_migration", "status": "identified",
                   "confidence": 0.9, "summary": "commit 45b232b uses orders.discount_code",
                   "suggested_fix": "add a migration", "evidence": [{"quote": "discount_code missing"}]},
        "stop_reason": "submitted", "totals": {"steps": 1},
    }
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "s01_v3_x.json").write_text(json.dumps(run), encoding="utf-8")
    out = tmp_path / "data"

    assert main([str(runs), "--out", str(out)]) == 0

    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert [r["id"] for r in index] == ["s01_v3_x"]
    assert index[0]["verdict"] == "correct"
    detail = json.loads((out / "runs" / "s01_v3_x.json").read_text(encoding="utf-8"))
    assert detail["truth"]["id"] == "s01"
    assert detail["quote_locations"] == [[{"step": 1, "call": 0}]]
