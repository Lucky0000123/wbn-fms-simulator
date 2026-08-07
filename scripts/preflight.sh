#!/usr/bin/env bash
# Read-only pre-flight checks from AGENTS.md "Before claiming done".
set -uo pipefail
cd "$(dirname "$0")/.."

echo "=== health ==="
curl -s -m 10 http://127.0.0.1:5055/health || echo "server not running"
echo

echo "=== js syntax ==="
fail=0
for f in static/js/*.js; do
  node --check "$f" || { echo "FAIL $f"; fail=1; }
done
[ "$fail" = 0 ] && echo "all js parse OK"

echo "=== duplicate top-level declarations (must be empty) ==="
grep -hoE "^(let|const|var|function) [A-Za-z_$][A-Za-z0-9_$]*" static/js/*.js | sort | uniq -d
echo "=== done ==="
