"""agent/loop.py with a scripted fake LLM: no network, deterministic.

These tests skip until the TODO(human) in run_agent is filled.
"""

from pathlib import Path

import pytest

from agent.loop import run_agent

S01 = Path(__file__).resolve().parents[1] / "scenarios" / "s01"

REPORT = {
    "status": "identified",
    "root_cause_category": "missing_migration",
    "summary": "Column added in code without a migration.",
    "evidence": [{"source": "logs/api.jsonl", "quote": "column does not exist"}],
    "confidence": 0.8,
    "suggested_fix": "Add and run the migration.",
}
USAGE = {"input_tokens": 100, "output_tokens": 10, "latency_ms": 5, "model": "fake"}


def call(name: str, args: dict, i: int = 0) -> dict:
    return {"role": "assistant", "content": f"Hypothesis {i}", "tool_calls": [{"id": f"c{i}", "name": name, "args": args}]}


class FakeLLM:
    """Plays back scripted assistant messages; `default` is used once the script runs out."""

    def __init__(self, script: list[dict], default: dict | None = None):
        self.script, self.default = list(script), default
        self.calls: list[dict] = []           # what the loop sent each time

    def __call__(self, messages, tools, **kwargs):
        self.calls.append({"messages": [dict(m) for m in messages], "kwargs": kwargs})
        tool_choice = kwargs.get("tool_choice", "auto")
        if tool_choice == "submit_report":
            return call("submit_report", REPORT, 99), USAGE
        msg = self.script.pop(0) if self.script else self.default
        return msg, USAGE


def run(fake: FakeLLM, **kw) -> dict:
    try:
        return run_agent(S01, "test prompt", llm=fake, **kw)
    except NotImplementedError:
        pytest.skip("fill the TODO(human) in agent/loop.py")


def test_stops_on_submit_report():
    fake = FakeLLM([call("log_stats", {"service": "api"}, 1), call("submit_report", REPORT, 2)])
    traj = run(fake)
    assert traj["stop_reason"] == "submitted"
    assert traj["report"]["root_cause_category"] == "missing_migration"
    assert len(fake.calls) == 2
    # the 2nd call must contain the log_stats result
    tool_msgs = [m for m in fake.calls[1]["messages"] if m["role"] == "tool"]
    assert tool_msgs and tool_msgs[0]["name"] == "log_stats" and not tool_msgs[0]["is_error"]
    assert traj["steps"][0]["hypothesis"] == "Hypothesis 1"


def test_bad_tool_call_becomes_error_result():
    fake = FakeLLM([call("read_logs", {}, 1), call("search_logs", {}, 2), call("submit_report", REPORT, 3)])
    traj = run(fake)
    assert traj["stop_reason"] == "submitted"
    errors = [c for s in traj["steps"] for c in s["tool_calls"] if c["is_error"]]
    assert len(errors) == 2                                   # unknown tool + missing 'service'
    assert "Unknown tool" in errors[0]["result"]


def test_step_limit_forces_a_report():
    fake = FakeLLM([], default=call("log_stats", {"service": "api"}))
    traj = run(fake, max_steps=3)
    assert traj["stop_reason"] == "step_limit"
    assert traj["report"] is not None
    assert len(fake.calls) == 4                               # 3 steps + 1 forced
    assert fake.calls[-1]["kwargs"].get("tool_choice") == "submit_report"


def test_text_only_answers_still_terminate():
    fake = FakeLLM([], default={"role": "assistant", "content": "I think it's the DB.", "tool_calls": []})
    traj = run(fake, max_steps=3)
    assert traj["stop_reason"] is not None
    assert len(fake.calls) <= 4


def test_system_prompt_has_no_giveaway():
    from agent.prompts import SYSTEM_PROMPT
    text = SYSTEM_PROMPT.lower()
    assert "submit_report" in text and "not_identified" in text
    for banned in ("ground_truth", "ground truth", "fault", "missing_migration", "pool"):
        assert banned not in text, banned
