#!/usr/bin/env python
"""Daily weather for the mine site, cached locally.

Phase 3 could not use rainfall as a feature: the site gauges stopped reporting
on 2026-04-06, so every row after that read 0.0 mm — an outage, not a drought.
The pipeline imputed a seasonal mean and flagged it, which is honest but carries
no real information. This module replaces the guess with measurement.

Source: Open-Meteo's ERA5 archive. Chosen over Visual Crossing because it needs
no API key (nothing to leak into a public repo), covers the whole training
window, and is free for this volume. Values are daily aggregates at the site
coordinates, so they describe site weather rather than a single gauge that can
fail.

The cache is a plain CSV keyed by date, so a rebuild costs one HTTP call for the
missing range instead of re-fetching everything.

    python scripts/fetch_weather.py --start 2025-01-01 --end 2026-07-31
    python -c "import scripts.fetch_weather as w; print(w.load_weather())"
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
CACHE = os.path.join(DATA, "weather_cache.csv")

# Weda Bay Nickel site. The haul road runs TF -> FENI over 67.8 km, well inside
# one ERA5 cell, so a single point is the right granularity for daily weather.
# Coordinates come from the committed road survey
# (data/haul_road_chainage_public.csv, median 0.5586 N / 127.9647 E). The old
# value here (-0.7297) was the WRONG HEMISPHERE, ~140 km south of the road —
# re-run this script to rebuild data/weather_cache.csv at the correct point.
SITE_LAT = 0.5586
SITE_LON = 127.9647

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

DAILY_VARS = ["precipitation_sum", "temperature_2m_max", "temperature_2m_min",
              "relative_humidity_2m_mean", "wind_speed_10m_max",
              "precipitation_hours"]

FIELDS = ["date", "rainfall_mm", "temperature_max", "temperature_min",
          "humidity", "wind_speed_max", "precipitation_hours", "source"]


def _get(url: str, params: dict, timeout: int = 60) -> dict:
    q = urllib.parse.urlencode(params, doseq=True)
    with urllib.request.urlopen("%s?%s" % (url, q), timeout=timeout) as r:
        return json.load(r)


def fetch_range(start: str, end: str, lat: float = SITE_LAT,
                lon: float = SITE_LON) -> list:
    """Daily weather for [start, end]. Returns a list of dicts.

    The archive lags real time by about five days, so recent dates come from the
    forecast endpoint's past-days window instead. Both are queried and merged;
    whichever answers for a date wins, archive first.
    """
    rows: dict = {}
    params = {"latitude": lat, "longitude": lon, "daily": DAILY_VARS,
              "timezone": "UTC", "start_date": start, "end_date": end}
    try:
        d = _get(ARCHIVE_URL, params)
        rows.update(_rows_from(d, "era5-archive"))
    except Exception as exc:                                   # noqa: BLE001
        print("  archive fetch failed: %s" % str(exc)[:120], file=sys.stderr)

    missing = _missing_dates(start, end, rows)
    if missing:
        # Recent tail: ask the forecast endpoint for past days.
        span = (date.fromisoformat(end) - date.fromisoformat(missing[0])).days + 1
        try:
            d = _get(FORECAST_URL, {"latitude": lat, "longitude": lon,
                                    "daily": DAILY_VARS, "timezone": "UTC",
                                    "past_days": min(92, max(1, span)),
                                    "forecast_days": 1})
            for k, v in _rows_from(d, "forecast-recent").items():
                rows.setdefault(k, v)
        except Exception as exc:                               # noqa: BLE001
            print("  recent fetch failed: %s" % str(exc)[:120], file=sys.stderr)
    return [rows[k] for k in sorted(rows)]


def _rows_from(payload: dict, source: str) -> dict:
    daily = payload.get("daily") or {}
    times = daily.get("time") or []
    out = {}
    for i, t in enumerate(times):
        def val(name):
            seq = daily.get(name) or []
            return seq[i] if i < len(seq) else None
        if val("precipitation_sum") is None and val("temperature_2m_max") is None:
            continue                                    # nothing measured
        out[t] = {"date": t,
                  "rainfall_mm": val("precipitation_sum"),
                  "temperature_max": val("temperature_2m_max"),
                  "temperature_min": val("temperature_2m_min"),
                  "humidity": val("relative_humidity_2m_mean"),
                  "wind_speed_max": val("wind_speed_10m_max"),
                  "precipitation_hours": val("precipitation_hours"),
                  "source": source}
    return out


def _missing_dates(start: str, end: str, have: dict) -> list:
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    out, cur = [], d0
    while cur <= d1:
        if cur.isoformat() not in have:
            out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def load_cache() -> dict:
    if not os.path.exists(CACHE):
        return {}
    with open(CACHE, encoding="utf-8") as fh:
        return {r["date"]: r for r in csv.DictReader(fh)}


def save_cache(rows: dict) -> None:
    os.makedirs(DATA, exist_ok=True)
    with open(CACHE, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for k in sorted(rows):
            w.writerow({f: rows[k].get(f) for f in FIELDS})


def ensure_weather(start: str, end: str, refresh: bool = False) -> dict:
    """Return {date: row}, fetching only what the cache lacks."""
    cache = {} if refresh else load_cache()
    missing = _missing_dates(start, end, cache)
    if missing:
        print("  fetching %d missing day(s): %s .. %s"
              % (len(missing), missing[0], missing[-1]))
        for row in fetch_range(missing[0], missing[-1]):
            cache[row["date"]] = row
        save_cache(cache)
    return cache


def load_weather():
    """Cached weather as a DataFrame, for the pipeline."""
    import pandas as pd
    if not os.path.exists(CACHE):
        return pd.DataFrame(columns=FIELDS)
    df = pd.read_csv(CACHE)
    for c in ("rainfall_mm", "temperature_max", "temperature_min", "humidity",
              "wind_speed_max", "precipitation_hours"):
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2025-01-01")
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument("--refresh", action="store_true", help="ignore the cache")
    a = ap.parse_args()

    print("site %.4f, %.4f  |  %s .. %s" % (SITE_LAT, SITE_LON, a.start, a.end))
    cache = ensure_weather(a.start, a.end, refresh=a.refresh)
    sel = {k: v for k, v in cache.items() if a.start <= k <= a.end}
    if not sel:
        print("no weather returned", file=sys.stderr)
        return 1

    rain = [float(v["rainfall_mm"]) for v in sel.values()
            if v.get("rainfall_mm") not in (None, "")]
    wet = sum(1 for r in rain if r >= 10)
    print("\ncached %d days -> %s" % (len(cache), os.path.relpath(CACHE, BASE)))
    print("  range in view : %s .. %s (%d days)"
          % (min(sel), max(sel), len(sel)))
    if rain:
        print("  rainfall      : mean %.1f mm, max %.1f mm, %d wet days (>=10mm, %.0f%%)"
              % (sum(rain) / len(rain), max(rain), wet, 100 * wet / len(rain)))
    print("\nThis replaces the site gauges, which stopped reporting 2026-04-06.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
