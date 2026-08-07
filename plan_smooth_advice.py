"""Joint hour × section × plan-DT smooth-running advice (advisory only).

Ranks where/when to meter releases using Jul+ GPS hour speeds, holding-plan
section DT, optional illustration V/C, and optional posted-vs-GPS gaps.
Never clips /api/simulate tonnes. Never invents Jan–May or Playback haul speeds.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _f(x, default=None):
    try:
        if x is None or x == "":
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def _section_speeds(hours_payload: Optional[dict], fit: dict) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for row in (hours_payload or {}).get("by_section") or []:
        sec = row.get("section")
        spd = _f(row.get("speed_kmh"))
        if sec and spd is not None:
            out[str(sec)] = spd
    for row in fit.get("slow_sections") or []:
        sec = row.get("section")
        spd = _f(row.get("speed_kmh"))
        if sec and spd is not None and sec not in out:
            out[str(sec)] = spd
    return out


def _merge_windows(scored: List[dict], top_n: int = 5) -> List[dict]:
    """Collapse adjacent hours on the same section into meter windows."""
    if not scored:
        return []
    # Keep best hour rows first, then merge neighbours for readability
    scored = sorted(scored, key=lambda x: (-x["score"], x["section"], x["h"]))
    used = set()
    actions = []
    by_sec_hour = {(x["section"], x["h"]): x for x in scored}
    for row in scored:
        key = (row["section"], row["h"])
        if key in used:
            continue
        h0 = h1 = row["h"]
        # expand contiguous hours within 1 score band of this section
        while (row["section"], h0 - 1) in by_sec_hour and (row["section"], h0 - 1) not in used:
            prev = by_sec_hour[(row["section"], h0 - 1)]
            if prev["score"] < row["score"] * 0.55:
                break
            h0 -= 1
        while (row["section"], h1 + 1) in by_sec_hour and (row["section"], h1 + 1) not in used:
            nxt = by_sec_hour[(row["section"], h1 + 1)]
            if nxt["score"] < row["score"] * 0.55:
                break
            h1 += 1
        hours = list(range(h0, h1 + 1))
        for h in hours:
            used.add((row["section"], h))
        window_rows = [by_sec_hour[(row["section"], h)] for h in hours]
        best = max(window_rows, key=lambda x: x["score"])
        gap = best.get("limit_gap") or {}
        why_parts = [
            "plan ~%.0f DT on section" % best["plan_dt"],
            "Jul+ loaded ~%.1f km/h at %02d:00 (free ~%.1f)"
            % (best["speed_kmh"], best["h"], best["free_flow_kmh"]),
        ]
        if best.get("vc") is not None:
            why_parts.append("illustration V/C %.2f" % best["vc"])
        if gap.get("gap_kmh") is not None and gap["gap_kmh"] > 2:
            why_parts.append(
                "GPS ~%.0f vs posted ~%.0f km/h"
                % (gap.get("gps_kmh") or 0, gap.get("posted_kmh") or 0)
            )
        priority = "high" if best["score"] >= 0.45 or (best.get("vc") or 0) >= 1.0 else "medium"
        if best["score"] < 0.22:
            priority = "low"
        actions.append({
            "kind": "meter_window",
            "priority": priority,
            "section": row["section"],
            "hour_from": h0,
            "hour_to": h1,
            "window": "%02d:00–%02d:00" % (h0, h1),
            "score": round(best["score"], 3),
            "plan_dt": best["plan_dt"],
            "vc": best.get("vc"),
            "speed_kmh": best["speed_kmh"],
            "free_flow_kmh": best["free_flow_kmh"],
            "limit_gap": gap or None,
            "text": (
                "Meter releases on %s at %s — %s. "
                "Advisory only — does not change simulate tonnes."
                % (row["section"], "%02d:00–%02d:00" % (h0, h1), "; ".join(why_parts))
            ),
        })
        if len(actions) >= top_n:
            break
    return actions


def build_smooth_actions(
    fit: dict,
    hours_payload: Optional[dict] = None,
    plan_dt_by_section: Optional[dict] = None,
    vc_by_section: Optional[dict] = None,
    limit_gap_by_section: Optional[dict] = None,
    sections: Optional[Any] = None,
    top_n: int = 5,
) -> List[dict]:
    """Score (section, hour) pairs and return ranked meter windows."""
    if not fit or not fit.get("by_hour"):
        return []
    by_h = fit["by_hour"]
    free = _f(fit.get("free_flow_kmh"), 18.0) or 18.0
    sec_spd = _section_speeds(hours_payload, fit)

    plan_dt: Dict[str, float] = {}
    for k, v in (plan_dt_by_section or {}).items():
        dt = _f(v, 0.0) or 0.0
        if dt > 0 and k:
            plan_dt[str(k)] = dt
    if not plan_dt:
        # Fall back to slow sections so the timetable still teaches the clock
        for sec, spd in sec_spd.items():
            plan_dt[sec] = 1.0

    want = None
    if sections:
        want = {str(s).strip() for s in sections if str(s).strip()}
        filtered = {k: v for k, v in plan_dt.items() if k in want}
        if filtered:
            plan_dt = filtered

    max_dt = max(plan_dt.values()) if plan_dt else 1.0
    vc_map = {str(k): _f(v) for k, v in (vc_by_section or {}).items()}
    gap_map = {}
    for k, v in (limit_gap_by_section or {}).items():
        if isinstance(v, dict):
            gap_map[str(k)] = {
                "gps_kmh": _f(v.get("gps_kmh")),
                "posted_kmh": _f(v.get("posted_kmh")),
                "gap_kmh": _f(v.get("gap_kmh")),
            }

    scored = []
    for sec, dt in plan_dt.items():
        dt_n = dt / max_dt if max_dt else 0.0
        s_spd = sec_spd.get(sec)
        sec_slow = max(0.0, (free - s_spd) / free) if s_spd is not None else 0.15
        vc = vc_map.get(sec)
        vc_factor = max(vc, 1.0) if vc is not None else 1.0
        gap = gap_map.get(sec) or {}
        gap_boost = 1.0
        if gap.get("gap_kmh") is not None and gap["gap_kmh"] > 2:
            gap_boost = 1.0 + min(0.4, gap["gap_kmh"] / 40.0)

        for h, v in by_h.items():
            spd = _f(v.get("speed_kmh"))
            if spd is None:
                continue
            slow_frac = max(0.0, (free - spd) / free)
            # Skip near-free hours unless section V/C is already high
            if slow_frac < 0.08 and (vc is None or vc < 0.85):
                continue
            score = (
                dt_n
                * (0.50 * slow_frac + 0.20 * sec_slow + 0.30 * min(1.5, vc_factor) / 1.5)
                * gap_boost
            )
            if score < 0.08:
                continue
            scored.append({
                "section": sec,
                "h": int(h),
                "score": score,
                "plan_dt": dt,
                "vc": vc,
                "speed_kmh": spd,
                "free_flow_kmh": free,
                "limit_gap": gap,
            })

    return _merge_windows(scored, top_n=top_n)
