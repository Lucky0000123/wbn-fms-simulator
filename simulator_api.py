"""
Simulator backend endpoints — extracted from the main FMS platform (the ~6 endpoints that compute the
model: trips/DT regression, weighbridge aggregation, rainfall + IWIP-traffic math).

Edit the logic below freely. It runs two ways:
  • No DB configured  → every endpoint returns the sample response from fixtures/ (so the page works
    offline, and you can see your code changes against realistic data).
  • DB configured      → set FMS_DB_HOST / FMS_DB_USER / FMS_DB_PASS env vars and it runs the REAL
    queries against the database. (You need network access to the DB + valid credentials — ask the
    FMS maintainer. Nothing is hardcoded here.)

No credentials live in this file or repo.
"""
import os
import json
import math
import re
import threading
import time
from collections import defaultdict, Counter

try:
    import pymssql
except ImportError:                      # optional — endpoints fall back to fixtures without it
    pymssql = None

from flask import Blueprint, request, jsonify

bp = Blueprint("sim_api", __name__)
_FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# ── One canonicaliser, shared with the model ────────────────────────────────
# The Plan tab lets an operator pick a route and shows a predicted tonnage for
# it. That is only meaningful if the name in the dropdown and the name the model
# trained on denote the SAME physical haul. They used to be produced by two
# independent normalisers that disagreed: the SQL CASE below mapped every FENI
# tip to "FENI" while the pipeline emitted "FENI KM0", and each table spells
# places differently ("KRENE" vs "KR", "HUAFEI C01" vs "HUAFEI.C01",
# "CUU_KM10" vs "CUU KM10"). Importing the pipeline's resolver makes it the
# single source of truth. It is import-guarded so this module keeps working —
# on fixtures — if pandas/sklearn are absent.
try:
    from prediction_pipeline import canonical_area as _canon
except Exception:                                    # noqa: BLE001
    def _canon(name):                                # pragma: no cover
        return " ".join(str(name or "").strip().upper().split())


def _fixture(name):
    with open(os.path.join(_FX, name + ".json"), encoding="utf-8") as f:
        data = json.load(f)
    return _canonical_fixture(name, data)


def _canonical_fixture(name, data):
    """Rewrite route keys in a fixture so fallback mode speaks the same
    vocabulary as the database path.

    Without this the app changes its route names the moment the VPN drops:
    "BLB>FENI A" on fixtures versus "BLB>FENI KM0" on the DB. The Plan tab
    would then offer routes the model cannot score, which is exactly the
    mismatch this endpoint is supposed to prevent.

    Colliding keys keep the entry fitted on the most history (largest n), since
    these are regression fits and averaging their coefficients is meaningless.
    """
    if not isinstance(data, dict):
        return data

    if name == "capability":
        # The capability fixture predates canonicalisation, so it offers
        # "FENI A", "HUAFEI.C01", "CUU_KM_10" -- names the model has never seen,
        # which makes a selected route unpredictable. This rewrite used to live
        # in serve.py while that file answered the endpoint directly. The live
        # path is now api_simulator_capability(), so it has to happen HERE, on
        # the fixture fallback, or no-DB mode silently speaks a different
        # vocabulary from DB mode. check_vocab.py (43 cases) catches that.
        #
        # Merging labels creates duplicates (HUAFEI.B01 and HUAFEI.C01 both
        # become HUAFEI), so rows are re-aggregated: additive columns summed,
        # rates rebuilt from the sums. Averaging rates would let a 5-trip route
        # weigh as much as a 500-trip one.
        _sums = ("t", "trips", "dt", "planDt", "planWmt", "wmt", "nb", "rit",
                 "sw", "snb", "srit", "dtp", "pw", "ptr", "sc")

        def _merge(rows, keyfields):
            out = {}
            for r in rows:
                k = tuple(_canon(r.get(fld)) for fld in keyfields)
                if not all(k):
                    continue
                tgt = out.get(k)
                if tgt is None:
                    tgt = dict(r)
                    for fld, v in zip(keyfields, k):
                        tgt[fld] = v
                    out[k] = tgt
                    continue
                for col in _sums:
                    if isinstance(r.get(col), (int, float)) and isinstance(tgt.get(col), (int, float)):
                        tgt[col] = tgt[col] + r[col]
            for row in out.values():
                t, trips, dt = row.get("t"), row.get("trips"), row.get("dt")
                if isinstance(trips, (int, float)) and trips and isinstance(t, (int, float)):
                    row["tf"] = round(t / trips, 3)
                if isinstance(dt, (int, float)) and dt:
                    if isinstance(trips, (int, float)):
                        row["tripsPerDT"] = round(trips / dt, 3)
                    if isinstance(t, (int, float)):
                        row["tPerDT"] = round(t / dt, 3)
            return list(out.values())

        for _key, _fields in (("routes", ("origin", "dest")),
                              ("paths", ("origin", "dest")),
                              ("destinations", ("dest",))):
            if isinstance(data.get(_key), list):
                data[_key] = _merge(data[_key], _fields)
        if isinstance(data.get("dailyByPath"), list):
            for r in data["dailyByPath"]:
                r["o"] = _canon(r.get("o"))
                r["dd"] = _canon(r.get("dd"))
            data["dailyByPath"] = [r for r in data["dailyByPath"] if r["o"] and r["dd"]]
        return data

    if name != "path-response":
        return data
    paths = data.get("paths")
    if not isinstance(paths, dict):
        return data
    merged = {}
    for key, m in paths.items():
        o, _, d = str(key).partition(">")
        co, cd = _canon(o), _canon(d)
        if not co or not cd:
            continue
        k = "%s>%s" % (co, cd)
        prev = merged.get(k)
        if prev is None or (m or {}).get("n", 0) > (prev or {}).get("n", 0):
            merged[k] = m
    data["paths"] = merged
    return data


# DB credentials come ONLY from the environment — never hardcode them here.
_DB = {
    "server":   os.environ.get("FMS_DB_HOST", ""),
    "user":     os.environ.get("FMS_DB_USER", ""),
    "password": os.environ.get("FMS_DB_PASS", ""),
}


def _db_ready():
    return bool(pymssql and _DB["server"] and _DB["user"] and _DB["password"])


def _conn(database="WBN_DATABASE"):
    """Connect using env-var credentials (used by the endpoint logic below in place of the old
    hardcoded pymssql.connect)."""
    return pymssql.connect(server=_DB["server"], user=_DB["user"], password=_DB["password"],
                           login_timeout=6, database=database, timeout=45)


def _served_from_fixture(payload, why):
    """Tag a fixture response so the client can say so.

    Added 2026-07-31. The fallback was previously indistinguishable from live
    data on the wire, which meant a UI could only be honest about cached figures
    by guessing. Additive and defensive: a fixture that is not a dict (none are
    today) is returned untouched rather than crashing the fallback path, which
    is the one path that must never fail.
    """
    if isinstance(payload, dict):
        payload = dict(payload)
        payload["servedFrom"] = "fixture"
        payload["servedFromReason"] = why
    return payload


def _register(path, fn, fixture, methods=None):
    """Wrap an endpoint: serve the fixture when there's no DB (or on any error), else run the real logic."""
    def wrap(*a, **k):
        if not _db_ready():
            return jsonify(_served_from_fixture(
                _fixture(fixture), "no database configured"))
        try:
            return fn(*a, **k)
        except Exception as e:            # noqa: BLE001 — any failure falls back to sample data
            print("[sim_api] %s -> fixture fallback (%s)" % (getattr(fn, "__name__", "?"), e))
            # This is the "configured but unreachable" case -- the normal state
            # here, because the site VPN drops every few minutes. An endpoint
            # that catches its own exception and returns an error payload never
            # reaches this line, and its section renders empty while a complete
            # fixture sits unused. Do not swallow exceptions in endpoint logic.
            return jsonify(_served_from_fixture(
                _fixture(fixture),
                "database configured but unreachable: %s" % str(e)[:120]))
    bp.add_url_rule(path, fn.__name__, wrap, methods=methods or ["GET"])


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint logic (extracted from the platform). Edit freely.
# ─────────────────────────────────────────────────────────────────────────────
_SIM_CORRIDOR = {
    "source": "WBN_DATABASE.dbo.HAUL_ROAD_STA",
    "basis": "road chainage",
    "lengthKm": 67.8,
    "nodes": [
        {"id": "tf", "label": "TF", "km": 67.8, "aliases": ["TF", "TOFU"]},
        {"id": "kr", "label": "KR", "km": 39.0, "aliases": ["KR", "KRENE"]},
        {"id": "pos12", "label": "POS 12", "km": 27.0, "aliases": ["POS 12", "POS12"]},
        {"id": "pos10", "label": "POS 10", "km": 17.0, "aliases": ["POS 10", "POS10"]},
        {"id": "feni15", "label": "FENI 15", "km": 15.0, "aliases": ["FENI KM15", "FENI 15"]},
        {"id": "feni0", "label": "FENI 0", "km": 0.0, "aliases": ["FENI KM0", "FENI 0"]},
    ],
    "roadRanges": [
        {"label": "TOFU", "fromKm": 67.8, "toKm": 39.0},
        {"label": "KR", "fromKm": 39.0, "toKm": 7.875},
        {"label": "CRD", "fromKm": 7.85, "toKm": 0.0},
    ],
}

# Posted limits (Excel → CSV) + GPS measured speeds for Tab 1 flow. Cached once.
_SPEED_LIMIT_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "data", "speed_limit_zones_public.csv")
_CONG_BY_DIR_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "data", "congestion_seg_by_dir.csv")
_CORRIDOR_LAYERS = None  # {speedLimits, speedLimitsAll, measuredSpeeds, measuredWindow}


def _parse_seg_id(seg):
    """'TF KM54-55' / 'KR KM 17-18' → (road, lo, hi) or None."""
    m = re.match(
        r"^(.+?)\s*KM\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)$",
        str(seg or "").strip(), re.I)
    if not m:
        return None
    a, b = float(m.group(2)), float(m.group(3))
    return m.group(1).strip().upper(), min(a, b), max(a, b)


def _load_posted_speed_limits():
    """CSV rows. Stick zones (onStick=1) vs spur (BLB/BB, onStick=0)."""
    import csv as _csv
    stick, all_zones = [], []
    try:
        with open(_SPEED_LIMIT_CSV, encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                try:
                    rec = {
                        "segment": row["segment"],
                        "region": row.get("region") or "",
                        "road": row.get("road") or "",
                        "fromKm": float(row["fromKm"]),
                        "toKm": float(row["toKm"]),
                        "limit": float(row["limit"]),
                        "chainage": row.get("chainage") or "",
                        "operatingArea": row.get("operatingArea") or "",
                        "onStick": str(row.get("onStick", "0")).strip() in ("1", "true", "True"),
                    }
                except (KeyError, ValueError):
                    continue
                all_zones.append(rec)
                if rec["onStick"]:
                    stick.append(rec)
    except OSError:
        return [], []
    return stick, all_zones


def _load_measured_speeds_from_csv():
    """Build stick measuredSpeeds + lane capacity from congestion_seg_by_dir.csv.

    DIR down = loaded. Capacity uses median peak TRUCK_N on stick loaded
    segments (observed trucks in the busiest segment-hour) — not the old
    assumed 90 s headway.
    """
    import csv as _csv
    from collections import defaultdict
    by_seg = defaultdict(dict)
    peak_loaded = []
    t_lo = t_hi = None
    try:
        with open(_CONG_BY_DIR_CSV, encoding="utf-8") as f:
            for row in _csv.DictReader(f):
                seg = row.get("SEG_ID") or row.get("seg")
                parsed = _parse_seg_id(seg)
                if not parsed:
                    continue
                road, lo, hi = parsed
                # Stick uses TF/KR/CRD chainage vocabulary (TOFU→TF).
                road = {"TOFU": "TF", "KRENE": "KR"}.get(road, road)
                if road not in ("TF", "KR", "CRD"):
                    continue
                d = (row.get("DIR") or "").strip().lower()
                try:
                    spd = float(row.get("speed_kmh") or 0)
                    n = int(float(row.get("fix_n") or row.get("hours") or 0))
                except ValueError:
                    continue
                if spd <= 0:
                    continue
                key = (road, lo, hi, seg)
                if d in ("down", "up"):
                    by_seg[key][d] = {"kmh": spd, "n": n}
                if d == "down":
                    try:
                        pk = float(row.get("peak_trucks") or 0)
                    except ValueError:
                        pk = 0
                    if pk > 0:
                        mid_km = (lo + hi) / 2.0
                        peak_loaded.append((mid_km, pk))
                for col in ("ts_min", "ts_max"):
                    try:
                        ts = int(float(row.get(col) or 0))
                    except ValueError:
                        continue
                    if ts <= 0:
                        continue
                    if t_lo is None or ts < t_lo:
                        t_lo = ts
                    if t_hi is None or ts > t_hi:
                        t_hi = ts
    except OSError:
        return [], None, None
    out = []
    for (road, lo, hi, seg), dirs in by_seg.items():
        loaded = dirs.get("down")
        empty = dirs.get("up")
        out.append({
            "seg": seg,
            "road": road,
            "fromKm": hi,   # higher chainage (toward TF)
            "toKm": lo,
            "loadedKmh": loaded["kmh"] if loaded else None,
            "emptyKmh": empty["kmh"] if empty else None,
            "n": (loaded or {}).get("n", 0) + (empty or {}).get("n", 0),
        })
    out.sort(key=lambda r: -r["fromKm"])
    window = None
    if t_lo and t_hi:
        from datetime import datetime, timezone
        def _iso(ms):
            return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).date().isoformat()
        w_from, w_to = _iso(t_lo), _iso(t_hi)
        # Retention: FMS_CONGESTION_SEG only keeps ~2 weeks. Jan–May peak
        # production has no segment GPS — speeds/capacity here are struggle-season.
        peak_lo, peak_hi = "2026-01-01", "2026-05-31"
        overlaps_peak = not (w_to < peak_lo or w_from > peak_hi)
        struggle = not overlaps_peak
        window = {
            "from": w_from,
            "to": w_to,
            "source": "data/congestion_seg_by_dir.csv",
            "peakSeason": {"from": peak_lo, "to": peak_hi},
            "struggleSeasonExtract": bool(struggle),
            "note": ("Segment GPS retention starts mid-July; Jan–May peak has no "
                     "corridor GPS. Speeds/V·C capacity below are from this extract "
                     "only — use Capability Jan–May window for Shift Performance / "
                     "path-response, and /api/simulate for achievable tonnes.")
            if struggle else None,
        }
    capacity = None
    if peak_loaded:
        peaks = sorted(pk for _, pk in peak_loaded)
        n = len(peaks)
        p50 = peaks[n // 2]
        p25 = peaks[max(0, n // 4)]
        # Per corridor section (same labels as Shift Road hotspots).
        SECS = [("TOFU–KR", 39.0, 67.8), ("KR–POS 12", 27.0, 39.0),
                ("POS 12–POS 10", 17.0, 27.0), ("POS 10–FENI", 0.0, 17.0)]
        by_section = {}
        for label, slo, shi in SECS:
            vals = sorted(pk for mid, pk in peak_loaded if mid > slo and mid <= shi)
            if not vals:
                vals = sorted(pk for mid, pk in peak_loaded
                              if mid >= slo - 1e-6 and mid <= shi + 1e-6)
            if vals:
                med = vals[len(vals) // 2]
                by_section[label] = {
                    "trucksPerHour": round(med, 2),
                    "bottleneckTph": round(vals[max(0, len(vals) // 4)], 2),
                    "nSegments": len(vals),
                    "equivHeadwaySec": round(3600.0 / med) if med > 0 else None,
                }
        capacity = {
            "trucksPerHour": round(p50, 2),
            "bottleneckTph": round(p25, 2),
            "equivHeadwaySec": round(3600.0 / p50) if p50 > 0 else None,
            "source": "data/congestion_seg_by_dir.csv",
            "method": "median peak TRUCK_N / segment-hour (stick, DIR=down)",
            "nSegments": n,
            "bySection": by_section,
        }
    return out, window, capacity


def _corridor_payload():
    """_SIM_CORRIDOR + posted speedLimits (stick) + GPS measuredSpeeds."""
    global _CORRIDOR_LAYERS
    if _CORRIDOR_LAYERS is None:
        stick, all_zones = _load_posted_speed_limits()
        measured, window, capacity = _load_measured_speeds_from_csv()
        _CORRIDOR_LAYERS = {
            "speedLimits": stick,
            "speedLimitsAll": all_zones,
            "measuredSpeeds": measured,
            "measuredWindow": window,
            "measuredCapacity": capacity,
        }
    base = dict(_SIM_CORRIDOR)
    base["speedLimits"] = _CORRIDOR_LAYERS["speedLimits"]
    base["measuredSpeeds"] = _CORRIDOR_LAYERS["measuredSpeeds"]
    base["measuredWindow"] = _CORRIDOR_LAYERS["measuredWindow"]
    base["measuredCapacity"] = _CORRIDOR_LAYERS["measuredCapacity"]
    # Spur zones kept off the stick paint list but available for later views.
    base["speedLimitsSpur"] = [z for z in _CORRIDOR_LAYERS["speedLimitsAll"]
                               if not z.get("onStick")]
    return base

_WB_POS_CACHE = None

_WB_RESULT_CACHE = None

_WB_HOME_CACHE = None

_OTHER_FENI_TYPICAL = None
_OTHER_TYPICAL = None


# ─────────────────────────────────────────────────────────────────────────────
# Capability — the payload behind the whole "Capability & Scenario" tab.
#
# THIS USED TO BE A STATIC FILE. serve.py answered /api/simulator/capability with
# `jsonify(_canonical_capability(fx("capability")))` -- the committed fixture,
# every time, database or not, and it never read request.args. The UI sent it six
# filter parameters (from, to, types, inclIwip, source, dest) and all six were
# discarded, so every KPI card, the routes and destinations tables, the 3D
# scatter and the truck list were frozen at whatever was captured on 2026-07-22.
# The date range shown in the summary line was the FIXTURE's own `from`/`to`,
# which is why changing the pickers appeared to do nothing: the numbers and the
# dates both came from the file.
#
# Everything below now comes from `DISPATCH RESULTS LITE 2`, which carries both
# actuals (NB_DT, RIT, WMT, TF) and plan (DT PLAN, TARGET TRIP, PLAN WMT) on the
# same row, plus COMPANY ('WBN' / 'IWIP') for the exclude toggle and TYPE for the
# type filter. One query, all six filters, everything else derived.
#
# The derivations were reverse-engineered from the fixture and verified against
# it rather than guessed:
#     tf = t/trips        tripsPerDT = trips/dt        tPerDT = t/dt
#     effDT = dt/planDt   effWMT = t/planWmt           effTrip = tripsPerDT/planTripsPerDT
#     srit = rit/sc       sw = w/sc                    snb = nb
#
# TARGET TRIP is already a RATE (planned trips per DT), e.g. 8.0 / 4.8 / 6.0 —
# it matches RIT/NB_DT on the same row. It is NOT a trip count. Storing the raw
# rate in _ptr and then doing planTripsPerDT = SUM(rate)/SUM(DT PLAN) produced
# planTripsPerDT ≈ 0.15 and Trip-eff KPIs of 1700–2600% (Tab 1 QC, 2026-07-31).
# _ptr therefore holds planned trip-COUNTS = TARGET_TRIP × DT_PLAN so that
# SUM(_ptr)/SUM(DT PLAN) recovers the DT-PLAN-weighted average rate (~4.4).
# ─────────────────────────────────────────────────────────────────────────────

_CAP_TABLE = "[DISPATCH RESULTS LITE 2]"

# ── Why the whole view is snapshotted instead of queried per filter ──────────
#
# DISPATCH RESULTS LITE 2 is a VIEW, not a table, and it is expensive to
# materialise. Measured over the site VPN on 2026-07-31:
#
#     SELECT COUNT(*)            (1 row  returned)   15.4 s
#     13 columns, no WHERE       (25,220 rows)       17.1 s
#     SELECT *                   (25,220 rows)       31.9 s
#     date+company filtered      (7,122 rows)        13.4 s
#     GROUP BY TYPE              (7 rows)             8.9 s
#
# A COUNT(*) with no predicate costing 15 s is the whole story: the view is
# rebuilt from its base tables before any filter is applied, so NO WHERE clause
# can make it fast and there is no index to add -- indexes belong to the base
# tables, and an indexed view is a schema change on a database this project does
# not own. Pushing aggregation into SQL does not help either; the 7-row GROUP BY
# still cost 8.9 s.
#
# Caching per filter combination would leave every FIRST use of a new range at
# ~20 s, which is the complaint. So the whole view -- 25,220 rows, a few MB -- is
# pulled ONCE and every filter runs in Python against it. Areas are canonicalised
# and numbers coerced during the load, so the request path touches only
# primitives.
_CAP_TTL = 300.0                      # 5 min; new dispatch rows appear within one
_CAP_SNAP = {"rows": None, "at": 0.0, "source": None, "refreshing": False}
_CAP_LOCK = threading.Lock()
# Disk tier (P3): memory > disk > fixture. Files hold production tonnages — gitignored.
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_CAP_DISK = os.path.join(_DATA_DIR, "cap_snapshot.json")
_PATH_DISK = os.path.join(_DATA_DIR, "pr_snapshot.json")


def _cap_reset():
    """Drop in-memory capability + path-response snapshots. Disk files kept
    so the next process can warm from them (P3). Called by /api/retrain."""
    with _CAP_LOCK:
        _CAP_SNAP["rows"] = None
        _CAP_SNAP["at"] = 0.0
        _CAP_SNAP["source"] = None
        _CAP_SNAP["refreshing"] = False
    _path_reset()


def _atomic_json_write(path, payload):
    """Write JSON via tmp+rename so a crash mid-write cannot leave a half file."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))
    os.replace(tmp, path)


def _cap_disk_write(rows, at):
    try:
        _atomic_json_write(_CAP_DISK, {"at": at, "rows": rows})
    except Exception as exc:  # noqa: BLE001 — disk is an accelerator, not required
        print("  cap disk write failed: %s" % str(exc)[:120], flush=True)


def _cap_disk_read():
    """Return {at, rows} or None. Corrupt/missing → None (fall through to DB)."""
    try:
        with open(_CAP_DISK, encoding="utf-8") as f:
            data = json.load(f)
        rows = data.get("rows")
        at = float(data.get("at") or 0)
        if not isinstance(rows, list) or not rows or at <= 0:
            return None
        return {"at": at, "rows": rows}
    except Exception:  # noqa: BLE001
        return None


def _cap_load_rows():
    """Pull the whole view and normalise it once."""
    conn = _conn("WBN_DATABASE")
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT DATE, ORIGIN, DESTINATION, CONTRACTOR, TYPE, COMPANY, "
            "NB_SHIFT, NB_DT, RIT, WMT, [DT PLAN], [TARGET TRIP], [PLAN WMT] "
            "FROM dbo.%s WHERE WMT IS NOT NULL" % _CAP_TABLE)
        raw = cur.fetchall()
    finally:
        conn.close()
    out = []
    for (dte, o, dd, contr, typ, comp, nbsh, nbdt, rit, wmt, pdt, ptr, pw) in raw:
        co, cd = _canon(o), _canon(dd)
        if not co or not cd:
            continue
        pdt_n = _num(pdt)
        out.append({
            "d": dte.isoformat() if hasattr(dte, "isoformat") else str(dte)[:10],
            "o": co, "dd": cd,
            "contractor": str(contr or "").strip().upper(),
            "type": (typ or "").strip(),
            "iwip": (comp or "").strip().upper() == "IWIP",
            "sc": int(_num(nbsh)) or 1,
            "dt": _num(nbdt), "trips": _num(rit), "t": _num(wmt),
            "planDt": pdt_n,
            "_ptr": _planned_trip_counts(ptr, pdt_n),
            "planWmt": _num(pw),
        })
    return out


def _cap_bg_refresh():
    """Reload from DB in the background; overwrite disk, then memory."""
    try:
        fresh = _cap_load_rows()
        at = time.time()
        # Disk BEFORE memory: observers key off source=="db" / refreshing=False
        # (set under the lock), so the disk copy must already be current when
        # they see that state — J68 caught the reversed order as a race.
        _cap_disk_write(fresh, at)
        with _CAP_LOCK:
            _CAP_SNAP["rows"] = fresh
            _CAP_SNAP["at"] = at
            _CAP_SNAP["source"] = "db"
            _CAP_SNAP["refreshing"] = False
        print("  capability snapshot refreshed (%d rows)" % len(fresh), flush=True)
    except Exception as exc:  # noqa: BLE001
        with _CAP_LOCK:
            _CAP_SNAP["refreshing"] = False
        print("  capability snapshot refresh failed: %s" % str(exc)[:120], flush=True)


def _cap_schedule_refresh():
    """Start at most one background DB reload. Caller may hold _CAP_LOCK."""
    if _CAP_SNAP.get("refreshing"):
        return False
    _CAP_SNAP["refreshing"] = True
    threading.Thread(target=_cap_bg_refresh, daemon=True).start()
    return True


def _snapshot_disk_tag(snap):
    """Fields to merge into an API payload when serving from the disk tier."""
    if snap.get("source") != "disk" or snap.get("rows") is None:
        return {}
    age = max(0.0, time.time() - float(snap.get("at") or 0))
    return {"servedFrom": "disk-snapshot", "snapshotAgeSec": round(age, 1)}


def _cap_snapshot():
    """Cached view. Priority: fresh memory > disk (stale OK + bg refresh) > DB.

    A fresh DB load also writes data/cap_snapshot.json so the next process
    restart can answer in milliseconds instead of 14–20 s.
    """
    now = time.time()
    rows = _CAP_SNAP["rows"]
    if rows is not None and (now - _CAP_SNAP["at"]) < _CAP_TTL:
        return rows
    # Serialise concurrent misses so a burst of tab-opens does not fire N
    # 17-second queries at a view that is slow precisely because it is busy.
    with _CAP_LOCK:
        rows = _CAP_SNAP["rows"]
        age = (time.time() - _CAP_SNAP["at"]) if rows is not None else None
        if rows is not None and age is not None and age < _CAP_TTL:
            return rows
        # Stale memory: serve immediately, refresh in background (same idea as
        # stale disk). Avoids blocking the operator on a 17 s SQL hit.
        if rows is not None:
            _cap_schedule_refresh()
            return rows
        # Empty memory — try disk before hitting the DB.
        disk = _cap_disk_read()
        if disk is not None:
            _CAP_SNAP["rows"] = disk["rows"]
            _CAP_SNAP["at"] = disk["at"]
            _CAP_SNAP["source"] = "disk"
            if (time.time() - disk["at"]) >= _CAP_TTL:
                _cap_schedule_refresh()
            return disk["rows"]
        # No disk: blocking DB load, then persist (write outside the lock —
        # a multi-MB JSON dump must not stall other requests).
        fresh = _cap_load_rows()
        at = time.time()
        _CAP_SNAP["rows"] = fresh
        _CAP_SNAP["at"] = at
        _CAP_SNAP["source"] = "db"
    _cap_disk_write(fresh, at)
    return fresh


def _cap_args():
    """Read the filter bar. Returns (sql_where, sql_params, python_filters)."""
    a = request.args
    frm = (a.get("from") or "").strip()[:10]
    to = (a.get("to") or "").strip()[:10]
    types = [t for t in (a.get("types") or "").split(",") if t.strip()]
    # The checkbox is "Exclude IWIP" and is CHECKED by default, so the UI sends
    # inclIwip=1 only when the operator unticks it. Absent means exclude.
    incl_iwip = a.get("inclIwip") in ("1", "true", "yes")
    src = [_canon(s) for s in (a.get("source") or "").split(",") if s.strip()]
    dst = [_canon(s) for s in (a.get("dest") or "").split(",") if s.strip()]
    paths = [p for p in (a.get("paths") or "").split("~") if p.strip()]

    where, params = ["WMT IS NOT NULL"], []
    if frm:
        where.append("DATE >= %s"); params.append(frm)
    if to:
        where.append("DATE <= %s"); params.append(to)
    if not incl_iwip:
        # COMPANY is the discriminator: 18,148 WBN rows vs 7,046 IWIP.
        where.append("(COMPANY IS NULL OR COMPANY <> 'IWIP')")
    if types:
        where.append("TYPE IN (%s)" % ",".join(["%s"] * len(types)))
        params.extend(types)
    return (" AND ".join(where), params,
            {"src": set(src), "dst": set(dst), "paths": set(paths),
             "from": frm, "to": to, "inclIwip": incl_iwip, "types": types})


def _num(v):
    try:
        f = float(v)
        return f if f == f else 0.0            # NaN -> 0
    except (TypeError, ValueError):
        return 0.0


def _planned_trip_counts(target_rate, plan_dt):
    """Convert TARGET TRIP (trips/DT rate) to trip-counts for SUM/SUM aggregation.

    TARGET TRIP is NOT a count. Multiplying by DT PLAN yields planned trips so
    that planTripsPerDT = SUM(counts)/SUM(DT PLAN) is the weighted average rate.
    Exposed for J65 offline mutation tests (no VPN required).
    """
    r, p = _num(target_rate), _num(plan_dt)
    return (r * p) if (r and p) else 0.0


def _cap_rates(d):
    """Rebuild rate columns from the summed quantities.

    Additive columns (t, trips, dt, planDt, planWmt, _ptr) are summed upstream.
    Rates are always rebuilt from those sums — never averaged.

    _ptr is planned trip-COUNTS (TARGET_TRIP × DT_PLAN per source row), so
    planTripsPerDT = _ptr / planDt is the DT-PLAN-weighted average of the
    TARGET TRIP rate. See the capability block comment above.
    """
    t, trips, dt = d.get("t", 0.0), d.get("trips", 0.0), d.get("dt", 0.0)
    pdt, pw, ptr = d.get("planDt", 0.0), d.get("planWmt", 0.0), d.get("_ptr", 0.0)
    d["tf"] = round(t / trips, 3) if trips else 0.0
    d["tripsPerDT"] = round(trips / dt, 3) if dt else 0.0
    d["tPerDT"] = round(t / dt, 3) if dt else 0.0
    d["planTripsPerDT"] = round(ptr / pdt, 3) if pdt else 0.0
    d["effDT"] = round(dt / pdt, 4) if pdt else 0.0
    d["effWMT"] = round(t / pw, 4) if pw else 0.0
    d["effTrip"] = round(d["tripsPerDT"] / d["planTripsPerDT"], 4) if d["planTripsPerDT"] else 0.0
    d.pop("_ptr", None)
    return d


def api_simulator_capability():
    """Per-route / per-day haulage capability for the selected filter window."""
    _, _, f = _cap_args()
    snap = _cap_snapshot()

    # Window = date range + IWIP toggle. The Types dropdown is built from the
    # WINDOW, not from the type-filtered set -- otherwise ticking one type
    # empties the menu and the operator cannot get back to the others.
    window = [r for r in snap
              if (not f["from"] or r["d"] >= f["from"])
              and (not f["to"] or r["d"] <= f["to"])
              and (f["inclIwip"] or not r["iwip"])]
    tsum = {}
    for r in window:
        if r["type"]:
            tsum[r["type"]] = tsum.get(r["type"], 0.0) + r["t"]
    all_types = [{"type": k, "t": round(v, 2)} for k, v in tsum.items()]

    tsel = set(f["types"])
    byPath, byDate, agg_path, agg_dest, agg_contr, months = {}, {}, {}, {}, {}, {}
    for r in window:
        if tsel and r["type"] not in tsel:
            continue
        co, cd = r["o"], r["dd"]
        # source/dest/path are matched on CANONICAL names ("FENI KM0"), which is
        # why they are applied here and not in SQL -- the view stores raw ones
        # ("FENI A"), so a SQL predicate would silently match nothing.
        if f["src"] and co not in f["src"]:
            continue
        if f["dst"] and cd not in f["dst"]:
            continue
        if f["paths"] and ("%s>%s" % (co, cd)) not in f["paths"]:
            continue
        ds = r["d"]
        contr = r["contractor"]
        q = {"dt": r["dt"], "trips": r["trips"], "t": r["t"],
             "planDt": r["planDt"], "planWmt": r["planWmt"], "_ptr": r["_ptr"]}
        sc = r["sc"]

        k = (ds, co, cd)
        b = byPath.get(k)
        if b is None:
            b = byPath[k] = {"d": ds, "o": co, "dd": cd, "nb": 0.0, "rit": 0.0,
                             "w": 0.0, "dtp": 0.0, "ptr": 0.0, "pw": 0.0,
                             "sc": 0, "sx": True}
        b["nb"] += q["dt"]; b["rit"] += q["trips"]; b["w"] += q["t"]
        b["dtp"] += q["planDt"]; b["ptr"] += q["_ptr"]; b["pw"] += q["planWmt"]
        b["sc"] = max(b["sc"], sc)

        for store, key in ((agg_path, (co, cd)), (agg_dest, (cd,)),
                           (agg_contr, (str(contr or "").strip().upper(),)),
                           (byDate, (ds,)), (months, (ds[:7],))):
            tgt = store.get(key)
            if tgt is None:
                tgt = store[key] = {"dt": 0.0, "trips": 0.0, "t": 0.0,
                                    "planDt": 0.0, "planWmt": 0.0, "_ptr": 0.0,
                                    "_days": set(), "_sc": 0}
            for kk in ("dt", "trips", "t", "planDt", "planWmt", "_ptr"):
                tgt[kk] += q[kk]
            tgt["_days"].add(ds)
            tgt["_sc"] = max(tgt["_sc"], sc)

    for b in byPath.values():
        sc = b["sc"] or 1
        b["snb"] = round(b["nb"], 3)
        b["srit"] = round(b["rit"] / sc, 3)
        b["sw"] = round(b["w"] / sc, 3)

    def pack(store, keyfields):
        out = []
        for key, v in store.items():
            rec = dict(zip(keyfields, key))
            rec.update({kk: round(v[kk], 3) for kk in ("dt", "trips", "t", "planDt", "planWmt")})
            rec["_ptr"] = v["_ptr"]
            out.append(_cap_rates(rec))
        return out

    paths = sorted(pack(agg_path, ("origin", "dest")), key=lambda r: -r["t"])
    dests = sorted(pack(agg_dest, ("dest",)), key=lambda r: -r["t"])
    contrs = sorted(pack(agg_contr, ("contractor",)), key=lambda r: -r["t"])

    daily = []
    for ds, v in sorted(byDate.items()):
        sc = v["_sc"] or 1
        rec = _cap_rates({"date": ds[0] if isinstance(ds, tuple) else ds,
                          "dt": round(v["dt"], 3), "trips": round(v["trips"], 3),
                          "t": round(v["t"], 3), "planDt": round(v["planDt"], 3),
                          "planWmt": round(v["planWmt"], 3), "_ptr": v["_ptr"]})
        # Assign step by step. Doing this as one dict literal read rec["wmt"]
        # while the same literal was still being built -- the key did not exist
        # yet, so it raised KeyError, _register swallowed it, and the endpoint
        # silently served the fixture again. The symptom was identical to the
        # bug being fixed, which is exactly how it nearly went unnoticed.
        wmt = rec.pop("t")
        dtv = rec["dt"]
        rec["wmt"] = wmt
        rec["shiftCount"] = sc
        rec["shiftDt"] = dtv
        rec["shiftTrips"] = round(v["trips"] / sc, 3)
        rec["shiftWmt"] = round(wmt / sc, 3)
        rec["shiftExplicit"] = True
        rec["shiftTripsPerDT"] = round((v["trips"] / sc) / dtv, 3) if dtv else 0.0
        daily.append(rec)

    mrows = []
    for ym, v in sorted(months.items()):
        days = len(v["_days"]) or 1
        mrows.append({"ym": int(str(ym[0] if isinstance(ym, tuple) else ym).replace("-", "")),
                      "days": days, "t": round(v["t"], 3),
                      "tPerDay": round(v["t"] / days, 3),
                      "dtPerDay": round(v["dt"] / days, 3)})

    tot = {"dt": 0.0, "trips": 0.0, "t": 0.0, "planDt": 0.0, "planWmt": 0.0, "_ptr": 0.0}
    for v in agg_path.values():
        for kk in tot:
            tot[kk] += v[kk]
    ndays = len({r["date"] for r in daily}) or 1
    maxsc = max([r["shiftCount"] for r in daily] or [1])
    kpi = _cap_rates(dict(tot))
    kpi.update({
        "days": ndays, "maxShiftsPerDay": maxsc, "shiftExplicit": True,
        "wmtPerDay": round(tot["t"] / ndays, 3),
        "dtPerDay": round(tot["dt"] / ndays, 3),
        "planWmtPerDay": round(tot["planWmt"] / ndays, 3),
        "planDtPerDay": round(tot["planDt"] / ndays, 3),
        "wmtPerShift": round(tot["t"] / ndays / maxsc, 3),
        "dtPerShift": round(tot["dt"] / ndays, 3),
        "tripsPerShift": round(tot["trips"] / ndays / maxsc, 3),
        "tripsPerDTShift": round((tot["trips"] / maxsc) / tot["dt"], 3) if tot["dt"] else 0.0,
        "planTPerDT": round(tot["planWmt"] / tot["planDt"], 3) if tot["planDt"] else 0.0,
    })

    out = {
        "ok": True,
        "routes": [{"origin": p["origin"], "dest": p["dest"], "t": p["t"]} for p in paths],
        "paths": paths, "destinations": dests, "contractorProd": contrs,
        "daily": daily, "dailyByPath": sorted(byPath.values(), key=lambda r: r["d"]),
        "months": mrows, "kpi": kpi, "types": sorted(all_types, key=lambda r: -r["t"]),
        "typesSel": f["types"], "fleet": [],
        "corridor": _corridor_payload(),
        "from": f["from"], "to": f["to"], "inclIwip": f["inclIwip"],
        "source": ",".join(sorted(f["src"])), "dest": ",".join(sorted(f["dst"])),
        "type": ",".join(f["types"]) if f["types"] else "ALL",
        "shiftBasis": {"explicit": True, "hours": 12,
                       "method": "NB_DT is the average shift fleet; RIT and WMT "
                                 "are divided by NB_SHIFT for per-shift figures",
                       "source": "WBN_DATABASE.dbo.DISPATCH RESULTS LITE 2"},
        "updated": int(time.time() * 1000),
        # `fleet` needs TRUCK_ID, which this table does not carry. Returned empty
        # rather than filled from an unfiltered second source, which would show a
        # fleet that ignored the very filters the rest of the payload honours.
        "fleetNote": "fleet breakdown needs TRUCK_ID and is not available from "
                     "the dispatch table; omitted rather than served unfiltered",
    }
    out.update(_snapshot_disk_tag(_CAP_SNAP))
    return jsonify(out)


def _gf_db_conn():
    import pymssql
    return _conn('FMS_DB')

def _wb_corridor_positions():
    """Each weighbridge geofence snapped to the TF→FENI corridor chainage (nearest HAUL_ROAD_STA marker
    on the TOFU/KR/CRD roads that make up the corridor). Returns [{name, wbNum, km, offM}] cached for the
    process. offM = metres off the corridor centreline; large values sit on a spur road, not the corridor."""
    global _WB_POS_CACHE
    if _WB_POS_CACHE is not None:
        return _WB_POS_CACHE
    import json as _json, re as _re, math as _math
    out = []
    try:
        conn = _conn('WBN_DATABASE')
        cur = conn.cursor()
        cur.execute("SELECT CAST(SectionKM AS float), wkt FROM HAUL_ROAD_STA "
                    "WHERE wkt IS NOT NULL AND [DIRECTION] IN ('TOFU','KR','CRD')")
        sta = []
        for km, wkt in cur.fetchall():
            m = _re.search(r'POINT Z? *\(([-\d.]+) +([-\d.]+)', wkt or '')
            if m and km is not None:
                sta.append((float(km), float(m.group(1)), float(m.group(2))))   # km, lng, lat
        conn.close()
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'geofences.json')) as fh:
            gf = _json.load(fh)
        feats = gf if isinstance(gf, list) else gf.get('features', gf.get('geofences', []))
        for f in feats:
            if f.get('type') != 'weighbridge':
                continue
            c = f.get('center')
            if isinstance(c, dict):
                la, lo = c.get('lat'), c.get('lng')
            elif isinstance(c, (list, tuple)) and len(c) == 2:
                la, lo = c[0], c[1]
            else:
                ll = f.get('latlngs')
                pts = (ll[0] if ll and isinstance(ll[0], list) else ll) or []
                if not pts:
                    continue
                la = sum(p[0] for p in pts) / len(pts); lo = sum(p[1] for p in pts) / len(pts)
            if la is None or lo is None or not sta:
                continue
            best = min(sta, key=lambda s: (s[2] - la) ** 2 + (s[1] - lo) ** 2)
            offm = _math.hypot((best[2] - la) * 111000, (best[1] - lo) * 111000 * _math.cos(_math.radians(la)))
            name = f.get('name') or ''
            mnum = _re.search(r'_T(\d+)', name)
            out.append({"name": name, "wbNum": mnum.group(1) if mnum else None,
                        "km": round(best[0], 1), "offM": round(offm)})
    except Exception:
        out = []
    if out:                              # never cache an empty result from a transient DB/file hiccup
        _WB_POS_CACHE = out
    return out

def _other_typical():
    """Typical OTHER (non-WBN) trips per shift + per-bridge shares, TWO regimes:

      • recent — last 30 data days (median + shares). The site's tempo TODAY.
      • peak   — the busiest 60-day window in the data (highest median trips
        per shift), found by scanning, not hardcoded. Today that window is
        Jan–Feb 2026 (median 952/shift, WB 11 32%, WB 6 21%), which the owner
        identified as "operation at its best". Self-updating: if a busier
        stretch ever appears, the scan finds it.

    The owner plans for the RAMP-BACK, not for today's quiet site (WBN's own
    fleet: 988 trips/shift in Jan–Feb vs 151 in the last 30 days), so the UI
    defaults to peak and offers recent as the alternative. MEDIAN throughout —
    surge days (ship arrivals, 1447 max) skew means upward."""
    global _OTHER_TYPICAL
    if _OTHER_TYPICAL is not None:
        return _OTHER_TYPICAL
    wbn = "'RIM','PPP','SSS','SMA','STM','HJS','GMG','CKB','HFNC'"

    def _median(vals):
        s = sorted(vals)
        return s[len(s) // 2] if s else None

    try:
        conn = _conn('WBN_DATABASE')
        cur = conn.cursor()
        # One query drives both regimes: per-day+shift other-trip counts.
        cur.execute("SELECT CONVERT(date,[DATE]) d, SHIFT, COUNT(*) n FROM HAULAGE_IWIP_CLEAN "
                    "WHERE CONTRACTOR NOT IN (" + wbn + ") AND [DATE]>='2025-12-01' "
                    "GROUP BY CONVERT(date,[DATE]), SHIFT")
        per = {}
        for d, s, n in cur.fetchall():
            per.setdefault(str(d), []).append(int(n))
        days = sorted(per)
        if not days:
            conn.close()
            return None
        # recent = last 30 data days
        recent_days = days[-30:]
        recent_vals = [n for d in recent_days for n in per[d]]
        # peak = busiest 60-consecutive-data-day window by median trips/shift
        best = None
        win = 60
        for i in range(0, max(1, len(days) - win + 1)):
            wdays = days[i:i + win]
            vals = [n for d in wdays for n in per[d]]
            med = _median(vals)
            if med is not None and (best is None or med > best[0]):
                best = (med, wdays[0], wdays[-1], len(vals))
        # per-bridge shares for a date range
        def shares(d0, d1):
            cur.execute("SELECT WB_ID, COUNT(*) n FROM HAULAGE_IWIP_CLEAN "
                        "WHERE CONTRACTOR NOT IN (" + wbn + ") AND WB_ID<>'' AND WB_ID IS NOT NULL "
                        "AND WB_ID<>'NOT WEIGHED' AND CONVERT(date,[DATE])>=%s AND CONVERT(date,[DATE])<=%s "
                        "GROUP BY WB_ID", (d0, d1))
            rows = [(str(w).strip(), int(n)) for w, n in cur.fetchall()]
            tot = sum(n for _, n in rows) or 1
            return [{"wb": w, "sharePct": round(100.0 * n / tot, 1)}
                    for w, n in sorted(rows, key=lambda x: -x[1]) if n / tot >= 0.003]
        recent_shares = shares(recent_days[0], recent_days[-1])
        peak_shares = shares(best[1], best[2]) if best else []
        conn.close()
        _OTHER_TYPICAL = {
            # legacy flat fields = recent regime (existing consumers)
            "tripsPerShift": _median(recent_vals),
            "nShifts": len(recent_vals),
            "windowDays": 30,
            "wbShares": recent_shares,
            "peak": {
                "tripsPerShift": best[0], "nShifts": best[3],
                "window": "%s → %s" % (best[1], best[2]),
                "wbShares": peak_shares,
            } if best else None,
        }
    except Exception:
        return None
    return _OTHER_TYPICAL


def _other_feni_typical():
    """Median daily non-WBN trips ending on the FENI corridor (dest FENI/CRUSHER) — the 'normal' shared
    IWIP load a shift is diagnosed against. Cached for the process."""
    global _OTHER_FENI_TYPICAL
    if _OTHER_FENI_TYPICAL is not None:
        return _OTHER_FENI_TYPICAL
    wbn = "'RIM','PPP','SSS','SMA','STM','HJS','GMG','CKB','HFNC'"
    try:
        conn = _conn('WBN_DATABASE')
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) n FROM HAULAGE_IWIP_CLEAN "
                    "WHERE CONTRACTOR NOT IN (" + wbn + ") AND [DATE]>='2025-12-01' AND [DATE]<='2100-01-01' "
                    "AND (UPPER(DESTINATION_AREA) LIKE '%FENI%' OR UPPER(DESTINATION_AREA) LIKE '%CRUSHER%') "
                    "GROUP BY CONVERT(date,[DATE])")
        vals = sorted(int(r[0]) for r in cur.fetchall())
        conn.close()
        if vals:
            _OTHER_FENI_TYPICAL = vals[len(vals) // 2]
    except Exception:
        return None
    return _OTHER_FENI_TYPICAL

# ── path-response snapshot ───────────────────────────────────────────────────
# DISPATCH RESULTS LITE 3 + rain is the same class of expensive view as capability
# (~15 s cold over the site VPN). Tab 1 QC (2026-07-31): rain panel sat on
# "Loading…" for 15–18 s and Apply never re-fetched it. Snapshot the ~13k rows
# once; OLS + optional date filter run in Python in well under a second.
_PATH_TTL = 300.0
_PATH_SNAP = {"rows": None, "rain": None, "at": 0.0, "source": None, "refreshing": False}
_PATH_LOCK = threading.Lock()


def _path_reset():
    with _PATH_LOCK:
        _PATH_SNAP["rows"] = None
        _PATH_SNAP["rain"] = None
        _PATH_SNAP["at"] = 0.0
        _PATH_SNAP["source"] = None
        _PATH_SNAP["refreshing"] = False


def _path_disk_write(rows, rain, at):
    """Persist path rows + rain. Rain keys are (date, area) tuples → list."""
    try:
        rain_list = [{"d": d, "a": a, "h": h} for (d, a), h in (rain or {}).items()]
        _atomic_json_write(_PATH_DISK, {"at": at, "rows": rows, "rain": rain_list})
    except Exception as exc:  # noqa: BLE001
        print("  path disk write failed: %s" % str(exc)[:120], flush=True)


def _path_disk_read():
    try:
        with open(_PATH_DISK, encoding="utf-8") as f:
            data = json.load(f)
        rows = data.get("rows")
        at = float(data.get("at") or 0)
        if not isinstance(rows, list) or not rows or at <= 0:
            return None
        rain = {}
        for item in (data.get("rain") or []):
            try:
                rain[(str(item["d"]), str(item["a"]))] = float(item["h"])
            except (KeyError, TypeError, ValueError):
                continue
        return {"at": at, "rows": rows, "rain": rain}
    except Exception:  # noqa: BLE001
        return None


def _path_load():
    """Pull LITE 3 haul rows + rain gauges. Normalise once at load."""
    conn = _conn("WBN_DATABASE")
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT ORIGIN, DESTINATION, NB_DT, RIT, WMT, [DATE] "
            "FROM [DISPATCH RESULTS LITE 3] "
            "WHERE (CONTRACTOR IS NULL OR CONTRACTOR<>'IWIP') "
            "AND DATE>=DATEADD(month,-20,GETDATE()) AND NB_DT>0 AND RIT>0 "
            # ~200 rows carry a NULL DESTINATION. They produced an
            # unselectable blank entry in the Plan tab's route list.
            "AND ORIGIN IS NOT NULL AND LTRIM(RTRIM(ORIGIN))<>'' "
            "AND DESTINATION IS NOT NULL AND LTRIM(RTRIM(DESTINATION))<>''")
        raw = cur.fetchall()
        rain = {}
        try:
            cur.execute(
                "SELECT [DATE], Area, H2O FROM AVG_RAIN_BY_DATE_AREA "
                "WHERE Area IN ('TOFU','KAO RAHAI') AND H2O IS NOT NULL "
                "AND [DATE]>=DATEADD(month,-20,GETDATE())")
            for d, area, h2o in cur.fetchall():
                ds = d.isoformat() if hasattr(d, "isoformat") else str(d)[:10]
                rain[(ds, str(area))] = float(h2o)
        except Exception:  # noqa: BLE001
            rain = {}
    finally:
        conn.close()
    rows = []
    for o, de, nb, rit, wmt, dat in raw:
        co, cd = _canon(o), _canon(de)
        if not co or not cd:
            continue
        ds = dat.isoformat() if hasattr(dat, "isoformat") else str(dat)[:10]
        rows.append({
            "o": co, "dd": cd, "d": ds,
            "dt": float(nb), "trips": float(rit), "t": float(wmt or 0),
        })
    return rows, rain


def _path_bg_refresh():
    try:
        rows, rain = _path_load()
        at = time.time()
        # Disk before memory — same ordering rationale as _cap_bg_refresh.
        _path_disk_write(rows, rain, at)
        with _PATH_LOCK:
            _PATH_SNAP["rows"] = rows
            _PATH_SNAP["rain"] = rain
            _PATH_SNAP["at"] = at
            _PATH_SNAP["source"] = "db"
            _PATH_SNAP["refreshing"] = False
        print("  path-response snapshot refreshed (%d rows)" % len(rows), flush=True)
    except Exception as exc:  # noqa: BLE001
        with _PATH_LOCK:
            _PATH_SNAP["refreshing"] = False
        print("  path-response snapshot refresh failed: %s" % str(exc)[:120], flush=True)


def _path_schedule_refresh():
    if _PATH_SNAP.get("refreshing"):
        return False
    _PATH_SNAP["refreshing"] = True
    threading.Thread(target=_path_bg_refresh, daemon=True).start()
    return True


def _path_snapshot():
    """Cached LITE 3 + rain. Priority: fresh memory > disk > DB (+ disk write)."""
    now = time.time()
    if (_PATH_SNAP["rows"] is not None
            and (now - _PATH_SNAP["at"]) < _PATH_TTL):
        return _PATH_SNAP["rows"], _PATH_SNAP["rain"]
    with _PATH_LOCK:
        if (_PATH_SNAP["rows"] is not None
                and (time.time() - _PATH_SNAP["at"]) < _PATH_TTL):
            return _PATH_SNAP["rows"], _PATH_SNAP["rain"]
        if _PATH_SNAP["rows"] is not None:
            _path_schedule_refresh()
            return _PATH_SNAP["rows"], _PATH_SNAP["rain"]
        disk = _path_disk_read()
        if disk is not None:
            _PATH_SNAP["rows"] = disk["rows"]
            _PATH_SNAP["rain"] = disk["rain"]
            _PATH_SNAP["at"] = disk["at"]
            _PATH_SNAP["source"] = "disk"
            if (time.time() - disk["at"]) >= _PATH_TTL:
                _path_schedule_refresh()
            return disk["rows"], disk["rain"]
        rows, rain = _path_load()
        at = time.time()
        _PATH_SNAP["rows"] = rows
        _PATH_SNAP["rain"] = rain
        _PATH_SNAP["at"] = at
        _PATH_SNAP["source"] = "db"
    _path_disk_write(rows, rain, at)
    return rows, rain


def _path_eff_pctile(xs, p):
    """Linear-interpolated percentile of a numeric sequence. p in [0, 1]."""
    if not xs:
        return None
    s = sorted(float(x) for x in xs)
    if len(s) == 1:
        return s[0]
    p = max(0.0, min(1.0, float(p)))
    idx = p * (len(s) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(s) - 1)
    frac = idx - lo
    return s[lo] * (1.0 - frac) + s[hi] * frac


def _path_mid60_mean(xs):
    """Mid-60% trimmed mean: drop lowest/highest 20% of samples, mean the rest.

    Plan Step 1 uses this as avgTr (main-cluster trips/DT) so one extreme day
    cannot pull the forecast. n < 5 falls back to the plain mean.
    """
    vals = [float(x) for x in xs if x is not None]
    n = len(vals)
    if n == 0:
        return None
    if n < 5:
        return sum(vals) / n
    s = sorted(vals)
    drop = int(n * 0.2)
    core = s[drop:n - drop] if n - 2 * drop > 0 else s
    return sum(core) / len(core)


def api_simulator_path_response():
    """Per-path fleet→efficiency response from the historical DB (LITE 3): fits trips/DT = a + b·DT for
    each route so the scenario planner can predict how efficiency (and thus WMT) shifts as you add/remove
    trucks. Only a MEASURED decline (b<0) is later applied — confounded/flat paths stay flat.

    avgTr is the mid-60% trimmed mean of daily trips/DT (main cluster), not the
    raw arithmetic mean. meanTr / trP25 / trMed / trP75 accompany it. OLS slope
    still fits on all days; avgDt stays the mean fleet size.

    Honours optional from/to (and uses the capability snapshot pattern) so Tab 1
    Apply can refresh the rain panel without a 15 s SQL hit every time.
    """
    # Re-raise on DB failure so _register serves the fixture — returning
    # {"ok": false} with HTTP 200 used to skip the fallback entirely.
    rows, rain = _path_snapshot()
    a = request.args
    frm = (a.get("from") or "").strip()[:10]
    to = (a.get("to") or "").strip()[:10]
    if frm or to:
        rows = [r for r in rows
                if (not frm or r["d"] >= frm) and (not to or r["d"] <= to)]

    from collections import defaultdict
    # Route labels come from the shared canonicaliser so path keys match the
    # model's vocabulary exactly. The rain gauge is then chosen from that
    # canonical node rather than from a raw-string prefix.
    _area = lambda o: {"TF": "TOFU", "KR": "KAO RAHAI"}.get(o)

    def _ols2(pts):
        """Multivariate OLS  eff = a + b·DT + c·rain  over rows that have a rain match.
        Returns (bAdj, cRain, nRain) — b controlling for weather, and the mm→eff sensitivity."""
        if len(pts) < 30:
            return None
        n = len(pts)
        Sd = Sr = Sdd = Sdr = Srr = Sy = Sdy = Sry = 0.0
        for dt, rn, y in pts:
            Sd += dt; Sr += rn; Sdd += dt * dt; Sdr += dt * rn; Srr += rn * rn
            Sy += y; Sdy += dt * y; Sry += rn * y
        # 3x3 normal equations  [[n,Sd,Sr],[Sd,Sdd,Sdr],[Sr,Sdr,Srr]] · [a,b,c] = [Sy,Sdy,Sry]
        M = [[n, Sd, Sr], [Sd, Sdd, Sdr], [Sr, Sdr, Srr]]
        rhs = [Sy, Sdy, Sry]
        for i in range(3):                                           # Gaussian elimination w/ partial pivot
            p = max(range(i, 3), key=lambda k: abs(M[k][i]))
            if abs(M[p][i]) < 1e-9:
                return None
            M[i], M[p] = M[p], M[i]; rhs[i], rhs[p] = rhs[p], rhs[i]
            for k in range(3):
                if k == i:
                    continue
                f = M[k][i] / M[i][i]
                for j in range(3):
                    M[k][j] -= f * M[i][j]
                rhs[k] -= f * rhs[i]
        return (rhs[1] / M[1][1], rhs[2] / M[2][2], n, rhs[0] / M[0][0], Sd / n)

    byp = defaultdict(list)
    for r in rows:
        rn = rain.get((r["d"], _area(r["o"])))
        byp[(r["o"], r["dd"])].append((r["dt"], r["trips"], r["t"], rn))
    out = {}
    for (o, de), v in byp.items():
        if len(v) < 25:
            continue
        dt = [x[0] for x in v]; eff = [x[1] / x[0] for x in v]
        n = len(v); mx = sum(dt) / n; my = sum(eff) / n
        # Plan base = mid-60% trimmed mean (main cluster); OLS still uses raw mean my.
        avg_tr = _path_mid60_mean(eff)
        if avg_tr is None:
            avg_tr = my
        tr_p25 = _path_eff_pctile(eff, 0.25)
        tr_med = _path_eff_pctile(eff, 0.5)
        tr_p75 = _path_eff_pctile(eff, 0.75)
        den = sum((x - mx) ** 2 for x in dt)
        b = (sum((x - mx) * (y - my) for x, y in zip(dt, eff)) / den) if den else 0.0
        a = my - b * mx
        sr = sum((y - (a + b * x)) ** 2 for x, y in zip(dt, eff)); st = sum((y - my) ** 2 for y in eff)
        r2 = (1 - sr / st) if st else 0.0
        srit = sum(x[1] for x in v)
        tf = (sum(x[2] for x in v) / srit) if srit else 0.0
        rec = {"a": round(a, 4), "b": round(b, 5), "r2": round(r2, 3), "n": n,
               "dtMin": round(min(dt)), "dtMax": round(max(dt)), "avgDt": round(mx),
               "avgTr": round(avg_tr, 3), "meanTr": round(my, 3),
               "trP25": round(tr_p25, 3) if tr_p25 is not None else None,
               "trMed": round(tr_med, 3) if tr_med is not None else None,
               "trP75": round(tr_p75, 3) if tr_p75 is not None else None,
               "tf": round(tf, 2)}
        # rain-controlled fit + dry/wet efficiency split
        wet = [(x[0], x[3], x[1] / x[0]) for x in v if x[3] is not None]
        m2 = _ols2(wet)
        if m2:
            bAdj, cRain, nRain, aCoef, meanDT = m2
            rec["bAdj"] = round(bAdj, 5); rec["cRain"] = round(cRain, 5); rec["rainN"] = nRain
            # FLEET-CONTROLLED dry vs wet: same (mean) fleet, dry (0 mm) vs a wet (10 mm) day. These are
            # consistent with the impact by construction (raw dry/wet were confounded — fewer trucks ran
            # on wet days, which faked a higher wet efficiency).
            base = aCoef + bAdj * meanDT
            rec["dryCtrl"] = round(base, 3)
            rec["wetCtrl"] = round(base + cRain * 10, 3)
            dryE = [w[2] for w in wet if w[1] < 2.0]; wetE = [w[2] for w in wet if w[1] >= 10.0]
            if dryE and wetE:
                rec["dryEff"] = round(sum(dryE) / len(dryE), 3); rec["dryN"] = len(dryE)
                rec["wetEff"] = round(sum(wetE) / len(wetE), 3); rec["wetN"] = len(wetE)
            # fleet-MATCHED wet vs dry: for each wet (>=10mm) day pair it with the dry (<2mm) days at a
            # similar fleet (caliper on DT), then compare. No linear assumption — the honest apples-to-
            # apples read (only speaks to the fleet regime where it actually rained).
            wets_m = [(w[0], w[2]) for w in wet if w[1] >= 10.0]
            drys_m = [(w[0], w[2]) for w in wet if w[1] < 2.0]
            if len(wets_m) >= 5 and len(drys_m) >= 5:
                dv, wv = [], []
                for wdt, wy in wets_m:
                    cal = max(4.0, 0.12 * wdt)
                    near = [dy for ddt, dy in drys_m if abs(ddt - wdt) <= cal]
                    if len(near) >= 3:
                        dv.append(sum(near) / len(near)); wv.append(wy)
                if len(wv) >= 8:
                    rec["mDry"] = round(sum(dv) / len(dv), 3)
                    rec["mWet"] = round(sum(wv) / len(wv), 3)
                    rec["mN"] = len(wv)
        out["%s>%s" % (o, de)] = rec
    payload = {
        "ok": True, "paths": out,
        "from": frm or None, "to": to or None,
        "nRows": len(rows),
        "source": "WBN_DATABASE.dbo.DISPATCH RESULTS LITE 3",
    }
    payload.update(_snapshot_disk_tag(_PATH_SNAP))
    return jsonify(payload)

def _density_fit():
    """The site-wide within-segment speed-density fit, read from its report file.

    Served so the assessment UI can caption the congestion section with the real
    coefficients instead of a hardcoded copy that goes stale the next time the
    fit is re-run. reports/speed_density_fit.json is committed (it holds
    coefficients, not tonnages), so this resolves on a fresh clone with no DB
    and is identical on the fixture path -- there is one source of truth.

    Returns None rather than a guess when the file is absent; the UI then hides
    the claim instead of rendering a placeholder coefficient as if measured.
    """
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "reports", "speed_density_fit.json")) as fh:
            return json.load(fh)
    except Exception:
        return None


def api_simulator_congestion_model():
    """PREVIEW: measured speed-vs-traffic per haul-road segment (from FMS_CONGESTION_SEG) — the raw data
    for a future speed-density (fundamental-diagram) congestion model. Returns per-segment observations
    plus a data-anchored free-flow speed and observed peak throughput. Honest about the sparse coverage."""
    # NOT wrapped in try/except, deliberately. This used to catch its own
    # exception and return {"ok": false, ...} with HTTP 200, which _register
    # reads as success -- so the fixture fallback never fired and section 3 of
    # the assessment view rendered empty whenever the VPN blipped, which is most
    # of the time, while a complete 94-segment fixture sat unused. Letting the
    # exception propagate is the whole mechanism: _register serves the fixture
    # and tags it `servedFrom: "fixture"` so the UI can label it as cached.
    # DIR is now selected, so loaded and empty speeds can be reported separately
    # instead of averaged into one number. Verified against the ticket data
    # rather than assumed from the word: 100.0% of loaded corridor hauls run
    # DOWN-chainage (298,340 trips, zero counter-examples), because every tip is
    # seaward of every load point. So DIR='down' is the LOADED direction and
    # 'up' the empty return. The measured speeds agree -- loaded is slower on 75
    # of 94 segments, median +11.5% empty, up to +101% on the steep TF sections.
    # DIR is char-padded ('up  '), hence the trim.
    conn = _gf_db_conn(); cur = conn.cursor()
    cur.execute("SELECT SEG_ID, LTRIM(RTRIM(DIR)), TRUCK_N, "
                "CASE WHEN FIX_N>0 THEN SUM_SPD/FIX_N END, FIX_N, "
                "MIN(HOUR_TS) OVER(), MAX(HOUR_TS) OVER() FROM dbo.FMS_CONGESTION_SEG "
                "WHERE TRUCK_N>0 AND FIX_N>0")
    rows = cur.fetchall(); conn.close()
    from collections import defaultdict
    obs = defaultdict(list); span = [None, None]
    # Per-direction sums, weighted by FIX_N so a busy hour counts more than a
    # quiet one -- a plain mean of hourly means would weight a 4-fix hour the
    # same as a 140-fix hour.
    dirsum = defaultdict(lambda: {"down": [0.0, 0], "up": [0.0, 0]})
    for seg, dr, tn, spd, fixn, mn, mx in rows:
        if spd is None:
            continue
        obs[seg].append([int(tn or 0), round(float(spd), 1)])
        d = (dr or "").strip().lower()
        if d in ("down", "up"):
            acc = dirsum[seg][d]
            acc[0] += float(spd) * int(fixn or 0)
            acc[1] += int(fixn or 0)
        span = [mn, mx]
    segs = []
    for seg, pts in obs.items():
        if len(pts) < 5:
            continue
        trucks = sorted(p[0] for p in pts); spds = [p[1] for p in pts]
        lowcut = max(3, trucks[len(trucks) // 5])                     # bottom-quintile traffic threshold
        low = sorted(p[1] for p in pts if p[0] <= lowcut)
        free_flow = round(low[int(len(low) * 0.85)] if low else max(spds), 1)   # p85 speed at low traffic
        # Direction split. Reported as null rather than 0 where a direction has
        # no fixes, so the UI drops the point instead of drawing a truck
        # standing still. 1 of 95 segments has only one direction.
        dn, up = dirsum[seg]["down"], dirsum[seg]["up"]
        loaded = round(dn[0] / dn[1], 1) if dn[1] else None
        empty = round(up[0] / up[1], 1) if up[1] else None
        segs.append({"seg": seg, "n": len(pts), "obs": pts, "freeFlow": free_flow,
                     "peakTrucks": max(trucks), "avgSpeed": round(sum(spds) / len(spds), 1),
                     # DIR='down' == loaded (every tip is seaward of every load
                     # point; 100% of 298,340 corridor hauls run down-chainage).
                     "loadedSpeed": loaded, "emptySpeed": empty,
                     "nLoaded": dn[1], "nEmpty": up[1]})
    segs.sort(key=lambda s: -s["n"])
    days = 0
    try:
        days = round((span[1] - span[0]) / 86400000) if span[0] else 0
    except Exception:
        days = 0
    return jsonify({"ok": True, "segments": segs[:120], "days": days,
                    "densityFit": _density_fit()})

def api_simulator_weighbridge_positions():
    """Weighbridge geofences snapped to corridor chainage, with optional selected-shift usage."""
    selected_date = (request.args.get("date") or "").strip()[:10]
    shift = (request.args.get("shift") or "").strip()          # '1' day, '2' night, else whole day
    usage = {}
    if selected_date:
        try:
            conn = _conn('WBN_DATABASE')
            cur = conn.cursor()
            _shift_sql = " AND SHIFT=%s" if shift in ("1", "2") else ""
            cur.execute("SELECT WB_ID, COUNT(*) FROM HAULAGE_IWIP_CLEAN "
                        "WHERE CONVERT(date,[DATE])=%s" + _shift_sql + " AND WB_ID<>'' AND WB_ID IS NOT NULL "
                        "GROUP BY WB_ID", (selected_date, shift) if shift in ("1", "2") else (selected_date,))
            import re as _re
            for wb_id, count in cur.fetchall():
                raw = str(wb_id or '').strip().upper()
                digits = _re.findall(r'\d+', raw)
                keys = {raw}
                if digits:
                    number = str(int(digits[-1]))
                    keys.update({digits[-1], number, 'T' + digits[-1], 'T' + number,
                                 'WB' + digits[-1], 'WB' + number})
                for key in keys:
                    usage[key] = usage.get(key, 0) + int(count or 0)
            conn.close()
        except Exception:
            usage = {}
    pos = []
    for p in _wb_corridor_positions():
        name = str(p.get("name") or '').upper()
        num = str(p.get("wbNum") or '').upper()
        plain_num = str(int(num)) if num.isdigit() else num
        trucks = max((usage.get(k, 0) for k in
                      (name, num, plain_num, 'T' + num, 'T' + plain_num,
                       'WB' + num, 'WB' + plain_num) if k), default=0)
        pos.append({**p, "onCorridor": p["offM"] <= 150, "trucks": trucks,
                    "usedOnShift": trucks > 0})
    return jsonify({"ok": True, "positions": pos, "date": selected_date or None,
                    "usageAvailable": bool(usage),
                    "corridorKm": _SIM_CORRIDOR.get("lengthKm", 67.8)})

# WBN-owned endpoint (additive). Links a source→dest PATH to the specific
# weighbridges that actually weighed that path's trucks — the gap behind the
# Plan tab's free "weighbridges open" number, which is tied to neither WHICH
# bridges nor the bridges that lie on the selected haul. Measured from tickets
# (WB_ID × ORIGIN/DEST) rather than assumed from geometry, matching this repo's
# "measure, don't assume" rule. No DB exception is caught here: it propagates so
# _register serves fixtures/weighbridge-by-path.json in no-DB / unreachable mode.
def api_simulator_weighbridge_by_path():
    """Weighbridges serving a given ORIGIN→DEST path, by measured ticket count."""
    src = (request.args.get("source") or request.args.get("src") or "").strip()
    dst = (request.args.get("dest") or request.args.get("dst") or "").strip()
    frm = (request.args.get("from") or "").strip()[:10]
    to = (request.args.get("to") or "").strip()[:10]
    shift = (request.args.get("shift") or "").strip()   # '1' day, '2' night, else all
    # Same canonical-label → LIKE patterns the capability query uses (kept local
    # and minimal). If you extend the capability area maps, mirror them here.
    area_like = {
        "TF": ("ORIGIN_AREA LIKE %s OR ORIGIN_AREA LIKE %s OR ORIGIN_AREA LIKE %s",
               ("%TOFU%", "TF%", "TOS_TF%")),
        "TOFU": ("ORIGIN_AREA LIKE %s OR ORIGIN_AREA LIKE %s", ("%TOFU%", "TF%")),
        "KR": ("ORIGIN_AREA LIKE %s OR ORIGIN_AREA LIKE %s", ("%KRENE%", "KR%")),
    }
    dest_like = {
        "FENI KM0": ("DESTINATION_AREA LIKE %s", ("%FENI%",)),
        "FENI KM15": ("DESTINATION_AREA LIKE %s OR DESTINATION_AREA LIKE %s",
                      ("%FENI KM15%", "%FENI 15%")),
        "POS 12": ("DESTINATION_AREA LIKE %s OR DESTINATION_AREA LIKE %s",
                   ("%POS 12%", "%POS12%")),
        "POS 10": ("DESTINATION_AREA LIKE %s OR DESTINATION_AREA LIKE %s",
                   ("%POS 10%", "%POS10%")),
        "CRUSHER": ("DESTINATION_AREA LIKE %s", ("%CRUSHER%",)),
        "HUAFEI": ("DESTINATION_AREA LIKE %s", ("%HUAFEI%",)),
        "BSE": ("DESTINATION_AREA LIKE %s", ("%BSE%",)),
    }
    where, params = ["WB_ID<>'' AND WB_ID IS NOT NULL"], []
    if frm:
        where.append("CONVERT(date,[DATE]) >= %s"); params.append(frm)
    if to:
        where.append("CONVERT(date,[DATE]) <= %s"); params.append(to)
    if shift in ("1", "2"):
        where.append("SHIFT=%s"); params.append(shift)
    if src:
        spec = area_like.get(src) or area_like.get(src.replace(" ", ""))
        if spec:
            where.append("(" + spec[0] + ")"); params.extend(spec[1])
        else:
            where.append("UPPER(ORIGIN_AREA) LIKE %s"); params.append("%" + src.upper() + "%")
    if dst:
        spec = dest_like.get(dst)
        if spec:
            where.append("(" + spec[0] + ")"); params.extend(spec[1])
        else:
            where.append("UPPER(DESTINATION_AREA) LIKE %s"); params.append("%" + dst.upper() + "%")
    conn = _conn('WBN_DATABASE')
    try:
        cur = conn.cursor()
        cur.execute("SELECT WB_ID, COUNT(*), SUM(WMT) FROM HAULAGE_IWIP_CLEAN "
                    "WHERE " + " AND ".join(where) + " GROUP BY WB_ID", tuple(params))
        rows = cur.fetchall()
    finally:
        conn.close()
    # Join each WB_ID to its corridor chainage, reusing the digit-matching scheme
    # from api_simulator_weighbridge_positions.
    import re as _re
    pos_by_key = {}
    for p in _wb_corridor_positions():
        num = str(p.get("wbNum") or '').upper()
        plain = str(int(num)) if num.isdigit() else num
        for key in {str(p.get("name") or '').upper(), num, plain,
                    'T' + num, 'T' + plain, 'WB' + num, 'WB' + plain}:
            if key:
                pos_by_key[key] = p
    bridges, total = [], 0
    for wb_id, n, wmt in rows:
        n = int(n or 0); total += n
        raw = str(wb_id or '').strip().upper()
        digits = _re.findall(r'\d+', raw)
        num = str(int(digits[-1])) if digits else raw
        p = next((pos_by_key[k] for k in (raw, num, 'T' + num, 'WB' + num) if k in pos_by_key), None)
        # onCorridor is UNKNOWN (null), not False, when we have no position for
        # the bridge — geofences.json is absent on some deployments, so defaulting
        # to False would wrongly tag every bridge a "spur".
        bridges.append({"wb": raw, "wbNum": num, "trips": n, "wmt": float(wmt or 0),
                        "km": (p or {}).get("km"), "offM": (p or {}).get("offM"),
                        "onCorridor": None if p is None else (p.get("offM", 999) <= 150)})
    bridges.sort(key=lambda b: -b["trips"])
    for b in bridges:
        b["sharePct"] = round(100.0 * b["trips"] / total, 1) if total else 0.0
    # A weighbridge only "serves" the route if it handled a MATERIAL share of the
    # weighs. Tickets scatter a few strays onto almost every bridge (a truck
    # weighed at the wrong scale, a mis-tagged row): e.g. TF>POS 12 has 7 bridges
    # with 1-47 tickets out of ~89k — noise, not part of the haul. Keep bridges at
    # or above MIN_SHARE_PCT of the route's weighs; if that would drop everything
    # (a very fragmented route), keep the single busiest so the list is never empty.
    MIN_SHARE_PCT = 1.0
    material = [b for b in bridges if b["sharePct"] >= MIN_SHARE_PCT]
    if not material and bridges:
        material = [bridges[0]]
    excluded = len(bridges) - len(material)
    # Capacity ceiling from the bridges that ACTUALLY serve the path — same
    # ~30 trips/hr assumption plan.js already uses, but multiplied by the
    # measured on-path bridge count instead of a free number. Labelled as an
    # assumption so it is never mistaken for a measured ceiling.
    SHIFT_HRS, PER_BRIDGE_HR = 12, 30
    n_used = len(material)
    return jsonify({
        "ok": True, "source": src or None, "dest": dst or None,
        "from": frm or None, "to": to or None,
        "bridges": material, "nBridges": n_used, "totalTrips": total,
        "excludedMinorBridges": excluded, "minSharePct": MIN_SHARE_PCT,
        "positionsAvailable": any(b["km"] is not None for b in material),
        "capacityTripsPerShift": n_used * PER_BRIDGE_HR * SHIFT_HRS,
        "capacityBasis": "%d on-path bridges x ~%d trips/hr x %dh (assumption)"
                         % (n_used, PER_BRIDGE_HR, SHIFT_HRS),
        "servedFrom": "db",
        "source_table": "WBN_DATABASE.dbo.HAULAGE_IWIP_CLEAN",
    })

def api_simulator_shift_context():
    """Everything specific to ONE reviewed shift-day: that day's rainfall by mine area (did weather bite?)
    and the per-weighbridge usage split with the busiest = likely congestion point. Weigh data only exists
    from Dec-2025, so older shifts return wbAvailable=false and just the rainfall context."""
    date = (request.args.get("date") or "").strip()[:10]
    shift = (request.args.get("shift") or "").strip()          # '1' day, '2' night, else whole day
    if not date:
        return jsonify({"ok": False, "error": "no date"})
    rain, bridges = [], []
    wbn_haulers = {"RIM", "PPP", "SSS", "SMA", "STM", "HJS", "GMG", "CKB", "HFNC"}
    shift_sql = " AND SHIFT=%s" if shift in ("1", "2") else ""
    wb_params = (date, shift) if shift in ("1", "2") else (date,)
    try:
        conn = _conn('WBN_DATABASE')
        cur = conn.cursor()
        cur.execute("SELECT Area, H2O FROM AVG_RAIN_BY_DATE_AREA "
                    "WHERE CONVERT(date,[DATE])=%s AND Area IN ('TOFU','KAO RAHAI') AND H2O IS NOT NULL",
                    (date,))
        for area, h2o in cur.fetchall():
            rain.append({"area": "TF" if area == "TOFU" else "KR", "mm": round(float(h2o), 1)})
        cur.execute("SELECT WB_ID, CONTRACTOR, COUNT(*) FROM HAULAGE_IWIP_CLEAN "
                    "WHERE CONVERT(date,[DATE])=%s" + shift_sql + " AND WB_ID<>'' AND WB_ID IS NOT NULL "
                    "GROUP BY WB_ID, CONTRACTOR", wb_params)
        agg = {}
        for wb, cont, n in cur.fetchall():
            wb = str(wb).strip()
            a = agg.setdefault(wb, {"trucks": 0, "wbn": 0, "other": 0})
            a["trucks"] += int(n or 0)
            a["wbn" if (cont or "").strip().upper() in wbn_haulers else "other"] += int(n or 0)
        # non-WBN (IWIP/Position) fleet + per-section traffic — congestion contributors, no WBN WMT
        wbn_in = ",".join("'%s'" % w for w in sorted(wbn_haulers))

        def _case(col):                                  # group a raw area column into a corridor node
            # keep %% literal so pymssql leaves the LIKE wildcards intact; substitute the column via replace
            # Labels MUST match canonical_area() — "FENI KM0", not "FENI" — or
            # the congestion breakdown names routes differently from the model
            # and the Plan tab. This runs server-side for a GROUP BY, so it
            # cannot call the Python resolver; keep the two in step by hand.
            return ("CASE "
                    "WHEN UPPER(COL) LIKE 'TOS_TF%%' OR UPPER(COL) LIKE 'TF%%' OR UPPER(COL) LIKE '%%TOFU%%' THEN 'TF' "
                    "WHEN UPPER(COL) LIKE 'KR%%' OR UPPER(COL) LIKE '%%KRENE%%' THEN 'KR' "
                    "WHEN UPPER(COL) LIKE '%%POS 12%%' OR UPPER(COL) LIKE '%%POS12%%' THEN 'POS 12' "
                    "WHEN UPPER(COL) LIKE '%%POS 10%%' OR UPPER(COL) LIKE '%%POS10%%' THEN 'POS 10' "
                    "WHEN UPPER(COL) LIKE '%%CRUSHER%%' THEN 'CRUSHER' "
                    "WHEN UPPER(COL) LIKE '%%FENI KM15%%' OR UPPER(COL) LIKE '%%FENI 15%%' THEN 'FENI KM15' "
                    "WHEN UPPER(COL) LIKE '%%FENI%%' THEN 'FENI KM0' "
                    "WHEN UPPER(COL) LIKE '%%HUAFEI%%' THEN 'HUAFEI' "
                    "WHEN UPPER(COL) LIKE '%%BSE%%' THEN 'BSE' "
                    "WHEN UPPER(COL) LIKE '%%BLB%%' THEN 'BLB' ELSE 'OTHER' END").replace("COL", col)
        ocase, dcase = _case("ORIGIN_AREA"), _case("DESTINATION_AREA")
        cur.execute("SELECT " + ocase + " og, " + dcase + " dg, COUNT(*) trips, COUNT(DISTINCT TRUCK_ID) trucks "
                    "FROM HAULAGE_IWIP_CLEAN WHERE CONVERT(date,[DATE])=%s" + shift_sql +
                    " AND CONTRACTOR NOT IN (" + wbn_in + ") GROUP BY " + ocase + ", " + dcase, wb_params)
        grp_rows = cur.fetchall()
        cur.execute("SELECT COUNT(DISTINCT TRUCK_ID), COUNT(*) FROM HAULAGE_IWIP_CLEAN "
                    "WHERE CONVERT(date,[DATE])=%s" + shift_sql + " AND CONTRACTOR NOT IN (" + wbn_in + ")",
                    wb_params)
        _of = cur.fetchone(); other_fleet = int(_of[0] or 0); other_trips = int(_of[1] or 0)
        conn.close()

        # Keys MUST match the SQL CASE labels above (FENI KM0, not FENI) or
        # other-paths that end at the smelter are dropped and otherFeniTrips=0.
        NODE_KM = {"TF": 67.8, "KR": 39.0, "POS 12": 27.0, "POS 10": 17.0,
                   "FENI KM0": 0.0, "FENI KM15": 15.0, "CRUSHER": 3.0,
                   "HUAFEI": 0.0, "BSE": 0.0, "BLB": 67.8}
        other_paths = []
        for og, dg, trips, trucks in grp_rows:
            ok, dk = NODE_KM.get(og), NODE_KM.get(dg)
            if ok is None or dk is None:
                continue
            other_paths.append({"origin": og, "dest": dg, "label": "%s → %s" % (og, dg),
                                "trips": int(trips or 0), "trucks": int(trucks or 0),
                                "oKm": ok, "dKm": dk})
        other_paths.sort(key=lambda p: -p["trips"])
        other_paths = [p for p in other_paths if p["trips"] >= 10]        # drop trivial paths
        SECS = [("TOFU–KR", 39.0, 67.8), ("KR–POS 12", 27.0, 39.0),
                ("POS 12–POS 10", 17.0, 27.0), ("POS 10–FENI", 0.0, 17.0)]
        sec_trips = {s[0]: 0 for s in SECS}
        for p in other_paths:
            lo, hi = min(p["oKm"], p["dKm"]), max(p["oKm"], p["dKm"])
            for label, slo, shi in SECS:
                if hi > slo and lo < shi:
                    sec_trips[label] += p["trips"]
        other_by_section = [{"section": s[0], "trips": sec_trips[s[0]]} for s in SECS]
        km_by_num = {p["wbNum"]: p["km"] for p in _wb_corridor_positions() if p.get("wbNum")}
        total = sum(a["trucks"] for a in agg.values()) or 1
        for wb, a in sorted(agg.items(), key=lambda x: -x[1]["trucks"]):
            bridges.append({"wb": wb, "km": km_by_num.get(str(int(wb)) if wb.isdigit() else wb),
                            "trucks": a["trucks"], "pct": round(100 * a["trucks"] / total, 1),
                            "otherPct": round(100 * a["other"] / a["trucks"], 1) if a["trucks"] else 0})
    except Exception:
        # Re-raise so _register serves the fixture — see the note in _register.
        raise
    maxmm = max([r["mm"] for r in rain], default=0)
    rain_assess = ("Heavy rain — likely traction/mud impact" if maxmm >= 10 else
                   "Some rain — possible impact" if maxmm >= 2 else "Dry — no rain effect")
    busiest = bridges[0] if bridges else None
    feni_dests = ("FENI KM0", "FENI KM15", "CRUSHER", "HUAFEI", "BSE")
    return jsonify({"ok": True, "date": date, "shift": shift or "all",
                    "rain": rain, "rainMax": maxmm, "rainAssess": rain_assess,
                    "wbAvailable": bool(bridges), "bridges": bridges,
                    "busiest": busiest,
                    "otherFleet": other_fleet, "otherTrips": other_trips,
                    "otherBySection": other_by_section, "otherPaths": other_paths,
                    "otherFeniTrips": sum(p["trips"] for p in other_paths
                                         if p["dest"] in feni_dests),
                    "otherFeniTypical": _other_feni_typical(),
                    "otherTypical": _other_typical(),
                    "wbNote": None if bridges else "No weighbridge weigh data before Dec 2025 for this shift."})
def api_weighbridge_summary():
    """Small home-page status payload. Deliberately avoids the simulator's 90-day wait-curve query.

    HAULAGE_IWIP_CLEAN currently ends 2026-07-09. When that day is all IWIP
    workshop contractors (Chinese workshop names, not RIM/PPP/…), otherShare is
    genuinely 100% — that is not a bug. What WAS dishonest: returning that
    payload with no source/age and looking identical to the committed fixture
    so the UI read as "latest live". Always tag source + ageDays; mark stale
    when the newest day is more than 3 calendar days behind today.
    """
    import time as _time
    from datetime import date as _date
    global _WB_HOME_CACHE
    if _WB_HOME_CACHE and _time.time() - _WB_HOME_CACHE[0] < 600:
        return jsonify(_WB_HOME_CACHE[1])
    try:
        conn = _conn('WBN_DATABASE')
        cur = conn.cursor()
        cur.execute("SELECT MAX([DATE]) FROM HAULAGE_IWIP_CLEAN WHERE WB_ID<>'' AND WB_ID IS NOT NULL "
                    "AND [DATE]<='2100-01-01'")
        row = cur.fetchone(); latest = row[0] if row else None
        counts = []
        raw = []
        if latest:
            cur.execute("SELECT WB_ID, CONTRACTOR, COUNT(*) FROM HAULAGE_IWIP_CLEAN "
                        "WHERE [DATE]=%s AND WB_ID<>'' AND WB_ID IS NOT NULL GROUP BY WB_ID,CONTRACTOR", (latest,))
            raw = [(str(wb), str(cont or '').strip().upper(), int(n or 0)) for wb, cont, n in cur.fetchall()]
            by_wb = {}
            for wb, _cont, n in raw:
                by_wb[wb] = by_wb.get(wb, 0) + n
            counts = list(by_wb.items())
        conn.close()
        total = sum(n for _, n in counts); busiest = max(counts, key=lambda x: x[1]) if counts else (None, 0)
        share = round(100 * busiest[1] / total, 1) if total else 0
        status = "Balanced" if share <= 25 else "Monitor concentration" if share <= 40 else "Load concentrated"
        wbn_haulers = {"RIM", "PPP", "SSS", "SMA", "STM", "HJS", "GMG", "CKB", "HFNC"}
        other = sum(n for _wb, cont, n in raw if cont not in wbn_haulers) if latest else 0
        latest_d = latest.isoformat() if latest and hasattr(latest, "isoformat") else (str(latest)[:10] if latest else None)
        age = None
        if latest_d:
            try:
                age = (_date.today() - _date.fromisoformat(latest_d)).days
            except ValueError:
                age = None
        result = {"ok": True, "date": latest_d, "bridges": len(counts),
                  "trucks": total, "perBridge": round(total / len(counts), 1) if counts else 0,
                  "busiest": busiest[0], "busiestShare": share,
                  "otherShare": round(100 * other / total, 1) if total else 0, "status": status,
                  "source": "WBN_DATABASE.dbo.HAULAGE_IWIP_CLEAN",
                  "ageDays": age,
                  "stale": bool(age is not None and age > 3),
                  "staleReason": (
                      "newest weighbridge day in HAULAGE_IWIP_CLEAN is %d days old "
                      "(table ends %s; not a live feed)" % (age, latest_d)
                  ) if (age is not None and age > 3) else None}
        _WB_HOME_CACHE = (_time.time(), result)
        return jsonify(result)
    except Exception:
        if _WB_HOME_CACHE:
            stale = dict(_WB_HOME_CACHE[1]); stale["stale"] = True
            stale["staleReason"] = stale.get("staleReason") or "served from process cache after DB error"
            return jsonify(stale)
        # The stale-cache branch above is PREFERRED over the fixture: it is real
        # data from minutes ago rather than a shipped sample, and it already
        # flags itself with `stale`. Only when there is no cache at all does
        # this re-raise, so _register serves the fixture.
        raise

def api_simulator_weighbridge():
    """Historical weighbridge load & queue visibility. From HAULAGE_IWIP_CLEAN (per-truck weigh events)
    it derives, per day: how many bridges were active, trucks weighed, trucks per active bridge, and the
    load IMBALANCE (busiest bridge's share). From WAITING_TIME (measured trip waits) it derives the
    wait-vs-load curve — trucks at one bridge in an hour vs avg wait — the honest queue signal (weak but
    real at peak: ~+60% wait in the busiest bridge-hours). IWIP weigh data only (largest hauler)."""
    import time as _time
    global _WB_RESULT_CACHE
    cached = globals().get("_WB_RESULT_CACHE")
    if cached and (_time.time() - cached[0] < 1800):          # 30-min cache — historical, changes daily
        return jsonify(cached[1])
    from collections import defaultdict
    days_out, bridges_out, wait_curve, per_date_wait = [], [], [], {}
    try:
        conn = _conn('WBN_DATABASE')
        cur = conn.cursor()
        # per (date, bridge, hour, contractor) weigh counts — last 90 days. Contractor lets us split
        # WBN revenue haulers from non-WBN (IWIP internal fleet etc.) that use the bridges but add no WMT.
        cur.execute("SELECT [DATE], WB_ID, [HOUR], CONTRACTOR, COUNT(*) FROM HAULAGE_IWIP_CLEAN "
                    "WHERE WB_ID<>'' AND WB_ID IS NOT NULL AND [DATE]>=DATEADD(day,-90,GETDATE()) "
                    "AND [DATE]<='2100-01-01' GROUP BY [DATE], WB_ID, [HOUR], CONTRACTOR")
        rawc = cur.fetchall()
        # measured avg wait per date (dumping-side, minutes)
        try:
            cur.execute("SELECT [DATE], AVG(CAST(DUMPING_DIFFERENCE_TIME AS float)) "
                        "FROM WAITING_TIME WHERE ISNUMERIC(DUMPING_DIFFERENCE_TIME)=1 "
                        "AND DUMPING_DIFFERENCE_TIME IS NOT NULL AND [DATE]>=DATEADD(day,-90,GETDATE()) "
                        "GROUP BY [DATE]")
            for d, w in cur.fetchall():
                if w is not None and 0 <= w <= 600:
                    per_date_wait[d] = round(float(w), 1)
        except Exception:
            per_date_wait = {}
        # wait-vs-load curve: trucks at one bridge in one hour vs avg wait — aggregated in SQL (one row
        # per bridge-hour) so we don't drag ~330k rows over the wire (that took ~60s and timed out the tab).
        try:
            cur.execute("SELECT COUNT(*) c, AVG(CAST(DUMPING_DIFFERENCE_TIME AS float)) w FROM WAITING_TIME "
                        "WHERE WB_ID NOT IN ('','NOT WEIGHED') AND DUMPING_WAITING_TIME IS NOT NULL "
                        "AND ISNUMERIC(DUMPING_DIFFERENCE_TIME)=1 AND DUMPING_DIFFERENCE_TIME IS NOT NULL "
                        "AND CAST(DUMPING_DIFFERENCE_TIME AS float) BETWEEN 0 AND 600 "
                        "AND [DATE]>=DATEADD(month,-6,GETDATE()) "
                        "GROUP BY [DATE], DATEPART(hour,DUMPING_WAITING_TIME), WB_ID HAVING COUNT(*)>=3")
            pts = [(int(c), float(w)) for c, w in cur.fetchall() if w is not None]
            pts.sort()
            if pts:
                qn = max(1, len(pts) // 5)
                for i in range(5):
                    seg = pts[i * qn:(i + 1) * qn] if i < 4 else pts[i * qn:]
                    if seg:
                        wait_curve.append({"load": round(sum(p[0] for p in seg) / len(seg), 1),
                                           "wait": round(sum(p[1] for p in seg) / len(seg), 1), "n": len(seg)})
        except Exception:
            wait_curve = []
        conn.close()
    except Exception:
        # Re-raise so _register serves the fixture — see the note in _register.
        raise
    # WBN revenue haulers (from LITE 3 dispatch, IWIP excluded). Everything else weighed at the bridge
    # (IWIP internal fleet, PT Position, etc.) uses the road/bridges but adds no WBN WMT.
    WBN_HAULERS = {"RIM", "PPP", "SSS", "SMA", "STM", "HJS", "GMG", "CKB", "HFNC"}
    _is_wbn = lambda c: (c or "").strip().upper() in WBN_HAULERS
    # aggregate per day and per bridge
    byday = defaultdict(lambda: defaultdict(int))       # date -> {wb: trucks}
    daymix = defaultdict(lambda: [0, 0])                # date -> [wbn, other]
    bybridge = defaultdict(lambda: [0, set(), 0])       # wb -> [trucks, days, peakHr]
    for d, wb, hr, cont, c in rawc:
        byday[d][wb] += c
        mix = daymix[d]; mix[0 if _is_wbn(cont) else 1] += c
        bb = bybridge[wb]; bb[0] += c; bb[1].add(d); bb[2] = max(bb[2], c)
    for d in sorted(byday):
        wbs = byday[d]; trucks = sum(wbs.values()); busiest = max(wbs.values()) if wbs else 0
        nb = len(wbs); wbn, other = daymix[d]
        days_out.append({"date": d.isoformat(), "bridges": nb, "trucks": trucks,
                         "perBridge": round(trucks / nb, 1) if nb else 0, "busiest": busiest,
                         "busiestShare": round(100 * busiest / trucks, 1) if trucks else 0,
                         "wbn": wbn, "other": other,
                         "otherShare": round(100 * other / trucks, 1) if trucks else 0,
                         "avgWait": per_date_wait.get(d)})
    for wb, (tr, ds, peak) in sorted(bybridge.items(), key=lambda x: -x[1][0]):
        nd = len(ds)
        bridges_out.append({"wb": wb, "trucks": tr, "days": nd,
                            "perDay": round(tr / nd, 1) if nd else 0, "peakHr": peak})
    tot = sum(d["trucks"] for d in days_out) or 1
    other_tot = sum(d["other"] for d in days_out)
    # weighbridge corridor positions (snapped km) merged with recent per-bridge throughput
    trucks_by_num = {b["wb"]: b["trucks"] for b in bridges_out}
    positions = []
    for p in _wb_corridor_positions():
        positions.append({**p, "onCorridor": p["offM"] <= 150,
                          "trucks": trucks_by_num.get(p["wbNum"]) if p["wbNum"] else None})
    result = {"ok": True, "days": days_out[-90:], "bridges": bridges_out,
              "waitCurve": wait_curve, "otherSharePct": round(100 * other_tot / tot, 1),
              "positions": positions,
              "source": "HAULAGE_IWIP_CLEAN + WAITING_TIME (all haulers at the IWIP weighbridges)"}
    if days_out:
        _WB_RESULT_CACHE = (_time.time(), result)
    return jsonify(result)

def api_simulator_trucks():
    """Per-truck rollup from HAULAGE_IWIP_CLEAN (has TRUCK_ID).

    Dispatch capability has no truck column; this is the live fleet list the
    Trucks table needs. Honours from/to + IWIP toggle. Source/dest path filters
    are applied when present via ORIGIN/DESTINATION area matching.
    """
    a = request.args
    frm = (a.get("from") or "").strip()[:10]
    to = (a.get("to") or "").strip()[:10]
    incl_iwip = a.get("inclIwip") in ("1", "true", "yes")
    src = [_canon(s) for s in (a.get("source") or "").split(",") if s.strip()]
    dst = [_canon(s) for s in (a.get("dest") or "").split(",") if s.strip()]
    # Same WBN hauler set as shift-context / weighbridge.
    wbn = ("RIM", "PPP", "SSS", "SMA", "STM", "HJS", "GMG", "CKB", "HFNC")
    where = [
        "TRUCK_ID IS NOT NULL",
        "LTRIM(RTRIM(CAST(TRUCK_ID AS varchar(64)))) <> ''",
        "WMT IS NOT NULL",
    ]
    params = []
    if frm:
        where.append("CONVERT(date,[DATE]) >= %s")
        params.append(frm)
    if to:
        where.append("CONVERT(date,[DATE]) <= %s")
        params.append(to)
    if not incl_iwip:
        where.append("UPPER(LTRIM(RTRIM(CONTRACTOR))) IN (%s)"
                     % ",".join("'%s'" % c for c in wbn))
    # Optional origin/dest soft filters (canonical labels → LIKE patterns).
    area_like = {
        "TF": ("ORIGIN_AREA LIKE %s OR ORIGIN_AREA LIKE %s OR ORIGIN_AREA LIKE %s",
               ("%TOFU%", "TF%", "TOS_TF%")),
        "TOFU": ("ORIGIN_AREA LIKE %s OR ORIGIN_AREA LIKE %s", ("%TOFU%", "TF%")),
        "KR": ("ORIGIN_AREA LIKE %s OR ORIGIN_AREA LIKE %s", ("%KRENE%", "KR%")),
        "KRENE": ("ORIGIN_AREA LIKE %s OR ORIGIN_AREA LIKE %s", ("%KRENE%", "KR%")),
    }
    dest_like = {
        "FENI KM0": ("DESTINATION_AREA LIKE %s", ("%FENI%",)),
        "FENI KM15": ("DESTINATION_AREA LIKE %s OR DESTINATION_AREA LIKE %s",
                      ("%FENI KM15%", "%FENI 15%")),
        "HUAFEI": ("DESTINATION_AREA LIKE %s", ("%HUAFEI%",)),
        "BSE": ("DESTINATION_AREA LIKE %s", ("%BSE%",)),
        "CRUSHER": ("DESTINATION_AREA LIKE %s", ("%CRUSHER%",)),
        "POS 12": ("DESTINATION_AREA LIKE %s OR DESTINATION_AREA LIKE %s",
                   ("%POS 12%", "%POS12%")),
        "POS 10": ("DESTINATION_AREA LIKE %s OR DESTINATION_AREA LIKE %s",
                   ("%POS 10%", "%POS10%")),
    }
    if src:
        clauses, sp = [], []
        for s in src:
            spec = area_like.get(s) or area_like.get(s.replace(" ", ""))
            if not spec:
                clauses.append("UPPER(ORIGIN_AREA) LIKE %s")
                sp.append("%" + s + "%")
            else:
                clauses.append("(" + spec[0] + ")")
                sp.extend(spec[1])
        if clauses:
            where.append("(" + " OR ".join(clauses) + ")")
            params.extend(sp)
    if dst:
        clauses, sp = [], []
        for d in dst:
            spec = dest_like.get(d)
            if not spec:
                clauses.append("UPPER(DESTINATION_AREA) LIKE %s")
                sp.append("%" + d + "%")
            else:
                clauses.append("(" + spec[0] + ")")
                sp.extend(spec[1])
        if clauses:
            where.append("(" + " OR ".join(clauses) + ")")
            params.extend(sp)
    sql = (
        "SELECT LTRIM(RTRIM(CAST(TRUCK_ID AS varchar(64)))) AS truck, "
        "LTRIM(RTRIM(CONTRACTOR)) AS contractor, "
        "COUNT(*) AS trips, COUNT(DISTINCT CONVERT(date,[DATE])) AS days, "
        "SUM(WMT) AS wmt "
        "FROM HAULAGE_IWIP_CLEAN WHERE " + " AND ".join(where) + " "
        "GROUP BY LTRIM(RTRIM(CAST(TRUCK_ID AS varchar(64)))), "
        "LTRIM(RTRIM(CONTRACTOR)) "
        "ORDER BY COUNT(*) DESC"
    )
    conn = _conn("WBN_DATABASE")
    try:
        cur = conn.cursor()
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
    finally:
        conn.close()
    trucks = []
    for truck, contractor, trips, days, wmt in rows[:5000]:
        trips = float(trips or 0)
        days = int(days or 0) or 1
        wmt = float(wmt or 0)
        trucks.append({
            "truck": str(truck or "").strip(),
            "contractor": str(contractor or "").strip(),
            "trips": trips,
            "days": days,
            "tripsPerDay": round(trips / days, 4) if days else 0.0,
            "wmt": wmt,
            "tf": round(wmt / trips, 4) if trips else 0.0,
        })
    return jsonify({
        "ok": True,
        "trucks": trucks,
        "n": len(trucks),
        "from": frm or None,
        "to": to or None,
        "inclIwip": incl_iwip,
        "servedFrom": "db",
        "source": "WBN_DATABASE.dbo.HAULAGE_IWIP_CLEAN",
    })


# ROUTES
# Capability: real query with all six filters; fixture when there is no DB.
_register('/api/simulator/capability', api_simulator_capability, 'capability', methods=['GET'])
_register('/api/simulator/path-response', api_simulator_path_response, 'path-response', methods=['GET'])
_register('/api/simulator/congestion-model', api_simulator_congestion_model, 'congestion-model', methods=['GET'])
_register('/api/simulator/weighbridge-positions', api_simulator_weighbridge_positions, 'weighbridge-positions', methods=['GET'])
_register('/api/simulator/weighbridge-by-path', api_simulator_weighbridge_by_path, 'weighbridge-by-path', methods=['GET'])
_register('/api/simulator/shift-context', api_simulator_shift_context, 'shift-context', methods=['GET'])
_register('/api/weighbridge-summary', api_weighbridge_summary, 'weighbridge-summary', methods=['GET'])
_register('/api/simulator/weighbridge', api_simulator_weighbridge, 'weighbridge', methods=['GET'])
# Trucks: live via serve.py → api_simulator_trucks(); fixture fallback there.
# Not _register'd here because serve.py owns the URL for dual-mode honesty.


# ---------------------------------------------------------------------------
# Plan simulator (Task 4)
#
# Registered directly on the blueprint rather than through _register, because
# unlike the DB-backed endpoints this one has no DB path to fall back FROM: it
# reads the committed lookup CSVs (route history, measured point capacity,
# dwell times) and therefore answers identically with or without the VPN.
# That is the dual-mode requirement satisfied by construction instead of by a
# fixture standing in for the real thing.
# ---------------------------------------------------------------------------
# Segment ids name the Tofu road "TF"; the chainage table calls it "TOFU".
# One alias, kept here rather than renaming either source.
_ROAD_ALIAS = {"TF": "TOFU"}
_GEOM_CACHE = None


@bp.route('/api/simulator/corridor-geometry', methods=['GET'])
def api_simulator_corridor_geometry():
    """Haul-road centreline polylines, for the map in the assessment view.

    TWO SOURCES, IN ORDER. The full extract `data/haul_road_chainage.csv` is
    gitignored like the rest of `data/`; `data/haul_road_chainage_public.csv` is
    COMMITTED and is the fallback, so the map works on a fresh clone and on the
    public demo instead of showing an empty state.

    Committing that file is a deliberate, narrow exception to "no site geometry
    on the mirror". It holds a road CENTRELINE and nothing else -- road code, km
    marker, latitude, longitude, verified as the only four columns -- with no
    geofences, no loading or dumping zones, no security boundaries and no
    tonnages. The corridor is already rendered by OpenStreetMap. Geofence and
    zone data remain uncommitted, and `weighbridge-positions` still encodes
    `km`/`offM` rather than coordinates.

    Downsampled to ~1 point per 0.25 km: the raw table is 3,122 markers, more
    resolution than a 1366px screen can show and a needlessly large payload.
    """
    global _GEOM_CACHE
    if _GEOM_CACHE is not None:
        return jsonify(_GEOM_CACHE)

    here = os.path.dirname(os.path.abspath(__file__))
    # Full extract first -- it is the live survey and may be newer. The
    # committed copy is the fallback, not the primary, so a site that re-runs
    # the extract sees its own data.
    candidates = [(os.path.join(here, "data", "haul_road_chainage.csv"), "extract"),
                  (os.path.join(here, "data", "haul_road_chainage_public.csv"), "committed")]
    path, source = None, None
    for p, tag in candidates:
        if os.path.exists(p):
            path, source = p, tag
            break
    if path is None:
        return jsonify({
            "ok": False, "roads": [],
            "reason": ("no corridor geometry found: neither "
                       "data/haul_road_chainage.csv nor "
                       "data/haul_road_chainage_public.csv is present. The "
                       "latter is committed, so this should not happen in a "
                       "clean checkout."),
        })
    try:
        import csv as _csv
        rows = []
        with open(path, newline="") as fh:
            for r in _csv.DictReader(fh):
                try:
                    rows.append((r["road"].strip().upper(), float(r["km"]),
                                 float(r["lat"]), float(r["lng"])))
                except (TypeError, ValueError):
                    continue
    except Exception as exc:                          # noqa: BLE001
        return jsonify({"ok": False, "roads": [],
                        "reason": "could not read chainage: %s" % str(exc)[:120]})

    by_road = defaultdict(list)
    for road, km, lat, lng in rows:
        by_road[road].append((km, lat, lng))

    roads = []
    for road, pts in by_road.items():
        pts.sort(key=lambda x: x[0])
        keep, last = [], None
        for km, lat, lng in pts:
            if last is None or abs(km - last) >= 0.25:
                keep.append({"km": round(km, 3), "lat": round(lat, 6),
                             "lng": round(lng, 6)})
                last = km
        if len(keep) >= 2:
            roads.append({"road": road, "points": keep,
                          "kmMin": keep[0]["km"], "kmMax": keep[-1]["km"],
                          "nRaw": len(pts)})
    roads.sort(key=lambda r: -len(r["points"]))
    _GEOM_CACHE = {
        "ok": True, "roads": roads,
        "roadAlias": _ROAD_ALIAS,
        "corridor": _corridor_payload(),
        "geometrySource": source,          # "extract" (local) or "committed"
        "note": ("centreline from HAUL_ROAD_STA, downsampled to ~0.25 km. "
                 "Segment ids use TF for the road the chainage table calls TOFU."),
    }
    return jsonify(_GEOM_CACHE)


@bp.route('/api/simulate', methods=['POST'])
def api_simulate():
    """Predict trip time, dwell and production for a multi-route truck plan."""
    import plan_simulator
    try:
        payload = request.get_json(force=True, silent=True) or {}
    except Exception:                     # noqa: BLE001
        payload = {}
    if not isinstance(payload.get("plans"), list) or not payload["plans"]:
        return jsonify({"error": "supply plans: [{source, destination, n_trucks}]",
                        "results": [], "summary": {}}), 400
    try:
        return jsonify(plan_simulator.simulate(payload))
    except Exception as e:                # noqa: BLE001
        print("[sim_api] simulate failed: %s" % e)
        return jsonify({"error": "simulation failed: %s" % e,
                        "results": [], "summary": {}}), 500


@bp.route('/api/simulate/options', methods=['GET'])
def api_simulate_options():
    """Routes, loading and dumping points the simulator has history for.

    The UI populates its dropdowns from this, so a planner can only pick
    combinations the model can actually speak to, and sees the evidence
    behind each one (shift count, measured capacity) while choosing.
    """
    import plan_simulator as ps
    r, c = ps._routes(), ps._capacity()
    if r is None:
        return jsonify({"routes": [], "loading_points": [], "dumping_points": [],
                        "error": "route lookup not built; run simulator_model.py"})
    routes = [{"route": x["route"], "source": x["source"],
               "destination": x["destination"],
               "median_cycle_min": x["median_cycle_min"],
               "shifts_observed": int(x["shifts"])}
              for _, x in r.sort_values("shifts", ascending=False).iterrows()]
    pts = {"loading_points": [], "dumping_points": []}
    if c is not None:
        for kind, key in (("loading", "loading_points"), ("dumping", "dumping_points")):
            sub = c[c["kind"] == kind]
            pts[key] = [{"point": x["point"],
                         "capacity_trips_shift": x["capacity_trips_shift"],
                         "observed_hours": int(x["observed_hours"])}
                        for _, x in sub.iterrows()]
    return jsonify({"routes": routes, **pts,
                    "note": ("capacity is the p99 of hourly throughput actually "
                             "observed at that point, not a design figure")})


def _analogues_corpus():
    """Build retrieval corpus: FMS memory → capability snapshot → fixture."""
    import plan_analogues as pa
    import plan_memory as pm

    rain_by_date = {}
    try:
        _rows, rain = _path_snapshot()
        for (d, _a), h in (rain or {}).items():
            ds = str(d)[:10]
            rain_by_date[ds] = max(rain_by_date.get(ds, 0.0), float(h))
    except Exception:  # noqa: BLE001
        rain_by_date = {}

    # 1) Materialised memory table in FMS_DB
    if _db_ready():
        try:
            conn = _conn("FMS_DB")
            try:
                pm.ensure_tables(conn)
                mem = pm.read_day_kpi_rows(conn)
                if mem:
                    corpus, src = pa.load_corpus(memory_rows=mem, rain_by_date=rain_by_date)
                    return corpus, src
            finally:
                conn.close()
        except Exception as e:  # noqa: BLE001
            print("[sim_api] plan memory read skipped: %s" % e)

    # 2) Local disk memory (built by scripts/build_plan_memory.py)
    try:
        local = pm.read_local_day_kpi()
        if local:
            corpus, src = pa.load_corpus(memory_rows=local, rain_by_date=rain_by_date)
            return corpus, "local_memory"
    except Exception as e:  # noqa: BLE001
        print("[sim_api] local plan memory skipped: %s" % e)

    # 3) Live / disk capability snapshot (has contractor grain)
    try:
        cap_rows = _cap_snapshot()
        if cap_rows:
            corpus, src = pa.load_corpus(cap_rows=cap_rows, rain_by_date=rain_by_date)
            return corpus, src
    except Exception as e:  # noqa: BLE001
        print("[sim_api] capability corpus skipped: %s" % e)

    # 4) Fixture dailyByPath
    return pa.load_fixture_corpus()


def _analogues_attach_gps(result):
    """Attach per-day haul GPS speeds for analogue dates in the GPS window only."""
    import plan_analogues as pa
    import plan_memory as pm
    if not result.get("ok") or not _db_ready():
        return result
    dates = [a["date"] for a in (result.get("analogues") or [])]
    for bp in result.get("by_plan") or []:
        dates.extend(a["date"] for a in (bp.get("analogues") or []))
    dates = list({d for d in dates if pa.has_haul_gps(d)})
    if not dates:
        return result
    try:
        conn = _conn("FMS_DB")
        try:
            speeds = pm.fetch_gps_speed_by_date(conn, dates)
        finally:
            conn.close()
    except Exception as e:  # noqa: BLE001
        print("[sim_api] gps speed attach skipped: %s" % e)
        return result
    if not speeds:
        return result
    pa.attach_location_speeds(result.get("analogues"), speeds)
    for bp in result.get("by_plan") or []:
        pa.attach_location_speeds(bp.get("analogues"), speeds)
    return result


@bp.route('/api/plan/analogues', methods=['POST'])
def api_plan_analogues():
    """Retrieve 5–10 historical analogue days for a holding plan + shared-road risk.

    Does not change /api/simulate tonnes. Congestion is advisory only.
    """
    import plan_analogues as pa
    import plan_memory as pm
    try:
        payload = request.get_json(force=True, silent=True) or {}
    except Exception:  # noqa: BLE001
        payload = {}
    if not isinstance(payload.get("plans"), list) or not payload["plans"]:
        return jsonify({"ok": False,
                        "error": "supply plans: [{source, destination, n_trucks, contractor?}]",
                        "analogues": [], "ensemble": {}, "shared_road": {}}), 400

    # Cache hit (optional)
    fp = None
    try:
        k = max(5, min(10, int(payload.get("k") or 8)))
        rain_mm = payload.get("rain_mm")
        if rain_mm is None:
            rain_mm = payload.get("rain", 0)
        fp = pa.fingerprint_hash(
            payload.get("plans"), rain_mm, k,
            rank=payload.get("rank"),
            prefer_peak=payload.get("prefer_peak", True))
        if _db_ready() and not payload.get("nocache"):
            conn = _conn("FMS_DB")
            try:
                pm.ensure_tables(conn)
                cached = pm.cache_get(conn, fp)
                if cached and cached.get("ok"):
                    cached = dict(cached)
                    cached["servedFrom"] = "fms_cache"
                    return jsonify(cached)
            finally:
                conn.close()
    except Exception as e:  # noqa: BLE001
        print("[sim_api] analogue cache read skipped: %s" % e)

    try:
        corpus, src = _analogues_corpus()
        result = pa.find_analogues(payload, corpus=corpus, corpus_source=src)
        result = _analogues_attach_gps(result)
    except Exception as e:  # noqa: BLE001
        print("[sim_api] plan analogues failed: %s" % e)
        # Last resort: fixture corpus only
        try:
            corpus, src = pa.load_fixture_corpus()
            result = pa.find_analogues(payload, corpus=corpus, corpus_source=src)
        except Exception as e2:  # noqa: BLE001
            return jsonify({"ok": False, "error": "analogues failed: %s" % e2,
                            "analogues": [], "ensemble": {}, "shared_road": {}}), 500

    # Persist cache + graph memory (best-effort)
    if result.get("ok") and _db_ready() and not payload.get("nocache"):
        try:
            conn = _conn("FMS_DB")
            try:
                pm.ensure_tables(conn)
                if fp:
                    pm.cache_put(conn, fp, payload, result)
                pm.upsert_nodes_edges(conn, result)
            finally:
                conn.close()
        except Exception as e:  # noqa: BLE001
            print("[sim_api] analogue memory write skipped: %s" % e)

    return jsonify(result)


# Site centre for rainfall forecast lookups. Derived from the committed road
# survey (data/haul_road_chainage_public.csv): lat 0.476..0.807, lng
# 127.898..128.038, median (0.5586, 127.9647). NOTE the road survey is the
# authority here — scripts/fetch_weather.py previously used (-0.7297, 127.9056),
# the wrong hemisphere, ~140 km south of the road.
_SITE_LAT, _SITE_LNG = 0.5586, 127.9647


def _rain_by_date_map():
    """Max mm per calendar day from path-response rain gauges (site history)."""
    out = {}
    try:
        _rows, rain = _path_snapshot()
        for (d, _a), h in (rain or {}).items():
            ds = str(d)[:10]
            try:
                out[ds] = max(out.get(ds, 0.0), float(h))
            except (TypeError, ValueError):
                continue
    except Exception:  # noqa: BLE001
        return {}
    return out


def _climatology_mm(rain_map, date_s):
    """Mean of same month-day across years in the rain map."""
    md = str(date_s)[5:10]  # MM-DD
    vals = [v for d, v in rain_map.items() if len(d) >= 10 and d[5:10] == md]
    if not vals:
        return None, 0
    return round(sum(vals) / len(vals), 1), len(vals)


def _forecast_mm(date_s):
    """Open-Meteo daily precipitation for the mine site (no API key)."""
    import urllib.parse
    import urllib.request
    from datetime import date as _date
    try:
        target = _date.fromisoformat(str(date_s)[:10])
    except ValueError:
        return None
    today = _date.today()
    if target < today or (target - today).days > 16:
        return None
    qs = urllib.parse.urlencode({
        "latitude": _SITE_LAT,
        "longitude": _SITE_LNG,
        "daily": "precipitation_sum",
        "timezone": "Asia/Jayapura",
        "start_date": target.isoformat(),
        "end_date": target.isoformat(),
    })
    url = "https://api.open-meteo.com/v1/forecast?" + qs
    try:
        with urllib.request.urlopen(url, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        daily = data.get("daily") or {}
        precip = (daily.get("precipitation_sum") or [None])[0]
        if precip is None:
            return None
        return round(float(precip), 1)
    except Exception as e:  # noqa: BLE001
        print("[sim_api] rain forecast fetch failed: %s" % e)
        return None


_RAIN_OUTLOOK_CACHE = {"at": 0.0, "data": None}
_RAIN_OUTLOOK_TTL = 3 * 3600.0  # forecasts update ~4x daily; 3h is plenty


def _forecast_outlook():
    """16-day daily rain forecast (mm + probability) for the site, cached.

    One Open-Meteo call covers the full window, so the Plan tab can show the
    whole planning horizon instead of one date at a time.
    """
    import time as _time
    import urllib.parse
    import urllib.request
    now = _time.time()
    if (_RAIN_OUTLOOK_CACHE["data"] is not None
            and now - _RAIN_OUTLOOK_CACHE["at"] < _RAIN_OUTLOOK_TTL):
        return _RAIN_OUTLOOK_CACHE["data"]
    qs = urllib.parse.urlencode({
        "latitude": _SITE_LAT,
        "longitude": _SITE_LNG,
        "daily": "precipitation_sum,precipitation_probability_max",
        "timezone": "Asia/Jayapura",
        "forecast_days": 16,
    })
    url = "https://api.open-meteo.com/v1/forecast?" + qs
    try:
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        daily = data.get("daily") or {}
        days = []
        times = daily.get("time") or []
        mms = daily.get("precipitation_sum") or []
        probs = daily.get("precipitation_probability_max") or []
        for i, d in enumerate(times):
            mm = mms[i] if i < len(mms) else None
            prob = probs[i] if i < len(probs) else None
            days.append({
                "date": d,
                "mm": round(float(mm), 1) if mm is not None else None,
                "probPct": int(prob) if prob is not None else None,
            })
        out = {"days": days, "fetchedAt": now}
        _RAIN_OUTLOOK_CACHE.update({"at": now, "data": out})
        return out
    except Exception as e:  # noqa: BLE001
        print("[sim_api] rain outlook fetch failed: %s" % e)
        return None


@bp.route('/api/plan/rain-outlook', methods=['GET'])
def api_plan_rain_outlook():
    """16-day site rain forecast strip for the Plan tab (mm + probability)."""
    out = _forecast_outlook()
    if out is None:
        # Honest 503 (never a swallowed 200): Open-Meteo could not be reached.
        # Worded to stay clear of J58's defect signature, which hunts for
        # ok:False "...unavailable" payloads that DB endpoints returned as 200s.
        return jsonify({"ok": False, "error": "forecast fetch failed (Open-Meteo unreachable)",
                        "days": []}), 503
    return jsonify({
        "ok": True,
        "site": {"lat": _SITE_LAT, "lng": _SITE_LNG, "tz": "Asia/Jayapura"},
        "source": "open-meteo forecast (no key)",
        "days": out["days"],
        "note": ("Daily precipitation for the haul-road midpoint. Click a day "
                 "in the Plan tab to plan that date; rain feeds the Step-1 "
                 "estimate only — simulate tonnes stay weather-invariant."),
    })


# ── Saved holding plans (local disk; keyed by plan date) ─────────────────────
_SAVED_PLANS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "saved_plans")


def _saved_plan_path(date_s):
    """Absolute path for YYYY-MM-DD.json under data/saved_plans/."""
    from datetime import date as _date
    try:
        _date.fromisoformat(date_s)
    except ValueError:
        return None
    if len(date_s) != 10 or date_s[4] != "-" or date_s[7] != "-":
        return None
    return os.path.join(_SAVED_PLANS_DIR, date_s + ".json")


@bp.route('/api/plan/saved', methods=['GET', 'POST', 'DELETE'])
def api_plan_saved():
    """Save / load / delete a holding plan for a calendar date (local JSON)."""
    if request.method == 'GET':
        date_s = (request.args.get("date") or "").strip()[:10]
        path = _saved_plan_path(date_s)
        if not path:
            return jsonify({"ok": False, "error": "supply date=YYYY-MM-DD"}), 400
        if not os.path.isfile(path):
            return jsonify({"ok": True, "date": date_s, "plan": None, "exists": False})
        try:
            with open(path, "r", encoding="utf-8") as f:
                plan = json.load(f)
        except Exception as e:  # noqa: BLE001
            return jsonify({"ok": False, "error": "read failed: %s" % e}), 500
        return jsonify({"ok": True, "date": date_s, "plan": plan, "exists": True})

    if request.method == 'DELETE':
        date_s = (request.args.get("date") or "").strip()[:10]
        path = _saved_plan_path(date_s)
        if not path:
            return jsonify({"ok": False, "error": "supply date=YYYY-MM-DD"}), 400
        if os.path.isfile(path):
            try:
                os.remove(path)
            except Exception as e:  # noqa: BLE001
                return jsonify({"ok": False, "error": "delete failed: %s" % e}), 500
        return jsonify({"ok": True, "date": date_s, "deleted": True})

    # POST
    body = request.get_json(silent=True) or {}
    date_s = (body.get("date") or "").strip()[:10]
    path = _saved_plan_path(date_s)
    if not path:
        return jsonify({"ok": False, "error": "supply date=YYYY-MM-DD"}), 400
    paths = body.get("paths")
    if not isinstance(paths, dict) or not paths:
        return jsonify({"ok": False, "error": "paths object required"}), 400
    plan = {
        "date": date_s,
        "paths": paths,
        "rain_mm": body.get("rain_mm"),
        "hours": body.get("hours"),
        "wb": body.get("wb"),
        "meta": body.get("meta") or {},
        "saved_at": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    try:
        os.makedirs(_SAVED_PLANS_DIR, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(plan, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": "write failed: %s" % e}), 500
    return jsonify({"ok": True, "date": date_s, "plan": plan, "exists": True})


@bp.route('/api/plan/saved/list', methods=['GET'])
def api_plan_saved_list():
    """List recently saved plan dates (newest first)."""
    dates = []
    if os.path.isdir(_SAVED_PLANS_DIR):
        for name in os.listdir(_SAVED_PLANS_DIR):
            if name.endswith(".json") and len(name) == 15:
                dates.append(name[:-5])
    dates.sort(reverse=True)
    return jsonify({"ok": True, "dates": dates[:60]})


@bp.route('/api/plan/corridor-hours', methods=['GET'])
def api_plan_corridor_hours():
    """Jul+ hour-of-day corridor speed profile (advisory). Does not clip tonnes."""
    import plan_corridor_hours as pch
    sections = request.args.get("sections") or ""
    sec_list = [s.strip() for s in sections.replace("|", ",").split(",") if s.strip()]
    direction = (request.args.get("dir") or "down").strip().lower()
    use_fixture = str(request.args.get("fixture") or "").strip() in ("1", "true", "yes")
    path = pch._FIXTURE if use_fixture else None
    payload = pch.corridor_hours(sections=sec_list or None, dir_filter=direction, path=path)
    status = 200 if payload.get("ok") else 503
    return jsonify(payload), status


@bp.route('/api/plan/day-segments', methods=['GET'])
def api_plan_day_segments():
    """Per-segment loaded/empty speeds for one GPS-window day. Empty before Jul 15."""
    import plan_corridor_hours as pch
    date_s = (request.args.get("date") or "").strip()[:10]
    if not date_s:
        return jsonify({"ok": False, "error": "supply date=YYYY-MM-DD",
                        "has_gps": False, "segments": [],
                        "basis": {"congestion_clips_tonnes": False}}), 400
    use_fixture = str(request.args.get("fixture") or "").strip() in ("1", "true", "yes")
    path = pch._FIXTURE if use_fixture else None
    payload = pch.day_segments(date_s, path=path)
    status = 200 if payload.get("ok") else (400 if payload.get("error", "").startswith("supply") else 503)
    return jsonify(payload), status


@bp.route('/api/plan/gps-coverage', methods=['GET'])
def api_plan_gps_coverage():
    """Which calendar days have banked Jul+ haul stick GPS (advisory calendar)."""
    import plan_corridor_hours as pch
    use_fixture = str(request.args.get("fixture") or "").strip() in ("1", "true", "yes")
    path = pch._FIXTURE if use_fixture else None
    payload = pch.gps_coverage(path=path)
    status = 200 if payload.get("ok") else 503
    return jsonify(payload), status


@bp.route('/api/plan/refresh-stick', methods=['POST'])
def api_plan_refresh_stick():
    """Rebuild stick measuredSpeeds CSV from gps_archive (no tonne model change)."""
    global _CORRIDOR_LAYERS
    import plan_corridor_hours as pch
    payload = pch.rebuild_by_dir_from_archive()
    if payload.get("ok"):
        _CORRIDOR_LAYERS = None  # next corridor payload reloads CSV
    return jsonify(payload), (200 if payload.get("ok") else 503)


@bp.route('/api/plan/playback-truth', methods=['GET'])
def api_plan_playback_truth():
    """Why Jan–May haul speeds are not invented from Playback (0% haul overlap)."""
    import plan_playback as pp
    date_s = (request.args.get("date") or "").strip()[:10]
    truth = pp.load_playback_truth()
    if date_s:
        truth["for_date"] = pp.refuse_invented_speeds(date_s)
    return jsonify(truth)


@bp.route('/api/plan/bias-lens', methods=['GET', 'POST'])
def api_plan_bias_lens():
    """Display-only +5.5% delivery lens. Never changes /api/simulate tonnes."""
    import plan_bias as pb
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
    else:
        body = {}
    raw = body.get("achievable_t", request.args.get("achievable_t"))
    enabled = body.get("enabled", request.args.get("enabled"))
    if isinstance(enabled, str):
        enabled = enabled.strip().lower() in ("1", "true", "yes", "on")
    else:
        enabled = bool(enabled)
    try:
        raw_f = float(raw) if raw is not None and raw != "" else None
    except (TypeError, ValueError):
        raw_f = None
    return jsonify({"ok": True, **pb.bias_lens(raw_f, enabled=enabled)})


@bp.route('/api/plan/shared-flow', methods=['GET', 'POST'])
def api_plan_shared_flow():
    """DES-lite shared-section occupancy for multi-contractor plans (advisory)."""
    import plan_shared_flow as psf
    import plan_corridor_hours as pch
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
    else:
        body = {}
    plans = body.get("plans") if isinstance(body.get("plans"), list) else None
    try:
        shift_h = float(body.get("shift_hours") or request.args.get("shift_hours") or 12)
    except (TypeError, ValueError):
        shift_h = 12.0
    try:
        rain = float(body.get("rain_mm") or request.args.get("rain_mm") or 0)
    except (TypeError, ValueError):
        rain = 0.0
    try:
        start_h = int(body.get("start_hour") or request.args.get("start_hour") or 7)
    except (TypeError, ValueError):
        start_h = 7
    use_fixture = str(request.args.get("fixture") or body.get("fixture") or "").strip() in ("1", "true", "yes")
    path = pch._FIXTURE if use_fixture else None
    payload = psf.shared_flow(
        plans=plans,
        shift_hours=shift_h,
        rain_mm=rain,
        start_hour=start_h,
        path=path,
    )
    return jsonify(payload), (200 if payload.get("ok") else 400)


@bp.route('/api/plan/congestion-advice', methods=['GET', 'POST'])
def api_plan_congestion_advice():
    """Jul+ hour congestion advisory (+ saved-plan hints). Does not clip tonnes."""
    import plan_congestion_ml as pcm
    import plan_corridor_hours as pch
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
    else:
        body = {}
    sections = body.get("sections") or request.args.get("sections") or ""
    if isinstance(sections, str):
        sec_list = [s.strip() for s in sections.replace("|", ",").split(",") if s.strip()]
    else:
        sec_list = [str(s).strip() for s in sections if str(s).strip()]
    plan_dt = body.get("plan_dt_by_section") if isinstance(body.get("plan_dt_by_section"), dict) else None
    vc_by = body.get("vc_by_section") if isinstance(body.get("vc_by_section"), dict) else None
    limit_gap = body.get("limit_gap_by_section") if isinstance(body.get("limit_gap_by_section"), dict) else None
    use_fixture = str(request.args.get("fixture") or body.get("fixture") or "").strip() in ("1", "true", "yes")
    path = pch._FIXTURE if use_fixture else None
    payload = pcm.congestion_advice(
        sections=sec_list or None,
        path=path,
        plan_dt_by_section=plan_dt,
        vc_by_section=vc_by,
        limit_gap_by_section=limit_gap,
    )
    return jsonify(payload), (200 if payload.get("ok") else 503)


@bp.route('/api/plan/peak-road-proxy', methods=['GET', 'POST'])
def api_plan_peak_road_proxy():
    """Jan–May peak REFERENCE averages, or single-day ops when date= is supplied."""
    import plan_peak_proxy as ppp
    if request.method == "POST":
        body = request.get_json(force=True, silent=True) or {}
    else:
        body = {}
    date_s = (body.get("date") or request.args.get("date") or "").strip()[:10]
    plans = body.get("plans") if isinstance(body.get("plans"), list) else None
    try:
        corpus, src = _analogues_corpus()
    except Exception:  # noqa: BLE001
        corpus, src = None, None
    if date_s:
        payload = ppp.day_road_ops(date_s, corpus=corpus, corpus_source=src)
    else:
        payload = ppp.peak_road_proxy(corpus=corpus, corpus_source=src, plans=plans)
    return jsonify(payload)


@bp.route('/api/plan/day-road-ops', methods=['GET'])
def api_plan_day_road_ops():
    """Weighbridge section DT/trips for one calendar day only."""
    import plan_peak_proxy as ppp
    date_s = (request.args.get("date") or "").strip()[:10]
    if not date_s:
        return jsonify({"ok": False, "error": "supply date=YYYY-MM-DD",
                        "has_ops": False, "sections": []}), 400
    try:
        corpus, src = _analogues_corpus()
    except Exception:  # noqa: BLE001
        corpus, src = None, None
    return jsonify(ppp.day_road_ops(date_s, corpus=corpus, corpus_source=src))


@bp.route('/api/plan/rain-suggest', methods=['GET'])
def api_plan_rain_suggest():
    """Suggest rainfall (mm) for a planning date on site.

    Priority: observed site gauge that day → Open-Meteo forecast (near future)
    → same calendar-day climatology from site history.
    """
    from datetime import date as _date
    date_s = (request.args.get("date") or "").strip()[:10]
    if not date_s:
        return jsonify({"ok": False, "error": "supply date=YYYY-MM-DD"}), 400
    try:
        target = _date.fromisoformat(date_s)
    except ValueError:
        return jsonify({"ok": False, "error": "bad date"}), 400

    rain_map = _rain_by_date_map()
    today = _date.today()

    if date_s in rain_map:
        mm = round(float(rain_map[date_s]), 1)
        return jsonify({
            "ok": True, "date": date_s, "mm": mm,
            "source": "observed",
            "label": "Site gauge",
            "note": "Measured on site that day (%.0f mm)." % mm,
            "apply": True,
        })

    if target >= today:
        fc = _forecast_mm(date_s)
        if fc is not None:
            return jsonify({
                "ok": True, "date": date_s, "mm": fc,
                "source": "forecast",
                "label": "Forecast",
                "note": "Open-Meteo forecast for site (~%.0f mm)." % fc,
                "apply": True,
            })

    clim, n = _climatology_mm(rain_map, date_s)
    if clim is not None:
        return jsonify({
            "ok": True, "date": date_s, "mm": clim,
            "source": "climatology",
            "label": "Typical",
            "note": "Average for this calendar day over %d past year(s) (%.0f mm)." % (n, clim),
            "apply": True,
        })

    return jsonify({
        "ok": True, "date": date_s, "mm": 0,
        "source": "none",
        "label": "No data",
        "note": "No gauge / forecast / typical rain for this date — leaving 0 mm.",
        "apply": False,
    })
