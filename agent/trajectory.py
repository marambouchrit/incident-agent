"""Trajectory: the full record of one agent run, saved as JSON in runs/.

One step = one LLM call and the tool calls it made. Tool results are stored in
full (not a preview): the Day 5 evidence check needs to know exactly what the
agent saw, and the Day 11 viewer shows it.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def new_trajectory(scenario: str, incident: str, *, model: str = "", agent_version: str = "v0") -> dict:
    return {
        "scenario": scenario,
        "agent_version": agent_version,
        "model": model,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "incident": incident,
        "steps": [],
        "report": None,
        "stop_reason": None,
        "totals": {},
    }


def record_step(traj: dict, msg: dict, usage: dict, *, forced: bool = False) -> dict:
    """Add one LLM call to the trajectory. Returns the step so tool results can be attached."""
    if usage.get("model") and not traj["model"]:
        traj["model"] = usage["model"]
    step = {
        "step": len(traj["steps"]) + 1,
        "forced": forced,
        "hypothesis": msg.get("content"),
        "tool_calls": [],
        "tokens": {k: usage.get(k, 0) for k in ("input_tokens", "output_tokens", "thinking_tokens")},
        "latency_ms": usage.get("latency_ms", 0),
        "finish_reason": usage.get("finish_reason"),
    }
    traj["steps"].append(step)
    return step


def record_tool_result(step: dict, call: dict, result: str, *, is_error: bool = False,
                       duplicate: bool = False) -> None:
    step["tool_calls"].append({"tool": call["name"], "args": call["args"], "result": result,
                               "is_error": is_error, "duplicate": duplicate})


def finish(traj: dict, stop_reason: str, report: dict | None = None) -> dict:
    """stop_reason: 'submitted' | 'step_limit' | 'error' | anything your loop defines."""
    traj["stop_reason"] = stop_reason
    traj["report"] = report
    steps = traj["steps"]
    traj["totals"] = {
        "steps": len(steps),
        "tool_calls": sum(len(s["tool_calls"]) for s in steps),
        "tool_errors": sum(c["is_error"] for s in steps for c in s["tool_calls"]),
        "input_tokens": sum(s["tokens"]["input_tokens"] for s in steps),
        "output_tokens": sum(s["tokens"]["output_tokens"] for s in steps),
        "latency_ms": sum(s["latency_ms"] for s in steps),
    }
    return traj


def save(traj: dict, out_dir: Path = ROOT / "runs") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = out_dir / f"{traj['scenario']}_{traj['agent_version']}_{stamp}.json"
    path.write_text(json.dumps(traj, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
