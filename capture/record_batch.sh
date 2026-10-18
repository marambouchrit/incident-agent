#!/usr/bin/env bash
# capture/record_batch.sh <id>:<fault> [<id>:<fault> ...]
# Records several scenarios one after the other (one shop, so never in parallel).
# Each kit is dry-run first; a failing kit or capture is logged and skipped, the batch goes on.
# Progress: capture/.work/batch.log
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG="$ROOT/capture/.work/batch.log"
mkdir -p "$(dirname "$LOG")"

say() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$LOG"; }

say "batch start: $*"
for pair in "$@"; do
    id="${pair%%:*}"
    fault="${pair#*:}"
    if ! bash "$ROOT/capture/dry_run.sh" "$fault" >> "$LOG" 2>&1; then
        say "SKIP $id ($fault): dry run failed"
        continue
    fi
    say "RECORD $id ($fault) ..."
    if bash "$ROOT/capture/capture.sh" "$id" "$fault" >> "$LOG" 2>&1; then
        say "DONE $id"
    else
        say "FAIL $id ($fault): see log above"
    fi
done
say "batch end"
