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
        "logs have gaps, or other services fail to connect to it. Exit code 137 only means "
        "the process was killed (SIGKILL): oom_killed=True says memory was the reason; "
        "oom_killed=False means it was stopped from outside. Omit service to see all containers."
    ),
    "submit_report": (
        "Ends the investigation with your final report; call it exactly once. Use "
        "status='identified' when the evidence supports one cause, or 'not_identified' with "
        "category 'unknown' when it does not. Each evidence item needs its source (e.g. "
        "'logs/api.jsonl', 'git/<hash>', 'config/api.env', 'db/schema', 'containers') and a "
        "quote copied verbatim from a tool output; never invent or paraphrase quotes. Include "
        "evidence for both the symptom and the cause. confidence is 0-1: how sure you are "
        "this is the root cause, not just a symptom.\n"
        "root_cause_category, pick the ONE that names the failure mechanism. Classify the "
        "CHANGE that made the problem start (your root cause), not the loudest error it "
        "produces downstream. One exception wins over this rule: if one of the app's own "
        "processes is killed or restarts (OOM kill, crash loop), use infra_crash.\n"
        "- missing_migration: code uses a column/table the database does not have because "
        "a migration was never applied. A migration that DID run and removed an index is "
        "performance_regression.\n"
        "- bad_config: a configuration value is wrong (env var, URL, timeout, retries, DB "
        "server setting) and requests fail because of that value. If work had become slower "
        "earlier but only started failing when a timeout or limit was lowered, the lowered "
        "value is the cause: bad_config. Exception: pool sizes, see resource_exhaustion.\n"
        "- resource_exhaustion: the LIMIT of a shared pool (DB connection pool size/overflow, "
        "max connections) was lowered, or connections leak, so requests wait or time out on "
        "the full pool. Use it even when the smaller pool size was set in a config file.\n"
        "- performance_regression: a code or schema change made the same work slower "
        "(dropped index, N+1 or extra queries, removed LIMIT, heavier query). Use it even if "
        "the slow requests then fill a pool that was NOT made smaller, or cause timeouts "
        "whose value did NOT change.\n"
        "- code_bug: application logic is wrong and raises errors or wrong results for "
        "some inputs, independent of speed or capacity.\n"
        "- dependency_failure: a service the app calls but does not own (third-party "
        "API, external provider) is down or failing; the app's code and config are fine.\n"
        "- infra_crash: one of the app's own containers dies or restarts (OOM kill, crash "
        "loop). Use it whenever the app's process is killed, even if memory was the reason.\n"
        "- unknown: only with status='not_identified'."
    ),
}
