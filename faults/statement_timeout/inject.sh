#!/usr/bin/env bash
# Lowers statement_timeout in the tracked postgres config and reloads postgres.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

# Rewrite in place: config/postgres.conf is a single-file bind mount, a new inode may not reach the container.
python - <<'PY'
from pathlib import Path

file = Path("config/postgres.conf")
text = file.read_text(encoding="utf-8")
old = "statement_timeout = 30s\n"
assert text.count(old) == 1, "statement_timeout line not found"
with file.open("r+", encoding="utf-8", newline="\n") as handle:
    handle.seek(0)
    handle.write(text.replace(old, "statement_timeout = 250ms\n"))
    handle.truncate()
PY

commit_as "$PRIYA" "Align DB settings with staging"
mark_culprit
psql_db "SELECT pg_reload_conf()"

live="$(MSYS_NO_PATHCONV=1 docker compose exec -T db psql -U shopline -d shopline -tAc 'SHOW statement_timeout' 2>/dev/null | tr -d '\r' || true)"
if [ -n "$live" ] && [ "$live" != "250ms" ]; then
    echo "WARNING: postgres still reports statement_timeout=$live after reload" >&2
fi
