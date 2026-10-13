#!/usr/bin/env bash
# Build the target app's own git repo (target_app/_repo) with a realistic seed history.
# The repo is separate from this project's repo and is git-ignored here.
#   ./seed_history.sh [--force]
set -euo pipefail
unset MSYS_NO_PATHCONV  # this script passes POSIX paths to git, which needs path conversion on Windows
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/src"
HIST="$HERE/history"
REPO="$HERE/_repo"

if [ -d "$REPO" ]; then
    [ "${1:-}" = "--force" ] || { echo "$REPO already exists (use --force to rebuild)" >&2; exit 1; }
    # Docker Desktop can hold the bind-mounted config folder for a few seconds after a container stops
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        rm -rf "$REPO" 2>/dev/null && break
        sleep 3
    done
    [ ! -e "$REPO" ] || { echo "could not remove $REPO (still in use)" >&2; exit 1; }
fi
mkdir -p "$REPO"
git -C "$REPO" init -q -b main
git -C "$REPO" config core.autocrlf false

LINA="Lina Haddad <lina@shopline.example>"
TOMAS="Tomas Keller <tomas@shopline.example>"
PRIYA="Priya Nair <priya@shopline.example>"

# put <path under src> : copy a file or folder from src/ into the repo at the same path
put() {
    for rel in "$@"; do
        mkdir -p "$REPO/$(dirname "$rel")"
        cp -r "$SRC/$rel" "$REPO/$rel"
    done
}

# put_as <file under history> <path in repo> : copy an older version of a file
put_as() {
    mkdir -p "$REPO/$(dirname "$2")"
    cp "$HIST/$1" "$REPO/$2"
}

# commit <days ago> <HH:MM> <author> <message>
commit() {
    local when author name email
    when="$(date -u -d "$1 days ago" +%Y-%m-%d)T$2:00+00:00"
    author="$3"
    name="${author%% <*}"
    email="${author##*<}"
    email="${email%>}"
    git -C "$REPO" add -A
    GIT_AUTHOR_DATE="$when" GIT_COMMITTER_DATE="$when" \
        git -C "$REPO" -c user.name="$name" -c user.email="$email" commit -q -m "$4"
}

put .gitignore .dockerignore Dockerfile docker-compose.yml deploy.sh alembic.ini config \
    app/__init__.py app/config.py app/db.py app/logging_setup.py app/run.py app/routers/__init__.py \
    migrations/env.py migrations/script.py.mako
put_as requirements.v1.txt requirements.txt
put_as main.v1.py app/main.py
commit 21 09:40 "$LINA" "Initial project skeleton and Compose setup"

put app/models.py migrations/versions app/routers/products.py app/routers/users.py scripts
commit 19 14:05 "$LINA" "Add products and users endpoints"

put app/routers/orders.py app/routers/checkout.py app/payments_client.py
commit 17 11:20 "$TOMAS" "Add orders and checkout flow with payments client"

put app/middleware.py app/main.py
commit 15 16:30 "$PRIYA" "Add request logging middleware and request ids"

put worker/__init__.py worker/main.py worker/handlers/__init__.py \
    worker/handlers/order_confirmation.py worker/handlers/stock_reconcile.py
commit 12 10:15 "$TOMAS" "Add worker and jobs queue"

put payments_stub
commit 10 13:50 "$TOMAS" "Add payment provider stub for local runs"

put requirements.txt
commit 8 09:05 "$PRIYA" "Bump SQLAlchemy and psycopg versions"

put app/routers/search.py
commit 6 15:45 "$LINA" "Add product search endpoint"

put worker/handlers/sales_export.py
commit 4 11:00 "$PRIYA" "Add sales export job"

put README.md loadgen
commit 2 17:10 "$LINA" "Add load test script, update README and deploy notes"

git -C "$REPO" tag seed-base

echo "Seeded $REPO:"
git -C "$REPO" log --format='%h %ad %an  %s' --date=short
