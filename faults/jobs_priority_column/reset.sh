#!/usr/bin/env bash
# Put jobs and the schema version back to the base state (in case the migration was run by hand); clear unfinished jobs.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

psql_db "ALTER TABLE jobs DROP COLUMN IF EXISTS priority"
psql_db "UPDATE alembic_version SET version_num = '0001'"
psql_db "DELETE FROM jobs WHERE status <> 'done'"
