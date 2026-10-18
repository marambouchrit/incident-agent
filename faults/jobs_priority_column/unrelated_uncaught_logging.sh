#!/usr/bin/env bash
# Unrelated logging change (uncaught exceptions go through the JSON formatter), deployed to the worker.
set -euo pipefail
source "$FAULTS_DIR/lib.sh"

python - <<'PY'
from pathlib import Path

file = Path("app/logging_setup.py")
text = file.read_text(encoding="utf-8")
old = "    logging.captureWarnings(True)\n"
assert text.count(old) == 1, "expected exactly one match in app/logging_setup.py"
text = text.replace(
    old,
    old + "    sys.excepthook = lambda *exc_info: logging.getLogger(service).critical(\"uncaught exception\", exc_info=exc_info)\n",
)
file.write_text(text, encoding="utf-8", newline="\n")
PY

commit_as "$TOMAS" "Log uncaught exceptions as JSON"
deploy worker
