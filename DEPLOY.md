# Deploying the WBN Production Simulator

Everything here is prepared and locally tested **except the tunnel itself**,
which needs an ngrok authtoken this machine does not have. Read the blocker
first — it is not a scripting problem.

---

## BLOCKER: the documented pull would DOWNGRADE the deployment

`README.md` → "Git deployment" says, on Rudolf's Mac:

```bash
cd /Users/rdinkelmann/simulator-standalone
git pull --ff-only origin main
```

**Do not run that.** `origin` (`github.com/rdinkelmann/...`) is deliberately
frozen at **`48985b4`** — the owner put it on hold and every commit since exists
**only on the mirror** (`github.com/Lucky0000123/...`). Pulling `origin` today
fetches nothing newer, and on a machine that somehow has later code it would be
a downgrade.

Measured against the live site on 2026-07-31:

| Probe | Result | Means |
|---|---|---|
| `/health` | 200, `sample-fixtures` | up, running without a database |
| `/api/model-info` | **200** | newer than the handover's "404 = stale" marker |
| `/api/simulator/corridor-geometry` | **404** | predates the corridor map |
| `congestion-model` → `loadedSpeed` | **absent** | predates the loaded/empty split |
| `/simulator` → `pa-sections-top` | **absent** | predates the entire Plan Assessment View |

So the public site is running a build older than four rounds of work. Fixing that
needs **one owner decision**, and it is not mine to take:

- **A — lift the hold.** Push to `origin`, and the documented pull works
  unchanged. Everything else here applies as written.
- **B — repoint the deployed checkout at the mirror.** On Rudolf's Mac:
  `git remote set-url origin https://github.com/Lucky0000123/wbn-fms-simulator.git`
  then pull as documented. Nothing is pushed to Rudolf's repo, but his working
  copy now tracks the mirror.

Until one of those happens, **no amount of correct deployment tooling will put
this code on the public URL.**

---

## Prerequisites

| Need | Check | If missing |
|---|---|---|
| Python 3.11+ venv | `.venv/bin/python -V` | `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` |
| Runtime deps | `.venv/bin/python -c "import flask, pandas"` | `pip install -r requirements.txt` |
| ngrok 3.x | `ngrok version` | `brew install ngrok` |
| **ngrok authtoken** | `ngrok config check` | `ngrok config add-authtoken <token>` — free account at ngrok.com |
| Trained artifacts | `ls data/route_lookup.csv` | `.venv/bin/python train_model.py` |

**Optional — live data.** With no `FMS_DB_*` the app serves fixtures and every
endpoint answers; this is a supported mode, not a degraded one. For live data:

```bash
export FMS_DB_HOST=... FMS_DB_USER=... FMS_DB_PASS=...   # never commit these
```

The site VPN must be up for those to resolve. With them set but the host
unreachable — the normal state, the link drops every few minutes — endpoints fall
back to fixtures and tag the response `servedFrom: "fixture"`, and the UI labels
cached figures rather than passing them off as live.

**No token is stored in this repo.** ngrok reads its authtoken from its own
config; `FMS_DB_*` come from the environment. The mirror is public.

---

## Deploy

```bash
cd /Users/lucky/wbn-fms-simulator      # or the deployed checkout
scripts/deploy.sh
```

It runs preflight (venv, ngrok, deps, credentials), starts `serve.py` on 5055,
starts an **ephemeral** tunnel, then verifies and prints the public URL.

### The public URL is opt-in, on purpose

A plain run takes an ephemeral URL. The site's real endpoint is a **reserved**
ngrok domain, and claiming it from another machine **takes the public endpoint
over**. Binding it therefore needs two explicit things:

```bash
NGROK_DOMAIN=wbn-fms-simulator.ngrok-free.app scripts/deploy.sh --reserved
```

Only do that on the machine that is meant to serve the site.

---

## Verify

```bash
scripts/deploy.sh --check
```

Checks four things, and the fourth is the one that matters:

1. local app answers on `:5055`
2. an https tunnel exists
3. the tunnel's `/health` is reachable
4. **the deployed build contains `pa-sections-top`** — i.e. it actually includes
   the Plan Assessment View

Check 4 exists because the failure that really happened here was invisible to
the first three: a site that is up, healthy, and serving a build four rounds old.
`/health` cannot tell you that. Manual equivalents:

```bash
curl https://<url>/health                              # 200 + dataMode
curl -o /dev/null -w '%{http_code}\n' https://<url>/api/simulator/corridor-geometry   # 200, not 404
curl -s https://<url>/simulator | grep -c pa-sections-top                             # >= 1
```

---

## Restart after an update

```bash
git pull --ff-only mirror main     # NOT origin -- see the blocker above
scripts/deploy.sh --stop
scripts/deploy.sh
scripts/deploy.sh --check
```

WARNING: Flask runs with `use_reloader=False`, so a template or static change
does **not** reach the browser until the process restarts. A stale template has
twice presented as a code bug during development.

WARNING: stale `serve.py` processes survive `pkill`. The script sleeps 3 s after
killing before probing; do the same by hand.

### launchd (the persistent setup on Rudolf's Mac)

Two agents, per README:

- `com.wbn.simulator` — keeps `serve.py` on 5055
- `com.wbn.simulator.ngrok` — keeps the tunnel up

```bash
launchctl kickstart -k gui/$(id -u)/com.wbn.simulator
launchctl kickstart -k gui/$(id -u)/com.wbn.simulator.ngrok
```

`scripts/deploy.sh` is for a manual or first-time bring-up and for `--check`; it
does not manage the launch agents. If they are running, the script sees the app
already up and leaves it alone.

---

## What was tested here, and what was not

| | |
|---|---|
| preflight detection (venv, ngrok, deps, credentials) | **tested** |
| app start + `/health` wait + already-running detection | **tested** |
| `--check` against a live app with no tunnel | **tested**, correctly fails on the tunnel |
| `--stop` | **tested**, app and tunnel both down |
| tunnel bring-up | **NOT tested** — this machine's ngrok is unauthenticated (`ERR_NGROK_4018`). The script detects it and prints the fix. |
| reserved-domain bind | **NOT tested**, deliberately — it would take over the public endpoint |
| deploying to Rudolf's Mac | **not attempted** — blocked above |

The untested paths are the two that cannot be exercised without either a
credential I must not commit or an action that would hijack a live site.
