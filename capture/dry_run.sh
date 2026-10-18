#!/usr/bin/env bash
# capture/dry_run.sh <fault>
# Runs a fault's timeline scripts against a throwaway clone of the shop repo, with a fake `docker`
# (deploys, psql and loadgen are only printed). Catches broken edits and commits in seconds,
# before a 35-minute recording. Never touches target_app/_repo or the running shop.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FAULT="${1:?usage: capture/dry_run.sh <fault>}"
FAULT_DIR="$ROOT/faults/$FAULT"
[ -d "$FAULT_DIR" ] || { echo "no such fault: $FAULT_DIR" >&2; exit 2; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git clone -q "$ROOT/target_app/_repo" "$TMP/repo"
git -C "$TMP/repo" checkout -q seed-base

mkdir -p "$TMP/bin" "$TMP/work"
cat > "$TMP/bin/docker" <<'SH'
#!/usr/bin/env bash
echo "  [fake docker] $*" >&2
SH
chmod +x "$TMP/bin/docker"

export PATH="$TMP/bin:$PATH" WORK="$TMP/work" FAULTS_DIR="$ROOT/faults"

for f in inject.sh reset.sh incident.txt ground_truth.json; do
    [ -f "$FAULT_DIR/$f" ] || { echo "MISSING $f" >&2; exit 1; }
done

if [ -f "$FAULT_DIR/timeline.txt" ]; then
    scripts="$(grep -v '^\s*#' "$FAULT_DIR/timeline.txt" | awk 'NF {print $1, $2}')"
else
    scripts="18 inject.sh"
fi

echo "== reset.sh"
(cd "$TMP/repo" && bash "$FAULT_DIR/reset.sh")
while read -r minute script; do
    [ -n "$script" ] || continue
    echo "== minute $minute: $script"
    (cd "$TMP/repo" && bash "$FAULT_DIR/$script")
done <<< "$scripts"

echo "== commits added on top of seed-base"
git -C "$TMP/repo" log --format='%h %an: %s' seed-base..HEAD
if [ -f "$WORK/culprit_commit" ]; then
    echo "culprit: $(cat "$WORK/culprit_commit")"
elif grep -q '"culprit_commit": ""' "$FAULT_DIR/ground_truth.json"; then
    echo "culprit: none (cause is not a commit)"
else
    echo "NO culprit marked" >&2; exit 1
fi

echo "== diffstat"
git -C "$TMP/repo" diff --stat seed-base..HEAD

echo "== template + leak checks"
python - "$FAULT_DIR" "$TMP/repo" <<'PY'
import json, re, subprocess, sys
from pathlib import Path
fault_dir, repo = Path(sys.argv[1]), sys.argv[2]
cats = {"missing_migration", "bad_config", "resource_exhaustion", "performance_regression",
        "code_bug", "dependency_failure", "infra_crash", "unknown"}
truth = json.loads(re.sub(r"\{\{\w+\}\}", "X", (fault_dir / "ground_truth.json").read_text(encoding="utf-8")))
problems = []
if truth.get("category") not in cats: problems.append(f"bad category {truth.get('category')}")
if truth.get("difficulty") not in ("easy", "medium", "hard"): problems.append("bad difficulty")
if truth.get("split") not in ("dev", "holdout"): problems.append("bad split")
leak = re.compile(r"\b(fault\w*|inject\w*|scenario\w*|ground[_ ]truth|oops|hack|break\w*|bug|temporar\w*)\b", re.I)
visible = subprocess.run(["git", "-C", repo, "log", "-p", "seed-base..HEAD"], capture_output=True, text=True,
                         encoding="utf-8").stdout + re.sub(r"\{\{\w+\}\}", "X", (fault_dir / "incident.txt").read_text(encoding="utf-8"))
for line in visible.splitlines():
    if line.startswith(("+", "commit ", "    ")) or not line.startswith(("-", "@@", "diff", "index")):
        m = leak.search(line)
        if m: problems.append(f"leak word '{m.group(0)}': {line.strip()[:100]}")
print("\n".join(problems) if problems else "OK")
sys.exit(1 if problems else 0)
PY
echo "DRY RUN PASSED: $FAULT"
