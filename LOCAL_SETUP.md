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

That is not a failed install. To match the full planner you need a **private** copy of `data/saved_plans/`, `data/congestion_params.json`, `data/monthly_plans/`, and `data/*.pkl` — or a `.env` with `FMS_DB_*` / `WBN_*` on **this** PC (never commit `.env`).

## 5. Do not

- Do not `git add -A` — that can publish `.env`, GPS, and tonnages.
- Do not commit credentials or `geofences.json`.
- Do not expect ngrok / Rudolf’s Mac. That is a different machine. This file is local run only.

Flask uses `use_reloader=False`. After you edit `templates/simulator.html`, restart `serve.py`.
