#!/usr/bin/env bash
# Nothing outside git is changed by this fault; drop the column in case it was added by hand.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

psql_db "ALTER TABLE orders DROP COLUMN IF EXISTS discount_code"
