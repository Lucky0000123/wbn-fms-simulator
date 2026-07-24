# WBN FMS — Simulator (standalone)

Everything needed to work on the FMS **Haul-Road Simulator** — the front-end **and** the model backend.
**No other platform code, no database credentials in the repo.**

## Run it

```bash
pip install flask
python serve.py
```

Open **http://127.0.0.1:5055/simulator**. Keep that terminal running; use a second one for git.

By default it serves **sample data** (fixtures) — perfect for front-end work. To run the **real model
against the database**, set env vars (creds from the FMS maintainer; you also need network access to the DB):

```bash
FMS_DB_HOST=... FMS_DB_USER=... FMS_DB_PASS=... python serve.py
```

## What's here

| File | What it is |
|---|---|
| `templates/simulator.html` | The whole simulator page — HTML + JS + SVG. Edit for anything **visual / interactive**. |
| `simulator_api.py` | The **model backend** — the real endpoint logic (trips/DT regression, weighbridge aggregation, rainfall + IWIP-traffic math). Edit for anything about **what the data means**. |
| `serve.py` | Small dev server: serves the page, registers `simulator_api`, and mocks the few data-loader endpoints. |
| `fixtures/*.json` | Real captured API responses — used when no DB is configured. |

## How the backend behaves

`simulator_api.py` holds the actual extracted endpoints. Each one:
- **No DB configured** → returns the matching sample fixture (so the page always works).
- **DB configured** (env vars) → runs the **real SQL + computation**; if a query fails it falls back to the fixture.

So you can edit the regression / aggregation / rain / IWIP logic and:
- see the page still render on sample data, or
- point it at the real DB to run your changes for real.

**Endpoints in `simulator_api.py` (editable):** `path-response`, `weighbridge`, `weighbridge-positions`,
`shift-context`, `weighbridge-summary`, `congestion-model`.
**Served from fixtures only** (data loaders, not model math): `capability`, `trucks`, `constraints`.

## Limitations

- With no DB, data is a **fixed snapshot** — selecting a different shift returns the same sample.
- `weighbridge-positions` also needs a `geofences.json` (not shipped) to snap bridges — it falls back to
  the fixture without it.

## Shipping changes back to the platform

Commit + push here. When ready, the FMS maintainer copies your updated `simulator.html` and/or the
changed logic from `simulator_api.py` back into the main app and deploys. One-file/section handoff.
