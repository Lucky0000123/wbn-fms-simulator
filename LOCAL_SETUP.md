# Run this app on another PC (local)

This is the starting point. Clone from GitHub, run it on that machine, open it in a browser. You do not need this laptop.

**Current code on both remotes:** `56eb880` (`main`).

| Remote | Clone this |
|---|---|
| Lucky (mirror) | `https://github.com/Lucky0000123/wbn-fms-simulator.git` |
| Rudolf (origin) | `https://github.com/rdinkelmann/wbn-fms-simulator.git` |

They are the same commit. Either URL is fine.

## 1. Clone and install

Needs **Python 3.11+**. No Node, no npm, no database required.

```bash
git clone https://github.com/Lucky0000123/wbn-fms-simulator.git
cd wbn-fms-simulator

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install openpyxl          # Excel download on /monthly (not in requirements.txt yet)
```

Windows: use `py -3 -m venv .venv` then `.venv\Scripts\pip`.

## 2. Start it

```bash
.venv/bin/python serve.py
```

Open **http://127.0.0.1:5055/simulator**

You should see four tabs: Capability · Congestion · Plan · Monthly.

Check it is alive:

```bash
curl -s http://127.0.0.1:5055/health
# {"ok": true, "dataMode": "sample-fixtures", "prediction": true, ...}
```

`sample-fixtures` is correct on a fresh clone. That means it is running on committed sample data, not the mine database.

To let other machines on the same LAN open it:

```bash
SIMULATOR_HOST=0.0.0.0 .venv/bin/python serve.py
```

Then they use `http://<this-pc-ip>:5055/simulator`. Default bind is `127.0.0.1` (this PC only).

## 3. Where things live (so you know where to look)

| What | Where |
|---|---|
| Page | `templates/simulator.html` |
| Plan UI | `static/js/plan.js` and `static/js/plan_*.js` |
| Congestion UI | `static/js/congestion_charts.js` |
| Styles | `static/css/style.css` |
| Model / simulator APIs | `simulator_api.py` |
| Monthly / Excel | `monthly_api.py` + `/monthly` |
| Sample data (no DB) | `fixtures/` |
| Server | `serve.py` (port **5055**) |
| Owner planning rules | `planning_rules.md` |

`main.js` must stay last in the script list in `simulator.html`.

## 4. What git does **not** contain (on purpose)

Both GitHub remotes are **public**. Live plans, models, and passwords stay off git.

A clone will boot, but it will **not** look like the planner laptop:

| On the planner laptop | On your clone |
|---|---|
| Saved daily plans (Sep–Dec S3/S4/…) | empty Plan / empty year board |
| Congestion calibration + `.pkl` models | fixtures / reference curves |
| `.env` + live FMS / WBN databases | no database |

That is not a failed install. Git never contains the plans.

## 6. Connect saved plans (copy files, then Load in the UI)

There is no database table and no extra config key. The app reads JSON files from:

```
data/saved_plans/YYYY-MM-DD.json
```

On a clone that folder is empty (or missing). `/api/plan/saved/list` then returns no dates, so the Plan tab **Saved…** picker says `(0)`.

**Step A — copy the files onto this PC** (from the machine that already has plans). Do this while `serve.py` is stopped, or restart it after the copy.

```bash
mkdir -p data/saved_plans
# From a USB stick, AirDrop, scp, etc. Example:
scp user@planner-laptop:/path/to/wbn-fms-simulator/data/saved_plans/*.json data/saved_plans/
```

Only `YYYY-MM-DD.json` files count (name length 15). Backup folders inside `data/saved_plans/` are ignored.

**Step B — confirm the server can see them**

```bash
curl -s http://127.0.0.1:5055/api/plan/saved/list
# {"ok": true, "dates": ["2026-12-09", "2026-12-08", ...]}
```

If `dates` is still `[]`, the files are not in this checkout’s `data/saved_plans/`, or you are looking at a different `serve.py`.

**Step C — load in the Plan tab**

1. Open `/simulator` → **Plan**.
2. Use the **Saved…** dropdown (top right of the sticky bar) and pick a date — that sets the plan date and loads the file.
3. Or type the date in **Plan date** and click **Load saved**.

Day number is the scenario convention: **01 = S1**, **03 = S3**, **04 = S4** (day 02 is reserved; do not save there). Example: `2026-09-03.json` is September S3.

Do **not** `git add data/saved_plans/`. Those files carry real allocations and tonnages; both remotes are public.

For numbers to match the planner laptop, also copy (privately) `data/congestion_params.json`, `data/monthly_plans/`, and `data/*.pkl`. Paths and DT will load from the JSON alone; pricing may differ until those artifacts are present.

## 5. Do not

- Do not `git add -A` — that can publish `.env`, GPS, and tonnages.
- Do not commit credentials or `geofences.json`.
- Do not expect ngrok / Rudolf’s Mac. That is a different machine. This file is local run only.

Flask uses `use_reloader=False`. After you edit `templates/simulator.html`, restart `serve.py`.
