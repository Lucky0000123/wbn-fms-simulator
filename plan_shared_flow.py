"""DES-lite shared-road occupancy for multi-contractor holding plans.

Staggers truck releases using measured load/dump dwell, moves them across
named corridor sections at Jul+ GPS speeds, and bins concurrent occupancy.
Advisory only — never clips /api/simulate tonnes.

Phase 1: loaded outbound occupancy. Point-queue DES and empty-return density
are later phases.
"""
from __future__ import annotations

import csv
import math
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import plan_analogues as pa
import plan_corridor_hours as pch

_ROOT = os.path.dirname(os.path.abspath(__file__))
_SEG_CSV = os.path.join(_ROOT, "data", "congestion_seg_by_dir.csv")

FALLBACK_LOAD_MIN = 10.0
FALLBACK_DUMP_MIN = 10.0
DEFAULT_SPEED_KMH = 16.0
DEFAULT_CAP_TPH = 40.0  # trucks/hour when no measured peak
BIN_HOURS = 1.0         # hourly bins (matches congestion-hours UI)
MAX_TRUCKS_SIM = 400    # soft cap so huge fleets stay responsive


def _f(x, default=None):
    try:
        if x is None or x == "":
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def _section_length_km(label: str) -> float:
    for name, slo, shi in pa.SECTIONS:
        if name == label:
            return abs(float(shi) - float(slo))
    return 10.0


def _load_section_capacity_tph() -> Dict[str, float]:
    """Median peak TRUCK_N/hour per named section from stick CSV (DIR=down)."""
    if not os.path.isfile(_SEG_CSV):
        return {}
    peaks: List[Tuple[float, float]] = []
    try:
        with open(_SEG_CSV, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                direction = (row.get("DIR") or row.get("dir") or "").strip().lower()
                if direction and direction not in ("down", "loaded"):
                    continue
                stick = pch.parse_seg_id(row.get("SEG_ID") or row.get("seg"))
                if not stick:
                    continue
                _road, _lo, _hi, mid = stick
                try:
                    pk = float(row.get("peak_trucks") or row.get("PEAK_TRUCK_N") or 0)
                except (TypeError, ValueError):
                    continue
                if pk <= 0:
                    continue
                peaks.append((mid, pk))
    except OSError:
        return {}
    out: Dict[str, float] = {}
    for label, slo, shi in pa.SECTIONS:
        vals = sorted(pk for mid, pk in peaks if mid > slo and mid <= shi)
        if not vals:
            vals = sorted(pk for mid, pk in peaks
                          if mid >= slo - 1e-6 and mid <= shi + 1e-6)
        if vals:
            out[label] = float(vals[len(vals) // 2])
    return out


def _section_speeds_kmh(path=None) -> Dict[str, float]:
    payload = pch.corridor_hours(dir_filter="down", path=path)
    out: Dict[str, float] = {}
    if not payload.get("ok"):
        return out
    for row in payload.get("by_section") or []:
        sec = row.get("section")
        spd = _f(row.get("speed_kmh"))
        if sec and spd is not None and spd > 0.5:
            out[str(sec)] = spd
    return out


def _dwell_aliases(point: str) -> List[str]:
    p = str(point or "").strip().upper()
    out = [p]
    aliases = {
        "TOFU": ["TF", "BLB"],
        "TF": ["TOFU", "BLB"],
        "BLB": ["TF", "TOFU"],
        "KRENE": ["KR"],
        "KR": ["KRENE"],
        "FENI 15": ["FENI KM15"],
        "FENI KM15": ["FENI 15"],
        "FENI 0": ["FENI KM0", "HUAFEI", "BSE"],
        "FENI KM0": ["FENI 0", "HUAFEI", "BSE"],
        "POS12": ["POS 12"],
        "POS10": ["POS 10"],
    }
    for a in aliases.get(p, []):
        if a not in out:
            out.append(a)
    return out


def _point_dwell_min(point: str, kind: str, wet: bool) -> Tuple[float, str]:
    """Measured dwell; last resort 10 min (labelled)."""
    try:
        import plan_simulator as ps
        for cand in _dwell_aliases(point):
            v, basis = ps._point_dwell(cand, kind, wet)
            if v is not None and v > 0:
                note = basis or "measured"
                if cand.upper() != str(point).strip().upper():
                    note = "%s via %s" % (note, cand)
                return float(v), note
    except Exception:  # noqa: BLE000
        pass
    try:
        import pandas as pd
        csv_path = os.path.join(_ROOT, "data", "dwell_model_results.csv")
        if os.path.isfile(csv_path):
            d = pd.read_csv(csv_path)
            for cand in _dwell_aliases(point):
                hit = d[(d["point"].astype(str).str.upper() == cand.upper())
                        & (d["kind"] == kind)]
                if hit.empty:
                    continue
                row = hit.iloc[0]
                col = "wet_min" if wet else "dry_min"
                v = row.get(col)
                if pd.notna(v) and float(v) > 0:
                    return float(v), "measured (%s) via %s" % (
                        "wet" if wet else "dry", cand)
                v = row.get("median_min")
                if pd.notna(v) and float(v) > 0:
                    return float(v), "measured median via %s" % cand
    except Exception:  # noqa: BLE000
        pass
    fb = FALLBACK_LOAD_MIN if kind == "loading" else FALLBACK_DUMP_MIN
    return fb, "fallback %g min (no measured dwell)" % fb


def _norm_plans(plans: Optional[List[dict]]) -> List[dict]:
    out = []
    for i, p in enumerate(plans or []):
        if not isinstance(p, dict):
            continue
        src = str(p.get("source") or p.get("origin") or "").strip()
        dst = str(p.get("destination") or p.get("dest") or "").strip()
        dt = _f(p.get("n_trucks") if p.get("n_trucks") is not None else p.get("dt"), 0) or 0
        if not src or not dst or dt <= 0:
            continue
        out.append({
            "id": str(p.get("id") or "p%d" % i),
            "source": src,
            "destination": dst,
            "n_trucks": int(max(1, round(dt))),
            "contractor": str(p.get("contractor") or "").strip() or None,
            "route": "%s>%s" % (src, dst),
            "label": "%s → %s" % (src, dst)
                     + ((" · " + str(p.get("contractor"))) if p.get("contractor") else ""),
        })
    return out


def shared_flow(
    plans: Optional[List[dict]] = None,
    shift_hours: float = 12.0,
    rain_mm: float = 0.0,
    start_hour: int = 7,
    path=None,
    bin_hours: float = BIN_HOURS,
    whole_day: bool = False,
) -> dict:
    """Build shared-section occupancy timeline for a holding plan.

    whole_day=True runs TWO consecutive shifts (day + night, each
    shift_hours long, releases re-staggered at the changeover) so the
    timeline covers the full 24 h clock - the site runs 2 x 12 h, it is
    NOT one continuous 24 h shift (owner, 2026-08-19)."""
    shift_hours = max(1.0, _f(shift_hours, 12.0) or 12.0)
    wet = (_f(rain_mm, 0) or 0) >= 1.0
    start_hour = int(start_hour) % 24
    bin_hours = max(0.25, _f(bin_hours, BIN_HOURS) or BIN_HOURS)
    n_shifts = 2 if whole_day else 1
    horizon_h = shift_hours * n_shifts

    norm = _norm_plans(plans)
    basis = {
        "congestion_clips_tonnes": False,
        "simulate_unchanged": True,
        "invents_playback_haul_speeds": False,
        "phase": "des_segment_model_roundtrip" + ("_2shift" if whole_day else ""),
        "era": "struggle",
    }
    if not norm:
        return {
            "ok": False,
            "error": "supply plans with source, destination, n_trucks",
            "sections": [],
            "congestion_hours": [],
            "meter_hint": None,
            "basis": basis,
        }

    speeds = _section_speeds_kmh(path=path)
    caps = _load_section_capacity_tph()
    hours_payload = pch.corridor_hours(dir_filter="down", path=path)
    gps_ok = bool(hours_payload.get("ok"))

    # ── Enrich paths from the CURRENT physics model (owner, 2026-08-22:
    # the hourly view must match the segment model) ─────────────────────
    # Timing per truck comes from congestion.predictor at the PLAN's
    # combined fleets (segment_fleet = every route's trucks on the shared
    # windows, contractor baseline when calibrated): road time split over
    # the S1–S4 segments by the OFFICIAL directional speed-limit times,
    # release cadence = model cycle + overhead-per-trip (trucks do not
    # re-enter the road during breaks/dispatch/refuel). BLB is a spur —
    # its trucks occupy a 'BLB spur' pseudo-section, never the stick.
    from congestion.predictor import predict as _predict
    from congestion.segments import (route_segments as _route_segments,
                                     segment_trucks as _segment_trucks,
                                     node_km as _node_km)
    from congestion.speed_limits import span_times_min as _span_times

    comb: Dict[str, float] = defaultdict(float)
    for p in norm:
        comb[p["route"]] += p["n_trucks"]
    seg_fleet = _segment_trucks(dict(comb))

    path_rows = []
    dwell_notes = []
    for p in norm:
        segs = _route_segments(p["source"], p["destination"])
        load_min, load_basis = _point_dwell_min(p["source"], "loading", wet)
        dump_min, dump_basis = _point_dwell_min(p["destination"], "dumping", wet)
        if "fallback" in load_basis or "fallback" in dump_basis:
            dwell_notes.append("%s: load %s; dump %s" % (p["label"], load_basis, dump_basis))
        try:
            pr = _predict(p["route"], comb[p["route"]], None,
                          segment_fleet=seg_fleet,
                          contractor=p.get("contractor"),
                          rain_mm=rain_mm)
        except (ValueError, ArithmeticError):
            pr = None
        comp = (pr or {}).get("components") or {}
        road_min = (comp.get("t_free_road") or 0) + (comp.get("bpr_penalty_minutes") or 0)
        queue_min = comp.get("queue_wait_minutes") or 0.0
        overhead_min = comp.get("overhead_per_trip_minutes") or 240.0
        cyc_min = (pr or {}).get("cycle_time_minutes") or (road_min + load_min + dump_min)
        if road_min <= 0:
            road_min = max(30.0, cyc_min - load_min - dump_min - queue_min)
        # split the model's road time over the segments by the official
        # directional limit times (loaded down-chainage, empty up)
        sec_loaded, sec_empty = [], []
        if segs:
            a, b = _node_km(p["source"]), _node_km(p["destination"])
            lo, hi = min(a, b), max(a, b)
            raw = []
            for s, ov in segs:
                o_lo, o_hi = max(lo, s['bottom_km']), min(hi, s['top_km'])
                tl, te = _span_times(o_lo, o_hi)
                raw.append((s, ov, tl or ov, te or ov))
            tot = sum(r[2] + r[3] for r in raw) or 1.0
            k = road_min / tot
            for s, ov, tl, te in raw:
                sec_loaded.append({"section": s['label'], "hours": tl * k / 60.0,
                                   "speed_kmh": (s.get('speeds') or {}).get('loaded', {}).get('mean'),
                                   "km": round(ov, 1)})
                sec_empty.append({"section": s['label'], "hours": te * k / 60.0,
                                  "km": round(ov, 1)})
        else:
            # spur route (BLB …): own lane, not on the stick — loaded/empty
            # split by the site 1.25x empty-speed factor
            lbl = "%s spur" % p["source"].upper()
            sec_loaded.append({"section": lbl, "hours": road_min * (1.25 / 2.25) / 60.0,
                               "speed_kmh": None, "km": None})
            sec_empty.append({"section": lbl, "hours": road_min * (1.0 / 2.25) / 60.0,
                              "km": None})
        travel_h = sum(x["hours"] for x in sec_loaded)
        cycle_h = cyc_min / 60.0
        interval_h = (cyc_min + overhead_min) / 60.0   # true inter-trip spacing
        trips_per_truck = max(1, int(math.floor(shift_hours / max(interval_h, 0.25))))
        path_rows.append({
            **p,
            "sections": [x["section"] for x in sec_loaded],
            "load_min": round(load_min, 2),
            "dump_min": round(dump_min, 2),
            "load_basis": load_basis,
            "dump_basis": dump_basis,
            "queue_min": round(queue_min, 1),
            "overhead_min": round(overhead_min, 1),
            "sec_times": sec_loaded,
            "sec_times_empty": sec_empty,
            "travel_h": round(travel_h, 3),
            "cycle_h": round(cycle_h, 3),
            "interval_h": round(interval_h, 3),
            "trips_per_truck": trips_per_truck,
            "model": (pr or {}).get("model_version") or "fallback",
        })

    # Loader serialization: trucks at same source release every load_min
    by_src: Dict[str, List[dict]] = defaultdict(list)
    for pr in path_rows:
        by_src[pr["source"].upper()].append(pr)

    # Occupancy events: list of (section, t0, t1, plan_id, label)
    events: List[Tuple[str, float, float, str, str]] = []
    section_plans: Dict[str, set] = defaultdict(set)

    # Each shift restarts the release sequence: night crew re-staggers from
    # the loader at the changeover, exactly like the morning.
    for shift_i in range(n_shifts):
        shift_t0 = shift_i * shift_hours
        shift_t1 = shift_t0 + shift_hours
        for src, group in by_src.items():
            # Serialize all trucks from this source across plans by cumulative
            # index. Stagger = max of load times at this source.
            # Releases are PARALLEL across loading faces (rules §10.9:
            # ~1 loader per 15 trucks) — the old serial stagger assumed one
            # loader per pit and starved the road of most of the fleet
            src_trucks = sum(g["n_trucks"] for g in group)
            faces = max(1, round(src_trucks / 15.0))
            load_stagger_h = (max(g["load_min"] for g in group) / 60.0) / faces
            truck_idx = 0
            for pr in group:
                n = min(pr["n_trucks"], MAX_TRUCKS_SIM)
                for _t in range(n):
                    for trip in range(pr["trips_per_truck"]):
                        # Release after queue+load; trips repeat every
                        # cycle+overhead (the model's true inter-trip
                        # spacing), not every raw cycle
                        t_depart = (shift_t0 + truck_idx * load_stagger_h
                                    + (pr["queue_min"] + pr["load_min"]) / 60.0
                                    + trip * pr["interval_h"])
                        if t_depart >= shift_t1:
                            break
                        t_cursor = t_depart
                        # loaded pass, pit -> dump
                        for st in pr["sec_times"]:
                            t0, t1 = t_cursor, t_cursor + st["hours"]
                            if t0 < shift_t1:
                                events.append((st["section"], t0,
                                               min(t1, shift_t1 + 0.01),
                                               pr["id"], pr["label"]))
                                section_plans[st["section"]].add(pr["label"])
                            t_cursor = t1
                            if t_cursor >= shift_t1:
                                break
                        # dump dwell, then the EMPTY return in reverse —
                        # empty trucks occupy the road too (their own lane,
                        # counted in the section totals)
                        t_cursor += pr["dump_min"] / 60.0
                        for st in reversed(pr["sec_times_empty"]):
                            if t_cursor >= shift_t1:
                                break
                            t0, t1 = t_cursor, t_cursor + st["hours"]
                            if t0 < shift_t1:
                                events.append((st["section"], t0,
                                               min(t1, shift_t1 + 0.01),
                                               pr["id"], pr["label"]))
                                section_plans[st["section"]].add(pr["label"])
                            t_cursor = t1
                    truck_idx += 1

    n_bins = int(math.ceil(horizon_h / bin_hours))
    # section → bin → count / plan labels
    occ: Dict[str, List[int]] = defaultdict(lambda: [0] * n_bins)
    occ_plans: Dict[str, List[set]] = defaultdict(lambda: [set() for _ in range(n_bins)])

    for sec, t0, t1, pid, label in events:
        b0 = max(0, int(math.floor(t0 / bin_hours)))
        b1 = min(n_bins - 1, int(math.floor((t1 - 1e-9) / bin_hours)))
        for b in range(b0, b1 + 1):
            # Fractional presence in bin (conservative: count as 1 if any overlap)
            occ[sec][b] += 1
            occ_plans[sec][b].add(label)

    sections_out = []
    congested_clock = defaultdict(lambda: {"peak": 0, "sections": []})
    worst = None

    from congestion.segments import SEGMENTS as _SEGS
    _seg_by_label = {s['label']: s for s in _SEGS}
    all_secs = [s['label'] for s in _SEGS] + sorted(
        s for s in section_plans if s not in {x['label'] for x in _SEGS})
    used_secs = [s for s in all_secs if s in section_plans or s in occ]

    for sec in used_secs:
        counts = occ.get(sec) or [0] * n_bins
        peak = max(counts) if counts else 0
        peak_bin = counts.index(peak) if counts else 0
        seg = _seg_by_label.get(sec)
        if seg:
            # official capacity (speed limits / following distance) per lane;
            # occupancy counts BOTH directions and the road has a separate
            # lane each way, so the section carries 2x the lane capacity
            cap_tph = float(seg['cap_hr']) * 2.0
        elif sec.endswith(" spur"):
            cap_tph = 800.0        # 20 km/h floor / 50 m, two lanes (no sheet)
        else:
            cap_tph = caps.get(sec) or DEFAULT_CAP_TPH
        cap_bin = cap_tph * bin_hours
        ratio = (peak / cap_bin) if cap_bin > 0 else 0.0
        status = "High" if ratio >= 1.0 else ("Watch" if ratio >= 0.7 else "Open")
        plans_here = sorted(section_plans.get(sec) or [])
        shared = len(plans_here) >= 2
        row = {
            "section": sec,
            "plans": plans_here,
            "n_plans": len(plans_here),
            "shared": shared,
            "peak_trucks": peak,
            "peak_bin": peak_bin,
            "cap_trucks_bin": round(cap_bin, 1),
            "cap_tph": round(cap_tph, 1),
            "ratio": round(ratio, 3),
            "status": status,
            "speed_kmh": ((seg.get('speeds') or {}).get('loaded', {}).get('mean')
                          if seg else speeds.get(sec)),
            "cap_basis": ("official speed limits / 50 m following, 2 lanes"
                          if seg else ("spur estimate 20 km/h / 50 m, 2 lanes (no limit sheet)"
                                       if sec.endswith(" spur") else "measured peak")),
            "occupancy": counts,
        }
        sections_out.append(row)
        if peak > 0 and (worst is None or ratio > worst["ratio"]):
            worst = row
        for b, c in enumerate(counts):
            if c <= 0:
                continue
            r = c / cap_bin if cap_bin > 0 else 0
            if r >= 0.7:
                clock = (start_hour + int(round(b * bin_hours))) % 24
                slot = congested_clock[clock]
                if c > slot["peak"]:
                    slot["peak"] = c
                if sec not in slot["sections"]:
                    slot["sections"].append(sec)
                slot["ratio"] = round(r, 3)
                slot["status"] = "High" if r >= 1.0 else "Watch"

    congestion_hours = []
    for h in sorted(congested_clock.keys()):
        slot = congested_clock[h]
        congestion_hours.append({
            "h": h,
            "peak_trucks": slot["peak"],
            "sections": slot["sections"],
            "ratio": slot.get("ratio"),
            "status": slot.get("status"),
            "label": "%02d:00" % h,
        })
    congestion_hours.sort(key=lambda x: (-(1 if x["status"] == "High" else 0), -x["peak_trucks"], x["h"]))

    meter_hint = None
    if worst and worst["ratio"] >= 0.7 and worst["peak_trucks"] > 0:
        scale = min(1.0, (worst["cap_trucks_bin"] * 0.95) / worst["peak_trucks"])
        if scale < 0.999:
            suggestions = []
            for pr in path_rows:
                if worst["section"] not in pr["sections"]:
                    continue
                sug = max(1, int(math.floor(pr["n_trucks"] * scale)))
                if sug < pr["n_trucks"]:
                    suggestions.append({
                        "id": pr["id"],
                        "label": pr["label"],
                        "current_dt": pr["n_trucks"],
                        "suggested_dt": sug,
                        "section": worst["section"],
                    })
            meter_hint = {
                "section": worst["section"],
                "scale": round(scale, 3),
                "text": (
                    "To keep %s under measured peak (~%.0f trucks / %.0fh): "
                    "meter or cut ~%.0f%% DT on paths crossing it — advisory only, "
                    "does not change simulate tonnes."
                    % (worst["section"], worst["cap_trucks_bin"], bin_hours,
                       100 * (1 - scale))
                ),
                "suggestions": suggestions,
            }

    high_n = sum(1 for s in sections_out if s["status"] == "High")
    shared_n = sum(1 for s in sections_out if s["shared"])

    return {
        "ok": True,
        "shift_hours": shift_hours,
        "whole_day": whole_day,
        "n_shifts": n_shifts,
        "horizon_hours": horizon_h,
        "start_hour": start_hour,
        "bin_hours": bin_hours,
        "wet": wet,
        "paths": [{
            "id": p["id"], "label": p["label"], "source": p["source"],
            "destination": p["destination"], "n_trucks": p["n_trucks"],
            "sections": p["sections"], "load_min": p["load_min"],
            "dump_min": p["dump_min"], "load_basis": p["load_basis"],
            "dump_basis": p["dump_basis"], "cycle_h": p["cycle_h"],
            "interval_h": p.get("interval_h"), "queue_min": p.get("queue_min"),
            "overhead_min": p.get("overhead_min"), "model": p.get("model"),
            "trips_per_truck": p["trips_per_truck"],
        } for p in path_rows],
        "sections": sections_out,
        "congestion_hours": congestion_hours,
        "worst_section": worst["section"] if worst else None,
        "meter_hint": meter_hint,
        "summary": {
            "n_paths": len(path_rows),
            "n_shared_sections": shared_n,
            "n_high_sections": high_n,
            "gps_speeds": gps_ok,
        },
        "dwell_notes": dwell_notes,
        "gps_window": hours_payload.get("window") if gps_ok else None,
        "note": (
            "DES on the segment model: per-truck timing from the calibrated hybrid "
            "(plan segment fleets, contractor baselines, cycle + overhead cadence), "
            "road time split over S1–S4 by the official directional speed limits, "
            "loaded pass + dump + EMPTY return both occupy the road; BLB rides its "
            "spur pseudo-section. Advisory — never clips simulate tonnes."
        ),
        "basis": {
            **basis,
            "uses_measured_dwell": not any("fallback" in (p["load_basis"] + p["dump_basis"])
                                          for p in path_rows),
            "fallback_dwell_10min": any("fallback" in (p["load_basis"] + p["dump_basis"])
                                       for p in path_rows),
            "gps_speeds": gps_ok,
        },
    }
