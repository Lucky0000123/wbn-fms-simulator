#!/usr/bin/env python
"""Freeze the owner's reference saturation curves (trips/DT/day vs fleet).

TF>HUAFEI and BLB>POS 14 — the corridors the owner asked to see and plan
against (2026-08-21), priced by the corrected formula
trips = 1440/(road_congested + ops + queue + bunching + overhead_per_trip).

Per route the curve is emitted at BOTH loader bases:
  - calibrated faces  — the /api/congestion_curve default; what the
    Congestion-tab saturation chart draws;
  - proportional      — round(N / trucks-per-loader), the basis the plan
    builder prices with (planning_rules.md §10.9).

Writes:
  reports/saturation_curves.json  dense points, 10..800 DT step 10
  reports/SATURATION_CURVES.md    readable tables + method
  reports/saturation_curves.svg   chart, dependency-free

Committed on purpose — same rule as reports/speed_density_fit.json: model
outputs/coefficients, not operational tonnages. /api/congestion_curve
serves the JSON as a tagged fallback when calibration data is absent
(fresh clone, fixtures mode), so the app's charts and the plan builder see
the same reference curve everywhere. Regenerate after any recalibration:

    .venv/bin/python scripts/export_saturation_curves.py
"""
from __future__ import annotations

import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from congestion.predictor import predict          # noqa: E402
from congestion.config import route_params        # noqa: E402

ROUTES = ("TF>HUAFEI", "BLB>POS 14")
FLEETS = list(range(10, 801, 10))


def tpl_for(p):
    ref_t, ref_l = p.get("n_trucks_ref"), p.get("n_loaders")
    if p.get("calibrated") and ref_t and ref_l:
        return round(float(ref_t) / float(ref_l), 1)
    return 15.0


def point(p):
    return {
        "n_trucks": p["n_trucks"],
        "trips_per_dt": p["trips_per_DT_per_day"],
        "total_trips": p["total_trips_day"],
        "total_tonnes": p["total_tonnes_day"],
        "cycle_time_min": p["cycle_time_minutes"],
        "rho": p["rho"],
        "bottleneck": "road" if p.get("road_vc", 0) >= p.get("rho", 0) else "loader",
        "p10": p["uncertainty"]["p10"],
        "p90": p["uncertainty"]["p90"],
    }


def curve_for(route, loaders_fn):
    out = []
    for n in FLEETS:
        try:
            out.append(point(predict(route, float(n), loaders_fn(n))))
        except (ValueError, ArithmeticError):
            continue
    return out


def knee_of(curve):
    if not curve:
        return None
    base = curve[0]["trips_per_dt"]
    for c in curve:
        if c["trips_per_dt"] < 0.95 * base:
            return c["n_trucks"]
    return None


def build():
    routes = {}
    for route in ROUTES:
        p = route_params(route)
        tpl = tpl_for(p)
        faces = int(p.get("n_loaders") or 2)
        cal = curve_for(route, lambda n: faces)
        prop = curve_for(route, lambda n: max(1, round(n / tpl)))
        routes[route] = {
            "calibrated": bool(p.get("calibrated")),
            "n_loaders_calibrated": faces,
            "trucks_per_loader": tpl,
            "road_free_min": p.get("road_free_min"),
            "ops_min": p.get("ops_min"),
            "overhead_per_trip_min": p.get("overhead_per_trip_min"),
            "day_rate_anchor": p.get("day_rate"),
            "n_trucks_ref": p.get("n_trucks_ref"),
            "knee_dt": knee_of(cal),
            "curve": cal,                       # calibrated-faces basis (chart default)
            "curve_proportional": prop,         # plan-builder basis (§10.9)
        }
    return {
        "generated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": {
            "trips_formula": "1440 / (road_congested + ops + queue + bunching + overhead_per_trip)",
            "bpr": "applied to road_free only, capped at 3x",
            "loaders_bases": "curve = calibrated faces; curve_proportional = round(N / trucks_per_loader)",
            "source": "congestion.predictor at data/congestion_params.json calibration",
        },
        "routes": routes,
    }


def write_md(data, path):
    lines = ["# Reference saturation curves — trips/DT/day vs fleet",
             "",
             "> Generated %s by scripts/export_saturation_curves.py — regenerate after any" % data["generated_at"],
             "> recalibration. Formula: `trips = 1440/(road_congested + ops + queue +",
             "> bunching + overhead_per_trip)`; BPR on road time only, capped at 3x.",
             "> `calibrated faces` is what the Congestion-tab chart shows;",
             "> `proportional` is what the plan builder prices with (rules §10.9).",
             ""]
    for route, r in data["routes"].items():
        lines += ["## %s" % route,
                  "",
                  "road_free %.0f min · ops %.0f min · overhead/trip %.0f min · "
                  "anchor day-rate %.3f @ %s DT · knee ~%s DT · %.1f trucks/loader"
                  % (r["road_free_min"] or 0, r["ops_min"] or 0,
                     r["overhead_per_trip_min"] or 0, r["day_rate_anchor"] or 0,
                     r["n_trucks_ref"], r["knee_dt"], r["trucks_per_loader"]),
                  "",
                  "| DT | trips/DT (calibrated faces) | trips/DT (proportional loaders) | cycle min | p10–p90 |",
                  "|---:|---:|---:|---:|---|"]
        prop = {c["n_trucks"]: c for c in r["curve_proportional"]}
        for c in r["curve"]:
            if c["n_trucks"] % 50 != 0:
                continue
            pr = prop.get(c["n_trucks"], {})
            lines.append("| %d | %.2f | %s | %.0f | %.2f–%.2f |" % (
                c["n_trucks"], c["trips_per_dt"],
                ("%.2f" % pr["trips_per_dt"]) if pr else "—",
                c["cycle_time_min"], c["p10"], c["p90"]))
        lines.append("")
    mins = {route: min(c["trips_per_dt"] for c in r["curve"])
            for route, r in data["routes"].items()}
    lines += ["## Physical floor check",
              "",
              "The corrected formula can never predict below one trip per day:",
              ""]
    for route, m in mins.items():
        lines.append("- %s minimum over 10–800 DT: **%.2f** trips/DT/day" % (route, m))
    lines.append("")
    open(path, "w").write("\n".join(lines))


def write_svg(data, path):
    W, H = 960, 420
    panels = list(data["routes"].items())
    pw = (W - 60) // len(panels)
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
           'font-family="Helvetica,Arial,sans-serif" font-size="11">' % (W, H),
           '<rect width="%d" height="%d" fill="#0d1117"/>' % (W, H),
           '<text x="%d" y="22" fill="#e6edf3" font-size="15" text-anchor="middle">'
           'Saturation curves — trips/DT/day vs fleet (formula: 1440 / (road_congested '
           '+ ops + queue + overhead))</text>' % (W // 2)]
    for i, (route, r) in enumerate(panels):
        x0 = 50 + i * pw
        y0, ph = 60, H - 130
        ymax = max(c["trips_per_dt"] for c in r["curve"]) * 1.15
        xmax = 800.0

        def sx(n):
            return x0 + (n / xmax) * (pw - 40)

        def sy(v):
            return y0 + ph - (v / ymax) * ph

        out.append('<text x="%d" y="46" fill="#e6edf3" font-size="13">%s</text>'
                   % (x0, route.replace(">", " → ")))
        for gy in range(0, int(ymax) + 1):
            out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#21262d"/>'
                       % (x0, sy(gy), x0 + pw - 40, sy(gy)))
            out.append('<text x="%d" y="%.1f" fill="#8b98a5" text-anchor="end">%d</text>'
                       % (x0 - 6, sy(gy) + 4, gy))
        for gx in range(0, 801, 200):
            out.append('<text x="%.1f" y="%d" fill="#8b98a5" text-anchor="middle">%d</text>'
                       % (sx(gx), y0 + ph + 16, gx))
        for key, color, dash, label in (
                ("curve", "#38bdf8", "", "fixed loaders"),
                ("curve_proportional", "#f59e0b", ' stroke-dasharray="6 4"', "scaled loaders")):
            pts = " ".join("%.1f,%.1f" % (sx(c["n_trucks"]), sy(c["trips_per_dt"]))
                           for c in r[key])
            out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2"%s/>'
                       % (pts, color, dash))
        if r["knee_dt"]:
            out.append('<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" stroke="#eab308" '
                       'stroke-dasharray="3 3"/>' % (sx(r["knee_dt"]), y0,
                                                     sx(r["knee_dt"]), y0 + ph))
            out.append('<text x="%.1f" y="%d" fill="#eab308" text-anchor="middle">knee %d</text>'
                       % (sx(r["knee_dt"]), y0 - 4, r["knee_dt"]))
        out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#ef4444" '
                   'stroke-dasharray="2 3"/>' % (x0, sy(1.0), x0 + pw - 40, sy(1.0)))
        out.append('<rect x="%d" y="%d" width="12" height="3" fill="#38bdf8"/>'
                   '<text x="%d" y="%d" fill="#8b98a5">loaders FIXED at today’s %d faces '
                   '— loader queue saturates</text>'
                   % (x0 + 8, y0 + ph + 30, x0 + 26, y0 + ph + 34, r["n_loaders_calibrated"]))
        out.append('<rect x="%d" y="%d" width="12" height="3" fill="#f59e0b"/>'
                   '<text x="%d" y="%d" fill="#8b98a5">loaders ADDED with fleet, 1 per %.1f trucks '
                   '(measured ratio, rules §10.9) — only the road congests</text>'
                   % (x0 + 8, y0 + ph + 46, x0 + 26, y0 + ph + 50, r["trucks_per_loader"]))
    out.append('<text x="%d" y="%d" fill="#8b98a5" text-anchor="middle">DT on route · '
               'red dotted line = 1 trip/day physical floor</text>' % (W // 2, H - 8))
    out.append("</svg>")
    open(path, "w").write("\n".join(out))


def main():
    data = build()
    jp = os.path.join(ROOT, "reports", "saturation_curves.json")
    json.dump(data, open(jp, "w"), indent=1)
    write_md(data, os.path.join(ROOT, "reports", "SATURATION_CURVES.md"))
    write_svg(data, os.path.join(ROOT, "reports", "saturation_curves.svg"))
    for route, r in data["routes"].items():
        print("%s: %d pts, knee %s DT, min %.2f trips/DT (calibrated basis)" % (
            route, len(r["curve"]), r["knee_dt"],
            min(c["trips_per_dt"] for c in r["curve"])))
    print("wrote reports/saturation_curves.{json,svg} + SATURATION_CURVES.md")


if __name__ == "__main__":
    main()
