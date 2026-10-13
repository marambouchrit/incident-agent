"""Run one incident end to end and freeze it into scenarios/<id>/ + ground_truth/<id>.json.

    python capture/run_scenario.py <id> <fault> [--healthy-min 18] [--total-min 35]

Run from Git Bash (fault scripts are bash). Standard library only.
Flow: healthy shop -> traffic -> fault's timeline (inject.sh at --healthy-min) -> snapshot -> reset.sh.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "target_app"
REPO = APP / "_repo"
FAULTS = ROOT / "faults"

SERVICES = ["api", "worker", "db", "payments"]
LOG_FILES = {"api": "api.jsonl", "worker": "worker.jsonl", "db": "db.log"}
CATEGORIES = {
    "missing_migration", "bad_config", "resource_exhaustion", "performance_regression",
    "code_bug", "dependency_failure", "infra_crash", "unknown",
}
GT_KEYS = [
    "id", "fault", "category", "key_detail", "key_detail_aliases", "culprit_commit", "culprit_file",
    "first_error_ts", "symptom_location", "cause_location", "difficulty", "red_herrings", "split",
    "expected_fix", "notes",
]
LEAK = re.compile(r"\b(fault\w*|inject\w*|scenario\w*|ground[_ ]truth)\b", re.IGNORECASE)


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def run(cmd: list[str], *, capture: bool = False, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        cmd, cwd=REPO, env=env or base_env(), check=True, text=True, encoding="utf-8",
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout if capture else ""


def git(*args: str) -> str:
    return run(["git", *args], capture=True)


def base_env() -> dict[str, str]:
    version = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=REPO, check=True, text=True, stdout=subprocess.PIPE
    ).stdout.strip()
    return os.environ | {"MSYS_NO_PATHCONV": "1", "APP_VERSION": version}


def compose(*args: str, capture: bool = False) -> str:
    return run(["docker", "compose", *args], capture=capture)


def bash(script: Path, extra: dict[str, str] | None = None) -> None:
    exe = shutil.which("bash")
    if not exe or "system32" in exe.lower():
        sys.exit("Git Bash not found first on PATH. Run this command from a Git Bash terminal.")
    print(f"[{iso(now())}] running {script.relative_to(ROOT).as_posix()}", flush=True)
    subprocess.run([exe, script.as_posix()], cwd=REPO, env=base_env() | (extra or {}), check=True)


def read_timeline(fault_dir: Path, healthy_min: float) -> list[tuple[float, str]]:
    """Lines of '<minute> <script>' in timeline.txt; default is inject.sh at healthy_min."""
    path = fault_dir / "timeline.txt"
    if not path.exists():
        return [(healthy_min, "inject.sh")]
    steps = []
    for line in path.read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            minute, script = line.split()
            steps.append((float(minute), script))
    return sorted(steps)


def keep_awake() -> None:
    """Ask Windows not to idle-sleep while this process runs (released automatically on exit)."""
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)  # CONTINUOUS | SYSTEM_REQUIRED


def sleep_until(start: datetime, minute: float) -> None:
    """Wait in short slices; a slice that takes far too long means the machine was suspended."""
    while True:
        remaining = minute * 60 - (now() - start).total_seconds()
        if remaining <= 0:
            return
        before = now()
        time.sleep(min(5, remaining))
        if (now() - before).total_seconds() > 60:
            sys.exit("The computer was suspended during the recording, so the logs have a gap. Run it again.")


def mask(text: str) -> str:
    text = re.sub(r"(://[^:/@\s]+:)[^@\s]+@", r"\1***@", text)
    return re.sub(r"(POSTGRES_PASSWORD:\s*)\S+", r"\1***", text)


def fill(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def export_logs(work: Path, out: Path) -> dict[str, int]:
    counts = {}
    (out / "logs").mkdir(parents=True)
    for service, name in LOG_FILES.items():
        lines = (work / f"{service}.raw").read_text(encoding="utf-8", errors="replace").splitlines()
        if name.endswith(".jsonl"):
            kept = []
            for line in lines:
                try:
                    json.loads(line)
                    kept.append(line)
                except ValueError:
                    pass
            if len(kept) != len(lines):
                print(f"  note: dropped {len(lines) - len(kept)} non-JSON lines from {service}")
            lines = kept
        (out / "logs" / name).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        counts[name] = len(lines)
    return counts


def export_git(out: Path) -> int:
    (out / "git" / "diffs").mkdir(parents=True)
    commits = []
    for commit in git("log", "--format=%h").split():
        author, date, message = git("show", "-s", "--format=%an%x1f%cI%x1f%s", commit).strip().split("\x1f")
        files = git("show", "--name-only", "--format=", commit).split()
        commits.append({"hash": commit, "author": author, "date": date, "message": message, "files": files})
        patch = git("show", "--format=commit %h%nAuthor: %an%nDate:   %cI%n%n    %s%n", commit)
        (out / "git" / "diffs" / f"{commit}.patch").write_text(mask(patch), encoding="utf-8", newline="\n")
    with (out / "git" / "commits.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for commit in commits:
            handle.write(json.dumps(commit) + "\n")
    return len(commits)


def export_config(out: Path) -> None:
    (out / "config").mkdir()
    for path in [*sorted((REPO / "config").iterdir()), REPO / "docker-compose.yml"]:
        (out / "config" / path.name).write_text(mask(path.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")


def export_schema(out: Path) -> None:
    schema = compose("exec", "-T", "db", "pg_dump", "-U", "shopline", "-d", "shopline", "--schema-only", "--no-owner", capture=True)
    (out / "db").mkdir()
    (out / "db" / "schema.sql").write_text(schema, encoding="utf-8", newline="\n")


def export_containers(work: Path, out: Path) -> None:
    events: dict[str, dict[str, object]] = {}
    for line in (work / "events.raw").read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        attrs = event["Actor"]["Attributes"]
        # keyed by container id: a container replaced by a deploy must not leak its exit into the new one
        seen = events.setdefault(event["Actor"]["ID"], {"oom": False, "exit_code": None})
        if event["Action"] == "oom":
            seen["oom"] = True
        elif event["Action"] == "die":
            seen["exit_code"] = int(attrs.get("exitCode", 0))
    containers = []
    for service in SERVICES:
        ids = compose("ps", "-aq", service, capture=True).split()
        if not ids:
            continue
        info = json.loads(run(["docker", "inspect", ids[0]], capture=True))[0]
        state, seen = info["State"], events.get(info["Id"], {})
        containers.append({
            "service": service,
            "state": state["Status"],
            "restarts": info["RestartCount"],
            "exit_code": seen.get("exit_code") if seen.get("exit_code") is not None else state["ExitCode"],
            "oom_killed": bool(state["OOMKilled"] or seen.get("oom")),
            "mem_limit_mb": info["HostConfig"]["Memory"] // (1024 * 1024),
            "started_at": state["StartedAt"],
        })
    (out / "containers.json").write_text(json.dumps(containers, indent=2) + "\n", encoding="utf-8", newline="\n")


def first_error_ts(out: Path, since: str) -> str:
    found = []
    for name in ("api.jsonl", "worker.jsonl"):
        for line in (out / "logs" / name).read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            if record.get("level") in ("ERROR", "CRITICAL") and record.get("ts", "") >= since:
                found.append(record["ts"])
                break
    return min(found) if found else ""


def first_crash_ts(work: Path) -> str:
    """Time of the first out-of-memory kill, for incidents that log no error."""
    for line in (work / "events.raw").read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event["Action"] == "oom":
            return iso(datetime.fromtimestamp(event["timeNano"] / 1e9, tz=timezone.utc))
    return ""


def write_ground_truth(fault_dir: Path, values: dict[str, str], path: Path) -> None:
    truth = json.loads(fill((fault_dir / "ground_truth.json").read_text(encoding="utf-8"), values))
    missing = [key for key in GT_KEYS if key not in truth]
    problems = [f"missing keys: {missing}"] if missing else []
    if truth.get("category") not in CATEGORIES:
        problems.append(f"category {truth.get('category')!r} not in the fixed list")
    if truth.get("difficulty") not in ("easy", "medium", "hard"):
        problems.append("difficulty must be easy|medium|hard")
    if truth.get("split") not in ("dev", "holdout"):
        problems.append("split must be dev|holdout")
    if problems:
        sys.exit("ground_truth.json template is invalid: " + "; ".join(problems))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(truth, indent=2) + "\n", encoding="utf-8", newline="\n")


def leak_scan(out: Path) -> list[str]:
    hits = []
    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            match = LEAK.search(line)
            if match:
                hits.append(f"{path.relative_to(out).as_posix()}:{number}: '{match.group(0)}'")
    return hits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("id", help="neutral scenario id, e.g. s01")
    parser.add_argument("fault", help="folder name under faults/")
    parser.add_argument("--healthy-min", type=float, default=18, help="minute at which inject.sh runs")
    parser.add_argument("--total-min", type=float, default=35, help="length of the recorded window")
    parser.add_argument("--rps", help="steady traffic rate for this run (default: the shop's compose value)")
    parser.add_argument("--out-root", type=Path, default=ROOT, help="where scenarios/ and ground_truth/ are written")
    parser.add_argument("--force", action="store_true", help="overwrite an existing scenario with this id")
    args = parser.parse_args()

    fault_dir = FAULTS / args.fault
    for needed in ("inject.sh", "reset.sh", "incident.txt", "ground_truth.json"):
        if not (fault_dir / needed).exists():
            sys.exit(f"{fault_dir.relative_to(ROOT).as_posix()}/{needed} is missing")
    out = args.out_root / "scenarios" / args.id
    if out.exists():
        if not args.force:
            sys.exit(f"{out} already exists (use --force)")
        shutil.rmtree(out)
    work = ROOT / "capture" / ".work" / args.id
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    script_env = {"WORK": work.as_posix(), "FAULTS_DIR": FAULTS.as_posix()}

    keep_awake()
    if args.rps:
        os.environ["LOADGEN_RPS"] = args.rps
    print("== 1/5 healthy shop at the base commit", flush=True)
    if not (REPO / ".git").exists():
        bash(APP / "seed_history.sh")
    git("reset", "-q", "--hard", "seed-base")
    git("clean", "-fdq")
    bash(APP / "bootstrap.sh")
    bash(fault_dir / "reset.sh", script_env)

    print("== 2/5 recording and traffic", flush=True)
    start = now()
    # reach back a little so each service's own startup line is always in the recording
    since = (start - timedelta(seconds=45)).strftime("%Y-%m-%dT%H:%M:%SZ")
    recorders = []
    for service in LOG_FILES:
        handle = (work / f"{service}.raw").open("w", encoding="utf-8")
        cmd = ["docker", "compose", "logs", "-f", "--no-log-prefix", "--since", since, service]
        recorders.append((subprocess.Popen(cmd, cwd=REPO, env=base_env(), stdout=handle, stderr=subprocess.STDOUT), handle))
    handle = (work / "events.raw").open("w", encoding="utf-8")
    cmd = ["docker", "events", "--since", since, "--filter", "type=container", "--filter", "event=oom",
           "--filter", "event=die", "--format", "{{json .}}"]
    recorders.append((subprocess.Popen(cmd, stdout=handle), handle))
    compose("--profile", "load", "up", "-d", "--force-recreate", "--no-deps", "loadgen")

    print(f"== 3/5 timeline ({args.total_min:g} minutes in total)", flush=True)
    inject_at = None
    for minute, script in read_timeline(fault_dir, args.healthy_min):
        sleep_until(start, minute)
        if script == "inject.sh":
            inject_at = now()
        bash(fault_dir / script, script_env)
    sleep_until(start, args.total_min)

    print("== 4/5 snapshot", flush=True)
    compose("--profile", "load", "stop", "loadgen")
    time.sleep(3)
    for process, handle in recorders:
        process.terminate()
        process.wait()
        handle.close()

    counts = export_logs(work, out)
    commit_count = export_git(out)
    export_config(out)
    export_schema(out)
    export_containers(work, out)

    culprit = work / "culprit_commit"
    inject_ts = iso(inject_at or start)
    error_ts = first_error_ts(out, inject_ts)
    crash_ts = first_crash_ts(work)
    values = {
        "ID": args.id,
        "CULPRIT_COMMIT": culprit.read_text().strip() if culprit.exists() else "",
        "INJECT_TS": inject_ts,
        "INJECT_TIME": inject_ts[11:16],
        "FIRST_ERROR_TS": error_ts,
        "FIRST_ERROR_TIME": error_ts[11:16],
        "FIRST_CRASH_TS": crash_ts,
        "FIRST_CRASH_TIME": crash_ts[11:16],
    }
    incident = fill((fault_dir / "incident.txt").read_text(encoding="utf-8"), values)
    (out / "incident.txt").write_text(incident, encoding="utf-8", newline="\n")
    write_ground_truth(fault_dir, values, args.out_root / "ground_truth" / f"{args.id}.json")

    print("== 5/5 reset", flush=True)
    bash(fault_dir / "reset.sh", script_env)
    git("reset", "-q", "--hard", "seed-base")
    compose("--profile", "load", "stop")

    print(f"\nwrote {out}")
    print(f"  log lines: {counts}   commits: {commit_count}")
    print(f"  change applied at {inject_ts}   first error at {error_ts or '(none logged)'}   first kill at {crash_ts or '(none)'}")
    hits = leak_scan(out)
    print(f"  giveaway word scan: {len(hits)} hit(s)")
    for hit in hits[:20]:
        print(f"    {hit}")


if __name__ == "__main__":
    main()
