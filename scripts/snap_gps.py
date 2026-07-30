"""snap_gps.py — Steps 5 and 6: put GPS fixes on the road, then on the trip.

STEP 5, SNAPPING
HAUL_ROAD_STA holds 3,122 chainage markers every 25 m, each with a road code
(DIRECTION), a SectionKM and a WKT POINT Z. Snapping is nearest-marker by great
circle distance: for each GPS fix, find the closest marker and inherit its road
and kilometre.

Nearest-neighbour rather than interpolation along the polyline, deliberately.
Markers are 25 m apart, so nearest-marker error is bounded by ~12.5 m of
chainage, which is far below the 1 km segments the speeds are reported over.
Interpolating between markers would add complexity and no accuracy at this
resolution.

A fix that is far from every marker is OFF the mapped haul road (in a pit, a
workshop, a stockpile). Those are labelled rather than snapped, because forcing
them onto the nearest road would invent travel that never happened. The cutoff
is 150 m, wide enough for a two-lane road plus GPS scatter.

STEP 6, MATCHING TO TRIPS
A trip is bounded by its two weigh events. The GPS fixes with timestamps inside
that window ARE the trip, so no fuzzy matching is needed: the truck identity is
exact and the interval is measured.

Segment speed comes from consecutive fixes within one 1 km segment:
distance / elapsed. Direction is signed by whether chainage is rising or
falling, which separates the loaded and empty legs.

WHAT THIS CANNOT DO ON DAY X
24 trucks and 159 trips is enough to prove the mechanism, not to publish
operational speeds. Every output carries its n so nobody mistakes a 3-trip
segment mean for a fact.

READ ONLY apart from writing its own CSVs.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pymssql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import simulator_api as sim                                  # noqa: E402

DATA = os.path.join(ROOT, "data")
REPORTS = os.path.join(ROOT, "reports")

# A GPS fix further than this from any chainage marker is treated as off-road.
OFF_ROAD_M = 150.0
# Speeds above this are GPS error, not haul trucks.
MAX_PLAUSIBLE_KMH = 70.0
# A segment traverse needs at least this much elapsed time to give a stable
# speed; shorter intervals divide a small distance by a smaller time.
MIN_SEG_SECONDS = 20.0
EARTH_R = 6371000.0


def conn(db):
    return pymssql.connect(server=sim._DB["server"], user=sim._DB["user"],
                           password=sim._DB["password"], database=db,
                           login_timeout=10, timeout=1800, charset="LATIN1")


def haversine_m(lat1, lon1, lat2, lon2):
    p = np.pi / 180.0
    a = (np.sin((lat2 - lat1) * p / 2) ** 2
         + np.cos(lat1 * p) * np.cos(lat2 * p) * np.sin((lon2 - lon1) * p / 2) ** 2)
    return 2 * EARTH_R * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def load_chainage(w) -> pd.DataFrame:
    d = pd.read_sql("""
        SELECT NAME, DIRECTION, SectionKM, wkt
        FROM HAUL_ROAD_STA WHERE wkt IS NOT NULL AND SectionKM IS NOT NULL""", w)
    # WKT is 'POINT Z (lng lat z)'.
    xy = d["wkt"].str.extract(
        r"POINT Z?\s*\(\s*([-\d.]+)\s+([-\d.]+)")
    d["lng"] = pd.to_numeric(xy[0], errors="coerce")
    d["lat"] = pd.to_numeric(xy[1], errors="coerce")
    d = d.dropna(subset=["lat", "lng"]).reset_index(drop=True)
    d["road"] = d["DIRECTION"].astype(str).str.strip().str.upper()
    d["km"] = pd.to_numeric(d["SectionKM"], errors="coerce")
    print("chainage markers: %d across %d roads (%s)"
          % (len(d), d.road.nunique(), ", ".join(sorted(d.road.unique()))))
    return d[["road", "km", "lat", "lng"]]


def snap(gps: pd.DataFrame, ch: pd.DataFrame) -> pd.DataFrame:
    """Nearest chainage marker per GPS fix, vectorised in blocks."""
    clat = ch["lat"].values
    clng = ch["lng"].values
    out_km, out_road, out_dist = [], [], []
    BLOCK = 2000
    for i in range(0, len(gps), BLOCK):
        g = gps.iloc[i:i + BLOCK]
        d = haversine_m(g["LAT"].values[:, None], g["LNG"].values[:, None],
                        clat[None, :], clng[None, :])
        j = np.argmin(d, axis=1)
        out_km.append(ch["km"].values[j])
        out_road.append(ch["road"].values[j])
        out_dist.append(d[np.arange(len(g)), j])
    gps = gps.copy()
    gps["km_value"] = np.concatenate(out_km)
    gps["road"] = np.concatenate(out_road)
    gps["snap_dist_m"] = np.concatenate(out_dist)
    gps["on_road"] = (gps["snap_dist_m"] <= OFF_ROAD_M).astype(int)
    # 1 km bucket, named the same way FMS_CONGESTION_SEG names its segments.
    lo = np.floor(gps["km_value"]).astype(int)
    gps["section_name"] = gps["road"] + " KM" + lo.astype(str) + "-" + (lo + 1).astype(str)
    gps.loc[gps["on_road"] == 0, "section_name"] = None
    return gps


def segment_speeds(gps: pd.DataFrame, trips: pd.DataFrame) -> pd.DataFrame:
    """Per trip, per segment: speed from consecutive on-road fixes."""
    rows = []
    trips = trips.dropna(subset=["FIRST_WB_TIME", "SECOND_WB_TIME"]).copy()
    trips["t0"] = pd.to_datetime(trips["FIRST_WB_TIME"], utc=True)
    trips["t1"] = pd.to_datetime(trips["SECOND_WB_TIME"], utc=True)
    by_truck = {k: g for k, g in gps.groupby("truck")}

    for t in trips.itertuples():
        g = by_truck.get(t.truck)
        if g is None:
            continue
        m = g[(g["ts"] >= t.t0) & (g["ts"] <= t.t1) & (g["on_road"] == 1)]
        if len(m) < 3:
            continue
        m = m.sort_values("ts")
        lat = m["LAT"].values; lng = m["LNG"].values
        ts = m["ts"].values.astype("datetime64[s]").astype(np.int64)
        km = m["km_value"].values
        seg = m["section_name"].values
        step_m = haversine_m(lat[:-1], lng[:-1], lat[1:], lng[1:])
        step_s = np.diff(ts).astype(float)
        dkm = np.diff(km)
        # Aggregate consecutive steps by the segment they started in.
        df = pd.DataFrame({"seg": seg[:-1], "m": step_m, "s": step_s, "dkm": dkm})
        df = df[(df["s"] > 0) & df["seg"].notna()]
        if df.empty:
            continue
        a = df.groupby("seg").agg(dist_m=("m", "sum"), secs=("s", "sum"),
                                  dkm=("dkm", "sum"), n=("m", "size")).reset_index()
        a = a[a["secs"] >= MIN_SEG_SECONDS]
        if a.empty:
            continue
        a["avg_speed_kmh"] = (a["dist_m"] / 1000.0) / (a["secs"] / 3600.0)
        a = a[a["avg_speed_kmh"] <= MAX_PLAUSIBLE_KMH]
        # Chainage falling = heading toward the coast and the dump = loaded.
        a["direction"] = np.where(a["dkm"] < 0, "loaded", "empty")
        a["trip_id"] = t.trip_id
        a["truck_id"] = t.truck
        a["route"] = "%s>%s" % (t.ORIGIN_AREA, t.DESTINATION_AREA)
        rows.append(a)
    return (pd.concat(rows, ignore_index=True) if rows
            else pd.DataFrame(columns=["seg", "avg_speed_kmh", "direction"]))


def dwell_from_gps(gps: pd.DataFrame, trips: pd.DataFrame) -> pd.DataFrame:
    """Stationary time at each end of the trip, from the GPS itself.

    Defined as contiguous runs where the truck moves under 2 km/h. The longest
    such run before the trip's midpoint is taken as loading, the longest after
    it as dumping. This is an inference from movement, not a geofence event, and
    is labelled that way.
    """
    rows = []
    trips = trips.dropna(subset=["FIRST_WB_TIME", "SECOND_WB_TIME"]).copy()
    trips["t0"] = pd.to_datetime(trips["FIRST_WB_TIME"], utc=True)
    trips["t1"] = pd.to_datetime(trips["SECOND_WB_TIME"], utc=True)
    by_truck = {k: g for k, g in gps.groupby("truck")}
    for t in trips.itertuples():
        g = by_truck.get(t.truck)
        if g is None:
            continue
        m = g[(g["ts"] >= t.t0) & (g["ts"] <= t.t1)].sort_values("ts")
        if len(m) < 5:
            continue
        sp = pd.to_numeric(m["SPEED"], errors="coerce").fillna(0).values
        ts = m["ts"].values.astype("datetime64[s]").astype(np.int64)
        stopped = sp < 2.0
        mid = ts[0] + (ts[-1] - ts[0]) / 2
        runs, i = [], 0
        while i < len(stopped):
            if not stopped[i]:
                i += 1
                continue
            j = i
            while j + 1 < len(stopped) and stopped[j + 1]:
                j += 1
            runs.append((ts[i], ts[j], (ts[j] - ts[i]) / 60.0))
            i = j + 1
        pre = [r for r in runs if r[1] <= mid]
        post = [r for r in runs if r[0] > mid]
        rows.append({
            "trip_id": t.trip_id, "truck_id": t.truck,
            "route": "%s>%s" % (t.ORIGIN_AREA, t.DESTINATION_AREA),
            "source": t.ORIGIN_AREA, "destination": t.DESTINATION_AREA,
            "dwell_loading_min": round(max([r[2] for r in pre], default=0.0), 2),
            "dwell_dumping_min": round(max([r[2] for r in post], default=0.0), 2),
            "cycle_min": round(float(t.cycle_min), 2),
            "gps_fixes_in_trip": int(len(m)),
            "method": "longest sub-2km/h GPS run before/after trip midpoint",
        })
    return pd.DataFrame(rows)


def main():
    print("=== STEP 5+6: snap GPS to chainage, then to trips ===")
    gps = pd.read_csv(os.path.join(DATA, "day_x_gps.csv"))
    trips = pd.read_csv(os.path.join(DATA, "day_x_trips.csv"))
    if gps.empty or trips.empty:
        print("no data; run extract_day.py first")
        return
    gps["ts"] = pd.to_datetime(gps["ts"], utc=True)

    w = conn("WBN_DATABASE")
    try:
        ch = load_chainage(w)
    finally:
        w.close()

    gps = snap(gps, ch)
    on = gps["on_road"].mean()
    print("\nsnapped %s fixes; %.1f%% within %.0f m of a chainage marker"
          % ("{:,}".format(len(gps)), 100 * on, OFF_ROAD_M))
    print("median snap distance: %.1f m" % gps["snap_dist_m"].median())
    print("\nfixes by road:")
    print(gps[gps.on_road == 1].road.value_counts().to_string())
    print("\nkm range covered per road:")
    print(gps[gps.on_road == 1].groupby("road").km_value
            .agg(["min", "max", "size"]).round(2).to_string())
    gps.to_csv(os.path.join(DATA, "day_x_gps_snapped.csv"), index=False)

    seg = segment_speeds(gps, trips)
    print("\n=== segment speeds ===")
    if seg.empty:
        print("none derived")
    else:
        print("%d trip-segment observations across %d trips, %d segments"
              % (len(seg), seg.trip_id.nunique(), seg.seg.nunique()))
        piv = (seg.groupby(["seg", "direction"])
                  .agg(speed=("avg_speed_kmh", "mean"), n=("avg_speed_kmh", "size"),
                       trucks=("truck_id", "nunique")).reset_index())
        print(piv.sort_values("n", ascending=False).head(24).round(1).to_string(index=False))
        seg.to_csv(os.path.join(DATA, "day_x_segment_speeds.csv"), index=False)

    dw = dwell_from_gps(gps, trips)
    print("\n=== dwell from GPS movement ===")
    if dw.empty:
        print("none derived")
    else:
        print("%d trips with dwell" % len(dw))
        print(dw.groupby("source").agg(
            n=("trip_id", "size"), load=("dwell_loading_min", "median"),
            dump=("dwell_dumping_min", "median"),
            cycle=("cycle_min", "median")).round(1).to_string())
        dw.to_csv(os.path.join(DATA, "day_x_trip_gps_features.csv"), index=False)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "gps_fixes": int(len(gps)),
        "on_road_pct": round(100 * float(on), 1),
        "median_snap_dist_m": round(float(gps["snap_dist_m"].median()), 1),
        "snap_method": ("nearest HAUL_ROAD_STA marker by great-circle distance; "
                        "markers are 25 m apart so chainage error is bounded at "
                        "~12.5 m; fixes beyond %.0f m are labelled off-road, not "
                        "snapped" % OFF_ROAD_M),
        "segment_observations": int(len(seg)),
        "segments_covered": int(seg.seg.nunique()) if len(seg) else 0,
        "trips_with_segment_speeds": int(seg.trip_id.nunique()) if len(seg) else 0,
        "trips_with_dwell": int(len(dw)),
    }
    with open(os.path.join(REPORTS, "day_x_gps_features.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)
    print("\nwrote day_x_gps_snapped.csv, day_x_segment_speeds.csv, "
          "day_x_trip_gps_features.csv")


if __name__ == "__main__":
    main()
