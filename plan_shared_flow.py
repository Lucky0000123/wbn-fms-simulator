"""DES-lite shared-road occupancy for multi-contractor holding plans.

Per-truck timing comes from the calibrated segment model
(congestion.predictor at the plan's combined fleets); road time is split
over S1–S4 by the official directional speed limits; every trip occupies
the road both ways. Advisory only — never clips /api/simulate tonnes.

Two quantities, deliberately kept apart (they have different units):

* **presence** — trucks ON a section at one moment (a STOCK, trucks).
  Reported as `occupancy` (mean concurrent trucks per display bin),
  `peak_trucks` / `peak_concurrent` (bin-free instantaneous maximum) and
  `ratio_presence` against how many trucks physically FIT on the section
  at the mining following distance.
* **flow** — trucks PASSING per hour (a FLOW, trucks/h). This is what the
  official capacity measures (limit speed ÷ following distance), so the
  headline `ratio` (v/c) is flow ÷ flow. Its window is a fixed hour, never
  the display bin, so v/c is bin-size invariant.

Dividing a stock by a flow×time was the pre-2026-08-23 v/c and it moved
2.5x when the display bin changed on identical traffic. Little's law is
the bridge: presence = flow x time-in-section, and both are reported.
"""
from __future__ import annotations

import bisect
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
BIN_HOURS = 1.0         # hourly display bins (matches congestion-hours UI)

# Representative-truck sample size. A row with more trucks than this is
# simulated with MAX_TRUCKS_SIM trucks each carrying weight n/MAX_TRUCKS_SIM,
# so occupancy and flow stay UNBIASED at any fleet size — the sample only
# coarsens the resolution, it never removes traffic. Before 2026-08-23 the
# fleet was TRUNCATED here while the response echoed the full n_trucks and
# priced the full fleet: a 5,000-truck row ran 400 trucks on the road and
# said nothing. Whatever this is set to, the basis is disclosed in the
# payload (`basis.simulation`, per-path `sim_trucks` / `sim_weight`).
MAX_TRUCKS_SIM = 400

# v/c is a FLOW ratio and its window is a fixed hour, independent of the
# display bin: capacity is trucks/hour, so the numerator must be measured
# over an hour whether the grid draws 15-minute or 1-hour cells.
VC_WINDOW_H = 1.0
SPUR_SPEED_FLOOR_KMH = 20.0  # no limit sheet for a spur; slowest posted bin
SPUR_LANE_CAP_TPH = SPUR_SPEED_FLOOR_KMH * 1000.0 / 50.0   # ONE lane
SPUR_KM_FALLBACK = 19.9      # BLB spur length when the route has no distance
EMPTY_SPEED_FACTOR = 1.25    # site GPS: empty runs ~1.25x loaded (spur only;
                             # the stick uses the official directional limits)

# ── Release profile: WHEN the day's trips start ──────────────────────────────
# MEASURED, not assumed.  Source: HAULAGE_CLEAN.TIME_LOADED, n = 273,222 loads
# over 234 days, load starts binned by hours-since-shift-start (the site runs
# two 12-h shifts, 07:00 and 19:00) and expressed as a MULTIPLIER on the
# uniform release rate.  chi-square against uniform = 34,883 on 23 df: "flat"
# is not a rounding difference from this data, it is refuted by it.
#
# What the measurement does and does not say:
#
#  * There IS a 1-hour ramp-up at shift start and a 2-hour wind-down, with the
#    FINAL hour of each shift near-zero (0.15 day / 0.17 night) — the road
#    empties for the changeover.  A flat model put a full hour of traffic on a
#    road that is emptying, which is where its worst errors lived (+238% at
#    19:00, +202% at 07:00, +161% at 18:00 against measured presence).
#  * There is NO meal-break dip: 12:00 = 1.05x and 13:00 = 1.11x, both ABOVE
#    the shift-start hour.  Do not add one.
#  * The interior hours (+2..+8) are reported as a BAND (1.05-1.31 day,
#    0.98-1.47 night) with no reproducible shape inside it, so they are held
#    at ONE constant here rather than given invented hour-to-hour structure.
#    That constant is not a guess either: it is whatever makes the twelve
#    hours sum to 12, i.e. conserve the shift's total releases.  It lands at
#    1.190 (day) / 1.229 (night), both INSIDE the measured band — which is the
#    consistency check that the anchors and the band agree.  If a future
#    measurement resolves the interior hour by hour, replace the constant with
#    the series; the band check below is what will tell you they disagree.
#
# The profile is applied as a monotone TIME WARP of the schedule inside each
# shift (_warp_release_time): the same SET of load starts is re-timed, never
# added to or removed from, so the executed trip count is conserved EXACTLY
# rather than to within rounding.  Reshaping WHEN trucks are released must not
# change HOW MANY trips are executed.
RELEASE_PROFILE_SOURCE = (
    "HAULAGE_CLEAN.TIME_LOADED — n=273,222 loads over 234 days; load starts "
    "by hours-since-shift-start ÷ the uniform rate (chi2 vs uniform = 34,883 "
    "on 23 df)")
SHIFT_STARTS_H = (7, 19)          # the site's two 12-h shifts (owner)
RELEASE_PROFILE_HOURS = 12        # the profile is defined over one 12-h shift
# hour-since-shift-start -> measured multiplier, for the hours the measurement
# resolves individually. The rest are filled by _fill_release_profile().
_RELEASE_ANCHORS_DAY = {0: 0.56, 1: 1.22, 9: 1.14, 10: 0.60, 11: 0.15}
_RELEASE_ANCHORS_NIGHT = {0: 0.51, 1: 1.19, 9: 0.98, 10: 0.55, 11: 0.17}
# measured band for the un-resolved interior hours (+2..+8)
_RELEASE_INTERIOR_BAND = {"day": (1.05, 1.31), "night": (0.98, 1.47)}


def _fill_release_profile(anchors: Dict[int, float],
                          band: Tuple[float, float]) -> Tuple[float, ...]:
    """12 hourly multipliers: measured anchors + ONE constant interior.

    The interior constant is fixed by conservation (the twelve multipliers
    must average 1.0, so the shift's total releases are unchanged) and is then
    CHECKED against the measured band. A constant outside the band would mean
    the anchors and the band disagree — that is a data problem, not something
    to clamp away quietly, so it raises here at import.
    """
    free = [h for h in range(RELEASE_PROFILE_HOURS) if h not in anchors]
    interior = (RELEASE_PROFILE_HOURS - sum(anchors.values())) / len(free)
    lo, hi = band
    if not (lo - 1e-9 <= interior <= hi + 1e-9):
        raise ValueError(
            "release profile interior %.3f falls outside the measured band "
            "%.2f-%.2f: the anchors and the band no longer agree, re-derive "
            "the profile from %s" % (interior, lo, hi, RELEASE_PROFILE_SOURCE))
    return tuple(anchors.get(h, interior) for h in range(RELEASE_PROFILE_HOURS))


RELEASE_PROFILE_DAY = _fill_release_profile(
    _RELEASE_ANCHORS_DAY, _RELEASE_INTERIOR_BAND["day"])
RELEASE_PROFILE_NIGHT = _fill_release_profile(
    _RELEASE_ANCHORS_NIGHT, _RELEASE_INTERIOR_BAND["night"])

# ── Per-segment time split: the official limits are NOT uniformly optimistic ─
# The route's TOTAL road time stays dispatch-anchored (the calibrated cycle);
# NOTHING below changes it. These factors only change how that total is
# DISTRIBUTED over S1-S4, and they are applied BEFORE the normalisation that
# re-anchors the total, so only their RATIOS matter (the common level is
# absorbed by the anchor — which is why they sit near the repo's site-wide
# speed_factor of 1.59-1.86 with S4 as the outlier).
#
# Splitting by official speed-limit time assumes the limits are wrong by the
# same factor everywhere. Measured two independent ways — 463,060 vendor
# segment traversals (22 days) and 11,611 haul-truck GPS bin-traversals
# (8 days), agreeing within 6% — they are not:
#
#   segment           limit share   measured (vendor / GPS)   measured ÷ limit
#   S1 TF-KR             42.2%         47.1% / 44.5%            1.60-1.67
#   S2 KR-POS 12         14.9%         17.3% / 19.9%            1.67-2.11
#   S3 POS 12-KM15       15.4%         15.9% / 15.3%            1.49-1.57  (ok)
#   S4 KM15-coast        27.5%         19.7% / 20.3%            1.03-1.17
#
# S4 is the defect: the posted limits are essentially ACCURATE there while
# S1-S3 run 1.5-2.1x their posted time, so a limit-proportional split
# mechanically dumps 7.2-7.8 pp (36% relative) of every route's road time onto
# S4 — the tightest section on the road, and the one the card is read for.
# This is BIAS, not variance: S4's measured share never reaches 27.5% in ANY
# of the 24 hours (range 18.9-23.9%). The obvious suspect — the un-sheeted
# KM 0-5 port assumption (speed_limits.ASSUMPTIONS) — was tested and explains
# only 1.2 of the 7.8 pp, so it is not the cause and is left alone.
SEGMENT_TIME_FACTORS = {
    "S1": {"loaded": 1.60, "empty": 1.28},
    "S2": {"loaded": 1.67, "empty": 1.35},
    "S3": {"loaded": 1.50, "empty": 1.35},
    "S4": {"loaded": 1.05, "empty": 1.03},
}
SEGMENT_TIME_FACTORS_SOURCE = (
    "463,060 vendor segment traversals (22 days) + 11,611 haul-truck GPS "
    "bin-traversals (8 days), agreeing within 6%: measured segment share ÷ "
    "official-speed-limit share, applied before normalisation so the route's "
    "dispatch-anchored TOTAL road time is unchanged")
# The BLB spur has no limit sheet and no vendor/GPS traversal study of its own,
# so it keeps 1.0 — stated as un-measured rather than borrowed from the stick.
SPUR_TIME_FACTOR = 1.0


def _release_profile_for_clock(clock_h: float) -> Tuple[Tuple[float, ...], str]:
    """(profile, name) for the shift that starts at this clock hour."""
    c = float(clock_h) % 24.0
    if SHIFT_STARTS_H[0] <= c < SHIFT_STARTS_H[1]:
        return RELEASE_PROFILE_DAY, "day"
    return RELEASE_PROFILE_NIGHT, "night"


def _release_cdf(profile: Tuple[float, ...]) -> List[float]:
    """Cumulative share of the shift's releases at each hour boundary."""
    tot = float(sum(profile)) or 1.0
    out = [0.0]
    for v in profile:
        out.append(out[-1] + float(v) / tot)
    out[-1] = 1.0
    return out


def _warp_unit(u: float, cdf: List[float]) -> float:
    """Inverse CDF: uniform position u in [0,1) -> profile position in [0,1).

    Monotone and onto, so it re-times a schedule without changing how many
    departures it contains — the conservation property the whole fix rests on.
    """
    n = len(cdf) - 1
    if not (u > 0.0):
        return 0.0
    if u >= 1.0:
        return 1.0 - 1e-12
    i = min(max(bisect.bisect_right(cdf, u) - 1, 0), n - 1)
    span = cdf[i + 1] - cdf[i]
    frac = 0.0 if span <= 1e-15 else (u - cdf[i]) / span
    return (i + frac) / n


def _warp_release_time(t: float, shift_hours: float, n_shifts: int,
                       cdfs: List[List[float]]) -> float:
    """Re-time one load start inside its own shift window.

    Each window [s*shift_hours, (s+1)*shift_hours) maps onto ITSELF, so the
    warp is a bijection of the horizon: the trip count per row, per shift and
    in total is identical before and after.
    """
    if shift_hours <= 0 or not cdfs:
        return t
    s = min(max(int(t // shift_hours), 0), n_shifts - 1)
    u = (t - s * shift_hours) / shift_hours
    return (s + _warp_unit(u, cdfs[s])) * shift_hours


def _f(x, default=None):
    try:
        if x is None or x == "":
            return default
        v = float(x)
    except (TypeError, ValueError):
        return default
    # NaN/inf reach here from JSON as float('nan')/float('inf'); they used to
    # pass straight through and blow up in round() as a raw 500.
    return v if math.isfinite(v) else default


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


def _spur_junctions() -> Tuple[Dict[str, float], str]:
    """{origin: junction chainage km} for spur origins, plus its source.

    BLB is a spur that JOINS the stick at km 2.45, it is not a road of its
    own: in the committed survey (data/haul_road_chainage_public.csv) road
    BLB's km-2.450 point sits 0.2 m from the mainline's own km-2.450 point on
    the same datum, separating to 87 m by km 2.575, and congestion.physics
    says the same independently (SPUR_KM['BLB'] = 19.9 = 2.5 join + 17.4
    spur). So a BLB truck runs its spur AND the lower mainline below the
    junction — 2.45 km of S4 to the coast, 12.55 km to FENI KM15. Charging
    it to a spur pseudo-section ALONE under-counted S4, the tightest
    section, by 28% on the real 2026-09-03 plan.

    The constant is imported, never re-typed: congestion.segments first (its
    intended home), congestion.sections second (where it landed), and only
    then a literal that carries the survey citation with it.
    """
    for mod, attr in (("congestion.segments", "SPUR_JOIN_KM"),
                      ("congestion.sections", "SPUR_JOIN_KM")):
        try:
            m = __import__(mod, fromlist=[attr])
            table = getattr(m, attr, None)
            if isinstance(table, dict) and table:
                src = getattr(m, "SPUR_JOIN_SOURCE", None) or (
                    "%s.%s" % (mod, attr))
                return {str(k).upper(): float(v) for k, v in table.items()}, src
        except Exception:      # a co-owned module moving under us must not 500
            continue
    return ({"BLB": 2.45},
            "data/haul_road_chainage_public.csv: BLB km 2.450 is 0.2 m from "
            "mainline (CRD) km 2.450 on the same chainage datum "
            "(local fallback — congestion.segments.SPUR_JOIN_KM not found)")


def _wrap_spans(t0: float, dur: float, horizon: float) -> List[Tuple[float, float]]:
    """Split [t0, t0+dur) into pieces inside [0, horizon), wrapping the tail.

    A trip that starts before the end of the horizon does not evaporate when
    the clock runs out: the plan repeats day after day, so the tail of the
    last release is the traffic already on the road when the timeline starts.
    Wrapping (rather than clipping) is what makes truck-hours conserve
    exactly; clipping silently deleted 10-18% of the road's work.
    """
    out: List[Tuple[float, float]] = []
    if dur <= 0 or horizon <= 0:
        return out
    s = t0 % horizon
    left = min(dur, horizon)      # a single span never covers the day twice
    while left > 1e-12:
        take = min(left, horizon - s)
        out.append((s, s + take))
        left -= take
        s = 0.0
    return out


def _peak_concurrent(points: List[Tuple[float, float]]) -> float:
    """Max simultaneous weighted trucks from (time, +/-weight) sweep points.

    Bin-free: this is the true instantaneous maximum, so it cannot move when
    the display bin changes. Exits are applied before entries at equal times
    so a hand-over does not read as an extra truck.
    """
    if not points:
        return 0.0
    cur = best = 0.0
    for _t, dw in sorted(points, key=lambda x: (x[0], x[1])):
        cur += dw
        if cur > best:
            best = cur
    return best


def _peak_flow_per_h(entries: List[Tuple[float, float]], horizon: float,
                     window_h: float) -> float:
    """Max weighted passages in any `window_h` window (circular), per hour.

    The maximum of a sliding window over a counting process is attained at a
    window starting on an entry, so this is exact — no grid, and therefore no
    dependence on the display bin.
    """
    if not entries or horizon <= 0 or window_h <= 0:
        return 0.0
    total = sum(w for _t, w in entries)
    if window_h >= horizon:
        return total / horizon
    ts = sorted(entries)
    n = len(ts)
    times = [t for t, _w in ts]
    times = times + [t + horizon for t in times]
    weights = [w for _t, w in ts] * 2
    pref = [0.0]
    for w in weights:
        pref.append(pref[-1] + w)
    best = 0.0
    for i in range(n):
        j = bisect.bisect_left(times, times[i] + window_h, i, 2 * n)
        best = max(best, pref[j] - pref[i])
    return best / window_h


def _cross_sections(passes: List[Tuple[float, float, float, float, float, str]],
                    horizon: float, min_km: float = 0.05) -> List[dict]:
    """Split a section at every leg boundary and report each cross-section.

    A section is honestly ONE number only when every truck on it runs its whole
    length. BLB breaks that: a BLB truck joins the stick at SPUR_JOIN_KM = 2.45
    and occupies 2.45 km of KM15-coast's 15 km (16%), but a single section row
    counts it as a full passage. Measured on the real 2026-09-03 plan the
    loaded flow BELOW the junction is 50.7/h against 30.2/h above it — a 68%
    step hidden inside one reported number. POS 10 (km 17.0) does the same
    thing to POS 12-KM15 on a smaller scale.

    So report the pieces, and let the caller label the section headline as the
    WORST cross-section rather than an average of two different roads. Returns
    [] for a uniform section, where the split would be the section itself.
    """
    if not passes or horizon <= 0:
        return []
    edges = sorted({round(x, 6) for p in passes for x in (p[0], p[1])})
    if len(edges) <= 2:
        return []
    out: List[dict] = []
    for a, b in zip(edges, edges[1:]):
        if b - a < min_km:
            continue
        ent: Dict[str, List[Tuple[float, float]]] = {"loaded": [], "empty": []}
        th = 0.0
        for k_lo, k_hi, t_in, dur, w, dirn in passes:
            if k_lo > a + 1e-9 or k_hi < b - 1e-9:
                continue                      # this leg does not cover [a, b]
            span = k_hi - k_lo
            th += w * dur * (b - a) / span
            # Loaded runs DOWN-chainage (enters the slice at its top, b);
            # empty runs UP (enters at the bottom, a). 100.0% of loaded
            # corridor hauls run down-chainage — see CLAUDE.md, 298,340 trips,
            # zero counter-examples.
            off = (k_hi - b) / span if dirn == "loaded" else (a - k_lo) / span
            ent[dirn].append(((t_in + off * dur) % horizon, w))
        fl = _peak_flow_per_h(ent["loaded"], horizon, VC_WINDOW_H)
        fe = _peak_flow_per_h(ent["empty"], horizon, VC_WINDOW_H)
        out.append({
            "km_lo": round(a, 2), "km_hi": round(b, 2),
            "length_km": round(b - a, 2),
            "peak_flow_loaded_per_h": round(fl, 1),
            "peak_flow_empty_per_h": round(fe, 1),
            "peak_flow_per_h": round(max(fl, fe), 1),
            "mean_concurrent": round(th / horizon, 2),
            "truck_hours": round(th, 1),
        })
    return out


def _norm_plans(plans: Optional[List[dict]]) -> List[dict]:
    # canonical_area is the repo's ONE normaliser (see CLAUDE.md). Without it
    # an alias row ("TOFU>FENI KM0") builds a route key the calibration has
    # never seen and predict() silently prices it on DEFAULT params — the
    # J52 shape: wrong physics with a healthy-looking answer.
    from prediction_pipeline import canonical_area
    out = []
    for i, p in enumerate(plans or []):
        if not isinstance(p, dict):
            continue
        src = canonical_area(str(p.get("source") or p.get("origin") or "").strip())
        dst = canonical_area(str(p.get("destination") or p.get("dest") or "").strip())
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
    shift_hours long) so the timeline covers the full 24 h clock - the site
    runs 2 x 12 h, it is NOT one continuous 24 h shift (owner, 2026-08-19).

    Releases are uniform over each row's inter-trip interval, which makes a
    re-stagger at the changeover the SAME set of departure times as carrying
    on: the shift boundary no longer deletes the trips in flight across it
    (it used to lose 18% of the road's truck-hours). `bin_hours` sets the
    DISPLAY grain only - both the occupancy metric and the v/c are defined
    independently of it and are asserted invariant in
    test_plan_shared_flow.py."""
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
    from congestion.speed_limits import (span_times_min as _span_times,
                                         FOLLOWING_DISTANCE_M as _FOLLOW_M)
    from congestion.segments import SEGMENTS as _SEGMENTS
    from congestion.physics import (route_distance_km as _route_km,
                                    BLB_COASTAL_DEST as _COASTAL)
    _join_km, _join_src = _spur_junctions()

    warnings: List[str] = []
    unpriced: List[str] = []
    spur_km: Dict[str, float] = {}

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
        # An unseen route used to be priced SILENTLY on a 20-minute fallback
        # cycle and rendered like any other row. Price it if you must, but
        # say so: `priced` on the row, the route in basis.unpriced_routes and
        # a warning in the payload (owner-visible).
        if pr is None:
            priced = "fallback"
            unpriced.append(p["route"])
        elif pr.get("calibrated"):
            priced = "calibrated"
        else:
            priced = "model_defaults"
            unpriced.append(p["route"])
        comp = (pr or {}).get("components") or {}
        road_min = (comp.get("t_free_road") or 0) + (comp.get("bpr_penalty_minutes") or 0)
        queue_min = comp.get("queue_wait_minutes") or 0.0
        overhead_min = comp.get("overhead_per_trip_minutes") or 240.0
        cyc_min = (pr or {}).get("cycle_time_minutes") or (road_min + load_min + dump_min)
        if road_min <= 0:
            road_min = max(30.0, cyc_min - load_min - dump_min - queue_min)
        # Which chainage does this route occupy? Stick routes: node to node.
        # Spur origins (BLB): the spur leg PLUS the mainline between the
        # junction and the destination — both, never one instead of the other.
        # The coastal dumps (POS 14/15/16) sit on the spur itself, so they get
        # no mainline; the numeric guard catches any other such destination
        # (a mainline run longer than the calibrated route distance means the
        # mainline is not the way there).
        route_km = _route_km(p["source"], p["destination"])
        lo = hi = None
        join = _join_km.get(p["source"].upper())
        if segs:
            a, b = _node_km(p["source"]), _node_km(p["destination"])
            lo, hi = min(a, b), max(a, b)
        elif join is not None:
            dk = _node_km(p["destination"])
            if dk is not None and p["destination"].upper() not in _COASTAL:
                c_lo, c_hi = min(join, dk), max(join, dk)
                if not (route_km and (c_hi - c_lo) > route_km + 0.5):
                    lo, hi = c_lo, c_hi

        # raw = [(label, overlap_km, loaded_min, empty_min, speed_kmh,
        #         km_lo, km_hi)] in travel order (pit -> coast): the spur leg
        # first, then the mainline segments from the junction down. km_lo/km_hi
        # are the mainline chainage this leg actually occupies, and are None on
        # the spur (its own chainage is a different datum) — they are what lets
        # a section that is NOT uniform be reported cross-section by
        # cross-section instead of as one mixed number (_cross_sections).
        raw = []
        main_km = 0.0
        if lo is not None and hi is not None and hi - lo > 1e-9:
            for s in _SEGMENTS:
                o_lo, o_hi = max(lo, s['bottom_km']), min(hi, s['top_km'])
                ov = o_hi - o_lo
                if ov <= 1e-9:
                    continue
                tl, te = _span_times(o_lo, o_hi)
                # MEASURED correction: the official limits are 40-65% optimistic
                # on S1-S3 and accurate on S4, so splitting by limit time alone
                # pushes 7-8 pp of every route's road time onto S4. Applied
                # before the normalisation below, so the route TOTAL is
                # untouched — only its distribution moves.
                fac = SEGMENT_TIME_FACTORS.get(s['id']) or {}
                raw.append((s['label'], ov,
                            (tl or ov) * float(fac.get('loaded', 1.0)),
                            (te or ov) * float(fac.get('empty', 1.0)),
                            (s.get('speeds') or {}).get('loaded', {}).get('mean'),
                            o_lo, o_hi))
                main_km += ov
        if join is not None or not raw:
            # spur remainder: the route's calibrated distance less whatever of
            # it runs on the mainline — physics' own 17.4 km spur falls out of
            # this to within 50 m, so nothing is invented. (The BLB km column
            # has a 7.025 km chainage discontinuity, which is why the spur
            # length comes from route_distance_km and not from the survey span.)
            lbl = "%s spur" % p["source"].upper()
            km = max(0.0, (route_km or SPUR_KM_FALLBACK) - main_km)
            if km > 0.05 or not raw:
                km = km or SPUR_KM_FALLBACK
                spur_km[lbl] = max(spur_km.get(lbl, 0.0), float(km))
                tl_spur = 60.0 * km / SPUR_SPEED_FLOOR_KMH
                raw.insert(0, (lbl, km, tl_spur * SPUR_TIME_FACTOR,
                               tl_spur / EMPTY_SPEED_FACTOR * SPUR_TIME_FACTOR,
                               None, None, None))

        # The route's TOTAL road time stays dispatch-anchored; the official
        # limits (corrected by the measured SEGMENT_TIME_FACTORS) and the spur
        # floor only set each leg's SHARE of it. Because the factors are inside
        # `tot`, the normalisation absorbs their common level: the route total
        # is bit-for-bit what it was, and only the split moves.
        tot = sum(r[2] + r[3] for r in raw) or 1.0
        k = road_min / tot
        sec_loaded, sec_empty = [], []
        for lbl_, ov, tl, te, spd, k_lo, k_hi in raw:
            sec_loaded.append({"section": lbl_, "hours": tl * k / 60.0,
                               "speed_kmh": spd, "km": round(ov, 2),
                               "km_lo": k_lo, "km_hi": k_hi})
            sec_empty.append({"section": lbl_, "hours": te * k / 60.0,
                              "km": round(ov, 2),
                              "km_lo": k_lo, "km_hi": k_hi})
        travel_h = sum(x["hours"] for x in sec_loaded)
        cycle_h = cyc_min / 60.0
        interval_h = max((cyc_min + overhead_min) / 60.0, 1e-3)  # inter-trip spacing
        # The CADENCE, not a floor()ed count. `max(1, floor(shift/interval))`
        # both dropped part-trips (-41% on TF>POS 12) and credited a full trip
        # to a truck whose interval exceeds the shift (+35% on TF>HUAFEI,
        # interval 16.5 h against a 12 h shift). Trucks are released on the
        # continuous schedule below, so the executed count follows the model
        # rate instead of a rounding rule.
        trips_per_truck = shift_hours / interval_h
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
            "trips_per_truck": round(trips_per_truck, 2),
            "trips_per_truck_horizon": round(horizon_h / interval_h, 2),
            "trips_per_day": round(24.0 / interval_h, 3),
            "expected_trips": round(p["n_trucks"] * horizon_h / interval_h, 1),
            "priced": priced,
            "model": (pr or {}).get("model_version") or "fallback",
        })

    # ── Release schedule ────────────────────────────────────────────────
    # Each ROW's trucks are spread evenly over one inter-trip interval and
    # then repeat every interval — the steady dispatch the pricing model
    # charges for. Three defects die here:
    #
    #  * ORDER DEPENDENCE. The old loop walked a `truck_idx` that accumulated
    #    across every row at a source, so list position decided who got the
    #    late (and then clipped) release slots: swapping two 250-DT TF rows
    #    moved the KR–POS 12 peak by 43%. A row's releases now depend only on
    #    that row's own numbers.
    #  * TRIP COUNT. Departures are generated on the continuous schedule
    #    while t < horizon, so trips per truck average exactly
    #    horizon / interval_h. No floor(), no max(1, ...) crediting a trip to
    #    a truck whose interval exceeds the horizon.
    #  * SHIFT-BOUNDARY EVAPORATION. A trip that starts before the boundary
    #    RUNS TO COMPLETION and carries into the next window; the tail of the
    #    last release wraps onto the start of the timeline (the plan repeats),
    #    so nothing is dropped and nothing is counted twice. The old code
    #    dropped 66 of 1512 planned trips outright and clipped the rest at the
    #    changeover, losing 18% of road truck-hours.
    #
    # The uniform schedule is then RE-TIMED by the measured release profile
    # (RELEASE_PROFILE_DAY / _NIGHT). Until 2026-08-24 this model released
    # uniformly and the hour section of the card came out flat — CV 0.014-0.030
    # on real plans, 23 of 24 identical cells — against a measured presence CV
    # of 0.319 and a peak/trough of 2.6x-7.7x. That flat profile was wrong in a
    # specific, same-signed way: it put a full hour of traffic on a road that
    # empties for the shift changeover (+238% at 19:00, +202% at 07:00, +161%
    # at 18:00) and paid for it by understating 21:00-04:00, the genuinely
    # busiest hours, by 16-29%.
    #
    # The warp is anchored on the LOAD START, because that is what was measured
    # (HAULAGE_CLEAN.TIME_LOADED). The row's queue wait sits BEFORE the load, so
    # the schedule generated below is shifted by queue_min and wrapped onto the
    # horizon first (the plan repeats), and road entry is then load_min later.
    # Under a flat profile that shift was invisible — a uniform train rotated is
    # the same uniform train — which is exactly why it had never mattered; with
    # a profile it decides which clock hour a row's ramp lands on, and TF>HUAFEI
    # queues 182.6 min, three whole hours of it.
    #
    # CONSERVATION IS THE POINT: _warp_release_time maps each shift window onto
    # itself, so it re-times the SAME SET of departures. Executed trips per row,
    # per shift and in total are identical to the uniform schedule — reshaping
    # WHEN trucks are released must not change HOW MANY trips run. The test file
    # pins this (uniform vs profiled executed_trips, exactly equal).
    #
    # OPEN, and stated rather than tuned away: PRESENCE still lags the measured
    # presence profile by each section's TRANSIT TIME, because this model
    # completes trips in flight across the changeover (`trips_in_flight_complete`
    # below). Measured against the reconstructed measured presence on the real
    # 2026-09-03 plan, the amplitude is now right — median absolute hourly error
    # 0.7-4.1% on three of five sections once the section's own lag is allowed
    # for, against 17.7-18.6% for the flat model at ANY phase — but the lag
    # itself is 0-1 h (BLB spur, TF-KR) rising to 2-3 h (KM15-coast), while the
    # measurement shows ~0-1 h everywhere (its busiest presence hours are
    # 21:00-04:00, the same hours as the busiest RELEASES, not 2-3 h later).
    # The likely cause is that real trucks hand over / park at the changeover
    # instead of finishing the leg. Closing it needs a calibrated changeover
    # behaviour — how long a truck stands where at handover — which is not in
    # the release measurement. Inventing a freeze here would either destroy
    # trips or fabricate a duration, so it is left open and disclosed
    # (`basis.release_profile.presence_lag`).
    #
    # Still NOT modelled, and still not invented: synchronised meal breaks
    # (there is no meal-break dip in the data — 12:00 = 1.05x, 13:00 = 1.11x)
    # and a loader-face schedule (reports/ROAD_CROWDING_BY_HOUR_PLAN.md §6).
    #
    # Loading faces (rules §10.9, ~1 loader per 15 trucks) are no longer the
    # stagger: the model's interval already carries the loader queue
    # (queue_wait_minutes), so re-deriving a stagger from load time alone
    # double-counted it — and produced an 11 h release window for POS 12's 36
    # trucks while TF's 471 spread over 4.6 h. Faces are CHECKED and reported
    # against the release rate instead (`sources` in the payload).
    events: List[Tuple[str, float, float, float, str, str,
                       Optional[float], Optional[float]]] = []
    section_plans: Dict[str, set] = defaultdict(set)

    # One inverse-CDF per shift window, picked by the CLOCK hour that window
    # starts on (07:00 -> day, 19:00 -> night), so the same code serves
    # whole_day=True (two windows) and whole_day=False (one).
    release_windows = []
    for s in range(n_shifts):
        clock = (start_hour + s * shift_hours) % 24
        prof, pname = _release_profile_for_clock(clock)
        release_windows.append({"shift": s, "clock_start": round(clock, 2),
                                "profile": pname,
                                "multipliers": [round(v, 3) for v in prof]})
    release_cdfs = [_release_cdf(RELEASE_PROFILE_DAY if w["profile"] == "day"
                                 else RELEASE_PROFILE_NIGHT)
                    for w in release_windows]

    for pr in path_rows:
        n = pr["n_trucks"]
        n_sim = max(1, min(n, MAX_TRUCKS_SIM))
        weight = n / float(n_sim)
        pr["sim_trucks"] = n_sim
        pr["sim_weight"] = round(weight, 4)
        # A degenerate interval would otherwise spin the release loop for
        # millions of iterations and hang the endpoint; 3 minutes is already
        # far below any measured cycle here.
        interval_h = max(pr["interval_h"], 0.05)
        queue_h = pr["queue_min"] / 60.0
        load_h = pr["load_min"] / 60.0
        executed = 0.0
        for j in range(n_sim):
            phase = (j + 0.5) / n_sim * interval_h
            for k in range(int(math.ceil(horizon_h / interval_h)) + 1):
                t_depart = phase + k * interval_h
                if t_depart >= horizon_h:
                    break
                executed += weight
                # Dispatch -> queue -> LOAD START (what TIME_LOADED measures,
                # and what the release profile re-times) -> road.
                t_load = _warp_release_time(
                    (t_depart + queue_h) % horizon_h,
                    shift_hours, n_shifts, release_cdfs)
                t_cursor = t_load + load_h
                for st in pr["sec_times"]:             # loaded pass, pit -> dump
                    events.append((st["section"], t_cursor, t_cursor + st["hours"],
                                   weight, "loaded", pr["id"],
                                   st.get("km_lo"), st.get("km_hi")))
                    section_plans[st["section"]].add(pr["label"])
                    t_cursor += st["hours"]
                t_cursor += pr["dump_min"] / 60.0       # dump dwell (off road)
                for st in reversed(pr["sec_times_empty"]):   # EMPTY return
                    events.append((st["section"], t_cursor, t_cursor + st["hours"],
                                   weight, "empty", pr["id"],
                                   st.get("km_lo"), st.get("km_hi")))
                    section_plans[st["section"]].add(pr["label"])
                    t_cursor += st["hours"]
        pr["executed_trips"] = round(executed, 1)
        pr["release_headway_min"] = round(interval_h * 60.0 / max(n, 1), 2)

    # Loading-face check per source: fleet and faces decide whether the pit
    # can sustain the release rate the cadence implies. Reported, not applied
    # — the queue term inside interval_h is where loader contention is priced.
    by_src: Dict[str, List[dict]] = defaultdict(list)
    for pr in path_rows:
        by_src[pr["source"].upper()].append(pr)
    sources_out = []
    for src in sorted(by_src):
        group = by_src[src]
        src_trucks = sum(g["n_trucks"] for g in group)
        faces = max(1, int(round(src_trucks / 15.0)))
        load_min_src = max(g["load_min"] for g in group)
        rate_ph = sum(g["n_trucks"] / g["interval_h"] for g in group)
        face_cap_ph = faces * 60.0 / max(load_min_src, 1e-6)
        needed = max(1, int(math.ceil(rate_ph * load_min_src / 60.0)))
        limited = rate_ph > face_cap_ph * 1.001
        sources_out.append({
            "source": src, "n_trucks": src_trucks, "faces": faces,
            "faces_basis": "rules §10.9: ~1 loader per 15 trucks",
            "load_min": round(load_min_src, 2),
            "release_rate_per_h": round(rate_ph, 2),
            "face_capacity_per_h": round(face_cap_ph, 2),
            "faces_needed": needed,
            "load_limited": limited,
        })
        if limited:
            warnings.append(
                "%s: the plan releases %.1f trucks/h but %d loading face(s) at "
                "%.1f min serve %.1f/h — %d faces would be needed. Loader "
                "contention is already inside the model's interval; the road "
                "timeline is not re-staggered for it."
                % (src, rate_ph, faces, load_min_src, face_cap_ph, needed))

    # ── Binning ─────────────────────────────────────────────────────────
    # occ_h  = truck-HOURS per bin        -> mean concurrent trucks (a stock)
    # ent    = section entries per bin    -> passages per hour (a flow)
    # Presence and flow are accumulated separately and never divided by each
    # other's capacity.
    n_bins = int(math.ceil(horizon_h / bin_hours))
    bin_w = [min((b + 1) * bin_hours, horizon_h) - b * bin_hours
             for b in range(n_bins)]
    occ_h: Dict[str, List[float]] = defaultdict(lambda: [0.0] * n_bins)
    ent: Dict[str, List[float]] = defaultdict(lambda: [0.0] * n_bins)
    ent_dir: Dict[str, Dict[str, List[float]]] = defaultdict(
        lambda: {"loaded": [0.0] * n_bins, "empty": [0.0] * n_bins})
    entry_times: Dict[str, Dict[str, List[Tuple[float, float]]]] = defaultdict(
        lambda: {"loaded": [], "empty": []})
    sweep: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
    truck_h: Dict[str, float] = defaultdict(float)
    truck_h_path: Dict[str, float] = defaultdict(float)
    # (km_lo, km_hi, t_enter, duration, weight, direction) per section, for the
    # cross-section split of sections that are NOT uniform (see _cross_sections)
    passages: Dict[str, List[Tuple[float, float, float, float, float, str]]] = \
        defaultdict(list)

    # keyed on row id, NOT the display label: two rows can share a label
    # (TF>HUAFEI · SMA carries both a LIM-TOS and a LIM-LD row) and summing
    # them under one key would double-count each row's truck-hours.
    for sec, t0, t1, w, dirn, pid, km_lo, km_hi in events:
        dur = t1 - t0
        truck_h[sec] += w * dur
        truck_h_path[pid] += w * dur
        if km_lo is not None and km_hi is not None and km_hi - km_lo > 1e-9:
            passages[sec].append((float(km_lo), float(km_hi),
                                  t0 % horizon_h, dur, w, dirn))
        for a, b in _wrap_spans(t0, dur, horizon_h):
            b0 = min(n_bins - 1, max(0, int(a / bin_hours)))
            b1 = min(n_bins - 1, max(0, int(max(a, b - 1e-12) / bin_hours)))
            for bi in range(b0, b1 + 1):
                lo = max(a, bi * bin_hours)
                hi = min(b, (bi + 1) * bin_hours)
                if hi > lo:
                    occ_h[sec][bi] += w * (hi - lo)
            sweep[sec].append((a, w))
            sweep[sec].append((b, -w))
        t_in = t0 % horizon_h
        bi = min(n_bins - 1, max(0, int(t_in / bin_hours)))
        ent[sec][bi] += w
        ent_dir[sec][dirn][bi] += w
        entry_times[sec][dirn].append((t_in, w))

    sections_out = []
    congested_clock = defaultdict(lambda: {"peak": 0, "sections": []})
    worst = None

    from congestion.segments import SEGMENTS as _SEGS
    _seg_by_label = {s['label']: s for s in _SEGS}
    all_secs = [s['label'] for s in _SEGS] + sorted(
        s for s in section_plans if s not in {x['label'] for x in _SEGS})
    used_secs = [s for s in all_secs if s in section_plans or s in occ_h]

    for sec in used_secs:
        hours_in = occ_h.get(sec) or [0.0] * n_bins
        # mean concurrent trucks in each bin = truck-hours / bin width. A
        # proper time average: it does not change when the bin does, unlike
        # the old "count 1 for any overlap", which inflated a 1 h bin 3.7x
        # over the road's real truck-hours and 2.5x over a 15-minute bin.
        occ_mean = [(hours_in[b] / bin_w[b]) if bin_w[b] > 0 else 0.0
                    for b in range(n_bins)]
        peak_mean = max(occ_mean) if occ_mean else 0.0
        peak_bin = occ_mean.index(peak_mean) if occ_mean else 0
        peak_conc = _peak_concurrent(sweep.get(sec) or [])

        seg = _seg_by_label.get(sec)
        if seg:
            lane_cap_tph = float(seg['cap_hr'])       # official limit / following
            length_km = float(seg['length_km'])
            cap_basis = ("official speed limits ÷ %.0f m following, one lane "
                         "per direction" % _FOLLOW_M)
        elif sec.endswith(" spur"):
            lane_cap_tph = SPUR_LANE_CAP_TPH
            length_km = spur_km.get(sec) or SPUR_KM_FALLBACK
            cap_basis = ("spur estimate 20 km/h ÷ %.0f m following, one lane "
                         "per direction (no limit sheet)" % _FOLLOW_M)
        else:
            lane_cap_tph = (caps.get(sec) or DEFAULT_CAP_TPH) / 2.0
            length_km = _section_length_km(sec)
            cap_basis = "measured peak (no official limit sheet)"
        # Trucks that physically FIT on the section, both lanes: the honest
        # denominator for a presence count. (The old denominator was a FLOW
        # capacity multiplied by the display bin — a stock over a flow.)
        cap_present = max(1.0, length_km * 1000.0 / _FOLLOW_M * 2.0)

        # v/c: passages per hour against the lane's capacity flow, worst
        # direction, over a FIXED hour — invariant to the display bin.
        flow_loaded = _peak_flow_per_h(entry_times[sec]["loaded"], horizon_h, VC_WINDOW_H)
        flow_empty = _peak_flow_per_h(entry_times[sec]["empty"], horizon_h, VC_WINDOW_H)
        peak_lane_flow = max(flow_loaded, flow_empty)
        peak_both_flow = _peak_flow_per_h(
            entry_times[sec]["loaded"] + entry_times[sec]["empty"], horizon_h, VC_WINDOW_H)
        # A section whose trucks do not all run its whole length is not one
        # number. Split it at every leg boundary (BLB joins the stick at
        # km 2.45, POS 10 sits at km 17.0) and take the WORST cross-section as
        # the headline, labelled as such, instead of quietly mixing a 50.7/h
        # cross-section with a 30.2/h one.
        subs = _cross_sections(passages.get(sec) or [], horizon_h)
        if subs:
            peak_lane_flow = max([peak_lane_flow]
                                 + [s["peak_flow_per_h"] for s in subs])
            flow_basis = ("WORST CROSS-SECTION of %d: this section is not "
                          "uniform (%s), so one flow number would mix them"
                          % (len(subs),
                             ", ".join("km %g-%g %.1f/h" % (s["km_lo"], s["km_hi"],
                                                            s["peak_flow_per_h"])
                                       for s in subs)))
        else:
            flow_basis = "uniform section: every truck runs its whole length"
        ratio = (peak_lane_flow / lane_cap_tph) if lane_cap_tph > 0 else 0.0
        status = "High" if ratio >= 1.0 else ("Watch" if ratio >= 0.7 else "Open")
        plans_here = sorted(section_plans.get(sec) or [])
        shared = len(plans_here) >= 2
        row = {
            "section": sec,
            "plans": plans_here,
            "n_plans": len(plans_here),
            "shared": shared,
            # ── FLOW: the v/c. Both sides are trucks/hour.
            "ratio": round(ratio, 3),
            "status": status,
            "peak_flow_per_h": round(peak_lane_flow, 1),
            "peak_flow_per_h_both": round(peak_both_flow, 1),
            "cap_flow_per_h": round(lane_cap_tph, 1),
            "cap_flow_per_h_both": round(lane_cap_tph * 2.0, 1),
            "cap_tph": round(lane_cap_tph * 2.0, 1),   # kept: both-lane flow cap
            "flow_window_h": VC_WINDOW_H,
            "vc_basis": ("busiest %g h of passages in one direction ÷ that "
                         "lane's capacity flow" % VC_WINDOW_H),
            "flow_basis": flow_basis,
            "uniform_section": not subs,
            "cross_sections": subs,
            # ── PRESENCE: a stock, with a stock denominator.
            "peak_trucks": int(round(peak_conc)),
            "peak_concurrent": round(peak_conc, 1),
            "peak_bin_mean": round(peak_mean, 1),
            "peak_bin": peak_bin,
            "cap_trucks_present": round(cap_present, 1),
            "cap_trucks_bin": round(cap_present, 1),
            "ratio_presence": round(peak_conc / cap_present, 3) if cap_present else 0.0,
            "presence_basis": ("trucks on the section at once ÷ the %d that fit "
                               "at %.0f m spacing on both lanes"
                               % (int(round(cap_present)), _FOLLOW_M)),
            # one decimal below ~10 trucks: a mean of 0.6 trucks is a real
            # answer and rounding it to 1 or 0 would invent or delete traffic
            "occupancy": [round(x, 1) if x < 9.95 else int(round(x)) for x in occ_mean],
            "occupancy_mean": [round(x, 2) for x in occ_mean],
            "entries": [round(x, 1) for x in (ent.get(sec) or [0.0] * n_bins)],
            "flow_per_h": [round((ent.get(sec) or [0.0] * n_bins)[b] / bin_w[b], 1)
                           if bin_w[b] > 0 else 0.0 for b in range(n_bins)],
            "truck_hours": round(truck_h.get(sec, 0.0), 1),
            "section_km": round(length_km, 1),
            "speed_kmh": ((seg.get('speeds') or {}).get('loaded', {}).get('mean')
                          if seg else speeds.get(sec)),
            "cap_basis": cap_basis,
        }
        sections_out.append(row)
        if peak_conc > 0 and (worst is None or ratio > worst["ratio"]):
            worst = row
        for b in range(n_bins):
            if bin_w[b] <= 0:
                continue
            dir_flow = max((ent_dir[sec]["loaded"][b]) / bin_w[b],
                           (ent_dir[sec]["empty"][b]) / bin_w[b])
            r = dir_flow / lane_cap_tph if lane_cap_tph > 0 else 0.0
            if r >= 0.7:
                clock = (start_hour + int(round(b * bin_hours))) % 24
                slot = congested_clock[clock]
                trucks_here = int(round(occ_mean[b]))
                if trucks_here > slot["peak"]:
                    slot["peak"] = trucks_here
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
    if worst and worst["ratio"] >= 0.7 and worst["peak_flow_per_h"] > 0:
        # Metering is a FLOW cut: hold passages per hour under the lane's
        # capacity flow. (The old hint divided a truck count by a flow x bin
        # and so changed its advice when the grid changed.)
        scale = min(1.0, (worst["cap_flow_per_h"] * 0.95) / worst["peak_flow_per_h"])
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
                    "%s peaks at %.0f trucks/h in one direction against an "
                    "official lane capacity of %.0f/h: meter or cut ~%.0f%% DT "
                    "on paths crossing it — advisory only, does not change "
                    "simulate tonnes."
                    % (worst["section"], worst["peak_flow_per_h"],
                       worst["cap_flow_per_h"], 100 * (1 - scale))
                ),
                "suggestions": suggestions,
            }

    jammed = [s for s in sections_out if s["ratio_presence"] >= 1.0]
    if jammed:
        # Free-flow DES: trucks pass at the limit speed and do not queue on the
        # road. Past jam density that timing is no longer physical, so say so
        # rather than reporting a section holding more trucks than fit on it.
        warnings.append(
            "%s hold(s) more trucks at once than fit at %.0f m spacing "
            "(presence ratio up to %.1fx). Past jam density this DES no longer "
            "describes the road: it has no spill-back, so treat those hours as "
            "'over capacity', not as a timetable."
            % (", ".join(s["section"] for s in jammed), _FOLLOW_M,
               max(s["ratio_presence"] for s in jammed)))

    weighted = [p for p in path_rows if p["sim_trucks"] < p["n_trucks"]]
    if weighted:
        warnings.append(
            "%d row(s) larger than %d trucks are simulated with %d representative "
            "trucks carrying weight up to %.1f each (occupancy and flow are "
            "unbiased; the resolution is coarser)."
            % (len(weighted), MAX_TRUCKS_SIM, MAX_TRUCKS_SIM,
               max(p["sim_weight"] for p in weighted)))
    if unpriced:
        warnings.append(
            "No calibration for %s — priced on model defaults/fallback dwell, "
            "not on this route's measured history. Treat its road time as "
            "indicative." % ", ".join(sorted(set(unpriced))))

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
            "trips_per_truck_horizon": p["trips_per_truck_horizon"],
            "trips_per_day": p["trips_per_day"],
            "expected_trips": p["expected_trips"],
            "executed_trips": p["executed_trips"],
            "release_headway_min": p["release_headway_min"],
            "sim_trucks": p["sim_trucks"],
            "sim_weight": p["sim_weight"],
            "priced": p["priced"],
            "truck_hours": round(truck_h_path.get(p["id"], 0.0), 1),
            "sec_times_h": {x["section"]: round(x["hours"], 4) for x in p["sec_times"]},
            "sec_times_empty_h": {x["section"]: round(x["hours"], 4)
                                  for x in p["sec_times_empty"]},
        } for p in path_rows],
        "sections": sections_out,
        "sources": sources_out,
        "congestion_hours": congestion_hours,
        "worst_section": worst["section"] if worst else None,
        "meter_hint": meter_hint,
        "warnings": warnings,
        "summary": {
            "n_paths": len(path_rows),
            "n_shared_sections": shared_n,
            "n_high_sections": high_n,
            "gps_speeds": gps_ok,
            "trucks_planned": sum(p["n_trucks"] for p in path_rows),
            "trucks_simulated": sum(p["sim_trucks"] for p in path_rows),
            "expected_trips": round(sum(p["expected_trips"] for p in path_rows), 1),
            "executed_trips": round(sum(p["executed_trips"] for p in path_rows), 1),
            "road_truck_hours": round(sum(truck_h.values()), 1),
        },
        "dwell_notes": dwell_notes,
        "gps_window": hours_payload.get("window") if gps_ok else None,
        "note": (
            "DES on the segment model: per-truck timing from the calibrated hybrid "
            "(plan segment fleets, contractor baselines, cycle + overhead cadence), "
            "road time split over S1–S4 by the official directional speed limits "
            "CORRECTED by the measured segment factors (463k vendor traversals + "
            "11.6k GPS bin-traversals: the limits run 1.5–2.1x optimistic on "
            "S1–S3 but are accurate on S4, so an uncorrected split over-loaded "
            "KM15–coast by 7–8 pp), loaded pass + dump + EMPTY return both occupy "
            "the road; BLB rides its spur pseudo-section. Release times follow the "
            "MEASURED load-start profile by hours-since-shift-start (%s) — a "
            "1-hour ramp-up, a 2-hour wind-down and a near-empty final hour at "
            "each changeover; there is no meal-break dip in the data and none is "
            "added. Reshaping the release times does not change the trip count. "
            "Cells are the MEAN trucks on the section during the hour against the "
            "number that fit at %.0f m spacing; the v/c verdict is the busiest "
            "hour of passages against the official lane capacity flow, so neither "
            "moves with the bin size — and on a section that is not uniform "
            "(BLB joins the stick at km 2.45) it is the WORST cross-section, "
            "listed per cross-section on the row. Synchronised breaks and the "
            "loader-face schedule are still not modelled "
            "(reports/ROAD_CROWDING_BY_HOUR_PLAN.md §6). "
            "Advisory — never clips simulate tonnes."
            % (RELEASE_PROFILE_SOURCE, _FOLLOW_M)
        ),
        "basis": {
            **basis,
            "uses_measured_dwell": not any("fallback" in (p["load_basis"] + p["dump_basis"])
                                          for p in path_rows),
            "fallback_dwell_10min": any("fallback" in (p["load_basis"] + p["dump_basis"])
                                       for p in path_rows),
            "gps_speeds": gps_ok,
            # C1: the road's basis is stated, never implied by n_trucks alone.
            "simulation": ("weighted representative trucks"
                           if weighted else "every planned truck simulated"),
            "trucks_planned": sum(p["n_trucks"] for p in path_rows),
            "trucks_simulated": sum(p["sim_trucks"] for p in path_rows),
            "max_truck_weight": round(max((p["sim_weight"] for p in path_rows),
                                          default=1.0), 3),
            "max_trucks_sim_per_row": MAX_TRUCKS_SIM,
            "release_model": ("one inter-trip interval, repeating every interval "
                              "(order-invariant, steady state), then re-timed "
                              "inside each shift by the measured load-start "
                              "profile — same trips, different hours"),
            # What the card is allowed to say it applied. Everything here is
            # measured or derived from the measurement by conservation; nothing
            # is a modelling choice dressed as data.
            "release_profile": {
                "applied": True,
                "source": RELEASE_PROFILE_SOURCE,
                "table": "HAULAGE_CLEAN.TIME_LOADED",
                "n_loads": 273222,
                "n_days": 234,
                "chi2_vs_uniform": 34883.0,
                "chi2_df": 23,
                "units": ("multiplier on the uniform release rate, by "
                          "hours-since-shift-start"),
                "anchored_on": "load start (TIME_LOADED), not dispatch",
                "shift_starts_h": list(SHIFT_STARTS_H),
                "profile_hours": RELEASE_PROFILE_HOURS,
                "day": [round(v, 3) for v in RELEASE_PROFILE_DAY],
                "night": [round(v, 3) for v in RELEASE_PROFILE_NIGHT],
                "interior_hours_held_constant": [
                    h for h in range(RELEASE_PROFILE_HOURS)
                    if h not in _RELEASE_ANCHORS_DAY],
                "interior_measured_band": _RELEASE_INTERIOR_BAND,
                "meal_break_dip": False,
                "meal_break_measured": {"12:00": 1.05, "13:00": 1.11},
                "structure": ("1-hour ramp-up at shift start, 2-hour wind-down, "
                              "final hour near-zero for the changeover"),
                "method": ("monotone time warp inside each shift window: the "
                           "same SET of load starts is re-timed, so executed "
                           "trips are conserved exactly, not to rounding"),
                "conserves_executed_trips": True,
                "windows": release_windows,
                "start_hour_is_shift_start": start_hour in SHIFT_STARTS_H,
                "peak_over_trough": round(
                    max(max(RELEASE_PROFILE_DAY), max(RELEASE_PROFILE_NIGHT))
                    / min(min(RELEASE_PROFILE_DAY), min(RELEASE_PROFILE_NIGHT)), 2),
                "presence_lag": (
                    "the RELEASE hours are measured; the PRESENCE hours drawn "
                    "on a section lag them by that section's transit time "
                    "(0-1 h near the pit, 2-3 h on KM15-coast) because trips "
                    "in flight are completed across the changeover. The "
                    "measured presence lags by ~0-1 h everywhere, so the far "
                    "sections' trough is drawn 2-3 h late. Amplitude is right, "
                    "phase is not; a changeover behaviour is not calibrated "
                    "and is not invented here"),
            },
            "segment_time_split": {
                "basis": ("official directional speed-limit times × measured "
                          "per-segment correction factors, then normalised to "
                          "the route's dispatch-anchored total road time"),
                "source": SEGMENT_TIME_FACTORS_SOURCE,
                "factors": SEGMENT_TIME_FACTORS,
                "spur_factor": SPUR_TIME_FACTOR,
                "spur_factor_note": ("BLB spur has no limit sheet and no "
                                     "traversal study — left at 1.0, not "
                                     "borrowed from the stick"),
                "changes_total_road_time": False,
                "measured_target_share_loaded": {
                    "S1": "47.1 / 44.5%", "S2": "17.3 / 19.9%",
                    "S3": "15.9 / 15.3%", "S4": "19.7 / 20.3%"},
            },
            "trips_in_flight_complete": True,
            "tail_wraps_to_start": True,
            "occupancy_metric": "mean concurrent trucks per bin (time-weighted)",
            "occupancy_capacity": "trucks that fit at the following distance, both lanes",
            "vc_metric": ("peak %g-h directional passages ÷ official lane capacity "
                          "flow — invariant to bin size" % VC_WINDOW_H),
            "following_distance_m": _FOLLOW_M,
            "unpriced_routes": sorted(set(unpriced)),
        },
    }
