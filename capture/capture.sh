#!/usr/bin/env bash
# capture/capture.sh <id> <fault> [options]   (see run_scenario.py --help)
exec python "$(dirname "$0")/run_scenario.py" "$@"
