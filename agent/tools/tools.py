"""The agent's 7 read-only tools + the submit_report schema.

Each tool: (scenario_dir, args) -> str. Args are Pydantic models, so the
registry can build the JSON schema the LLM sees and validate what it sends.
Descriptions live in descriptions.py .
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from agent.tools.guards import ToolError, cap_output
from agent.tools.parsing import (
    LEVELS,
    LogEntry,
    exc_summary,
    filter_diff_by_path,
    format_entry,
    list_configs,
    load_commits,
    load_containers,
    load_diff,
    load_logs,
    not_found,
    parse_bucket,
    parse_schema,
    parse_ts,
    parse_user_time,
    read_config_file,
)

Level = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def _window(entries: list[LogEntry], since: str | None, until: str | None) -> list[LogEntry]:
    if not entries:
        return entries
    ref_day = entries[0].ts.replace(hour=0, minute=0, second=0, microsecond=0)
    lo, hi = parse_user_time(since, ref_day), parse_user_time(until, ref_day)
    if lo and hi and lo > hi:
        raise ToolError(f"'since' ({since}) is after 'until' ({until}).")
    return [e for e in entries if (lo is None or e.ts >= lo) and (hi is None or e.ts <= hi)]


# --- 1. log_stats ------------------------------------------------------------

class LogStatsArgs(BaseModel):
    service: str
    bucket: str = "1m"
    since: str | None = None
    until: str | None = None


def bucketize(entries: list[LogEntry], size_s: float) -> list[tuple[datetime, list[LogEntry]]]:
    """Group entries into consecutive time buckets (empty buckets included, oldest first)."""
    if not entries:
        return []
    start = entries[0].ts.timestamp() // size_s * size_s
    n = int((entries[-1].ts.timestamp() - start) // size_s) + 1
    buckets: list[list[LogEntry]] = [[] for _ in range(n)]
    for e in entries:
        buckets[int((e.ts.timestamp() - start) // size_s)].append(e)
    tz = entries[0].ts.tzinfo
    return [(datetime.fromtimestamp(start + i * size_s, tz), b) for i, b in enumerate(buckets)]


# Only blank what varies per request. Short numbers stay: "pool size 2",
# "timeout 1.00", "503" are evidence, not noise.
_NOISE = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "<email>"),
    (re.compile(r"\b[0-9a-f]{8,}\b"), "<id>"),
    (re.compile(r"\b\d{4,}\b"), "N"),
    (re.compile(r"\s+"), " "),
]


def _message_key(e: LogEntry) -> str:
    """The text that names the problem, with ids/emails/numbers blanked so
    1,000 'same error, different user' lines group into one."""
    text = e.msg
    if "exc" in e.fields:
        text += ": " + exc_summary(str(e.fields["exc"]))
    elif "error" in e.fields:
        text += ": " + str(e.fields["error"])
    for pattern, repl in _NOISE:
        text = pattern.sub(repl, text)
    return text[:200]


_ID_SEGMENT = re.compile(r"/\d+(?=/|$)")


def _starts(entries: list[LogEntry]) -> str | None:
    """Process (re)starts, with the deployed version when logged. Restarts and
    deploys are the two events most RCA timelines hinge on."""
    starts = [e for e in entries if e.msg == "service started"]
    if not starts:
        return None
    fmt = [f"{e.ts:%H:%M:%S}" + (f" (version {e.fields['version']})" if "version" in e.fields else "") for e in starts]
    if len(fmt) > 6:
        fmt = fmt[:3] + [f"... {len(fmt) - 5} more ..."] + fmt[-2:]
    return f"Service (re)starts: {len(starts)} -> " + ", ".join(fmt)


def _is_error(e: LogEntry) -> bool:
    return e.level in ("ERROR", "CRITICAL")


def _top(entries: list[LogEntry], n: int) -> list[str]:
    """Most frequent messages, each with count, first/last seen, and the
    endpoints it hit (maps the error back to the symptom in incident.txt)."""
    groups: dict[str, list[LogEntry]] = {}
    for e in entries:
        groups.setdefault(_message_key(e), []).append(e)
    ranked = sorted(groups.items(), key=lambda kv: len(kv[1]), reverse=True)[:n]
    out = []
    for key, es in ranked:
        paths = Counter(
            f"{e.fields['method']} {_ID_SEGMENT.sub('/{id}', str(e.fields['path']))}"
            for e in es if "path" in e.fields and "method" in e.fields
        )
        where = ("  on " + ", ".join(f"{p} ({c})" for p, c in paths.most_common(3))) if paths else ""
        out.append(f"  {len(es):>5}x  first {es[0].ts:%H:%M:%S}  last {es[-1].ts:%H:%M:%S}  {key}{where}")
    return out


def _latency(b: list[LogEntry]) -> list[float]:
    vals = []
    for e in b:
        v = e.fields.get("latency_ms", e.fields.get("duration_ms"))
        if isinstance(v, (int, float)):
            vals.append(float(v))
    return vals


def _p95(vals: list[float]) -> str:
    if not vals:
        return "-"
    s = sorted(vals)
    return f"{s[min(len(s) - 1, int(0.95 * len(s)))]:.0f}"


def format_stats(service: str, buckets: list[tuple[datetime, list[LogEntry]]]) -> str:
    entries = [e for _, b in buckets for e in b]
    errors = [e for e in entries if _is_error(e)]
    warnings = [e for e in entries if e.level == "WARNING"]
    size = (buckets[1][0] - buckets[0][0]).total_seconds() if len(buckets) > 1 else None
    has_latency = bool(_latency(entries))

    lines = [
        f"{service}: {len(entries)} entries, {entries[0].ts:%H:%M:%S}-{entries[-1].ts:%H:%M:%S} UTC, "
        f"{len(errors)} errors, {len(warnings)} warnings."
        + (f" Bucket = {size:g}s." if size else ""),
        "time        total   warn  error" + ("  p95_ms" if has_latency else ""),
    ]

    def row(label: str, total: str, warn: str, err: str, p95: str, mark: str = "") -> str:
        return f"{label:<11} {total:>5} {warn:>6} {err:>6}" + (f" {p95:>7}" if has_latency else "") + mark

    # Runs of 3+ buckets with no warnings/errors are folded into one line:
    # the model needs the shape (quiet -> errors), not 20 identical rows.
    quiet: list[tuple[datetime, list[LogEntry]]] = []

    def flush() -> None:
        if len(quiet) >= 3:
            totals = [len(b) for _, b in quiet]
            p95s = [float(p) for p in (_p95(_latency(b)) for _, b in quiet) if p != "-"]
            lines.append(row(
                f"{quiet[0][0]:%H:%M}-{quiet[-1][0]:%H:%M}", f"{min(totals)}-{max(totals)}", "0", "0",
                f"{min(p95s):.0f}-{max(p95s):.0f}" if p95s else "-", f"  ({len(quiet)} quiet buckets)",
            ))
        else:
            for start, b in quiet:
                lines.append(row(f"{start:%H:%M:%S}", str(len(b)), "0", "0", _p95(_latency(b))))
        quiet.clear()

    seen_error = False
    for start, b in buckets:
        n_err = sum(_is_error(e) for e in b)
        n_warn = sum(e.level == "WARNING" for e in b)
        if not n_err and not n_warn:
            quiet.append((start, b))
            continue
        flush()
        mark = ""
        if n_err and not seen_error:
            mark, seen_error = "  <- first errors", True
        lines.append(row(f"{start:%H:%M:%S}", str(len(b)), str(n_warn), str(n_err), _p95(_latency(b)), mark))
    flush()

    starts = _starts(entries)
    if starts:
        lines.append(starts)
    lines.append("Top error messages (emails/ids/long numbers masked):")
    lines += _top(errors, 5) or ["  none"]
    lines.append("Top warning messages:")
    lines += _top(warnings, 3) or ["  none"]
    return "\n".join(lines)


def log_stats(scenario_dir: Path, a: LogStatsArgs) -> str:
    entries = _window(load_logs(scenario_dir, a.service), a.since, a.until)
    if not entries:
        return f"No log entries for {a.service!r} in that time window."
    return format_stats(a.service, bucketize(entries, parse_bucket(a.bucket).total_seconds()))


# --- 2. search_logs ----------------------------------------------------------

class SearchLogsArgs(BaseModel):
    service: str
    level: Level | None = None          # minimum level: WARNING -> WARNING, ERROR, CRITICAL
    keyword: str | None = None          # case-insensitive, matches message and fields
    since: str | None = None
    until: str | None = None
    limit: int = Field(50, ge=1, le=100)


def search_logs(scenario_dir: Path, a: SearchLogsArgs) -> str:
    entries = _window(load_logs(scenario_dir, a.service), a.since, a.until)
    if a.level:
        min_rank = LEVELS.index(a.level)
        entries = [e for e in entries if e.level in LEVELS and LEVELS.index(e.level) >= min_rank]
    if a.keyword:
        kw = a.keyword.lower()
        entries = [e for e in entries if kw in e.msg.lower() or kw in str(e.fields).lower()]
    if not entries:
        return "No matching log entries."
    shown = entries[: a.limit]
    header = f"{len(entries)} matching entries" + (
        f", showing the first {len(shown)} (oldest first)." if len(entries) > len(shown) else "."
    )
    return "\n".join([header] + [format_entry(e) for e in shown])


# --- 3. list_commits ---------------------------------------------------------

class ListCommitsArgs(BaseModel):
    since: str | None = None            # ISO timestamp or HH:MM on the incident day
    path: str | None = None             # only commits touching a file containing this text
    limit: int = Field(20, ge=1, le=100)


def list_commits(scenario_dir: Path, a: ListCommitsArgs) -> str:
    commits = load_commits(scenario_dir)
    if a.since:
        ref_day = parse_ts(commits[0]["date"]).replace(hour=0, minute=0, second=0, microsecond=0)
        lo = parse_user_time(a.since, ref_day)
        commits = [c for c in commits if parse_ts(c["date"]) >= lo]
    if a.path:
        commits = [c for c in commits if any(a.path in f for f in c["files"])]
    if not commits:
        return "No matching commits."
    lines = [
        f"{c['hash']} {c['date']} {c['author']}: {c['message']} [{', '.join(c['files'])}]"
        for c in commits[: a.limit]
    ]
    return "\n".join([f"{len(commits)} commits (newest first):"] + lines)


# --- 4. show_commit ----------------------------------------------------------

class ShowCommitArgs(BaseModel):
    hash: str
    path: str | None = None             # only this file's part of the diff
    max_lines: int = Field(100, ge=10, le=100)


def show_commit(scenario_dir: Path, a: ShowCommitArgs) -> str:
    diff = load_diff(scenario_dir, a.hash)
    if a.path:
        diff = filter_diff_by_path(diff, a.path)
    return cap_output(diff, a.max_lines)


# --- 5. read_config ----------------------------------------------------------

class ReadConfigArgs(BaseModel):
    name: str | None = None             # omit to list the config files


def read_config(scenario_dir: Path, a: ReadConfigArgs) -> str:
    if not a.name:
        return "Config files: " + ", ".join(list_configs(scenario_dir))
    return read_config_file(scenario_dir, a.name)


# --- 6. get_db_schema --------------------------------------------------------

class GetDbSchemaArgs(BaseModel):
    table: str | None = None            # omit for an overview of all tables


def get_db_schema(scenario_dir: Path, a: GetDbSchemaArgs) -> str:
    tables = parse_schema(scenario_dir)
    if not a.table:
        return "\n".join(
            f"{t.name}: {len(t.columns)} columns; indexes: {', '.join(t.indexes) or 'none'}"
            for t in tables.values()
        )
    t = tables.get(a.table)
    if t is None:
        raise not_found("table", a.table, list(tables))
    return "\n".join(
        [f"TABLE {t.name}", "Columns:"] + [f"  {c}" for c in t.columns]
        + ["Constraints:"] + [f"  {c}" for c in t.constraints or ["none"]]
        + ["Indexes:"] + [f"  {i}" for i in t.indexes or ["none"]]
    )


# --- 7. get_container_status -------------------------------------------------

class GetContainerStatusArgs(BaseModel):
    service: str | None = None          # omit for all containers


def get_container_status(scenario_dir: Path, a: GetContainerStatusArgs) -> str:
    containers = load_containers(scenario_dir)
    if a.service:
        picked = [c for c in containers if c["service"] == a.service]
        if not picked:
            raise not_found("container", a.service, [c["service"] for c in containers])
        containers = picked
    return "\n".join(
        f"{c['service']}: state={c['state']} restarts={c['restarts']} exit_code={c['exit_code']} "
        f"oom_killed={c['oom_killed']} mem_limit_mb={c['mem_limit_mb']} started_at={c['started_at']}"
        for c in containers
    )


# --- terminal tool: submit_report --------------------------------------------

Category = Literal[
    "missing_migration", "bad_config", "resource_exhaustion", "performance_regression",
    "code_bug", "dependency_failure", "infra_crash", "unknown",
]


class Evidence(BaseModel):
    source: str                         # e.g. "logs/api.jsonl", "git/45b232b", "config/api.env"
    quote: str                          # copied verbatim from a tool output


class SubmitReportArgs(BaseModel):
    status: Literal["identified", "not_identified"]
    root_cause_category: Category
    summary: str
    evidence: list[Evidence]
    confidence: float = Field(ge=0.0, le=1.0)
    suggested_fix: str


def submit_report(scenario_dir: Path, a: SubmitReportArgs) -> str:
    # The loop (Day 3) detects this tool and stops; validation rules on top of
    # the schema (min evidence, quote really seen, ...) are yours, Day 4.
    return "Report received."
