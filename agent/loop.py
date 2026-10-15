"""The agent loop: reason -> act -> observe, until submit_report or the step limit.

The state is the message list (see agent/llm.py for its format). Every step:
the model sees the whole history, answers with text (its hypothesis) and/or
tool calls, we run the tools and append their results.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from agent import trajectory as tr
from agent.llm import LLMError, llm_call
from agent.prompts import initial_user_message
from agent.tools.guards import ToolError
from agent.tools.registry import TOOLS, run_tool, tool_specs

MAX_STEPS = 15
TERMINAL_TOOL = "submit_report"


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

    # Control loop: written by Claude at my request (Day 3).
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

        report = _dispatch(msg["tool_calls"], messages, step, scenario_dir)
        if report is not None:
            return tr.finish(traj, "submitted", report)

    # Step budget used up: force one last call that can only be submit_report.
    messages.append({"role": "user", "content": FORCE_REPORT.format(n=max_steps)})
    try:
        msg, usage = llm(messages, tools, tool_choice=TERMINAL_TOOL)
    except LLMError as err:
        return _abort(traj, err)
    messages.append(msg)
    step = tr.record_step(traj, msg, usage, forced=True)
    calls = [c for c in msg["tool_calls"] if c["name"] == TERMINAL_TOOL]
    return tr.finish(traj, "step_limit", _dispatch(calls, messages, step, scenario_dir))


NUDGE = ("You answered without calling a tool. Continue the investigation with a tool call, "
         "or call submit_report if you have enough evidence.")
FORCE_REPORT = ("You have used all {n} investigation steps. Call submit_report now with what you have. "
                "If the evidence is not enough, use status 'not_identified' and say what is missing.")


def _dispatch(calls: list[dict], messages: list[dict], step: dict, scenario_dir: Path) -> dict | None:
    """Run the tool calls of one turn in order. Returns the report if a valid
    submit_report was among them (later calls are then skipped), else None."""
    for call in calls:
        try:
            result, is_error = run_tool(call["name"], call["args"], scenario_dir), False
        except ToolError as err:                  # unknown tool, bad args, timeout, invalid report
            result, is_error = str(err), True
        messages.append(tool_message(call, result, is_error=is_error))
        tr.record_tool_result(step, call, result, is_error=is_error)
        if call["name"] == TERMINAL_TOOL and not is_error:
            return call["args"]
    return None


def _abort(traj: dict, err: Exception) -> dict:
    """Provider failure the model can't fix: stop, but keep the trajectory so far."""
    traj["error"] = str(err)
    return tr.finish(traj, "llm_error")
