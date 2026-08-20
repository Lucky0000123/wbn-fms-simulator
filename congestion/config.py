"""Per-route parameters for the hybrid congestion model.

Loaded from data/congestion_params.json (written by
scripts/calibrate_congestion.py from WBN_DATABASE); safe defaults otherwise.
"""
from __future__ import annotations

import json
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARAMS_PATH = os.path.join(_ROOT, "data", "congestion_params.json")

DEFAULTS = {
    "alpha": 0.15,
    "beta": 4.0,
    "load_min": 5.0,          # loader service time per truck
    "spot_min": 1.0,
    "dump_min": 2.0,
    "rr_pct": 2.0,            # rolling resistance, maintained road
    "n_loaders": 2,           # per-route default; UI should supply the real one
    "safe_headway_s": 60.0,
    "n_lanes": 1,
    "k_bunch": 0.03,
    "shifts_per_day": 2,
    "hours_per_shift": 12.0,
}

_cache = {"at": 0.0, "data": None}


def load_params() -> dict:
    import time
    if _cache["data"] is not None and time.time() - _cache["at"] < 60:
        return _cache["data"]
    data = {}
    if os.path.isfile(PARAMS_PATH):
        try:
            with open(PARAMS_PATH, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            data = {}
    _cache["data"] = data
    _cache["at"] = time.time()
    return data


def route_params(route: str) -> dict:
    """DEFAULTS overlaid with global then per-route calibrated values."""
    data = load_params()
    p = dict(DEFAULTS)
    p.update({k: v for k, v in (data.get("global") or {}).items()
              if not isinstance(v, dict)})
    rp = (data.get("routes") or {}).get(route) or {}
    p.update({k: v for k, v in rp.items() if v is not None})
    p["calibrated"] = bool(rp)
    return p
