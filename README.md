# WBN FMS — Simulator (standalone dev)

Front-end development harness for the FMS **Haul-Road Simulator** page. Everything you need to work on
`templates/simulator.html` — UI, JS, SVG charts, styling — is here. **No backend, no database, no
credentials.**

## Run it

```bash
pip install flask
python serve.py
```

Then open **http://127.0.0.1:5055/simulator**

## What's here

| File | What it is |
|---|---|
| `templates/simulator.html` | **The only file you edit** — the whole simulator page (HTML + inline JS + inline SVG). |
| `serve.py` | Tiny Flask dev server: serves the page and returns the sample API responses below. |
| `fixtures/*.json` | Real captured responses for each API the page calls. |

## How it works

`simulator.html` fetches these endpoints; `serve.py` answers each with the matching fixture:

- `/api/simulator/capability` — the main historical dataset (scatter / scenario planner)
- `/api/simulator/path-response` — per-path efficiency + rain model
- `/api/simulator/shift-context` — selected-shift rainfall + weighbridge + IWIP traffic
- `/api/simulator/weighbridge`, `/api/simulator/weighbridge-positions`, `/api/weighbridge-summary`
- `/api/simulator/congestion-model`, `/api/simulator/trucks`, `/api/simulator/constraints`

## Limitations (it's a mock)

- The sample data is a **fixed snapshot** — selecting a different shift/date returns the same data.
- Edits you make don't persist server-side (the constraints POST just echoes the fixture).

This is intentional: it's for **UI/UX and logic work on the page**, not for running the real model.

## Shipping your changes

When your edited `simulator.html` is ready, it gets copied back into the main FMS app's
`templates/simulator.html` and deployed there. Just commit + push your changes to this repo and let
the FMS maintainer pull the file across.
