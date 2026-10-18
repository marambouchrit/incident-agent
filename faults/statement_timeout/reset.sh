#!/usr/bin/env bash
# Put the base postgres config back (in place, same inode) and reload it, so the running db matches seed-base.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

git show seed-base:config/postgres.conf > "$WORK/postgres.conf.base"
python - "$WORK/postgres.conf.base" <<'PY'
import sys
from pathlib import Path

base = Path(sys.argv[1]).read_text(encoding="utf-8")
assert "statement_timeout = 30s\n" in base
if Path("config/postgres.conf").read_text(encoding="utf-8") != base:
    with open("config/postgres.conf", "r+", encoding="utf-8", newline="\n") as handle:
        handle.write(base)
        handle.truncate()
PY
psql_db "SELECT pg_reload_conf()"
