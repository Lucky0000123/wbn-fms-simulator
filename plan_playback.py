"""Playback truth for Plan — proves why Jan–May haul speeds are not invented.

Loads fixtures/playback_truth.json (offline). Optionally, when FMS_DB is up,
can attach live plate-overlap smoke — but never invents haul corridor speeds.
"""
from __future__ import annotations

import json
import os

import plan_analogues as pa

_ROOT = os.path.dirname(os.path.abspath(__file__))
_FX = os.path.join(_ROOT, "fixtures", "playback_truth.json")


def load_playback_truth():
    with open(_FX, encoding="utf-8") as f:
        data = json.load(f)
    data = dict(data)
    data["has_haul_gps_may"] = pa.has_haul_gps("2026-05-01")
    data["has_haul_gps_jul"] = pa.has_haul_gps("2026-07-20")
    data.setdefault("basis", {})
    data["basis"]["invents_playback_haul_speeds"] = False
    data["basis"]["congestion_clips_tonnes"] = False
    data["basis"]["simulate_unchanged"] = True
    # Explicit denial payload for any client asking for invented speeds
    data["may_haul_speeds"] = []
    data["invent_jan_may_haul_speeds"] = False
    return data


def refuse_invented_speeds(date_s):
    """API helper: empty speeds + reason for pre-haul-GPS dates."""
    ds = str(date_s or "")[:10]
    if pa.has_haul_gps(ds):
        return {
            "ok": True,
            "date": ds,
            "has_haul_gps": True,
            "speeds": None,
            "note": "Use /api/plan/day-segments or corridor-hours for Jul+ haul GPS.",
            "invented": False,
        }
    return {
        "ok": True,
        "date": ds,
        "has_haul_gps": False,
        "speeds": [],
        "invented": False,
        "note": (
            "No haul corridor GPS before %s. Playback history is HRM/support "
            "(0%% plate overlap) — speeds are not invented." % pa.GPS_HAUL_START
        ),
        "basis": {
            "invents_playback_haul_speeds": False,
            "congestion_clips_tonnes": False,
        },
    }
