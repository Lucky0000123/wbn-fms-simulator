#!/usr/bin/env python3
"""Wait for the VPN to 10.211.10.1 to come back, then run phase 5 and fold the
results into the report automatically.

The VPN and the LUCKY_SSD credential volume both flap (see HANDOVER.md), so the
decisive join test cannot be run on demand. This polls until the DB answers,
runs fuel_recon5, then appends a results block to the report. Safe to leave
running in the background; safe to run twice.

    ./.venv/bin/python scripts/fuel_recon5_when_up.py [--max-hours 24]
"""
import argparse
import datetime
import pathlib
import socket
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
HOST, PORT = "10.211.10.1", 1433
OUTJSON = ROOT / "data" / "fuel_recon" / "phase5_join_test.json"


def up(timeout=8):
    try:
        with socket.create_connection((HOST, PORT), timeout):
            return True
    except OSError:
        return False


def log(m):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {m}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-hours", type=float, default=24.0)
    ap.add_argument("--interval", type=int, default=120)
    a = ap.parse_args()

    deadline = time.time() + a.max_hours * 3600
    n = 0
    while time.time() < deadline:
        if up():
            log("VPN up — running phase 5")
            r = subprocess.run(
                [sys.executable, str(HERE / "fuel_recon5.py")],
                cwd=ROOT, capture_output=True, text=True)
            sys.stdout.write(r.stdout)
            sys.stderr.write(r.stderr)
            if r.returncode == 0 and OUTJSON.exists():
                log("phase 5 done — folding into report")
                r2 = subprocess.run(
                    [sys.executable, str(HERE / "fuel_report5.py")],
                    cwd=ROOT, capture_output=True, text=True)
                sys.stdout.write(r2.stdout)
                sys.stderr.write(r2.stderr)
                log("COMPLETE")
                return 0
            log(f"phase 5 failed (rc={r.returncode}) — VPN likely flapped, retrying")
        n += 1
        if n % 10 == 1:
            log(f"still down (attempt {n}), polling every {a.interval}s")
        time.sleep(a.interval)
    log(f"gave up after {a.max_hours}h")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
