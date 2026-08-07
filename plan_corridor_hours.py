"""Jul+ haul GPS hour-of-day profiles + per-day segment speeds for Plan Step 2.

Advisory only — never clips /api/simulate tonnes. Never invents pre-GPS-window
speeds (Playback / Jan–May). Reads gps_archive hourly CSV when present; tests
use fixtures/gps_archive_hourly_sample.csv.
"""
from __future__ import annotations

import csv
import os
import re
from collections import defaultdict
from datetime import datetime, timezone, timedelta

# FMS HOUR_TS is TRUE epoch ms (verified: under UTC labels the fleet's
# truck-count dips sit at 07/10 UTC and peaks at 23/11 UTC; shifted +9 h they
# align with the site's 07:00/19:00 shift changes — dips AT the change,
# peaks the hour after). Halmahera is WIT, UTC+9, no DST.
SITE_TZ = timezone(timedelta(hours=9))

import plan_analogues as pa

_ROOT = os.path.dirname(os.path.abspath(__file__))
_ARCHIVE = os.path.join(_ROOT, "data", "gps_archive", "congestion_seg_hourly.csv")
_FIXTURE = os.path.join(_ROOT, "fixtures", "gps_archive_hourly_sample.csv")

# Stick roads only (same vocabulary as simulator_api measuredSpeeds).
_STICK_ROADS = frozenset({"TF", "KR", "CRD", "TOFU", "KRENE"})
_ROAD_ALIAS = {"TOFU": "TF", "KRENE": "KR"}

_SEG_RE = re.compile(
    r"^(.+?)\s*KM\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$", re.I
)


def parse_seg_id(seg):
    """'TF KM54-55' → (road, lo, hi, mid_km) or None."""
    m = _SEG_RE.match(str(seg or "").strip())
    if not m:
        return None
    road = m.group(1).strip().upper()
    road = _ROAD_ALIAS.get(road, road)
    a, b = float(m.group(2)), float(m.group(3))
    lo, hi = min(a, b), max(a, b)
    return road, lo, hi, (lo + hi) / 2.0


def section_for_mid(mid_km):
    """Named corridor section for a stick mid-chainage."""
    for label, slo, shi in pa.SECTIONS:
        if mid_km > slo and mid_km <= shi:
            return label
    for label, slo, shi in pa.SECTIONS:
        if mid_km >= slo - 1e-6 and mid_km <= shi + 1e-6:
            return label
    return None


def resolve_hourly_path(path=None):
    """Prefer explicit path, then live archive, then committed fixture sample."""
    if path and os.path.isfile(path):
        return path, "explicit"
    if os.path.isfile(_ARCHIVE):
        return _ARCHIVE, "gps_archive"
    if os.path.isfile(_FIXTURE):
        return _FIXTURE, "fixture"
    return None, "missing"


def _iter_hourly_rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            yield row


def _row_day_hour(ts_ms):
    try:
        ts = int(float(ts_ms))
    except (TypeError, ValueError):
        return None, None
    if ts <= 0:
        return None, None
    # Convert true-epoch HOUR_TS to SITE wall clock (WIT, UTC+9) so that
    # "slow hour 19:00" means 19:00 on the haul road, not 19:00 UTC.
    dt = datetime.fromtimestamp(ts / 1000.0, tz=SITE_TZ)
    return dt.date().isoformat(), dt.hour


def _stick_seg(seg_id):
    parsed = parse_seg_id(seg_id)
    if not parsed:
        return None
    road, lo, hi, mid = parsed
    if road not in _STICK_ROADS and road not in ("TF", "KR", "CRD"):
        return None
    if road not in ("TF", "KR", "CRD"):
        return None
    sec = section_for_mid(mid)
    if not sec:
        return None
    return {"road": road, "lo": lo, "hi": hi, "mid": mid, "section": sec, "seg": str(seg_id).strip()}


def corridor_hours(sections=None, dir_filter="down", path=None, min_fix=5):
    """Aggregate 0–23 loaded (or empty) speeds across Jul+ stick segments.

    Returns advisory payload; never includes clips_tonnes / simulate fields.
    """
    csv_path, source = resolve_hourly_path(path)
    if not csv_path:
        return {
            "ok": False,
            "error": "no gps_archive hourly CSV and no fixture sample",
            "hours": [],
            "by_section": [],
            "slow_hours": [],
            "slow_sections": [],
            "window": None,
            "source": source,
            "basis": {"congestion_clips_tonnes": False, "era": "struggle"},
        }

    want_secs = None
    if sections:
        want_secs = {s.strip() for s in sections if str(s).strip()}

    d = (dir_filter or "down").strip().lower()
    if d not in ("down", "up", "both"):
        d = "down"

    # hour → sum_spd, fix_n, truck_n_sum, n_rows
    by_h = {h: {"sum_spd": 0.0, "fix_n": 0, "truck_n": 0.0, "n": 0} for h in range(24)}
    # section → hour → same
    by_sec_h = defaultdict(lambda: {h: {"sum_spd": 0.0, "fix_n": 0, "truck_n": 0.0, "n": 0}
                                    for h in range(24)})
    # section → sum for ranking
    by_sec = defaultdict(lambda: {"sum_spd": 0.0, "fix_n": 0, "truck_n": 0.0, "n": 0})
    days = set()
    t_lo = t_hi = None

    for row in _iter_hourly_rows(csv_path):
        stick = _stick_seg(row.get("SEG_ID") or row.get("seg"))
        if not stick:
            continue
        if want_secs and stick["section"] not in want_secs:
            continue
        direction = (row.get("DIR") or "").strip().lower()
        if d != "both" and direction != d:
            continue
        day, hour = _row_day_hour(row.get("HOUR_TS"))
        if day is None or hour is None:
            continue
        if not pa.has_haul_gps(day):
            continue
        try:
            sum_spd = float(row.get("SUM_SPD") or 0)
            fix_n = float(row.get("FIX_N") or 0)
            truck_n = float(row.get("TRUCK_N") or 0)
        except (TypeError, ValueError):
            continue
        if fix_n < min_fix or sum_spd <= 0:
            continue
        days.add(day)
        try:
            ts = int(float(row.get("HOUR_TS") or 0))
        except (TypeError, ValueError):
            ts = 0
        if ts > 0:
            if t_lo is None or ts < t_lo:
                t_lo = ts
            if t_hi is None or ts > t_hi:
                t_hi = ts
        bucket = by_h[hour]
        bucket["sum_spd"] += sum_spd
        bucket["fix_n"] += fix_n
        bucket["truck_n"] += truck_n
        bucket["n"] += 1
        sb = by_sec_h[stick["section"]][hour]
        sb["sum_spd"] += sum_spd
        sb["fix_n"] += fix_n
        sb["truck_n"] += truck_n
        sb["n"] += 1
        sec = by_sec[stick["section"]]
        sec["sum_spd"] += sum_spd
        sec["fix_n"] += fix_n
        sec["truck_n"] += truck_n
        sec["n"] += 1

    def _pack_hour(h, b):
        spd = (b["sum_spd"] / b["fix_n"]) if b["fix_n"] > 0 else None
        tavg = (b["truck_n"] / b["n"]) if b["n"] > 0 else None
        return {
            "h": h,
            "speed_kmh": round(spd, 2) if spd is not None else None,
            "truck_n": round(tavg, 2) if tavg is not None else None,
            "n": int(b["n"]),
            "fix_n": int(b["fix_n"]),
        }

    hours = [_pack_hour(h, by_h[h]) for h in range(24)]
    with_spd = [x for x in hours if x["speed_kmh"] is not None]
    slow_hours = sorted(with_spd, key=lambda x: (x["speed_kmh"], -x["truck_n"] or 0))[:3]

    by_section = []
    for label, _slo, _shi in pa.SECTIONS:
        if label not in by_sec_h and label not in by_sec:
            continue
        if want_secs and label not in want_secs:
            continue
        sec_hours = [_pack_hour(h, by_sec_h[label][h]) for h in range(24)]
        agg = by_sec[label]
        spd = (agg["sum_spd"] / agg["fix_n"]) if agg["fix_n"] > 0 else None
        by_section.append({
            "section": label,
            "speed_kmh": round(spd, 2) if spd is not None else None,
            "hours": sec_hours,
            "n": int(agg["n"]),
        })

    slow_sections = sorted(
        [s for s in by_section if s["speed_kmh"] is not None],
        key=lambda x: x["speed_kmh"],
    )[:4]

    w_from = min(days) if days else None
    w_to = max(days) if days else None
    if t_lo and t_hi:
        w_from = datetime.fromtimestamp(t_lo / 1000.0, tz=SITE_TZ).date().isoformat()
        w_to = datetime.fromtimestamp(t_hi / 1000.0, tz=SITE_TZ).date().isoformat()

    return {
        "ok": True,
        "window": {
            "from": w_from,
            "to": w_to,
            "era": "struggle",
            "gps_haul_start": pa.GPS_HAUL_START,
            "note": ("Jul+ measured haul GPS · struggle-season illustration. "
                     "Not peak Jan–May ops. Advisory only — does not change simulate tonnes."),
        },
        "dir": d,
        "hours": hours,
        "by_section": by_section,
        "slow_hours": [{"h": x["h"], "speed_kmh": x["speed_kmh"], "truck_n": x["truck_n"]}
                       for x in slow_hours],
        "slow_sections": [{"section": x["section"], "speed_kmh": x["speed_kmh"]}
                          for x in slow_sections],
        "source": source,
        "days_n": len(days),
        "basis": {
            "congestion_clips_tonnes": False,
            "era": "struggle",
            "simulate_unchanged": True,
        },
    }


def day_segments(date_s, path=None, min_fix=3):
    """Per-segment loaded/empty speeds for one calendar day in the GPS window."""
    date_s = str(date_s or "")[:10]
    if not date_s:
        return {"ok": False, "error": "supply date=YYYY-MM-DD", "has_gps": False,
                "segments": [], "basis": {"congestion_clips_tonnes": False}}
    if not pa.has_haul_gps(date_s):
        return {
            "ok": True,
            "date": date_s,
            "has_gps": False,
            "segments": [],
            "by_section": [],
            "note": ("No haul corridor GPS before %s — ops-only day; "
                     "speeds are not invented from Playback.") % pa.GPS_HAUL_START,
            "source": None,
            "basis": {"congestion_clips_tonnes": False, "simulate_unchanged": True},
        }

    csv_path, source = resolve_hourly_path(path)
    if not csv_path:
        return {
            "ok": False,
            "date": date_s,
            "has_gps": True,
            "error": "no gps_archive hourly CSV and no fixture sample",
            "segments": [],
            "basis": {"congestion_clips_tonnes": False},
        }

    # seg → dir → sum_spd, fix_n, peak trucks, hours
    agg = defaultdict(lambda: {
        "down": {"sum_spd": 0.0, "fix_n": 0, "peak": 0, "hours": 0},
        "up": {"sum_spd": 0.0, "fix_n": 0, "peak": 0, "hours": 0},
        "meta": None,
    })

    for row in _iter_hourly_rows(csv_path):
        stick = _stick_seg(row.get("SEG_ID") or row.get("seg"))
        if not stick:
            continue
        day, _hour = _row_day_hour(row.get("HOUR_TS"))
        if day != date_s:
            continue
        direction = (row.get("DIR") or "").strip().lower()
        if direction not in ("down", "up"):
            continue
        try:
            sum_spd = float(row.get("SUM_SPD") or 0)
            fix_n = float(row.get("FIX_N") or 0)
            truck_n = float(row.get("TRUCK_N") or 0)
        except (TypeError, ValueError):
            continue
        if fix_n < min_fix or sum_spd <= 0:
            continue
        key = stick["seg"]
        bucket = agg[key]
        bucket["meta"] = stick
        d = bucket[direction]
        d["sum_spd"] += sum_spd
        d["fix_n"] += fix_n
        d["hours"] += 1
        if truck_n > d["peak"]:
            d["peak"] = truck_n

    segments = []
    for seg, bucket in agg.items():
        meta = bucket["meta"]
        loaded = bucket["down"]
        empty = bucket["up"]
        lk = (loaded["sum_spd"] / loaded["fix_n"]) if loaded["fix_n"] > 0 else None
        ek = (empty["sum_spd"] / empty["fix_n"]) if empty["fix_n"] > 0 else None
        segments.append({
            "seg": seg,
            "section": meta["section"],
            "road": meta["road"],
            "fromKm": meta["hi"],
            "toKm": meta["lo"],
            "loadedKmh": round(lk, 2) if lk is not None else None,
            "emptyKmh": round(ek, 2) if ek is not None else None,
            "peak_trucks": int(max(loaded["peak"], empty["peak"])),
            "hours": int(loaded["hours"] + empty["hours"]),
        })
    segments.sort(key=lambda r: (-(r["fromKm"] or 0), r["seg"]))

    by_sec = defaultdict(lambda: {"sum_spd": 0.0, "fix_n": 0, "n": 0})
    for s in segments:
        if s["loadedKmh"] is None:
            continue
        # re-weight by hours as proxy weight
        w = max(1, s["hours"])
        by_sec[s["section"]]["sum_spd"] += s["loadedKmh"] * w
        by_sec[s["section"]]["fix_n"] += w
        by_sec[s["section"]]["n"] += 1
    by_section = []
    for label, _a, _b in pa.SECTIONS:
        b = by_sec.get(label)
        if not b or b["fix_n"] <= 0:
            continue
        by_section.append({
            "section": label,
            "loadedKmh": round(b["sum_spd"] / b["fix_n"], 2),
            "n": int(b["n"]),
        })

    return {
        "ok": True,
        "date": date_s,
        "has_gps": True,
        "segments": segments,
        "by_section": by_section,
        "note": ("Measured stick segments for %s (Jul+ haul GPS). "
                 "Advisory — does not change simulate tonnes.") % date_s,
        "source": source,
        "basis": {"congestion_clips_tonnes": False, "simulate_unchanged": True},
    }


def slow_sections_for_optimize(path=None, dir_filter="down"):
    """Thin helper for Optimize reason strings."""
    payload = corridor_hours(dir_filter=dir_filter, path=path)
    return payload.get("slow_sections") or []


def gps_coverage(path=None, stick_only=True):
    """Calendar of days with banked haul segment GPS (Jul+ window only)."""
    csv_path, source = resolve_hourly_path(path)
    if not csv_path:
        return {
            "ok": False,
            "error": "no gps_archive hourly CSV and no fixture sample",
            "days": [],
            "source": source,
            "gps_haul_start": pa.GPS_HAUL_START,
            "basis": {"congestion_clips_tonnes": False},
        }
    by_day = defaultdict(lambda: {"hours": set(), "segs": set(), "fix_n": 0})
    for row in _iter_hourly_rows(csv_path):
        if stick_only and not _stick_seg(row.get("SEG_ID") or row.get("seg")):
            continue
        day, hour = _row_day_hour(row.get("HOUR_TS"))
        if day is None or not pa.has_haul_gps(day):
            continue
        try:
            fix_n = float(row.get("FIX_N") or 0)
        except (TypeError, ValueError):
            fix_n = 0
        if fix_n <= 0:
            continue
        b = by_day[day]
        b["hours"].add(hour)
        b["segs"].add(str(row.get("SEG_ID") or "").strip())
        b["fix_n"] += fix_n
    days = [{
        "date": d,
        "hours_n": len(by_day[d]["hours"]),
        "segs_n": len(by_day[d]["segs"]),
        "fix_n": int(by_day[d]["fix_n"]),
        "has_gps": True,
    } for d in sorted(by_day)]
    return {
        "ok": True,
        "days": days,
        "from": days[0]["date"] if days else None,
        "to": days[-1]["date"] if days else None,
        "n": len(days),
        "source": source,
        "gps_haul_start": pa.GPS_HAUL_START,
        "note": ("Haul corridor GPS banked days (stick segments). "
                 "Before %s there is no haul GPS — not invented.") % pa.GPS_HAUL_START,
        "basis": {"congestion_clips_tonnes": False, "simulate_unchanged": True},
    }


def rebuild_by_dir_from_archive(path=None, out_path=None):
    """Roll hourly archive into congestion_seg_by_dir.csv for the stick.

    Offline — no VPN. Same grain as scripts/extract_direction_and_hrm.py.
    """
    csv_path, source = resolve_hourly_path(path)
    if not csv_path:
        return {"ok": False, "error": "no archive", "source": source, "rows": 0}
    out_path = out_path or os.path.join(_ROOT, "data", "congestion_seg_by_dir.csv")
    # SEG_ID, DIR → aggregates
    agg = defaultdict(lambda: {
        "sum_spd": 0.0, "fix_n": 0.0, "sum_trav_ms": 0.0, "trav_n": 0.0,
        "peak_trucks": 0.0, "truck_sum": 0.0, "hours": 0,
        "ts_min": None, "ts_max": None,
    })
    for row in _iter_hourly_rows(csv_path):
        seg = str(row.get("SEG_ID") or "").strip()
        direction = (row.get("DIR") or "").strip()
        if not seg or not direction:
            continue
        day, _h = _row_day_hour(row.get("HOUR_TS"))
        if day is None or not pa.has_haul_gps(day):
            continue
        try:
            sum_spd = float(row.get("SUM_SPD") or 0)
            fix_n = float(row.get("FIX_N") or 0)
            truck_n = float(row.get("TRUCK_N") or 0)
            sum_trav = float(row.get("SUM_TRAV_MS") or 0)
            trav_n = float(row.get("TRAV_N") or 0)
            ts = int(float(row.get("HOUR_TS") or 0))
        except (TypeError, ValueError):
            continue
        if fix_n <= 0 or truck_n <= 0:
            continue
        key = (seg, direction)
        b = agg[key]
        b["sum_spd"] += sum_spd
        b["fix_n"] += fix_n
        b["sum_trav_ms"] += sum_trav
        b["trav_n"] += trav_n
        b["truck_sum"] += truck_n
        b["hours"] += 1
        if truck_n > b["peak_trucks"]:
            b["peak_trucks"] = truck_n
        if ts > 0:
            if b["ts_min"] is None or ts < b["ts_min"]:
                b["ts_min"] = ts
            if b["ts_max"] is None or ts > b["ts_max"]:
                b["ts_max"] = ts

    rows = []
    for (seg, direction), b in sorted(agg.items()):
        if b["fix_n"] <= 0:
            continue
        rows.append({
            "SEG_ID": seg,
            "DIR": direction.strip(),
            "sum_spd": b["sum_spd"],
            "fix_n": b["fix_n"],
            "sum_trav_ms": b["sum_trav_ms"],
            "trav_n": b["trav_n"],
            "peak_trucks": b["peak_trucks"],
            "mean_trucks": b["truck_sum"] / b["hours"] if b["hours"] else 0,
            "hours": b["hours"],
            "ts_min": b["ts_min"] or 0,
            "ts_max": b["ts_max"] or 0,
            "speed_kmh": round(b["sum_spd"] / b["fix_n"], 2),
        })
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fieldnames = ["SEG_ID", "DIR", "sum_spd", "fix_n", "sum_trav_ms", "trav_n",
                  "peak_trucks", "mean_trucks", "hours", "ts_min", "ts_max", "speed_kmh"]
    tmp = out_path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, out_path)
    return {
        "ok": True,
        "rows": len(rows),
        "segments": len({r["SEG_ID"] for r in rows}),
        "path": out_path,
        "source": source,
    }
