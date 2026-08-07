#!/usr/bin/env bash
# Copy FMS credentials (and related secrets) from LUCKY_SSD into the local repo
# so cron / serve / scripts do not need the volume mounted.
#
# Destination is gitignored (.env). Never commit these files — the public mirror
# must not see passwords.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
SSD_ENV="/Volumes/LUCKY_SSD/LV_APP/fms-dashboard/backend/.env"
SSD_BACKEND="/Volumes/LUCKY_SSD/LV_APP/fms-dashboard/backend"
LOCAL_ENV="$REPO/.env"
LOCAL_SECRETS="$REPO/secrets"

stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }

if [ ! -d /Volumes/LUCKY_SSD ]; then
  echo "$(stamp) FAIL: /Volumes/LUCKY_SSD is not mounted."
  echo "  Plug in / unlock the drive until Finder shows LUCKY_SSD, then re-run:"
  echo "  $REPO/scripts/sync_creds_from_ssd.sh"
  exit 1
fi

if [ ! -f "$SSD_ENV" ]; then
  echo "$(stamp) FAIL: expected $SSD_ENV"
  echo "  Volume is up but the dashboard .env path is missing."
  exit 1
fi

mkdir -p "$LOCAL_SECRETS"
chmod 700 "$LOCAL_SECRETS" 2>/dev/null || true

# Primary: repo-root .env (preferred by accumulate_gps_cron + Python loaders)
cp -f "$SSD_ENV" "$LOCAL_ENV"
chmod 600 "$LOCAL_ENV"
# Keep a dated backup under secrets/ (still gitignored)
cp -f "$SSD_ENV" "$LOCAL_SECRETS/fms.env"
chmod 600 "$LOCAL_SECRETS/fms.env"
cp -f "$SSD_ENV" "$LOCAL_SECRETS/fms.env.$(date -u +%Y%m%dT%H%M%SZ)"

# Optional extras from the same backend folder (no secrets in names beyond .env)
for name in config.py .env.example; do
  if [ -f "$SSD_BACKEND/$name" ]; then
    cp -f "$SSD_BACKEND/$name" "$LOCAL_SECRETS/$name"
    echo "$(stamp) copied $name -> secrets/"
  fi
done

# Sanity: required keys present (values not printed)
need_ok=1
for k in FMS_DB_HOST FMS_DB_USER FMS_DB_PWD; do
  if ! grep -qE "^${k}=" "$LOCAL_ENV"; then
    echo "$(stamp) WARN: $k missing in copied .env"
    need_ok=0
  fi
done

echo "$(stamp) OK local credentials at $LOCAL_ENV (and secrets/fms.env)"
echo "$(stamp) Scripts now prefer this path over the SSD."
[ "$need_ok" = 1 ] || exit 2
exit 0
