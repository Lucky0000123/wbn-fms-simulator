"""Advisory congestion model from Jul+ GPS archive + saved plans.

Not a tonne model. Fits hour-of-day loaded speed and optional truck_n effect
from stick segments in gps_archive. Saved plans contribute path/section demand
hints only. Never clips /api/simulate.
"""
from __future__ import annotations

import json
import math
import os
from collections import defaultdict

import plan_analogues as pa
import plan_corridor_hours as pch
import plan_smooth_advice as psa

_ROOT = os.path.dirname(os.path.abspath(__file__))
_SAVED = os.path.join(_ROOT, "data", "saved_plans")


def _fit_hour_model(path=None):
    """Per-hour mean loaded speed + mean trucks from archive/fixture."""
    hours_payload = pch.corridor_hours(dir_filter="down", path=path)
    if not hours_payload.get("ok"):
        return None, hours_payload
    by_h = {}
    for h in hours_payload.get("hours") or []:
        if h.get("speed_kmh") is None:
            continue
        by_h[int(h["h"])] = {
            "h": int(h["h"]),
            "speed_kmh": float(h["speed_kmh"]),
            "truck_n": float(h["truck_n"]) if h.get("truck_n") is not None else None,
            "n": int(h.get("n") or 0),
        }
    if len(by_h) < 6:
        return None, hours_payload
    spds = [v["speed_kmh"] for v in by_h.values()]
    free = sorted(spds)[int(0.75 * (len(spds) - 1))] if spds else None
    return {
        "by_hour": by_h,
        "free_flow_kmh": round(free, 2) if free is not None else None,
        "window": hours_payload.get("window"),
        "source": hours_payload.get("source"),
        "slow_hours": hours_payload.get("slow_hours") or [],
        "slow_sections": hours_payload.get("slow_sections") or [],
    }, hours_payload


def _saved_plan_hints():
    """Aggregate DT by section from dated saved plans (if any)."""
    if not os.path.isdir(_SAVED):
        return {"n_plans": 0, "section_dt": {}, "dates": []}
    section_dt = defaultdict(float)
    dates = []
    for name in os.listdir(_SAVED):
        if not name.endswith(".json"):
            continue
        path = os.path.join(_SAVED, name)
        try:
            with open(path, encoding="utf-8") as f:
                plan = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        dates.append(name[:-5])
        paths = plan.get("paths") or plan.get("draft") or []
        # saved shape: {paths: [{source,dest,dt,...}]} or draft dict
        if isinstance(paths, dict):
            entries = []
            for _id, r in paths.items():
                if not isinstance(r, dict):
                    continue
                key = r.get("key") or ""
                parts = key.split(">")
                entries.append({
                    "source": r.get("source") or (parts[0] if parts else ""),
                    "destination": r.get("dest") or (parts[1] if len(parts) > 1 else ""),
                    "dt": r.get("dt") or 0,
                })
            paths = entries
        for p in paths or []:
            if not isinstance(p, dict):
                continue
            src = p.get("source") or p.get("origin")
            dst = p.get("destination") or p.get("dest")
            dt = float(p.get("dt") or p.get("n_trucks") or 0)
            if not src or not dst or dt <= 0:
                continue
            for sec in pa.route_sections(src, dst):
                section_dt[sec] += dt
    return {
        "n_plans": len(dates),
        "dates": sorted(dates),
        "section_dt": {k: round(v, 1) for k, v in sorted(section_dt.items())},
    }


def congestion_advice(
    sections=None,
    path=None,
    plan_dt_by_section=None,
    vc_by_section=None,
    limit_gap_by_section=None,
):
    """Build advisory meter-release / slow-window guidance + smooth_actions."""
    fit, raw = _fit_hour_model(path=path)
    saved = _saved_plan_hints()
    if not fit:
        return {
            "ok": False,
            "error": (raw or {}).get("error") or "insufficient Jul+ GPS to fit",
            "advice": [],
            "smooth_actions": [],
            "model": None,
            "saved_plans": saved,
            "basis": {
                "congestion_clips_tonnes": False,
                "simulate_unchanged": True,
                "invents_playback_haul_speeds": False,
                "era": "struggle",
                "joint_hour_section_score": False,
            },
        }

    want = None
    if sections:
        want = {s.strip() for s in sections if str(s).strip()}

    by_h = fit["by_hour"]
    free = fit["free_flow_kmh"] or 18.0
    # Score hours: slower + busier = higher congestion index
    scored = []
    for h, v in by_h.items():
        spd = v["speed_kmh"]
        tn = v["truck_n"] or 0
        slow_frac = max(0.0, (free - spd) / max(free, 1e-6))
        score = slow_frac * 0.7 + min(1.0, tn / 12.0) * 0.3
        scored.append({
            "h": h,
            "speed_kmh": spd,
            "truck_n": v["truck_n"],
            "congestion_index": round(score, 3),
            "relative_to_free_pct": round(100.0 * spd / free, 1) if free else None,
        })
    scored.sort(key=lambda x: (-x["congestion_index"], x["speed_kmh"]))

    release = [x for x in scored if x["congestion_index"] >= 0.25][:5]
    quiet = sorted(scored, key=lambda x: (x["congestion_index"], -x["speed_kmh"]))[:3]

    advice = []
    if release:
        hs = ", ".join("%02d:00" % x["h"] for x in release[:3])
        advice.append({
            "kind": "meter_release",
            "priority": "high" if release[0]["congestion_index"] >= 0.35 else "medium",
            "text": (
                "Meter releases in slower Jul+ hours %s (loaded ~%.1f km/h vs free ~%.1f). "
                "Advisory only — does not change simulate tonnes."
                % (hs, release[0]["speed_kmh"], free)
            ),
        })
    if quiet:
        hs = ", ".join("%02d:00" % x["h"] for x in quiet[:2])
        advice.append({
            "kind": "prefer_window",
            "priority": "low",
            "text": "Quieter measured hours (struggle season): %s." % hs,
        })

    slow_secs = fit.get("slow_sections") or []
    if want:
        slow_secs = [s for s in slow_secs if s.get("section") in want] or slow_secs
    if slow_secs:
        s0 = slow_secs[0]
        advice.append({
            "kind": "slow_section",
            "priority": "medium",
            "text": (
                "Slowest stick section %s ~%s km/h loaded (Jul+). "
                "Watch shared-road overlap — tonnes still from simulate."
                % (s0.get("section"), s0.get("speed_kmh"))
            ),
            "section": s0.get("section"),
            "speed_kmh": s0.get("speed_kmh"),
        })

    # Saved-plan demand hint
    if saved["n_plans"] and saved["section_dt"]:
        top = sorted(saved["section_dt"].items(), key=lambda kv: -kv[1])[:2]
        advice.append({
            "kind": "saved_plan_demand",
            "priority": "low",
            "text": (
                "From %d saved plan(s): highest held DT on %s."
                % (saved["n_plans"], ", ".join("%s (~%.0f DT)" % (a, b) for a, b in top))
            ),
        })

    # Optional: if current plan_dt_by_section provided, flag overlap with slow secs
    if plan_dt_by_section and slow_secs:
        slow_names = {s["section"] for s in slow_secs}
        hit = [sec for sec, dt in plan_dt_by_section.items()
               if sec in slow_names and dt > 0]
        if hit:
            advice.append({
                "kind": "plan_crosses_slow",
                "priority": "high",
                "text": (
                    "Holding plan crosses slow Jul+ section(s): %s. "
                    "Meter releases; do not cut simulate tonnes for road V/C."
                    % ", ".join(hit)
                ),
            })

    # Simple linear: speed ≈ a + b*hour_sin — expose coefficients for literacy
    # Fit speed ~ intercept + cos/sin of hour angle (circular)
    xs, ys = [], []
    for h, v in by_h.items():
        ang = 2 * math.pi * h / 24.0
        xs.append((1.0, math.cos(ang), math.sin(ang)))
        ys.append(v["speed_kmh"])
    # Normal equations 3x3
    coef = None
    if len(ys) >= 8:
        def dot(a, b):
            return sum(i * j for i, j in zip(a, b))
        # X'X and X'y
        xtx = [[0.0] * 3 for _ in range(3)]
        xty = [0.0] * 3
        for xrow, y in zip(xs, ys):
            for i in range(3):
                xty[i] += xrow[i] * y
                for j in range(3):
                    xtx[i][j] += xrow[i] * xrow[j]
        # Solve 3x3 via Cramer's / gaussian
        def solve(A, b):
            M = [row[:] + [bv] for row, bv in zip(A, b)]
            n = 3
            for col in range(n):
                piv = max(range(col, n), key=lambda r: abs(M[r][col]))
                M[col], M[piv] = M[piv], M[col]
                if abs(M[col][col]) < 1e-12:
                    return None
                div = M[col][col]
                for j in range(col, n + 1):
                    M[col][j] /= div
                for r in range(n):
                    if r == col:
                        continue
                    f = M[r][col]
                    for j in range(col, n + 1):
                        M[r][j] -= f * M[col][j]
            return [M[i][n] for i in range(n)]
        coef = solve(xtx, xty)
        if coef:
            coef = [round(c, 4) for c in coef]

    smooth = psa.build_smooth_actions(
        fit,
        hours_payload=raw,
        plan_dt_by_section=plan_dt_by_section,
        vc_by_section=vc_by_section,
        limit_gap_by_section=limit_gap_by_section,
        sections=want,
        top_n=5,
    )
    if smooth:
        advice.append({
            "kind": "smooth_timetable",
            "priority": smooth[0].get("priority") or "medium",
            "text": (
                "Smooth-running timetable below joins plan DT × Jul+ hour × section"
                "%s — meter those windows; tonnes still from simulate."
                % (" × illustration V/C" if vc_by_section else "")
            ),
        })

    return {
        "ok": True,
        "model": {
            "type": "hour_of_day_loaded_speed",
            "era": "struggle",
            "free_flow_kmh": fit["free_flow_kmh"],
            "n_hours": len(by_h),
            "source": fit["source"],
            "window": fit["window"],
            "circular_coef": (
                {"intercept": coef[0], "cos": coef[1], "sin": coef[2]}
                if coef else None
            ),
            "note": (
                "Fit on Jul+ haul stick GPS only. Not peak Jan–May behaviour. "
                "Advisory — never clips simulate tonnes. Playback not used."
            ),
        },
        "ranked_hours": scored,
        "meter_release_hours": release,
        "quiet_hours": quiet,
        "slow_sections": slow_secs,
        "smooth_actions": smooth,
        "advice": advice,
        "saved_plans": saved,
        "basis": {
            "congestion_clips_tonnes": False,
            "simulate_unchanged": True,
            "invents_playback_haul_speeds": False,
            "trains_away_bias": False,
            "era": "struggle",
            "joint_hour_section_score": True,
            "uses_illustration_vc": bool(vc_by_section),
        },
    }
