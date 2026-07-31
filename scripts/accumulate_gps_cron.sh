#!/usr/bin/env bash
# Cron wrapper for scripts/accumulate_gps.py.
#
# Why this file exists: the accumulator reads FMS_DB_HOST/USER/PASS from the
# environment, and cron runs with a near-empty environment -- no shell profile,
# no exported vars. The bare crontab line in the handover would therefore have
# connected to nothing and logged a traceback twice a day, while looking
# scheduled. Every one of those nights would have lost segment speeds that the
# site deletes upstream and that cannot be backfilled.
#
# Credentials are read at runtime from the SSD .env and never written into the
# repo -- the mirror is public. Note the .env names the password FMS_DB_PWD,
# not FMS_DB_PASS, so it must be mapped. The .env is NOT sourced: FMS_DB_DRIVER
# holds an unquoted value with spaces ("ODBC Driver 17 for SQL Server"), which
# a shell would try to execute. Keys are extracted by name instead.
#
# A missing SSD or a dropped VPN exits 0, because both are routine here and
# must not look like a failure. But they are always LOGGED: a silent skip is
# indistinguishable from a successful run in a log file, and that ambiguity is
# exactly how a decaying archive goes unnoticed.
set -uo pipefail

REPO="/Users/lucky/wbn-fms-simulator"
ENVF="/Volumes/LUCKY_SSD/LV_APP/fms-dashboard/backend/.env"

stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }

cd "$REPO" || { echo "$(stamp) FATAL repo missing: $REPO"; exit 1; }

if [ ! -f "$ENVF" ]; then
  echo "$(stamp) SKIP credentials volume not mounted ($ENVF) - no append this run"
  exit 0
fi

# Read one key's value without echoing it. head -1 guards against a duplicated
# key later in the file silently winning.
val() { grep -E "^$1=" "$ENVF" | head -1 | cut -d= -f2- | tr -d '\r"'; }

export FMS_DB_HOST="$(val FMS_DB_HOST)"
export FMS_DB_USER="$(val FMS_DB_USER)"
export FMS_DB_PASS="$(val FMS_DB_PWD)"
DB_PORT="$(val FMS_DB_PORT)"; DB_PORT="${DB_PORT:-1433}"

if [ -z "$FMS_DB_HOST" ] || [ -z "$FMS_DB_USER" ] || [ -z "$FMS_DB_PASS" ]; then
  echo "$(stamp) SKIP credentials incomplete in .env - no append this run"
  exit 0
fi

# The site VPN drops every few minutes. Probe first so a down link costs 8s
# instead of hanging a cron job against a 1433 connect timeout.
if ! nc -z -G 8 "$FMS_DB_HOST" "$DB_PORT" >/dev/null 2>&1; then
  echo "$(stamp) SKIP ${FMS_DB_HOST}:${DB_PORT} unreachable (VPN down) - no append this run"
  exit 0
fi

echo "$(stamp) START accumulate_gps"
"$REPO/.venv/bin/python" scripts/accumulate_gps.py 2>&1 \
  | grep -vE "UserWarning: pandas only supports SQLAlchemy|new = pd.read_sql|frames.append\(pd.read_sql"
rc=${PIPESTATUS[0]}
echo "$(stamp) END accumulate_gps exit=$rc"
exit "$rc"
