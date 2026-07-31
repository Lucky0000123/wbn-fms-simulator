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
    if name != "path-response" or not isinstance(data, dict):
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

_WB_POS_CACHE = None

_WB_RESULT_CACHE = None

_WB_HOME_CACHE = None

_OTHER_FENI_TYPICAL = None

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

def api_simulator_path_response():
    """Per-path fleet→efficiency response from the historical DB (LITE 3): fits trips/DT = a + b·DT for
    each route so the scenario planner can predict how efficiency (and thus WMT) shifts as you add/remove
    trucks. Only a MEASURED decline (b<0) is later applied — confounded/flat paths stay flat."""
    try:
        conn = _conn('WBN_DATABASE')
        cur = conn.cursor()
        cur.execute("SELECT ORIGIN, DESTINATION, NB_DT, RIT, WMT, [DATE] FROM [DISPATCH RESULTS LITE 3] "
                    "WHERE (CONTRACTOR IS NULL OR CONTRACTOR<>'IWIP') "
                    "AND DATE>=DATEADD(month,-20,GETDATE()) AND NB_DT>0 AND RIT>0 "
                    # ~200 rows carry a NULL DESTINATION. They produced an
                    # unselectable blank entry in the Plan tab's route list.
                    "AND ORIGIN IS NOT NULL AND LTRIM(RTRIM(ORIGIN))<>'' "
                    "AND DESTINATION IS NOT NULL AND LTRIM(RTRIM(DESTINATION))<>''")
        rows = cur.fetchall()
        # per-day rainfall by mine area — TOFU serves TF routes, KAO RAHAI serves KR routes
        rain = {}
        try:
            cur.execute("SELECT [DATE], Area, H2O FROM AVG_RAIN_BY_DATE_AREA "
                        "WHERE Area IN ('TOFU','KAO RAHAI') AND H2O IS NOT NULL "
                        "AND [DATE]>=DATEADD(month,-20,GETDATE())")
            for d, area, h2o in cur.fetchall():
                rain[(d, area)] = float(h2o)
        except Exception:
            rain = {}
        conn.close()
    except Exception:
        # Re-raise so _register serves the fixture. Returning an error payload
        # with HTTP 200 looks like success to the wrapper, so the fallback never
        # fired and this endpoint went blank whenever the VPN dropped.
        raise
    from collections import defaultdict
    # Route labels come from the shared canonicaliser so path keys match the
    # model's vocabulary exactly. The rain gauge is then chosen from that
    # canonical node rather than from a raw-string prefix.
    _kr = _canon
    _area = lambda o: {"TF": "TOFU", "KR": "KAO RAHAI"}.get(_canon(o))

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
    for o, de, nb, rit, wmt, dat in rows:
        rn = rain.get((dat, _area(o)))
        byp[(_kr(o), _kr(de))].append((float(nb), float(rit), float(wmt or 0), rn))
    out = {}
    for (o, de), v in byp.items():
        if len(v) < 25:
            continue
        dt = [x[0] for x in v]; eff = [x[1] / x[0] for x in v]
        n = len(v); mx = sum(dt) / n; my = sum(eff) / n
        den = sum((x - mx) ** 2 for x in dt)
        b = (sum((x - mx) * (y - my) for x, y in zip(dt, eff)) / den) if den else 0.0
        a = my - b * mx
        sr = sum((y - (a + b * x)) ** 2 for x, y in zip(dt, eff)); st = sum((y - my) ** 2 for y in eff)
        r2 = (1 - sr / st) if st else 0.0
        srit = sum(x[1] for x in v)
        tf = (sum(x[2] for x in v) / srit) if srit else 0.0
        rec = {"a": round(a, 4), "b": round(b, 5), "r2": round(r2, 3), "n": n,
               "dtMin": round(min(dt)), "dtMax": round(max(dt)), "avgDt": round(mx),
               "avgTr": round(my, 3), "tf": round(tf, 2)}
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
    return jsonify({"ok": True, "paths": out})

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

        # FENI smelter bays (FENI K/M/Q/A/…) sit at the FENI 0 end; CRUSHER CAS is just up-corridor of it.
        NODE_KM = {"TF": 67.8, "KR": 39.0, "POS 12": 27.0, "POS 10": 17.0, "FENI": 0.0, "CRUSHER": 3.0}
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
    return jsonify({"ok": True, "date": date, "shift": shift or "all",
                    "rain": rain, "rainMax": maxmm, "rainAssess": rain_assess,
                    "wbAvailable": bool(bridges), "bridges": bridges,
                    "busiest": busiest,
                    "otherFleet": other_fleet, "otherTrips": other_trips,
                    "otherBySection": other_by_section, "otherPaths": other_paths,
                    "otherFeniTrips": sum(p["trips"] for p in other_paths if p["dest"] in ("FENI", "CRUSHER")),
                    "otherFeniTypical": _other_feni_typical(),
                    "wbNote": None if bridges else "No weighbridge weigh data before Dec 2025 for this shift."})

def api_weighbridge_summary():
    """Small home-page status payload. Deliberately avoids the simulator's 90-day wait-curve query."""
    import time as _time
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
        result = {"ok": True, "date": latest.isoformat() if latest else None, "bridges": len(counts),
                  "trucks": total, "perBridge": round(total / len(counts), 1) if counts else 0,
                  "busiest": busiest[0], "busiestShare": share,
                  "otherShare": round(100 * other / total, 1) if total else 0, "status": status}
        _WB_HOME_CACHE = (_time.time(), result)
        return jsonify(result)
    except Exception:
        if _WB_HOME_CACHE:
            stale = dict(_WB_HOME_CACHE[1]); stale["stale"] = True
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

# ROUTES
_register('/api/simulator/path-response', api_simulator_path_response, 'path-response', methods=['GET'])
_register('/api/simulator/congestion-model', api_simulator_congestion_model, 'congestion-model', methods=['GET'])
_register('/api/simulator/weighbridge-positions', api_simulator_weighbridge_positions, 'weighbridge-positions', methods=['GET'])
_register('/api/simulator/shift-context', api_simulator_shift_context, 'shift-context', methods=['GET'])
_register('/api/weighbridge-summary', api_weighbridge_summary, 'weighbridge-summary', methods=['GET'])
_register('/api/simulator/weighbridge', api_simulator_weighbridge, 'weighbridge', methods=['GET'])


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

    NO FIXTURE, AND NO COMMITTED COORDINATES -- deliberately. Every other
    fixture in this repo is free of lat/lng, and `weighbridge-positions` encodes
    chainage offsets (`km`, `offM`) rather than coordinates even though the live
    endpoint has the geofences. AGENTS.md warns against committing geofence data
    to the mirror, which is public. So site geometry is read from the local
    `data/haul_road_chainage.csv` extract (cached, needs no VPN) and this returns
    an honest empty state where that file is absent -- a fresh clone, or the
    public demo. The map then says so instead of drawing an empty ocean.

    Downsampled to ~1 point per 0.25 km: the raw table is 3,122 markers, which
    is more resolution than a 1366px screen can show and a needlessly large
    payload for a polyline.
    """
    global _GEOM_CACHE
    if _GEOM_CACHE is not None:
        return jsonify(_GEOM_CACHE)

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "data", "haul_road_chainage.csv")
    if not os.path.exists(path):
        return jsonify({
            "ok": False, "roads": [],
            "reason": ("no corridor geometry on this machine: "
                       "data/haul_road_chainage.csv is gitignored, because site "
                       "coordinates are not committed to a public mirror. "
                       "Rebuild it from HAUL_ROAD_STA with the VPN up."),
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
        "corridor": _SIM_CORRIDOR,
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
