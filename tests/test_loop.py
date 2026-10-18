"""agent/loop.py with a scripted fake LLM: no network, deterministic."""

from pathlib import Path

from agent.llm import LLMError
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

    def __init__(self, script: list[dict], default: dict | None = None, forced: list[dict] | None = None):
        self.script, self.default = list(script), default
        self.forced = list(forced or [])      # scripted answers to forced calls; then a valid report
        self.calls: list[dict] = []           # what the loop sent each time

    def __call__(self, messages, tools, **kwargs):
        self.calls.append({"messages": [dict(m) for m in messages], "kwargs": kwargs})
        tool_choice = kwargs.get("tool_choice", "auto")
        if tool_choice == "submit_report":
            return (self.forced.pop(0) if self.forced else call("submit_report", REPORT, 99)), USAGE
        msg = self.script.pop(0) if self.script else self.default
        return msg, USAGE


def run(fake: FakeLLM, **kw) -> dict:
    return run_agent(S01, "test prompt", llm=fake, **kw)


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


def test_provider_failure_keeps_the_trajectory():
    script = [call("log_stats", {"service": "api"}, 1)]

    def flaky(messages, tools, **kwargs):
        if script:
            return script.pop(0), USAGE
        raise LLMError("HTTP 503: overloaded")

    traj = run_agent(S01, "test prompt", llm=flaky)
    assert traj["stop_reason"] == "llm_error"
    assert "503" in traj["error"]
    assert len(traj["steps"]) == 1                            # step 1 is kept


def test_system_prompt_has_no_giveaway():
    from agent.prompts import SYSTEM_PROMPT
    text = SYSTEM_PROMPT.lower()
    assert "submit_report" in text and "not_identified" in text
    for banned in ("ground_truth", "ground truth", "fault", "missing_migration", "pool"):
        assert banned not in text, banned


# --- invalid submit_report: one retry for the whole run (on_invalid_report) ---

BAD_REPORT = {**REPORT, "confidence": 1.5}                    # out of [0, 1]


def report_results(traj: dict) -> list[dict]:
    return [c for s in traj["steps"] for c in s["tool_calls"] if c["tool"] == "submit_report"]


def test_report_bad_then_good_is_submitted():
    fake = FakeLLM([call("submit_report", BAD_REPORT, 1), call("submit_report", REPORT, 2)])
    traj = run(fake)
    assert traj["stop_reason"] == "submitted"
    assert traj["invalid_reports"] == 1
    first = report_results(traj)[0]
    assert first["is_error"] and "confidence" in first["result"]   # the model sees what is wrong


def test_report_bad_twice_stops_with_invalid_report():
    fake = FakeLLM([call("submit_report", BAD_REPORT, 1)] * 2, default=call("log_stats", {"service": "api"}))
    traj = run(fake)
    assert traj["stop_reason"] == "invalid_report"
    assert traj["report"] is None
    assert len(fake.calls) == 2                               # no third chance
    assert len(traj["steps"]) == 2                            # trajectory kept


def test_report_forced_bad_then_good():
    fake = FakeLLM([], default=call("log_stats", {"service": "api"}), forced=[call("submit_report", BAD_REPORT, 98)])
    traj = run(fake, max_steps=2)
    assert traj["stop_reason"] == "step_limit"
    assert traj["report"]["confidence"] == REPORT["confidence"]
    assert len(fake.calls) == 4                               # 2 steps + forced + 1 retry


def test_report_retry_budget_is_shared_with_forced_call():
    bad = call("submit_report", BAD_REPORT, 98)
    fake = FakeLLM([call("submit_report", BAD_REPORT, 1)], default=call("log_stats", {"service": "api"}), forced=[bad])
    traj = run(fake, max_steps=2)
    assert traj["stop_reason"] == "invalid_report"           # retry already used at step 1
    assert len(fake.calls) == 3


# --- duplicate calls: same tool + same args -> not run again (on_duplicate) ---

from agent.loop import call_key


def test_call_key_ignores_order_and_none():
    assert call_key("search_logs", {"service": "api", "query": "x"}) ==         call_key("search_logs", {"query": "x", "service": "api", "since": None})
    assert call_key("search_logs", {"service": "api"}) != call_key("search_logs", {"service": "worker"})


def test_duplicate_is_not_run_again_and_says_so():
    same = {"service": "api"}
    fake = FakeLLM([call("log_stats", same, 1), call("log_stats", same, 2), call("submit_report", REPORT, 3)])
    traj = run(fake)
    assert traj["stop_reason"] == "submitted"
    assert traj["duplicate_calls"] == 1
    first, second = (s["tool_calls"][0] for s in traj["steps"][:2])
    assert not first["duplicate"] and second["duplicate"]
    assert second["result"] != first["result"]                # a message, not the tool output again
    assert "1" in second["result"]                           # points back to step 1
    assert len(traj["steps"]) == 3                           # the repeat still costs a step


def test_duplicate_loop_still_ends():
    fake = FakeLLM([], default=call("log_stats", {"service": "api"}))
    traj = run(fake, max_steps=4)
    assert traj["stop_reason"] == "step_limit"
    assert traj["duplicate_calls"] == 3


def test_no_culprit_commit_in_prompt_or_tool_descriptions():
    # Day 7: v1's evidence example quoted "git/45b232b", s01's real culprit commit.
    import json
    from pathlib import Path
    from agent.prompts import SYSTEM_PROMPT
    from agent.tools.descriptions import DESCRIPTIONS
    text = (SYSTEM_PROMPT + " ".join(DESCRIPTIONS.values())).lower()
    for gt in sorted(Path(__file__).resolve().parents[1].glob("ground_truth/*.json")):
        culprit = json.loads(gt.read_text(encoding="utf-8"))["culprit_commit"][:7].lower()
        assert not culprit or culprit not in text, (gt.name, culprit)
