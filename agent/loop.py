"""The agent loop: reason -> act -> observe, until submit_report or the step limit.

The state is the message list (see agent/llm.py for its format). Every step:
the model sees the whole history, answers with text (its hypothesis) and/or
tool calls, we run the tools and append their results.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from agent import trajectory as tr
from agent.llm import LLMError, llm_call
from agent.prompts import initial_user_message
from agent.tools.guards import ToolError
from agent.tools.registry import TOOLS, run_tool, tool_specs

MAX_STEPS = 15
TERMINAL_TOOL = "submit_report"
MAX_REPORT_RETRIES = 1        # second chances after an invalid submit_report, for the whole run
DUPLICATE_PREVIEW_LINES = 5   # lines of the earlier result shown again on a repeated call


def tool_message(call: dict, content: str, *, is_error: bool = False) -> dict:
    """Build the message that answers one tool call."""
    return {"role": "tool", "tool_call_id": call["id"], "name": call["name"],
            "content": content, "is_error": is_error}


def run_agent(
    scenario_dir: Path,
    system_prompt: str,
    *,
    llm: Callable[..., tuple[dict, dict]] = llm_call,
    max_steps: int = MAX_STEPS,
) -> dict:
    """Investigate one scenario. Returns the finished trajectory (not saved)."""
    scenario_dir = Path(scenario_dir)
    incident = (scenario_dir / "incident.txt").read_text(encoding="utf-8")
    traj = tr.new_trajectory(scenario_dir.name, incident)
    tools = tool_specs()
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": initial_user_message(incident)},
    ]
    state = {"invalid_reports": 0,                # lives for the whole run, forced call included
             "seen": {}, "duplicates": 0}         # seen: call_key -> (step number, result)

    # Control loop
    for _ in range(max_steps):
        try:
            msg, usage = llm(messages, tools)
        except LLMError as err:
            return _abort(traj, err)
        messages.append(msg)                      # as returned: keeps provider signatures
        step = tr.record_step(traj, msg, usage)

        if not msg["tool_calls"]:
            # Text only (or an empty/malformed answer): push back to the tools. Costs a step.
            messages.append({"role": "user", "content": NUDGE})
            continue

        report, stop = _dispatch(msg["tool_calls"], messages, step, scenario_dir, state)
        if stop:
            return _finish(traj, state, stop, report)

    # Step budget used up: force a call that can only be submit_report.
    # Bounded: the forced call itself gets at most MAX_REPORT_RETRIES extra tries.
    messages.append({"role": "user", "content": FORCE_REPORT.format(n=max_steps)})
    for _ in range(MAX_REPORT_RETRIES + 1):
        try:
            msg, usage = llm(messages, tools, tool_choice=TERMINAL_TOOL)
        except LLMError as err:
            return _abort(traj, err)
        messages.append(msg)
        step = tr.record_step(traj, msg, usage, forced=True)
        calls = [c for c in msg["tool_calls"] if c["name"] == TERMINAL_TOOL]
        report, stop = _dispatch(calls, messages, step, scenario_dir, state)
        if stop == "submitted":
            return _finish(traj, state, "step_limit", report)
        if stop or not calls:
            break
    return _finish(traj, state, stop or "step_limit", None)


NUDGE = ("You answered without calling a tool. Continue the investigation with a tool call, "
         "or call submit_report if you have enough evidence.")
FORCE_REPORT = ("You have used all {n} investigation steps. Call submit_report now with what you have. "
                "If the evidence is not enough, use status 'not_identified' and say what is missing.")


def on_invalid_report(n_invalid: int, error: str) -> tuple[bool, str]:
    """Policy for the n-th invalid submit_report of the run (n_invalid starts at 1).

    error: the validation message from run_tool, e.g.
        "Invalid arguments for submit_report: confidence: Input should be less than or equal to 1."
    Returns (stop, feedback):
        stop     -- True ends the run now with stop_reason 'invalid_report'
        feedback -- the tool result the model sees for this call
    """
    tries_left = MAX_REPORT_RETRIES + 1 - n_invalid
    if tries_left <= 0:
        return True, (f"{error}\nReport rejected {n_invalid} times; no retries left. "
                      "The run ends without a report.")
    return False, (f"{error}\nYour report was rejected and NOT recorded. Fix only the field(s) named "
                   f"above and call submit_report again with the complete report. "
                   f"Tries left: {tries_left}.")


def call_key(name: str, args: dict) -> str:
    """Identity of a tool call: same tool + same args, whatever the key order.
    None values are dropped: {"since": None} means the same as leaving 'since' out."""
    clean = {k: v for k, v in (args or {}).items() if v is not None}
    return name + json.dumps(clean, sort_keys=True, ensure_ascii=False)


def on_duplicate(call: dict, first_step: int, first_result: str) -> str:
    """Tool result for a call identical to one already run at step `first_step`.
    The tool is NOT run again; this text is what the model sees instead (the step still counts)."""
    lines = first_result.splitlines()
    preview = "\n".join("  " + line[:200] for line in lines[:DUPLICATE_PREVIEW_LINES])
    more = f"\n  ... ({len(lines) - DUPLICATE_PREVIEW_LINES} more lines at step {first_step})" \
        if len(lines) > DUPLICATE_PREVIEW_LINES else ""
    return (f"Duplicate call: you already ran {call['name']} with these exact arguments at step "
            f"{first_step}. It was NOT run again; the result has not changed. Start of that result:\n"
            f"{preview}{more}\n"
            "Repeating a call gives no new information. Try a different angle: another service, "
            "a narrower time window, a different query, or another tool. If you already have "
            "enough evidence, call submit_report.")


def _dispatch(calls: list[dict], messages: list[dict], step: dict, scenario_dir: Path,
              state: dict) -> tuple[dict | None, str | None]:
    """Run the tool calls of one turn in order. Returns (report, stop):
    (report, 'submitted') on a valid submit_report -- later calls are skipped;
    (None, 'invalid_report') when on_invalid_report says stop; (None, None) otherwise."""
    for call in calls:
        key = call_key(call["name"], call["args"])
        if call["name"] != TERMINAL_TOOL and key in state["seen"]:
            first_step, first_result = state["seen"][key]
            result = on_duplicate(call, first_step, first_result)
            state["duplicates"] += 1
            messages.append(tool_message(call, result, is_error=True))
            tr.record_tool_result(step, call, result, is_error=True, duplicate=True)
            continue
        try:
            result, is_error = run_tool(call["name"], call["args"], scenario_dir), False
        except ToolError as err:                  # unknown tool, bad args, timeout, invalid report
            result, is_error = str(err), True
        if call["name"] != TERMINAL_TOOL:
            state["seen"][key] = (step["step"], result)
        stop = False
        if call["name"] == TERMINAL_TOOL and is_error:
            state["invalid_reports"] += 1
            stop, result = on_invalid_report(state["invalid_reports"], result)
        messages.append(tool_message(call, result, is_error=is_error))
        tr.record_tool_result(step, call, result, is_error=is_error)
        if call["name"] == TERMINAL_TOOL and not is_error:
            return call["args"], "submitted"
        if stop:
            return None, "invalid_report"
    return None, None


def _finish(traj: dict, state: dict, stop_reason: str, report: dict | None) -> dict:
    traj["invalid_reports"] = state["invalid_reports"]
    traj["duplicate_calls"] = state["duplicates"]
    return tr.finish(traj, stop_reason, report)


def _abort(traj: dict, err: Exception) -> dict:
    """Provider failure the model can't fix: stop, but keep the trajectory so far."""
    traj["error"] = str(err)
    return tr.finish(traj, "llm_error")
