#!/usr/bin/env bash
# Put the order_items indexes and the schema version back to the base state; clear unfinished jobs.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

psql_db "CREATE INDEX IF NOT EXISTS ix_order_items_order_id ON order_items (order_id)"
psql_db "DROP INDEX IF EXISTS ix_order_items_product_id"
psql_db "UPDATE alembic_version SET version_num = '0001'"
psql_db "DELETE FROM jobs WHERE status <> 'done'"
