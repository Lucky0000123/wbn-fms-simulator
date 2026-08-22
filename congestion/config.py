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
    # Geometry capacity: c_road = n_lanes_loaded * 3600 / headway_s.
    # v in BPR is loaded-direction flow (one pass per cycle), so a two-way
    # road is n_lanes_loaded=1. Headway is a documented following gap, not a
    # dial for trips/DT. Long corridors (chainage >= long_haul_km) use 60 s
    # (585 m at 35 km/h). Short hauls use 15 s (62 m at 15 km/h).
    "n_lanes_loaded": 1,
    "n_lanes": 1,                 # alias of n_lanes_loaded (bpr helper)
    "headway_s": 60.0,            # long-corridor following gap
    "headway_s_short": 15.0,      # short-haul following gap
    "safe_headway_s": 60.0,       # predictor fallback if a route has no c_road
    "long_haul_km": 50.0,
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


def route_params(route: str, contractor: str | None = None) -> dict:
    """DEFAULTS overlaid with global, per-route, then per-contractor values.

    Per-contractor overrides live under rec["contractors"][NAME] — written
    by scripts/calibrate_congestion.py from MATCHED same-day history (owner,
    2026-08-21: contractors on one road need their own baselines). Missing
    contractor -> pooled route baseline, unchanged behaviour."""
    data = load_params()
    p = dict(DEFAULTS)
    p.update({k: v for k, v in (data.get("global") or {}).items()
              if not isinstance(v, dict)})
    rp = (data.get("routes") or {}).get(route) or {}
    p.update({k: v for k, v in rp.items()
              if v is not None and k != "contractors"})
    if contractor:
        cp = (rp.get("contractors") or {}).get(str(contractor).strip().upper()) or {}
        p.update({k: v for k, v in cp.items() if v is not None})
        p["contractor_calibrated"] = bool(cp)
    p["calibrated"] = bool(rp)
    return p
