"""Corridor ops pressure from weighbridge path-days — not invented GPS speeds.

- day_road_ops(date): DT/trips for ONE calendar day (what the selected day ran).
- peak_road_proxy(): Jan–May averages — peak-season REFERENCE only, never shown
  as if it belonged to a selected Jul+ GPS day.
"""
from __future__ import annotations

from collections import defaultdict

import plan_analogues as pa

PEAK_FROM = "2026-01-01"
PEAK_TO = "2026-05-31"


def _section_totals_for_days(corpus, day_from, day_to=None):
    """Sum path-day DT/trips onto corridor sections for dates in [from, to]."""
    day_to = day_to or day_from
    sec_dt = defaultdict(float)
    sec_trips = defaultdict(float)
    sec_days = defaultdict(set)
    n_days = set()
    path_n = 0
    for c in corpus:
        d = str(c.get("date") or "")[:10]
        if not d or d < day_from or d > day_to:
            continue
        n_days.add(d)
        path_n += 1
        dt = float(c.get("dt") or c.get("n_trucks") or 0)
        trips = float(c.get("trips") or 0)
        secs = c.get("sections") or pa.route_sections(
            c.get("source") or c.get("origin"),
            c.get("destination") or c.get("dest"))
        for s in secs or []:
            sec_dt[s] += dt
            sec_trips[s] += trips
            sec_days[s].add(d)
    sections = []
    for label, _a, _b in pa.SECTIONS:
        if label not in sec_dt:
            continue
        days_n = len(sec_days[label]) or 1
        sections.append({
            "section": label,
            "total_dt": round(sec_dt[label], 1),
            "total_trips": round(sec_trips[label], 0),
            "days_n": len(sec_days[label]),
            "avg_dt_per_day": round(sec_dt[label] / days_n, 1),
            "avg_trips_per_day": round(sec_trips[label] / days_n, 0),
            # Single-day aliases (same as totals when days_n==1)
            "dt": round(sec_dt[label], 1),
            "trips": round(sec_trips[label], 0),
        })
    sections.sort(key=lambda x: -x["total_dt"])
    return sections, n_days, path_n


def day_road_ops(date_s, corpus=None, corpus_source=None):
    """Weighbridge path-day DT/trips on corridor sections for ONE date only."""
    date_s = str(date_s or "")[:10]
    if not date_s:
        return {
            "ok": False, "error": "supply date=YYYY-MM-DD", "date": None,
            "sections": [], "has_ops": False,
            "basis": {"congestion_clips_tonnes": False},
        }
    if corpus is None:
        corpus, corpus_source = pa.load_fixture_corpus()
    elif corpus_source is None:
        corpus_source = "provided"

    sections, days, path_n = _section_totals_for_days(corpus, date_s, date_s)
    has_ops = path_n > 0
    return {
        "ok": True,
        "date": date_s,
        "has_ops": has_ops,
        "path_days_n": path_n,
        "sections": sections,
        "corpus_source": corpus_source,
        "speeds_kmh": None,
        "invents_playback_haul_speeds": False,
        "note": (
            ("Weighbridge path-days on %s — DT/trips of hauls that crossed each "
             "section that day. Not GPS speeds. Advisory only.") % date_s
            if has_ops else
            ("No weighbridge path-day rows for %s in the ops corpus — "
             "cannot invent section DT/trips for this date.") % date_s
        ),
        "basis": {
            "congestion_clips_tonnes": False,
            "simulate_unchanged": True,
            "invents_playback_haul_speeds": False,
            "source": "ops_weighbridge_path_days",
            "scope": "single_day",
        },
    }


def peak_road_proxy(corpus=None, corpus_source=None, plans=None):
    """Jan–May section averages — peak-season REFERENCE only (not a selected day)."""
    if corpus is None:
        corpus, corpus_source = pa.load_fixture_corpus()
    elif corpus_source is None:
        corpus_source = "provided"

    sections, n_days, _path_n = _section_totals_for_days(corpus, PEAK_FROM, PEAK_TO)

    plan_secs = []
    if plans:
        for p in plans:
            for s in pa.route_sections(p.get("source") or p.get("origin"),
                                       p.get("destination") or p.get("dest")):
                plan_secs.append(s)
        plan_secs = sorted(set(plan_secs))
    busy = [s for s in sections if not plan_secs or s["section"] in plan_secs]

    return {
        "ok": True,
        "window": {"from": PEAK_FROM, "to": PEAK_TO, "era": "peak"},
        "days_n": len(n_days),
        "corpus_source": corpus_source,
        "sections": sections,
        "plan_sections": plan_secs,
        "busy_for_plan": busy[:4],
        "speeds_kmh": None,
        "invents_playback_haul_speeds": False,
        "is_reference": True,
        "note": (
            "REFERENCE only — Jan–May peak-season averages across many days. "
            "Not the selected GPS day. For a selected day use that day's ops + Jul+ GPS."
        ),
        "basis": {
            "congestion_clips_tonnes": False,
            "simulate_unchanged": True,
            "invents_playback_haul_speeds": False,
            "source": "ops_weighbridge_path_days",
            "scope": "peak_season_average",
        },
    }
