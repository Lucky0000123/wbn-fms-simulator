"""dem_grade.py — road grade from SURVEYED coordinates, or nothing.

STATUS: the feature does NOT currently ship, and this file exists to record why
and to switch it on the moment the data supports it.

The brief supplied five hardcoded lat/lon pairs for TF, KR, POS10, POS12 and
FENI. Those coordinates are invented — they do not appear anywhere in this
repository or the database, and shipping a grade computed from them would
produce a physically-styled feature made of guesses, which is worse than having
no feature at all because it looks credible.

WHAT REAL GEOMETRY EXISTS, measured
`FMS_GEOFENCES` (FMS_DB) holds 3,490 surveyed geofences with CENTER_LAT and
CENTER_LNG. That is genuine survey data and this module uses it. Two problems
stop it from producing a usable grade today:

  1. NODE COVERAGE 3/26 (11.5%). Only BLB, KR and TF match a geofence by name.
     The other 23 model nodes — CRUSHER, FENI KM0, POS 10, POS 12, HUAFEI and
     the rest — have no geofence under any normalisation, exact or substring.
     The 60% coverage rule in `trip_extraction.py` therefore drops the feature.

  2. NO ELEVATION ANYWHERE. `FMS_GEOFENCES.ELEVATIONS` exists as a column and is
     100% NULL across all 3,490 rows. So even for the three matched nodes there
     is no surveyed height, and grade is a height difference.

Deriving node positions from GPS instead does not rescue it either:
`FMS_PLAYBACK_TRACK_DATA` has 26.1M points but only 217 distinct trucks against
2,650 in the ticket data over the same window, and its `plateNumber` values
("SS074") do not share a format with ticket `TRUCK_ID` values ("N962"), so the
two cannot be joined without an identity map that does not exist yet.

HOW TO TURN THIS ON
Either populate `FMS_GEOFENCES.ELEVATIONS` from the survey, or supply a
`data/node_coordinates.json` of {"NODE": [lat, lon]} for the model's nodes. With
>= 60% of nodes covered, `attach_grade()` starts returning real values, elevation
comes from the OpenTopoData SRTM API (cached on disk), and the coverage gate in
`trip_extraction.py` lets the feature through automatically.
"""
from __future__ import annotations

import json
import os
import time

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
ELEV_CACHE = os.path.join(DATA, "elevation_cache.json")
NODE_COORDS = os.path.join(DATA, "node_coordinates.json")

# Public 90 m SRTM. No API key, and the cache means a node is fetched once ever.
TOPO_URL = "https://api.opentopodata.org/v1/srtm90m?locations=%s,%s"
REQUEST_PAUSE_S = 1.0          # the public endpoint asks for 1 call/second

# Deliberately empty. A hardcoded fallback here is exactly the invented-data
# failure this module exists to prevent.
FALLBACK_COORDS: dict[str, tuple[float, float]] = {}


def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:                                       # noqa: BLE001
        return default


def load_node_coordinates(conn=None) -> dict:
    """Surveyed node positions: local override first, then FMS_GEOFENCES.

    Returns {} rather than guesses when nothing is available, so callers can
    detect the absence instead of silently modelling fiction.
    """
    override = _load_json(NODE_COORDS, None)
    if override:
        return {k: tuple(v) for k, v in override.items()}

    try:
        import pandas as pd
        import simulator_api as sim
        from prediction_pipeline import canonical_area

        close = False
        if conn is None:
            if not sim._db_ready():
                return dict(FALLBACK_COORDS)
            conn, close = sim._conn("FMS_DB"), True
        try:
            g = pd.read_sql(
                "SELECT NAME, CENTER_LAT, CENTER_LNG FROM FMS_GEOFENCES "
                "WHERE CENTER_LAT IS NOT NULL AND CENTER_LNG IS NOT NULL", conn)
        finally:
            if close:
                conn.close()
        out = {}
        for _, r in g.iterrows():
            node = canonical_area(r["NAME"])
            if node and node not in out:
                out[node] = (float(r["CENTER_LAT"]), float(r["CENTER_LNG"]))
        return out
    except Exception:                                       # noqa: BLE001
        return dict(FALLBACK_COORDS)


def fetch_elevation(lat: float, lon: float) -> float | None:
    """SRTM elevation in metres, cached on disk. None on any failure."""
    cache = _load_json(ELEV_CACHE, {})
    key = "%.5f,%.5f" % (lat, lon)
    if key in cache:
        return cache[key]
    try:
        import requests
        r = requests.get(TOPO_URL % (lat, lon), timeout=20).json()
        elev = r["results"][0]["elevation"]
    except Exception:                                       # noqa: BLE001
        return None
    if elev is None:
        return None
    cache[key] = float(elev)
    os.makedirs(DATA, exist_ok=True)
    with open(ELEV_CACHE, "w", encoding="utf-8") as fh:
        json.dump(cache, fh)
    time.sleep(REQUEST_PAUSE_S)
    return float(elev)


def route_grade(source: str, destination: str, distance_km: float,
                coords: dict | None = None) -> dict:
    """Net grade percent over a haul. Returns None fields when unknown.

    Net grade is a crude summary: a route that climbs 200 m then drops 200 m
    reads as flat while costing a loaded truck real time. It is the honest limit
    of point-to-point elevation, and a proper answer needs the road polyline.
    """
    coords = load_node_coordinates() if coords is None else coords
    a, b = coords.get(source), coords.get(destination)
    if not a or not b or not distance_km or distance_km <= 0:
        return {"net_grade_pct": None, "elev_gain_m": None, "grade_known": False}
    ea, eb = fetch_elevation(*a), fetch_elevation(*b)
    if ea is None or eb is None:
        return {"net_grade_pct": None, "elev_gain_m": None, "grade_known": False}
    gain = eb - ea
    return {"net_grade_pct": round(100.0 * gain / (distance_km * 1000.0), 3),
            "elev_gain_m": round(gain, 1), "grade_known": True}


def attach_grade(df):
    """Add grade columns to a trip frame. Returns (frame, coverage_fraction).

    `trip_extraction.py` drops the feature when coverage is below 60%, so this
    never has to decide policy — it just reports what it could resolve.
    """
    import numpy as np

    coords = load_node_coordinates()
    nodes = set(df["source"]) | set(df["destination"])
    known = {n for n in nodes if n in coords}
    node_cov = len(known) / len(nodes) if nodes else 0.0
    if node_cov < 0.60:
        # Do not spend API calls resolving a feature that will be dropped.
        df["net_grade_pct"] = np.nan
        df["elev_gain_m"] = np.nan
        return df, 0.0

    cache = {}
    for s, d, km in df[["source", "destination", "distance_km"]].drop_duplicates().values:
        cache[(s, d)] = route_grade(s, d, km, coords)
    df["net_grade_pct"] = [cache.get((s, d), {}).get("net_grade_pct")
                           for s, d in zip(df["source"], df["destination"])]
    df["elev_gain_m"] = [cache.get((s, d), {}).get("elev_gain_m")
                         for s, d in zip(df["source"], df["destination"])]
    return df, float(df["net_grade_pct"].notna().mean())


def coverage_report(conn=None) -> dict:
    """What stops the grade feature shipping, as numbers."""
    coords = load_node_coordinates(conn)
    try:
        import pandas as pd
        t = pd.read_csv(os.path.join(DATA, "training_data.csv"))
        nodes = sorted(set(t["source"]) | set(t["destination"]))
    except Exception:                                       # noqa: BLE001
        nodes = []
    matched = [n for n in nodes if n in coords]
    return {
        "geofences_with_coords": len(coords),
        "model_nodes": len(nodes),
        "nodes_matched": len(matched),
        "node_coverage": round(len(matched) / len(nodes), 4) if nodes else 0.0,
        "matched_nodes": matched,
        "unmatched_nodes": [n for n in nodes if n not in coords],
        "elevation_source": "OpenTopoData SRTM 90m (cached)",
        "blocker": ("FMS_GEOFENCES.ELEVATIONS is 100% NULL and only a minority "
                    "of model nodes match a surveyed geofence by name"),
        "ships": len(matched) / len(nodes) >= 0.60 if nodes else False,
    }


if __name__ == "__main__":
    rep = coverage_report()
    print("geofences with coordinates: %s" % rep["geofences_with_coords"])
    print("model nodes matched: %s/%s (%.1f%%)"
          % (rep["nodes_matched"], rep["model_nodes"], 100 * rep["node_coverage"]))
    print("matched: %s" % ", ".join(rep["matched_nodes"]) or "(none)")
    print("feature ships: %s" % rep["ships"])
    if not rep["ships"]:
        print("blocker: %s" % rep["blocker"])
        print("unmatched: %s" % ", ".join(rep["unmatched_nodes"][:14]))
