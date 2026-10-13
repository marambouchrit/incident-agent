#!/usr/bin/env bash
# Bring the healthy shop up from nothing: repo, images, schema, demo data, all services.
#   ./bootstrap.sh            start (keeps existing data)
#   ORDERS=200000 ./bootstrap.sh   smaller demo dataset on first start
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$HERE/_repo"
export MSYS_NO_PATHCONV=1

[ -d "$REPO/.git" ] || "$HERE/seed_history.sh"
cd "$REPO"

APP_VERSION="$(git rev-parse --short HEAD)"
export APP_VERSION

docker compose build api
docker compose up -d db
echo "waiting for db..."
until docker compose exec -T db pg_isready -U shopline >/dev/null 2>&1; do sleep 1; done

docker compose run --rm --no-deps api alembic upgrade head

USERS="$(docker compose exec -T db psql -U shopline -d shopline -tAc 'SELECT count(*) FROM users')"
if [ "$USERS" = "0" ]; then
    echo "seeding demo data (${ORDERS:-1500000} orders)..."
    docker compose exec -T db psql -q -U shopline -d shopline -v ON_ERROR_STOP=1 \
        -v orders="${ORDERS:-1500000}" < scripts/seed.sql
fi

docker compose up -d --force-recreate api worker payments
echo "shop is up at http://localhost:18000 (version $APP_VERSION)"
echo "start traffic with: (cd $REPO && docker compose --profile load up -d loadgen)"
