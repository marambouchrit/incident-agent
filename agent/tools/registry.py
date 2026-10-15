"""Tool registry: name -> (function, args model). Builds the schemas the LLM sees
and runs one tool call safely (validate -> timeout -> cap)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ValidationError

from agent.tools import tools as t
from agent.tools.descriptions import DESCRIPTIONS
from agent.tools.guards import ToolError, cap_output, run_with_timeout


@dataclass(frozen=True)
class Tool:
    name: str
    fn: Callable[[Path, BaseModel], str]
    args: type[BaseModel]
    terminal: bool = False


TOOLS: dict[str, Tool] = {
    tool.name: tool
    for tool in [
        Tool("log_stats", t.log_stats, t.LogStatsArgs),
        Tool("search_logs", t.search_logs, t.SearchLogsArgs),
        Tool("list_commits", t.list_commits, t.ListCommitsArgs),
        Tool("show_commit", t.show_commit, t.ShowCommitArgs),
        Tool("read_config", t.read_config, t.ReadConfigArgs),
        Tool("get_db_schema", t.get_db_schema, t.GetDbSchemaArgs),
        Tool("get_container_status", t.get_container_status, t.GetContainerStatusArgs),
        Tool("submit_report", t.submit_report, t.SubmitReportArgs, terminal=True),
    ]
}


def _strip_titles(schema: dict) -> dict:
    """Pydantic adds 'title' everywhere; it's noise for the LLM."""
    if isinstance(schema, dict):
        return {k: _strip_titles(v) for k, v in schema.items() if k != "title"}
    if isinstance(schema, list):
        return [_strip_titles(v) for v in schema]
    return schema


def tool_specs() -> list[dict]:
    """Provider-neutral specs: [{name, description, parameters (JSON schema)}].
    agent/llm.py (Day 3) converts these to the provider's format."""
    return [
        {"name": tool.name, "description": DESCRIPTIONS[tool.name],
         "parameters": _strip_titles(tool.args.model_json_schema())}
        for tool in TOOLS.values()
    ]


def _validation_message(name: str, err: ValidationError) -> str:
    problems = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'args'}: {e['msg']}" for e in err.errors())
    return f"Invalid arguments for {name}: {problems}."


def run_tool(name: str, raw_args: dict, scenario_dir: Path, timeout_s: float = 10.0) -> str:
    """Validate and run one tool call. Raises ToolError (incl. ToolTimeout) for
    anything the model can fix; the loop decides how to show that to the model."""
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolError(f"Unknown tool {name!r}. Available: {', '.join(TOOLS)}.")
    try:
        args = tool.args.model_validate(raw_args or {})
    except ValidationError as err:
        raise ToolError(_validation_message(name, err)) from None
    return cap_output(run_with_timeout(tool.fn, Path(scenario_dir), args, timeout_s=timeout_s))
