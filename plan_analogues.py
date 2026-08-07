"""Historical analogue retrieval + corridor interaction for Plan / Production Simulator.

Transparent k-NN over path-day history (not a neural net). Congestion risk is
advisory only — never clips /api/simulate tonnes.

Corpus sources (priority):
  1. Capability raw snapshot rows (date × OD × contractor) when available
  2. fixtures/capability.json dailyByPath (offline / no DB)
  3. Optional FMS_DB.SIM_PLAN_DAY_KPI memory table when materialised
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import statistics
from collections import defaultdict
from datetime import datetime

# Corridor chainage — must match simulator_api shift-context / flow stick.
NODE_KM = {
    "TF": 67.8, "TOFU": 67.8, "BLB": 67.8,
    "KR": 39.0, "KRENE": 39.0,
    "POS 12": 27.0, "POS12": 27.0,
    "POS 10": 17.0, "POS10": 17.0,
    "FENI KM15": 15.0, "FENI 15": 15.0,
    "FENI KM0": 0.0, "FENI 0": 0.0, "HUAFEI": 0.0, "BSE": 0.0,
    "CRUSHER": 3.0,
}

SECTIONS = (
    ("TOFU–KR", 39.0, 67.8),
    ("KR–POS 12", 27.0, 39.0),
    ("POS 12–POS 10", 17.0, 27.0),
    ("POS 10–FENI", 0.0, 17.0),
)

# Working-era vs struggle calendar (site collapses end of June).
STRUGGLE_CUTOFF = "2026-06-16"
# Haul-relevant corridor GPS retention starts mid-July — never invent earlier.
GPS_HAUL_START = "2026-07-15"

_FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

try:
    from prediction_pipeline import canonical_area as _canon
except Exception:  # noqa: BLE001
    def _canon(name):  # pragma: no cover
        return " ".join(str(name or "").strip().upper().split())


def _num(v, default=0.0):
    try:
        if v is None:
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _pctile(sorted_vals, p):
    if not sorted_vals:
        return None
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def season_tag(date_s):
    ds = str(date_s or "")[:10]
    if not ds:
        return "unknown"
    if ds >= STRUGGLE_CUTOFF:
        return "struggle"
    return "peak"


def has_haul_gps(date_s):
    """True only when haul corridor GPS could exist for that calendar day."""
    return str(date_s or "")[:10] >= GPS_HAUL_START


def node_km(name):
    n = _canon(name)
    if n in NODE_KM:
        return NODE_KM[n]
    # Soft aliases
    if n.startswith("FENI"):
        if "15" in n:
            return 15.0
        return 0.0
    if n.startswith("POS") and "12" in n:
        return 27.0
    if n.startswith("POS") and "10" in n:
        return 17.0
    return None


def route_sections(origin, dest):
    """Named corridor sections crossed by origin→dest (chainage overlap)."""
    ok, dk = node_km(origin), node_km(dest)
    if ok is None or dk is None:
        return []
    lo, hi = min(ok, dk), max(ok, dk)
    out = []
    for label, slo, shi in SECTIONS:
        if hi > slo and lo < shi:
            out.append(label)
    return out


def route_key(origin, dest):
    return "%s>%s" % (_canon(origin), _canon(dest))


def _wet(rain_mm):
    return _num(rain_mm) >= 1.0


# ── Corpus ───────────────────────────────────────────────────────────────────

def _row_from_daily_bypath(r):
    """Normalise a capability dailyByPath row into a corpus day-path record."""
    o, dd = _canon(r.get("o")), _canon(r.get("dd"))
    if not o or not dd:
        return None
    dt = _num(r.get("snb") if r.get("snb") is not None else r.get("nb"))
    trips = _num(r.get("srit") if r.get("srit") is not None else r.get("rit"))
    # Prefer shift-normalised WMT when present
    wmt = _num(r.get("sw") if r.get("sw") is not None else r.get("w"))
    if dt <= 0 or trips < 0:
        return None
    d = str(r.get("d") or "")[:10]
    tr = trips / dt if dt else 0.0
    tf = wmt / trips if trips else 0.0
    return {
        "date": d,
        "origin": o,
        "dest": dd,
        "route": "%s>%s" % (o, dd),
        "contractor": str(r.get("contractor") or "").strip().upper() or None,
        "dt": round(dt, 3),
        "trips": round(trips, 3),
        "wmt": round(wmt, 3),
        "trips_per_dt": round(tr, 4),
        "payload_t": round(tf, 3),
        "rain_mm": r.get("rain_mm"),
        "wet": _wet(r.get("rain_mm")) if r.get("rain_mm") is not None else None,
        "sections": route_sections(o, dd),
        "season": season_tag(d),
        "has_gps": has_haul_gps(d),
        "avg_speed_kmh": r.get("avg_speed_kmh"),
        "wb_trucks": r.get("wb_trucks"),
        "source": r.get("source") or "capability",
    }


def build_corpus_from_daily_bypath(rows, rain_by_date=None):
    rain_by_date = rain_by_date or {}
    out = []
    for r in rows or []:
        rr = dict(r)
        d = str(rr.get("d") or "")[:10]
        if d in rain_by_date and rr.get("rain_mm") is None:
            rr["rain_mm"] = rain_by_date[d]
        rec = _row_from_daily_bypath(rr)
        if rec:
            out.append(rec)
    return out


def build_corpus_from_cap_rows(raw_rows, rain_by_date=None):
    """Aggregate capability snapshot rows to (date, OD, contractor)."""
    rain_by_date = rain_by_date or {}
    agg = {}
    for r in raw_rows or []:
        o, dd = _canon(r.get("o")), _canon(r.get("dd"))
        if not o or not dd:
            continue
        if r.get("iwip"):
            continue
        d = str(r.get("d") or "")[:10]
        contr = str(r.get("contractor") or "").strip().upper() or None
        sc = int(_num(r.get("sc")) or 1)
        k = (d, o, dd, contr)
        b = agg.get(k)
        if b is None:
            b = agg[k] = {
                "d": d, "o": o, "dd": dd, "contractor": contr,
                "nb": 0.0, "rit": 0.0, "w": 0.0, "sc": sc,
            }
        b["nb"] += _num(r.get("dt"))
        b["rit"] += _num(r.get("trips"))
        b["w"] += _num(r.get("t"))
        b["sc"] = max(b["sc"], sc)
    rows = []
    for b in agg.values():
        sc = b["sc"] or 1
        rows.append({
            "d": b["d"], "o": b["o"], "dd": b["dd"],
            "contractor": b["contractor"],
            "snb": b["nb"],
            "srit": b["rit"] / sc,
            "sw": b["w"] / sc,
            "nb": b["nb"], "rit": b["rit"], "w": b["w"],
            "sc": sc,
            "rain_mm": rain_by_date.get(b["d"]),
            "source": "capability_raw",
        })
    return build_corpus_from_daily_bypath(rows, rain_by_date)


def load_fixture_corpus():
    path = os.path.join(_FX, "capability.json")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    # Canonicalise OD like simulator_api does
    rows = data.get("dailyByPath") or []
    for r in rows:
        r["o"] = _canon(r.get("o"))
        r["dd"] = _canon(r.get("dd"))
    return build_corpus_from_daily_bypath(rows), "fixture"


def load_corpus(cap_rows=None, daily_bypath=None, rain_by_date=None,
                memory_rows=None):
    """Return (corpus_list, source_tag)."""
    if memory_rows:
        return build_corpus_from_daily_bypath(memory_rows, rain_by_date), "fms_memory"
    if cap_rows:
        return build_corpus_from_cap_rows(cap_rows, rain_by_date), "capability_raw"
    if daily_bypath:
        return build_corpus_from_daily_bypath(daily_bypath, rain_by_date), "dailyByPath"
    return load_fixture_corpus()


# ── Scoring ──────────────────────────────────────────────────────────────────

def _score_candidate(cand, plan_dt, plan_wet, plan_contractor, prefer_peak=True):
    """Lower score = better match. Returns (score, why_bits)."""
    why = []
    # Fleet band — primary (normalise by plan DT so 50 vs 55 is close)
    dt = cand["dt"]
    plan_dt = max(1.0, _num(plan_dt, 1.0))
    dt_err = abs(dt - plan_dt) / plan_dt
    score = dt_err * 10.0
    why.append("fleet Δ%.0f DT" % (dt - plan_dt))

    # Contractor soft boost
    pc = (plan_contractor or "").strip().upper()
    cc = (cand.get("contractor") or "").strip().upper()
    if pc and cc:
        if pc == cc:
            score -= 1.5
            why.append("contractor %s" % cc)
        else:
            score += 0.8
            why.append("contractor %s≠%s" % (cc, pc))
    elif pc and not cc:
        why.append("no contractor in history grain")

    # Weather
    if plan_wet is not None and cand.get("wet") is not None:
        if bool(cand["wet"]) == bool(plan_wet):
            score -= 0.6
            why.append("weather match")
        else:
            score += 1.2
            why.append("weather mismatch")

    # Prefer working-era analogues for planning "how we run"
    if prefer_peak:
        if cand.get("season") == "peak":
            score -= 0.4
        elif cand.get("season") == "struggle":
            score += 0.9
            why.append("struggle era")

    # Tiny preference for denser activity (more evidence)
    if cand["trips"] >= 50:
        score -= 0.15

    return score, why


def remark_for_day(day, plan_dt, peer_med_tr=None):
    """Short planner-style remark from known fields (no external LLM)."""
    bits = []
    rain = day.get("rain_mm")
    if rain is not None:
        if _num(rain) >= 10:
            bits.append("Heavy rain (~%.0f mm) — traction/mud likely cut output" % _num(rain))
        elif _num(rain) >= 2:
            bits.append("Some rain (~%.0f mm) that day" % _num(rain))
        elif _num(rain) >= 1:
            bits.append("Light rain (~%.0f mm)" % _num(rain))
        else:
            bits.append("Dry day")
    if day.get("season") == "struggle":
        bits.append("Struggle-season calendar (post mid-June)")
    elif day.get("season") == "peak":
        bits.append("Peak / working-era day")
    who = (day.get("contractor") or "").strip()
    if who:
        bits.append(who)
    pdt = max(1.0, _num(plan_dt, 1.0))
    ddt = _num(day.get("dt"))
    if abs(ddt - pdt) <= max(2.0, 0.05 * pdt):
        bits.append("Same fleet size as your plan")
    elif ddt > pdt:
        bits.append("Ran ~%.0f more DT than your plan" % (ddt - pdt))
    else:
        bits.append("Ran ~%.0f fewer DT than your plan" % (pdt - ddt))
    if peer_med_tr and day.get("trips_per_dt"):
        tr = _num(day["trips_per_dt"])
        if tr >= peer_med_tr * 1.15:
            bits.append("Strong trips/DT vs similar-fleet peers")
        elif tr <= peer_med_tr * 0.85:
            bits.append("Soft trips/DT vs similar-fleet peers")
    if day.get("has_gps") and day.get("avg_speed_kmh") is not None:
        bits.append("Corridor GPS ~%.0f km/h" % _num(day["avg_speed_kmh"]))
    # Do not mention missing haul GPS — ops days are the normal planning record.
    return "; ".join(bits) if bits else "Similar fleet on this haul"


def find_best_output_days(corpus, origin, dest, n_trucks, contractor=None,
                          rain_mm=0, k=10, dt_band=0.35):
    """Same/similar DT on this haul for Plan Step 1 'best past days'.

    When a contractor is selected (e.g. RIM), history is taken from that
    contractor first — other haulers only fill gaps if too few matching days.

    Rank within that pool:
      1) closest fleet size to the planned DT
      2) then highest trips
      3) then highest trips/DT
    """
    rk = route_key(origin, dest)
    plan_dt = max(1.0, _num(n_trucks, 1.0))
    lo, hi = plan_dt * (1.0 - dt_band), plan_dt * (1.0 + dt_band)
    pc = (contractor or "").strip().upper()

    def _in_band(rows, lo_b, hi_b):
        return [c for c in rows if lo_b <= c["dt"] <= hi_b]

    route_all = [c for c in corpus if c["route"] == rk]
    if pc:
        own = [c for c in route_all
               if (c.get("contractor") or "").strip().upper() == pc]
    else:
        own = list(route_all)

    cands = _in_band(own, lo, hi)
    used_band = [round(lo, 1), round(hi, 1)]
    contractor_only = bool(pc)
    if len(cands) < 3:
        lo2, hi2 = plan_dt * 0.5, plan_dt * 1.5
        cands = _in_band(own, lo2, hi2)
        used_band = [round(lo2, 1), round(hi2, 1)]
    if len(cands) < 3 and pc:
        # Not enough days for this contractor — widen to other haulers on route
        contractor_only = False
        mixed = _in_band(route_all, lo, hi) or _in_band(route_all, plan_dt * 0.5, plan_dt * 1.5)
        if mixed:
            cands = mixed
            used_band = [round(lo, 1), round(hi, 1)]
    if not cands:
        cands = own or route_all
        contractor_only = bool(pc and cands and all(
            (c.get("contractor") or "").strip().upper() == pc for c in cands))

    def sort_key(c):
        same_c = 1 if pc and (c.get("contractor") or "").upper() == pc else 0
        return (same_c, -abs(c["dt"] - plan_dt),
                _num(c.get("trips")), _num(c.get("trips_per_dt")))

    ranked = sorted(cands, key=sort_key, reverse=True)
    out, seen = [], set()
    peer_trs = [_num(c["trips_per_dt"]) for c in ranked[:40] if c.get("trips_per_dt")]
    peer_med = _pctile(sorted(peer_trs), 0.5) if peer_trs else None
    for c in ranked:
        if c["date"] in seen:
            continue
        seen.add(c["date"])
        row = dict(c)
        row["score"] = round(_num(c.get("trips")), 1)
        row["exact_route"] = True
        row["same_contractor"] = bool(
            pc and (c.get("contractor") or "").strip().upper() == pc)
        who = (c.get("contractor") or "").strip() or "—"
        row["why"] = "%s · near %.0f DT · %.0f trips · %.2f trips/DT" % (
            who, _num(c.get("dt")), _num(c.get("trips")), _num(c.get("trips_per_dt")))
        if row.get("has_gps") and row.get("avg_speed_kmh") is not None:
            row["location_note"] = "haul GPS speed attached"
        elif row.get("has_gps"):
            row["location_note"] = "haul GPS window (speed not attached)"
        else:
            row["location_note"] = ""
        row["remark"] = remark_for_day(row, plan_dt, peer_med)
        out.append(row)
        if len(out) >= k:
            break
    return out, {
        "exact_route_pool": True,
        "candidates": len(cands),
        "route": rk,
        "rank": "best_output",
        "dt_band": used_band,
        "contractor": pc or None,
        "contractor_only": contractor_only,
    }


def find_route_analogues(corpus, origin, dest, n_trucks, contractor=None,
                         rain_mm=0, k=8, prefer_peak=True, rank="match"):
    """Top-k historical days for one OD (+ optional contractor).

    rank='match' → closest fleet/weather (default).
    rank='best_output' → similar fleet, closest DT then trips then trips/DT.
    """
    if rank in ("best_output", "best", "peak_output"):
        return find_best_output_days(
            corpus, origin, dest, n_trucks, contractor=contractor,
            rain_mm=rain_mm, k=k)

    rk = route_key(origin, dest)
    plan_wet = _wet(rain_mm)
    cands = [c for c in corpus if c["route"] == rk]
    # Soft fallback: same origin or same dest if exact OD rare
    exact = True
    if len(cands) < max(3, k // 2):
        o, d = _canon(origin), _canon(dest)
        soft = [c for c in corpus
                if c["origin"] == o or c["dest"] == d]
        # Prefer keeping exact first, then soft
        seen = {(c["date"], c["route"], c.get("contractor")) for c in cands}
        for c in soft:
            key = (c["date"], c["route"], c.get("contractor"))
            if key not in seen:
                cands.append(c)
                seen.add(key)
        exact = False

    scored = []
    for c in cands:
        sc, why = _score_candidate(c, n_trucks, plan_wet, contractor, prefer_peak)
        if c["route"] != rk:
            sc += 2.5
            why.append("near-OD %s" % c["route"])
        scored.append((sc, c, why))
    scored.sort(key=lambda x: (x[0], -x[1]["trips"]))

    # Dedupe by date (keep best contractor match per day)
    out, seen_dates = [], set()
    for sc, c, why in scored:
        if c["date"] in seen_dates:
            continue
        seen_dates.add(c["date"])
        row = dict(c)
        row["score"] = round(sc, 3)
        row["why"] = "; ".join(why)
        row["exact_route"] = c["route"] == rk
        # Location honesty label
        if row.get("has_gps") and row.get("avg_speed_kmh") is not None:
            row["location_note"] = "haul GPS speed attached"
        elif row.get("has_gps"):
            row["location_note"] = "haul GPS window (speed not attached)"
        else:
            row["location_note"] = "ops-only (no haul GPS)"
        out.append(row)
        if len(out) >= k:
            break
    return out, {"exact_route_pool": exact, "candidates": len(cands), "route": rk}


def ensemble_from_analogues(analogues, n_trucks, payload_t=None):
    """Median / P25 / P75 forecast from matched days' trips/DT × planned DT."""
    if not analogues:
        return {
            "n": 0, "trips_per_dt_p25": None, "trips_per_dt_med": None,
            "trips_per_dt_p75": None, "trips_p25": None, "trips_med": None,
            "trips_p75": None, "wmt_p25": None, "wmt_med": None, "wmt_p75": None,
            "payload_t_med": None,
        }
    trs = sorted(a["trips_per_dt"] for a in analogues if a.get("trips_per_dt") is not None)
    payloads = sorted(a["payload_t"] for a in analogues if a.get("payload_t") and a["payload_t"] > 0)
    pay = payload_t if payload_t and payload_t > 0 else (_pctile(payloads, 0.5) or 0.0)
    dt = max(0.0, _num(n_trucks))
    p25, med, p75 = _pctile(trs, 0.25), _pctile(trs, 0.5), _pctile(trs, 0.75)
    def _t(tr):
        if tr is None:
            return None
        trips = tr * dt
        return {
            "trips": round(trips, 1),
            "wmt": round(trips * pay, 1) if pay else None,
        }
    t25, tmed, t75 = _t(p25), _t(med), _t(p75)
    return {
        "n": len(trs),
        "trips_per_dt_p25": round(p25, 3) if p25 is not None else None,
        "trips_per_dt_med": round(med, 3) if med is not None else None,
        "trips_per_dt_p75": round(p75, 3) if p75 is not None else None,
        "trips_p25": t25["trips"] if t25 else None,
        "trips_med": tmed["trips"] if tmed else None,
        "trips_p75": t75["trips"] if t75 else None,
        "wmt_p25": t25["wmt"] if t25 else None,
        "wmt_med": tmed["wmt"] if tmed else None,
        "wmt_p75": t75["wmt"] if t75 else None,
        "payload_t_med": round(pay, 3) if pay else None,
        "note": ("History band from matched days' trips/DT × planned DT × median "
                 "payload. Kept separate from /api/simulate achievable tonnes."),
    }


# ── Shared road / multi-plan ─────────────────────────────────────────────────

def plans_shared_sections(plans):
    """Intersection of section sets across plans (≥2 plans)."""
    if not plans or len(plans) < 2:
        return []
    sets = []
    for p in plans:
        secs = set(route_sections(p.get("source") or p.get("origin"),
                                  p.get("destination") or p.get("dest")))
        sets.append(secs)
    shared = set.intersection(*sets) if sets else set()
    return sorted(shared)


def section_day_load(corpus):
    """date → section → {dt, trips, routes}."""
    out = defaultdict(lambda: defaultdict(lambda: {"dt": 0.0, "trips": 0.0, "routes": set()}))
    for c in corpus:
        for sec in c.get("sections") or []:
            b = out[c["date"]][sec]
            b["dt"] += c["dt"]
            b["trips"] += c["trips"]
            b["routes"].add(c["route"])
    return out


def shared_road_analysis(plans, corpus, k_evidence=5):
    """Human congestion advisory when plans share corridor sections."""
    shared = plans_shared_sections(plans)
    plan_dt_total = sum(_num(p.get("n_trucks") or p.get("dt")) for p in plans)
    plan_routes = [route_key(p.get("source") or p.get("origin"),
                             p.get("destination") or p.get("dest"))
                   for p in plans]

    if len(plans) < 2:
        return {
            "shared_sections": [],
            "risk": "none",
            "risk_label": "Single plan — no multi-plan road interaction",
            "plan_dt_total": plan_dt_total,
            "evidence": [],
            "max_hist_section_dt": None,
            "note": "Add a second plan on an overlapping corridor to see shared-road risk.",
        }

    if not shared:
        return {
            "shared_sections": [],
            "risk": "low",
            "risk_label": "Low — plans do not share named corridor sections",
            "plan_dt_total": plan_dt_total,
            "evidence": [],
            "max_hist_section_dt": None,
            "note": "Routes may still meet at loaders/dumps (see simulate shared_with).",
        }

    loads = section_day_load(corpus)
    # For each day, take max DT across shared sections; also require ≥2 plan routes if possible
    day_scores = []
    for date, secmap in loads.items():
        sec_dt = sum(secmap[s]["dt"] for s in shared if s in secmap)
        if sec_dt <= 0:
            continue
        routes_present = set()
        for s in shared:
            routes_present |= secmap.get(s, {}).get("routes") or set()
        overlap = len(routes_present & set(plan_routes))
        # Prefer days where multiple of our routes ran
        closeness = abs(sec_dt - plan_dt_total) / max(plan_dt_total, 1.0)
        score = closeness - 0.5 * overlap
        # trips/DT on shared sections that day
        trips = sum(secmap[s]["trips"] for s in shared if s in secmap)
        tr = trips / sec_dt if sec_dt else 0.0
        day_scores.append({
            "date": date,
            "section_dt": round(sec_dt, 2),
            "trips_per_dt": round(tr, 3),
            "routes_overlap": overlap,
            "season": season_tag(date),
            "has_gps": has_haul_gps(date),
            "score": score,
            "sections": {s: round(secmap[s]["dt"], 2) for s in shared if s in secmap},
        })
    day_scores.sort(key=lambda x: x["score"])
    evidence = day_scores[:k_evidence]

    # Quiet vs busy comparison for risk badge
    all_sec_dt = [d["section_dt"] for d in day_scores] or [0]
    max_hist = max(all_sec_dt) if all_sec_dt else 0
    # Busy = top quartile section DT; quiet = bottom
    sorted_dt = sorted(all_sec_dt)
    q75 = _pctile(sorted_dt, 0.75) or 0
    q25 = _pctile(sorted_dt, 0.25) or 0
    busy = [d for d in day_scores if d["section_dt"] >= q75 and q75 > 0]
    quiet = [d for d in day_scores if d["section_dt"] <= q25 and q25 > 0]
    busy_tr = statistics.median([d["trips_per_dt"] for d in busy]) if busy else None
    quiet_tr = statistics.median([d["trips_per_dt"] for d in quiet]) if quiet else None
    collapse_pct = None
    if busy_tr is not None and quiet_tr and quiet_tr > 0:
        collapse_pct = round(100.0 * (quiet_tr - busy_tr) / quiet_tr, 1)

    # Risk: how close is planned DT to historical crowded corridor
    risk, label = "low", "Low"
    if max_hist > 0 and plan_dt_total >= 0.85 * max_hist:
        risk, label = "high", "High"
    elif max_hist > 0 and plan_dt_total >= 0.55 * max_hist:
        risk, label = "medium", "Medium"
    elif collapse_pct is not None and collapse_pct >= 15:
        risk, label = "medium", "Medium"
    if risk == "high":
        label = "High — planned fleet near historical peak load on shared sections"
    elif risk == "medium":
        label = "Medium — shared corridor historically busy at similar fleets"
    else:
        label = "Low — shared sections but planned fleet below typical busy days"

    return {
        "shared_sections": shared,
        "risk": risk,
        "risk_label": label,
        "plan_dt_total": round(plan_dt_total, 1),
        "max_hist_section_dt": round(max_hist, 1) if max_hist else None,
        "busy_trips_per_dt_med": round(busy_tr, 3) if busy_tr is not None else None,
        "quiet_trips_per_dt_med": round(quiet_tr, 3) if quiet_tr is not None else None,
        "trips_per_dt_collapse_pct": collapse_pct,
        "evidence": evidence,
        "note": ("Advisory only — does not change /api/simulate tonnes. "
                 "GPS speeds only on days ≥ %s; peak Jan–May is ops-only." % GPS_HAUL_START),
    }


# ── Public entry ─────────────────────────────────────────────────────────────

def fingerprint_hash(plans, rain_mm, k, rank="match", prefer_peak=True):
    # rank/prefer_peak change the RESULT (match vs best_output ordering), so
    # they must change the cache key too — a cached rank=match answer must
    # never be served for rank=best_output. Defaults keep old keys stable for
    # the common (match, True) case.
    blob = json.dumps({
        "plans": [{"s": p.get("source") or p.get("origin"),
                   "d": p.get("destination") or p.get("dest"),
                   "n": int(_num(p.get("n_trucks") or p.get("dt"))),
                   "c": (p.get("contractor") or "").upper()}
                  for p in (plans or [])],
        "rain": _num(rain_mm), "k": int(k),
        "rank": str(rank or "match").strip().lower(),
        "peak": bool(prefer_peak),
    }, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def find_analogues(payload, corpus=None, corpus_source=None):
    """Main API body. payload: {plans, rain_mm|rain, k, shift_minutes}."""
    plans_in = payload.get("plans") or []
    if not isinstance(plans_in, list) or not plans_in:
        return {"ok": False, "error": "supply plans: [{source, destination, n_trucks, contractor?}]",
                "analogues": [], "ensemble": {}, "shared_road": {}}

    rain_mm = payload.get("rain_mm")
    if rain_mm is None:
        rain_mm = 0.0 if str(payload.get("weather") or "dry").lower() == "dry" else 2.0
        if payload.get("rain") is not None:
            rain_mm = payload.get("rain")
    k = int(payload.get("k") or 8)
    k = max(5, min(10, k))
    prefer_peak = bool(payload.get("prefer_peak", True))
    rank = str(payload.get("rank") or "match").strip().lower()

    if corpus is None:
        corpus, corpus_source = load_fixture_corpus()
    elif corpus_source is None:
        corpus_source = "provided"

    plans = []
    for p in plans_in:
        src = p.get("source") or p.get("origin")
        dst = p.get("destination") or p.get("dest")
        if not src or not dst:
            continue
        plans.append({
            "source": _canon(src),
            "destination": _canon(dst),
            "route": route_key(src, dst),
            "n_trucks": int(round(_num(p.get("n_trucks") or p.get("dt") or 0))),
            "contractor": (str(p.get("contractor") or "").strip().upper() or None),
            "sections": route_sections(src, dst),
        })
    if not plans:
        return {"ok": False, "error": "no valid plans with source/destination",
                "analogues": [], "ensemble": {}, "shared_road": {}}

    by_plan = []
    all_analogues = []
    for p in plans:
        an, meta = find_route_analogues(
            corpus, p["source"], p["destination"], p["n_trucks"],
            contractor=p["contractor"], rain_mm=rain_mm, k=k,
            prefer_peak=prefer_peak, rank=rank)
        # Ensure remarks present for match-mode too
        peer_trs = sorted(_num(a["trips_per_dt"]) for a in an if a.get("trips_per_dt"))
        peer_med = _pctile(peer_trs, 0.5) if peer_trs else None
        for a in an:
            if not a.get("remark"):
                a["remark"] = remark_for_day(a, p["n_trucks"], peer_med)
        ens = ensemble_from_analogues(an, p["n_trucks"])
        by_plan.append({
            "route": p["route"], "source": p["source"],
            "destination": p["destination"], "n_trucks": p["n_trucks"],
            "contractor": p["contractor"], "sections": p["sections"],
            "analogues": an, "ensemble": ens, "meta": meta,
        })
        all_analogues.extend(an)

    # Combined day view: unique dates from best per-plan matches, re-ranked
    by_date = {}
    best_mode = rank in ("best_output", "best", "peak_output")
    for a in all_analogues:
        prev = by_date.get(a["date"])
        if prev is None:
            by_date[a["date"]] = a
        elif best_mode:
            # Prefer the already-ranked per-plan order (closest DT already applied)
            if (_num(a.get("score")), _num(a.get("trips")), _num(a.get("trips_per_dt"))) > (
                    _num(prev.get("score")), _num(prev.get("trips")), _num(prev.get("trips_per_dt"))):
                by_date[a["date"]] = a
        elif a["score"] < prev["score"]:
            by_date[a["date"]] = a
    if best_mode:
        # Keep by_plan order when single plan; for multi, prefer higher trips among ties
        combined = sorted(
            by_date.values(),
            key=lambda x: (-_num(x.get("trips")), -_num(x.get("trips_per_dt"))))[:k]
        # Re-sort single-plan best_output: contractor → closest DT → trips
        if len(plans) == 1:
            pdt = max(1.0, _num(plans[0].get("n_trucks"), 1.0))
            pc = (plans[0].get("contractor") or "").strip().upper()
            combined = sorted(
                by_date.values(),
                key=lambda x: (
                    0 if (pc and (x.get("contractor") or "").upper() == pc) else 1,
                    abs(_num(x.get("dt")) - pdt),
                    -_num(x.get("trips")), -_num(x.get("trips_per_dt"))))[:k]
    else:
        combined = sorted(by_date.values(), key=lambda x: x["score"])[:k]
    # Method label
    method = ("contractor + closest DT, then trips, then trips/DT"
              if best_mode else
              "kNN path-day retrieval (fleet band + contractor + weather + season)")

    # Multi-plan ensemble: sum of per-plan medians (independent) — labelled
    trips_med = sum((bp["ensemble"].get("trips_med") or 0) for bp in by_plan)
    wmt_med = sum((bp["ensemble"].get("wmt_med") or 0) for bp in by_plan)
    trips_p25 = sum((bp["ensemble"].get("trips_p25") or 0) for bp in by_plan)
    trips_p75 = sum((bp["ensemble"].get("trips_p75") or 0) for bp in by_plan)
    wmt_p25 = sum((bp["ensemble"].get("wmt_p25") or 0) for bp in by_plan)
    wmt_p75 = sum((bp["ensemble"].get("wmt_p75") or 0) for bp in by_plan)

    shared = shared_road_analysis(plans, corpus, k_evidence=min(5, k))

    return {
        "ok": True,
        "k": k,
        "rank": rank,
        "rain_mm": _num(rain_mm),
        "wet": _wet(rain_mm),
        "fingerprint": fingerprint_hash(plans, rain_mm, k, rank=rank, prefer_peak=prefer_peak),
        "plans": plans,
        "analogues": combined,
        "by_plan": by_plan,
        "ensemble": {
            "n_plans": len(plans),
            "trips_p25": round(trips_p25, 1),
            "trips_med": round(trips_med, 1),
            "trips_p75": round(trips_p75, 1),
            "wmt_p25": round(wmt_p25, 1),
            "wmt_med": round(wmt_med, 1),
            "wmt_p75": round(wmt_p75, 1),
            "note": ("Analogue ensemble = sum of per-route history bands. "
                     "Not averaged with /api/simulate."),
        },
        "shared_road": shared,
        "basis": {
            "method": method,
            "corpus_source": corpus_source,
            "corpus_n": len(corpus),
            "struggle_cutoff": STRUGGLE_CUTOFF,
            "gps_haul_start": GPS_HAUL_START,
            "congestion_clips_tonnes": False,
            "simulate_unchanged": True,
        },
    }


def attach_location_speeds(analogues, speed_by_date=None):
    """Fill avg_speed_kmh when provided; never invent pre-GPS_HAUL_START speeds."""
    speed_by_date = speed_by_date or {}
    for a in analogues or []:
        d = a.get("date")
        if not has_haul_gps(d):
            a["avg_speed_kmh"] = None
            a["has_gps"] = False
            a["location_note"] = "ops-only (no haul GPS)"
            continue
        a["has_gps"] = True
        if d in speed_by_date and speed_by_date[d] is not None:
            a["avg_speed_kmh"] = round(_num(speed_by_date[d]), 2)
            a["location_note"] = "haul GPS speed attached"
        elif a.get("avg_speed_kmh") is None:
            a["location_note"] = "haul GPS window (speed not attached)"
    return analogues
