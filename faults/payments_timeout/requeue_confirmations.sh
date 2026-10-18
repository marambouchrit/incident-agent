#!/usr/bin/env bash
# Support re-sends confirmation emails for a few orders; the order ids no longer exist, so these
# jobs fail in the worker (ERROR "job failed", LookupError) before and after the real change.
# Run times: now, +7 min, +19 min (three attempts each, 30 s apart).
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

psql_db "INSERT INTO jobs (kind, payload, status, attempts, run_at)
SELECT 'order_confirmation',
       jsonb_build_object('order_id', (SELECT coalesce(max(id), 0) FROM orders) + 500000 + v.n),
       'pending', 0, now() + make_interval(mins => v.m)
FROM (VALUES (17, 0), (342, 7), (905, 19)) AS v(n, m)"
