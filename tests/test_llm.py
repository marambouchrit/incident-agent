"""agent/llm.py: format conversion and response parsing, no network."""

from agent import llm
from agent.tools.registry import tool_specs


def test_tools_keep_full_json_schema():
    decls = llm.to_gemini_tools(tool_specs())[0]["functionDeclarations"]
    names = {d["name"] for d in decls}
    assert "submit_report" in names and "log_stats" in names
    log_stats = next(d for d in decls if d["name"] == "log_stats")
    # Optional[str] arrives as anyOf; parametersJsonSchema accepts it unchanged
    assert "anyOf" in log_stats["parametersJsonSchema"]["properties"]["since"]


def test_contents_system_and_roles():
    system, contents = llm.to_gemini_contents([
        {"role": "system", "content": "You are an SRE."},
        {"role": "user", "content": "Incident: checkout fails."},
    ])
    assert system == {"parts": [{"text": "You are an SRE."}]}
    assert contents == [{"role": "user", "parts": [{"text": "Incident: checkout fails."}]}]


def test_consecutive_tool_results_merge_into_one_turn():
    _, contents = llm.to_gemini_contents([
        {"role": "user", "content": "go"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "a", "name": "log_stats", "args": {"service": "api"}},
            {"id": "b", "name": "read_config", "args": {}},
        ]},
        {"role": "tool", "tool_call_id": "a", "name": "log_stats", "content": "ok"},
        {"role": "tool", "tool_call_id": "b", "name": "read_config", "content": "bad", "is_error": True},
    ])
    assert [c["role"] for c in contents] == ["user", "model", "user"]
    parts = contents[2]["parts"]
    assert parts[0]["functionResponse"]["response"] == {"result": "ok"}
    assert parts[1]["functionResponse"]["response"] == {"error": "bad"}


SAMPLE = {
    "candidates": [{
        "content": {"role": "model", "parts": [
            {"text": "Hypothesis: missing migration."},
            {"functionCall": {"name": "search_logs", "args": {"service": "api"}}, "thoughtSignature": "sig=="},
        ]},
        "finishReason": "STOP",
    }],
    "usageMetadata": {"promptTokenCount": 900, "candidatesTokenCount": 40, "totalTokenCount": 940},
}


def test_parse_response_and_replay_keeps_signature():
    msg, usage = llm.parse_response(SAMPLE)
    assert msg["content"] == "Hypothesis: missing migration."
    assert msg["tool_calls"] == [{"id": "call_1", "name": "search_logs", "args": {"service": "api"}}]
    assert usage["input_tokens"] == 900 and usage["output_tokens"] == 40
    assert usage["finish_reason"] == "STOP"
    # sending the message back must replay the raw parts, signature included
    _, contents = llm.to_gemini_contents([msg])
    assert contents[0]["parts"][1]["thoughtSignature"] == "sig=="


def test_parse_empty_response():
    msg, usage = llm.parse_response({"candidates": [{"finishReason": "MALFORMED_FUNCTION_CALL"}]})
    assert msg["content"] is None and msg["tool_calls"] == []
    assert usage["finish_reason"] == "MALFORMED_FUNCTION_CALL"


def test_tool_choice_forces_one_tool():
    cfg = llm._tool_config("submit_report")["functionCallingConfig"]
    assert cfg == {"mode": "ANY", "allowedFunctionNames": ["submit_report"]}
