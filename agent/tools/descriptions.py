"""What the LLM reads to choose a tool. This is the tool's real interface."""

_TIME = "Times are UTC: 'HH:MM' (incident day) or ISO like '2026-10-13T14:05:00Z'."
_SERVICES = "service = a log file name: 'api', 'worker' or 'db'."

DESCRIPTIONS: dict[str, str] = {
    "log_stats": (
        "Timeline overview of one service's logs. Per time bucket: entry, warning and error "
        "counts and p95 latency; quiet stretches are folded into one line; the first bucket "
        "with errors is marked. Also lists every service (re)start with the deployed version "
        "(commit hash), and the most frequent error and warning messages with count, first/last "
        "time seen and affected endpoints. Use this when you start looking at a service: it "
        "tells you WHEN things changed and WHAT dominates, so you know where to search next. "
        f"{_SERVICES} bucket like '30s', '1m', '5m'. {_TIME}"
    ),
    "search_logs": (
        "Returns matching log lines of one service, oldest first, one entry per line with its "
        "fields (path, status, latency_ms, ...); tracebacks are reduced to their final exception "
        "line. Use this when you need exact lines to quote as evidence, or the details behind a "
        "message or time seen in log_stats. Always narrow: level is a minimum ('WARNING' also "
        "returns ERROR), keyword is a case-insensitive substring of the message or fields, "
        f"since/until bound the time. {_SERVICES} {_TIME}"
    ),
    "list_commits": (
        "Lists commits of the application repo, newest first: hash, commit time, author, "
        "message, changed files. Use this when you want to know what changed shortly before "
        "the errors began. A commit's hash matches the 'version' in log_stats restarts, so you "
        "can see which commit was running when. Filter with since (a time) or path (substring "
        "of a changed file path). Commit messages can be wrong or vague: check the diff."
    ),
    "show_commit": (
        "Shows the diff of one commit (all files, or only those whose path contains `path`). "
        "Use this when a commit's time or changed files make it a suspect and you need to see "
        "exactly what it changed. Pass a hash from list_commits."
    ),
    "read_config": (
        "Returns one deployment config file verbatim: env files per service, "
        "docker-compose.yml (images, memory limits, env), postgres.conf. Use this when you "
        "suspect a setting: connection strings and hosts, pool sizes, timeouts, memory "
        "limits, feature flags. Call without name to list the files."
    ),
    "get_db_schema": (
        "Returns the database schema as it is now. Without table: one line per table with "
        "its indexes. With table: its columns, constraints and indexes. Use this when errors "
        "mention a missing column or table, or when queries got slow (missing index), to "
        "compare what the code expects with what the database really has."
    ),
    "get_container_status": (
        "Returns each container's current state, restart count, last exit code, OOM-killed "
        "flag, memory limit and start time. Use this when a service restarts repeatedly, its "
        "logs have gaps, or other services fail to connect to it. Exit code 137 or "
        "oom_killed=True means it ran out of memory. Omit service to see all containers."
    ),
    "submit_report": (
        "Ends the investigation with your final report; call it exactly once. Use "
        "status='identified' when the evidence supports one cause, or 'not_identified' with "
        "category 'unknown' when it does not. Each evidence item needs its source (e.g. "
        "'logs/api.jsonl', 'git/<hash>', 'config/api.env', 'db/schema', 'containers') and a "
        "quote copied verbatim from a tool output; never invent or paraphrase quotes. Include "
        "evidence for both the symptom and the cause. confidence is 0-1: how sure you are "
        "this is the root cause, not just a symptom."
    ),
}
