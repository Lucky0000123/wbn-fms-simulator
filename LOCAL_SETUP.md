# Run this app on another PC (local)

This is the starting point. Clone from GitHub, run it on that machine, open it in a browser. You do not need this laptop.

**Pull latest `main`.** After this work, `git grep WBN_FMS_SIMULATOR_SAVED_PLANS` must find the SQL table. If it does not, you have an old clone.

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

## 5. Connect saved plans

The Plan object is unchanged (same JSON, same Save / Load / Allocate). Two ways to get that JSON onto another PC:

### A — SQL Server (shared; this is the intended path)

Separate table in **WBN_DATABASE** only — not haulage, GPS, or weighbridge:

`dbo.WBN_FMS_SIMULATOR_SAVED_PLANS`

One row per date. `plan_json` is the exact saved-plan object (`paths`, allocation, rain, …). The app creates the table on first use.

**On the planner laptop** (has `data/saved_plans/*.json` and `.env`):

```bash
.venv/bin/python scripts/upload_saved_plans.py
.venv/bin/python scripts/upload_saved_plans.py --check
```

After that, **Save plan** in the UI also writes SQL when `FMS_DB_*` is set. Disk is still always written.

**On the other PC:** put the same `.env` next to `serve.py` (never commit it), start the app, open Plan → **Saved…**. GET reads SQL when the local file is missing or older, then caches a JSON file so Load still works if the VPN drops.

```bash
curl -s http://127.0.0.1:5055/api/plan/saved/list
# dates from SQL + any local files
```

Optional hand DDL: `scripts/sql/WBN_FMS_SIMULATOR_SAVED_PLANS.sql`

### B — copy JSON files (no database)

```bash
mkdir -p data/saved_plans
scp user@planner-laptop:/path/to/wbn-fms-simulator/data/saved_plans/*.json data/saved_plans/
```

Restart `serve.py`. Only `YYYY-MM-DD.json` counts (name length 15).

**Load in the UI** (same for A or B)

1. `/simulator` → **Plan**.
2. **Saved…** dropdown, or set **Plan date** and **Load saved**.

Day number: **01 = S1**, **03 = S3**, **04 = S4**. Example: `2026-09-03` is September S3.

Do **not** `git add data/saved_plans/`.

For numbers to match the planner laptop, also copy (privately) `data/congestion_params.json`, `data/monthly_plans/`, and `data/*.pkl`.

## 6. Do not

- Do not `git add -A` — that can publish `.env`, GPS, and tonnages.
- Do not commit credentials or `geofences.json`.
- Do not expect ngrok / Rudolf’s Mac. That is a different machine. This file is local run only.

Flask uses `use_reloader=False`. After you edit `templates/simulator.html`, restart `serve.py`.
