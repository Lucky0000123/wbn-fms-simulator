# WBN FMS — Simulator

Standalone FMS Haul-Road Simulator. It runs with sample fixtures when the FMS database is unavailable,
so the public simulator does not go down with the database.

## Public simulator

**https://wbn-fms-simulator.ngrok-free.app/simulator**

Health check: **https://wbn-fms-simulator.ngrok-free.app/health**

## Run locally

```bash
pip install flask
python serve.py
```

Open **http://127.0.0.1:5055/simulator**

Keep that terminal running while you work; use a second terminal for git.

It runs on **sample data** out of the box—no setup or database required.

## Publish with ngrok

The public endpoint forwards to the local simulator on port `5055`:

```bash
ngrok http 5055 --url=https://wbn-fms-simulator.ngrok-free.app
```

The Mac deployment uses two launch agents:

- `com.wbn.simulator` — keeps `serve.py` running on port 5055.
- `com.wbn.simulator.ngrok` — keeps the public ngrok endpoint connected.

Useful checks:

```bash
curl -I http://127.0.0.1:5055/simulator
curl https://wbn-fms-simulator.ngrok-free.app/health
```

## Git deployment

```bash
cd /Users/rdinkelmann/simulator-standalone
git pull --ff-only origin main
git status
git add serve.py simulator_api.py templates fixtures README.md requirements.txt
git commit -m "Describe the simulator change"
git push origin main
launchctl kickstart -k gui/$(id -u)/com.wbn.simulator
```

Only commit the files changed for the simulator task. The launch agents and ngrok credentials remain
local to the Mac and are not stored in Git.

## Files

| File | Edit this for… |
|---|---|
| `templates/simulator.html` | the page — layout, charts, styling, interactions |
| `simulator_api.py` | the calculations behind the data |

Commit and push your changes when done.
