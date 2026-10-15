from pathlib import Path

import pytest

from agent.tools.descriptions import DESCRIPTIONS
from agent.tools.guards import ToolError
from agent.tools.registry import TOOLS, run_tool, tool_specs

REPO = Path(__file__).resolve().parents[1]
S01 = REPO / "scenarios" / "s01"
SCENARIOS = sorted(p for p in (REPO / "scenarios").iterdir() if p.is_dir())

# One sensible call per tool; every one must stay under the cap on every scenario.
CALLS = [
    ("search_logs", {"service": "api", "level": "ERROR"}),
    ("search_logs", {"service": "db", "keyword": "error", "limit": 20}),
    ("list_commits", {}),
    ("read_config", {}),
    ("read_config", {"name": "api.env"}),
    ("get_db_schema", {}),
    ("get_db_schema", {"table": "orders"}),
    ("get_container_status", {}),
]


def lines(text: str) -> int:
    return len(text.splitlines())


# --- every tool, every scenario: runs and fits ---------------------------------

@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda p: p.name)
@pytest.mark.parametrize("name,args", CALLS, ids=lambda x: str(x))
def test_tool_runs_and_fits(scenario, name, args):
    out = run_tool(name, args, scenario)
    assert out.strip()
    assert lines(out) <= 101


def test_show_commit_latest_s01():
    first = run_tool("list_commits", {"limit": 1}, S01).splitlines()[1].split()[0]
    out = run_tool("show_commit", {"hash": first}, S01)
    assert out.startswith(f"commit {first}")
    assert lines(out) <= 101


# --- content checks on s01 (missing migration) ---------------------------------

def test_search_logs_s01_finds_the_exception_line():
    out = run_tool("search_logs", {"service": "api", "level": "ERROR", "limit": 5}, S01)
    assert "does not exist" in out          # traceback reduced to its exception line
    assert "Traceback" not in out


def test_search_logs_time_window():
    out = run_tool("search_logs", {"service": "api", "since": "14:00", "until": "14:01"}, S01)
    for line in out.splitlines()[1:]:
        assert line.startswith("2026-10-13T14:00") or line.startswith("2026-10-13T14:01:00")


def test_db_log_details_are_folded_in():
    out = run_tool("search_logs", {"service": "db", "level": "ERROR", "limit": 3}, S01)
    assert "statement=" in out              # STATEMENT line attached to its ERROR


def test_schema_shows_indexes():
    out = run_tool("get_db_schema", {"table": "order_items"}, S01)
    assert "ix_order_items_order_id" in out


def test_show_commit_path_filter():
    out = run_tool("show_commit", {"hash": "45b232b", "path": "models.py"}, S01)
    assert "app/models.py" in out and "checkout.py" not in out


# --- errors the model can recover from ------------------------------------------

@pytest.mark.parametrize(
    "name,args,expect",
    [
        ("search_logs", {"service": "chekout"}, "api"),          # lists real services
        ("read_config", {"name": "nope.env"}, "api.env"),
        ("get_db_schema", {"table": "order"}, "orders"),
        ("show_commit", {"hash": "zzzz"}, "list_commits"),
        ("show_commit", {"hash": "deadbeef"}, "45b232b"),
        ("search_logs", {"service": "api", "since": "yesterday"}, "HH:MM"),
        ("search_logs", {"service": "api", "limit": 5000}, "limit"),
        ("log_stats", {"service": "api", "bucket": "1 minute"}, "1m"),
        ("no_such_tool", {}, "search_logs"),
        ("search_logs", {}, "service"),
    ],
)
def test_errors_tell_the_model_what_to_do(name, args, expect):
    with pytest.raises(ToolError) as exc:
        run_tool(name, args, S01)
    assert expect in str(exc.value)


def test_no_tool_reaches_ground_truth():
    for name, args in [
        ("read_config", {"name": "../../ground_truth/s01.json"}),
        ("search_logs", {"service": "../../ground_truth/s01"}),
        ("get_container_status", {"service": "../ground_truth"}),
    ]:
        with pytest.raises(ToolError):
            run_tool(name, args, S01)


# --- registry ---------------------------------------------------------------------

def test_specs_cover_every_tool():
    specs = tool_specs()
    assert [s["name"] for s in specs] == list(TOOLS)
    for s in specs:
        assert s["parameters"]["type"] == "object"


def test_submit_report_schema_validates():
    ok = {
        "status": "identified", "root_cause_category": "missing_migration",
        "summary": "x", "evidence": [{"source": "logs/api.jsonl", "quote": "y"}],
        "confidence": 0.8, "suggested_fix": "z",
    }
    assert run_tool("submit_report", ok, S01) == "Report received."
    with pytest.raises(ToolError):
        run_tool("submit_report", {**ok, "root_cause_category": "aliens"}, S01)
    assert TOOLS["submit_report"].terminal


# --- your gaps --------------------------------------------------------------------

def test_descriptions_written():
    for name in TOOLS:
        d = DESCRIPTIONS[name]
        assert len(d) >= 40, f"{name}: description too short"
    for name in TOOLS:
        if name != "submit_report":
            assert "use this when" in DESCRIPTIONS[name].lower(), name


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda p: p.name)
def test_log_stats_fits(scenario):
    out = run_tool("log_stats", {"service": "api"}, scenario)
    assert 3 <= lines(out) <= 60            # an overview, not a dump


def test_log_stats_s01_shows_when_and_what():
    out = run_tool("log_stats", {"service": "api"}, S01)
    assert "14:06" in out                   # when errors start
    assert "discount_code" in out           # what dominates (the real exception)


def test_log_stats_keeps_small_numbers():
    # grouping must not erase evidence: "pool size 2" is the clue in s04
    out = run_tool("log_stats", {"service": "api"}, REPO / "scenarios" / "s04")
    assert "QueuePool limit of size 2" in out


def test_log_stats_shows_latency_and_endpoints():
    # s05 has no errors at all: the signal is latency on one endpoint
    out = run_tool("log_stats", {"service": "api"}, REPO / "scenarios" / "s05")
    assert "p95_ms" in out
    assert "GET /orders" in out


def test_log_stats_shows_restarts_with_version():
    out = run_tool("log_stats", {"service": "worker"}, REPO / "scenarios" / "s03")
    assert "(re)starts: 19" in out
    out = run_tool("log_stats", {"service": "api"}, S01)
    assert "version 45b232b" in out         # deploy marker links logs to git


def test_log_stats_groups_paths_with_ids():
    out = run_tool("log_stats", {"service": "api"}, S01)
    assert "GET /orders/{id}" in out
    assert "/orders/825117" not in out


def test_log_stats_folds_quiet_buckets():
    out = run_tool("log_stats", {"service": "worker"}, S01)
    assert "quiet buckets" in out
    assert len(out.splitlines()) < 15
