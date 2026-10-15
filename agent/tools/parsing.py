"""Read and parse the files of one scenario folder.

Pure plumbing: no decisions about what the model sees. Every path goes
through safe_path, so nothing here can leave the scenario folder.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agent.tools.guards import ToolError, safe_path

LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# PostgreSQL severities -> our levels
_PG_LEVEL = {"DEBUG": "DEBUG", "LOG": "INFO", "INFO": "INFO", "NOTICE": "INFO",
             "WARNING": "WARNING", "ERROR": "ERROR", "FATAL": "CRITICAL", "PANIC": "CRITICAL"}
# These pg lines belong to the entry just before them
_PG_ATTACHED = {"DETAIL", "HINT", "STATEMENT", "CONTEXT", "QUERY", "LOCATION"}
_PG_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d\d-\d\d \d\d:\d\d:\d\d(?:\.\d+)?) UTC \[\d+\] (?:\S+ )?(?P<sev>[A-Z]+):\s+(?P<msg>.*)$"
)
_EXC_LINE = re.compile(r"^[A-Za-z_][\w.]*(Error|Exception|Exit|Timeout|Interrupt)\b.*")


@dataclass
class LogEntry:
    ts: datetime
    level: str
    msg: str
    fields: dict = field(default_factory=dict)  # everything else (path, status, exc, ...)


def not_found(kind: str, given: str, available: list[str]) -> ToolError:
    # Wording follows ROADMAP §1.3 ("No logs for service 'chekout'. Available services: ...").
    # Error messages are yours to tune (CLAUDE.md ownership split).
    return ToolError(f"No {kind} {given!r}. Available: {', '.join(available) or '(none)'}.")


# --- time --------------------------------------------------------------------

def parse_ts(value: str) -> datetime:
    """Parse an ISO timestamp (with Z or offset, or naive = UTC)."""
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_user_time(value: str | None, ref_day: datetime) -> datetime | None:
    """Accept 'HH:MM', 'HH:MM:SS' (on the incident day, UTC) or a full ISO timestamp."""
    if value is None:
        return None
    v = value.strip()
    try:
        if re.fullmatch(r"\d{1,2}:\d\d(:\d\d)?", v):
            parts = [int(p) for p in v.split(":")] + [0]
            return ref_day.replace(hour=parts[0], minute=parts[1], second=parts[2], microsecond=0)
        return parse_ts(v)
    except ValueError:
        raise ToolError(f"Bad time {value!r}. Use 'HH:MM' (UTC, incident day) or ISO like '2026-10-13T14:05:00Z'.")


def parse_bucket(value: str) -> timedelta:
    m = re.fullmatch(r"(\d+)\s*([smh])", value.strip())
    if not m or int(m.group(1)) == 0:
        raise ToolError(f"Bad bucket {value!r}. Use e.g. '30s', '1m', '5m', '1h'.")
    unit = {"s": "seconds", "m": "minutes", "h": "hours"}[m.group(2)]
    return timedelta(**{unit: int(m.group(1))})


# --- logs --------------------------------------------------------------------

def list_services(scenario_dir: Path) -> list[str]:
    logs = safe_path(scenario_dir, "logs")
    return sorted(p.stem for p in logs.iterdir() if p.suffix in (".jsonl", ".log"))


def _log_file(scenario_dir: Path, service: str) -> Path:
    for name in (f"{service}.jsonl", f"{service}.log"):
        p = safe_path(scenario_dir, f"logs/{name}")
        if p.is_file():
            return p
    raise not_found("logs for service", service, list_services(scenario_dir))


def _parse_jsonl(path: Path) -> list[LogEntry]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
            ts, level, msg = parse_ts(d.pop("ts")), d.pop("level", "INFO").upper(), d.pop("msg", "")
        except (ValueError, KeyError):
            continue  # skip a corrupt line rather than failing the whole tool
        d.pop("service", None)
        out.append(LogEntry(ts, level, msg, d))
    return out


def _parse_pg(path: Path) -> list[LogEntry]:
    """Postgres text log: one entry per severity line; DETAIL/STATEMENT and
    tab-indented continuation lines are folded into the entry above."""
    out: list[LogEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = _PG_LINE.match(line)
        if m and m["sev"] in _PG_LEVEL:
            out.append(LogEntry(parse_ts(m["ts"].replace(" ", "T")), _PG_LEVEL[m["sev"]], m["msg"]))
        elif m and m["sev"] in _PG_ATTACHED and out:
            out[-1].fields[m["sev"].lower()] = m["msg"]
        elif out and line.strip():
            # continuation of a multi-line STATEMENT (or msg)
            key = "statement" if "statement" in out[-1].fields else None
            if key:
                out[-1].fields[key] += " " + line.strip()
            else:
                out[-1].msg += " " + line.strip()
    return out


def load_logs(scenario_dir: Path, service: str) -> list[LogEntry]:
    path = _log_file(scenario_dir, service)
    return _parse_jsonl(path) if path.suffix == ".jsonl" else _parse_pg(path)


def exc_summary(exc: str) -> str:
    """The last 'SomethingError: ...' line of a traceback (the one that names the failure)."""
    hits = [l.strip() for l in exc.splitlines() if _EXC_LINE.match(l.strip())]
    if hits:
        return hits[-1]
    lines = [l.strip() for l in exc.splitlines() if l.strip()]
    return lines[-1] if lines else ""


def format_entry(e: LogEntry) -> str:
    """One log entry -> one line. Tracebacks are reduced to their exception line."""
    ts = e.ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{e.ts.microsecond // 1000:03d}Z"
    extras = []
    for k, v in e.fields.items():
        v = exc_summary(str(v)) if k == "exc" else " ".join(str(v).split())
        extras.append(f"{k}={v}")
    tail = (" | " + " ".join(extras)) if extras else ""
    return f"{ts} {e.level} {' '.join(e.msg.split())}{tail}"


# --- git ---------------------------------------------------------------------

def load_commits(scenario_dir: Path) -> list[dict]:
    path = safe_path(scenario_dir, "git/commits.jsonl")
    commits = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    commits.sort(key=lambda c: c["date"], reverse=True)  # newest first
    return commits


def load_diff(scenario_dir: Path, commit_hash: str) -> str:
    h = commit_hash.strip()
    if not re.fullmatch(r"[0-9a-fA-F]{4,40}", h):
        raise ToolError(f"Bad commit hash {commit_hash!r}. Use a hash from list_commits.")
    hashes = [c["hash"] for c in load_commits(scenario_dir)]
    matches = [x for x in hashes if x.startswith(h) or h.startswith(x)]
    if len(matches) != 1:
        raise not_found("commit", commit_hash, hashes)
    return safe_path(scenario_dir, f"git/diffs/{matches[0]}.patch").read_text(encoding="utf-8")


def filter_diff_by_path(diff: str, path: str) -> str:
    """Keep the commit header and only the file sections whose path contains `path`."""
    parts = re.split(r"(?m)^(?=diff --git )", diff)
    header, files = parts[0], parts[1:]
    kept = [f for f in files if path in f.splitlines()[0]]
    if not kept:
        names = [f.splitlines()[0].split(" b/")[-1] for f in files]
        raise not_found("file in this commit", path, names)
    return header + "".join(kept)


# --- config, db, containers --------------------------------------------------

def list_configs(scenario_dir: Path) -> list[str]:
    return sorted(p.name for p in safe_path(scenario_dir, "config").iterdir() if p.is_file())


def read_config_file(scenario_dir: Path, name: str) -> str:
    available = list_configs(scenario_dir)
    if name not in available:
        raise not_found("config file", name, available)
    return safe_path(scenario_dir, f"config/{name}").read_text(encoding="utf-8")


@dataclass
class Table:
    name: str
    columns: list[str] = field(default_factory=list)      # "name type [NOT NULL] [DEFAULT ..]"
    constraints: list[str] = field(default_factory=list)  # PRIMARY KEY / UNIQUE / FOREIGN KEY
    indexes: list[str] = field(default_factory=list)      # "ix_name (col, col)"


def parse_schema(scenario_dir: Path) -> dict[str, Table]:
    """Parse a pg_dump schema into tables with columns, constraints and indexes."""
    sql = safe_path(scenario_dir, "db/schema.sql").read_text(encoding="utf-8")
    tables: dict[str, Table] = {}

    for m in re.finditer(r"CREATE TABLE public\.(\w+) \((.*?)\n\);", sql, re.S):
        t = Table(m[1])
        for line in m[2].splitlines():
            line = line.strip().rstrip(",")
            if line and not line.startswith("CONSTRAINT"):
                t.columns.append(line)
        tables[t.name] = t

    for m in re.finditer(r"ALTER TABLE ONLY public\.(\w+)\s+ADD CONSTRAINT (\w+) (.*?);", sql, re.S):
        if m[1] in tables:
            tables[m[1]].constraints.append(f"{m[2]} {' '.join(m[3].split())}")

    for m in re.finditer(r"CREATE (UNIQUE )?INDEX (\w+) ON public\.(\w+) USING \w+ \((.*?)\);", sql):
        if m[3] in tables:
            tables[m[3]].indexes.append(f"{m[2]} ({m[4]}){' UNIQUE' if m[1] else ''}")

    return tables


def load_containers(scenario_dir: Path) -> list[dict]:
    return json.loads(safe_path(scenario_dir, "containers.json").read_text(encoding="utf-8"))
