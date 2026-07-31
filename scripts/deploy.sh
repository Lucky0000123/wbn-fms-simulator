#!/usr/bin/env bash
# Start the simulator and expose it through ngrok, then PROVE it is reachable.
#
#   scripts/deploy.sh                 # ephemeral ngrok URL (safe anywhere)
#   scripts/deploy.sh --check         # verify a running deployment, start nothing
#   scripts/deploy.sh --stop          # stop what this script started
#   NGROK_DOMAIN=... scripts/deploy.sh --reserved
#
# WHY --reserved IS OPT-IN. The site's public URL is a RESERVED ngrok domain
# served from Rudolf's Mac. Claiming it from another machine takes the public
# endpoint over. So a plain run always gets an ephemeral URL, and binding the
# reserved domain requires both NGROK_DOMAIN and an explicit --reserved.
#
# NO TOKENS IN THIS FILE. ngrok reads its own authtoken from its config
# (`ngrok config add-authtoken ...`); FMS_DB_* come from the environment. The
# mirror is public.
#
# WARNING: this script does NOT pull. See DEPLOY.md -- the documented pull is
# from `origin`, which is currently frozen, so pulling it would DOWNGRADE a
# machine that already has newer code.
set -uo pipefail

cd "$(dirname "$0")/.." || exit 2
PORT="${SIMULATOR_PORT:-5055}"
PY=.venv/bin/python
LOG_APP=/tmp/wbn_simulator.log
LOG_NGROK=/tmp/wbn_ngrok.log
PID_APP=/tmp/wbn_simulator.pid
PID_NGROK=/tmp/wbn_ngrok.pid
NGROK_API=http://127.0.0.1:4040/api/tunnels

say()  { printf '  %s\n' "$*"; }
ok()   { printf '  \033[32mOK\033[0m   %s\n' "$*"; }
bad()  { printf '  \033[31mFAIL\033[0m %s\n' "$*"; }

tunnel_url() {
  curl -s --max-time 5 "$NGROK_API" 2>/dev/null \
    | "$PY" -c "import json,sys
try:
    t=[x for x in json.load(sys.stdin).get('tunnels',[]) if x.get('proto')=='https']
    print(t[0]['public_url'] if t else '')
except Exception: print('')" 2>/dev/null
}

stop_all() {
  for f in "$PID_NGROK" "$PID_APP"; do
    [ -f "$f" ] && { kill "$(cat "$f")" 2>/dev/null; rm -f "$f"; }
  done
  pkill -f "serve.py" 2>/dev/null
  pkill -f "ngrok http" 2>/dev/null
  say "stopped app and tunnel"
}

check_only() {
  local rc=0
  [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 8 "http://127.0.0.1:$PORT/health")" = "200" ] \
    && ok "local app on :$PORT" || { bad "local app not answering on :$PORT"; rc=1; }
  local url; url="$(tunnel_url)"
  if [ -n "$url" ]; then
    ok "tunnel: $url"
    [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$url/health")" = "200" ] \
      && ok "public /health reachable" || { bad "tunnel up but /health not reachable"; rc=1; }
    # A deployed build that predates the assessment view is the failure mode
    # that has actually happened here, and it is invisible from /health alone.
    if curl -s --max-time 20 "$url/simulator" | grep -q "pa-sections-top"; then
      ok "deployed build INCLUDES the plan assessment view"
    else
      bad "deployed build PREDATES the plan assessment view (stale checkout)"
      rc=1
    fi
  else
    bad "no https tunnel found on $NGROK_API"; rc=1
  fi
  return $rc
}

case "${1:-}" in
  --stop)  stop_all; exit 0 ;;
  --check) echo "== checking =="; check_only; exit $? ;;
esac

RESERVED=0
[ "${1:-}" = "--reserved" ] && RESERVED=1

echo "== preflight =="
[ -x "$PY" ] && ok "venv at $PY" || { bad "no venv -- python3 -m venv .venv && pip install -r requirements.txt"; exit 1; }
command -v ngrok >/dev/null && ok "ngrok $(ngrok version 2>/dev/null | head -1)" \
  || { bad "ngrok not installed -- brew install ngrok"; exit 1; }
"$PY" -c "import flask, pandas" 2>/dev/null && ok "runtime deps import" \
  || { bad "missing deps -- pip install -r requirements.txt"; exit 1; }

if [ -n "${FMS_DB_HOST:-}" ] && [ -n "${FMS_DB_USER:-}" ] && [ -n "${FMS_DB_PASS:-}" ]; then
  ok "FMS_DB_* set -- will serve live data if the host is reachable"
else
  say "FMS_DB_* not set -- fixtures mode. Every endpoint still answers; this is"
  say "supported, not a failure. Set them for live data."
fi

echo
echo "== starting app on :$PORT =="
if [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:$PORT/health")" = "200" ]; then
  say "already running -- leaving it alone"
else
  # Stale serve.py processes survive pkill, so wait before probing.
  pkill -f serve.py 2>/dev/null; sleep 3
  SIMULATOR_PORT="$PORT" nohup "$PY" serve.py > "$LOG_APP" 2>&1 &
  echo $! > "$PID_APP"
  for i in $(seq 1 20); do
    sleep 1
    [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "http://127.0.0.1:$PORT/health")" = "200" ] && break
  done
fi
[ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:$PORT/health")" = "200" ] \
  && ok "app up: $(curl -s --max-time 5 http://127.0.0.1:$PORT/health)" \
  || { bad "app did not come up -- see $LOG_APP"; tail -20 "$LOG_APP"; exit 1; }

echo
echo "== starting tunnel =="
if [ -n "$(tunnel_url)" ]; then
  say "a tunnel is already running -- leaving it alone"
else
  if [ "$RESERVED" = "1" ]; then
    [ -n "${NGROK_DOMAIN:-}" ] || { bad "--reserved needs NGROK_DOMAIN"; exit 1; }
    say "binding RESERVED domain $NGROK_DOMAIN -- this takes over the public endpoint"
    nohup ngrok http "$PORT" --domain "$NGROK_DOMAIN" --log stdout > "$LOG_NGROK" 2>&1 &
  else
    say "ephemeral URL (pass --reserved with NGROK_DOMAIN for the public one)"
    nohup ngrok http "$PORT" --log stdout > "$LOG_NGROK" 2>&1 &
  fi
  echo $! > "$PID_NGROK"
  for i in $(seq 1 20); do sleep 1; [ -n "$(tunnel_url)" ] && break; done
fi

URL="$(tunnel_url)"
if [ -z "$URL" ]; then
  bad "tunnel did not come up -- see $LOG_NGROK"
  grep -iE "err|authtoken|ERR_NGROK" "$LOG_NGROK" | head -5
  say "an unauthenticated ngrok needs: ngrok config add-authtoken <token>"
  exit 1
fi

echo
echo "== verifying =="
check_only
RC=$?

echo
echo "=================================================================="
printf '  PUBLIC URL: %s\n' "$URL"
echo "  app log   : $LOG_APP"
echo "  ngrok log : $LOG_NGROK"
echo "  stop with : scripts/deploy.sh --stop"
echo "=================================================================="
exit $RC
