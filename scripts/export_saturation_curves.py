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
    .venv/bin/python scripts/export_saturation_curves.py --svg-only   # restyle from frozen JSON
    .venv/bin/python scripts/export_saturation_curves.py --check      # FRESHNESS GATE

WHY --check EXISTS. "Regenerate after any recalibration" was a sentence in a
docstring, and a sentence is not a check. The artifact frozen 2026-08-21T04:54Z
survived the 2026-08-22T04:05-04:42Z recalibration + official-capacity work
untouched and kept being SERVED, tagged `servedFrom:"reference"` and
`calibrated:true`, priced up to 40.7% below the live model on TF>HUAFEI. A
frozen artifact with no freshness signal cannot tell anyone it has rotted; it
just keeps answering. So every export now records the provenance it was built
from — the calibration's own `generated_at` plus a fingerprint of every input
that determines the curves (per-route params AND the speed-limit / segment
network, since segment pricing now shapes road time) — and `--check`
recomputes those inputs, prints WHAT changed, and exits non-zero when the
frozen copy predates them. Wire it to a gate; do not trust the docstring.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from congestion.predictor import predict          # noqa: E402
from congestion.config import PARAMS_PATH, load_params, route_params   # noqa: E402

ROUTES = ("TF>HUAFEI", "BLB>POS 14")
FLEETS = list(range(10, 801, 10))

JSON_PATH = os.path.join(ROOT, "reports", "saturation_curves.json")

# Fleet points --check reports drift at. Subset of FLEETS on purpose: every one
# is a real grid point in the frozen artifact, so the comparison is
# frozen-value vs current-value at the SAME fleet — never an interpolation
# artifact. Spread low (pre-knee) to high (deep saturation), because the two
# regimes drift for different reasons.
CHECK_FLEETS = (50, 100, 200, 300, 400, 500, 650, 790)

# Prose only: it can change without moving a single curve point, so including
# it would make the fingerprint cry wolf. Everything else route_params()
# returns is treated as curve-determining — a false "stale" costs one
# regeneration, a false "fresh" costs another 40% mispricing.
PROVENANCE_SKIP_FIELDS = ("distance_source",)

# Reference-side drift the manager should not ship without regenerating.
# Not a physics constant — a review threshold. Anything above it means the
# served reference and the live model would answer the same question
# differently by more than rounding.
DRIFT_WARN_PCT = 1.0


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


# ── Provenance: what the frozen curves were built FROM ──────────────────────
# The curves are a pure function of these inputs, so recording them is what
# makes staleness detectable instead of merely documented. Two families,
# because since 2026-08-22 both shape a curve:
#   1. per-route calibration params (data/congestion_params.json)
#   2. the NETWORK — official speed limits + segment geometry — because stick
#      routes price road time per segment. TF>HUAFEI is a stick route; a
#      speed-limit or capacity edit moves its curve while congestion_params.
#      json's own mtime never changes. Fingerprinting only the params file
#      would have missed the entire official-capacity round.


def _sha(payload):
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _route_param_snapshot(route):
    """Curve-determining params for one route, prose fields dropped."""
    p = route_params(route)
    return {k: v for k, v in sorted(p.items()) if k not in PROVENANCE_SKIP_FIELDS}


def _network_snapshot():
    from congestion import physics, segments, speed_limits
    return {
        "speed_limits": {
            "source_doc": speed_limits.SOURCE_DOC,
            "loaded": [list(x) for x in speed_limits.LOADED_LIMITS],
            "empty": [list(x) for x in speed_limits.EMPTY_LIMITS],
            "following_distance_m": speed_limits.FOLLOWING_DISTANCE_M,
            "road_width_m": speed_limits.ROAD_WIDTH_M,
            "separate_lanes": speed_limits.SEPARATE_LANES,
            "overtaking": speed_limits.OVERTAKING,
        },
        "segments": [
            {k: s.get(k) for k in ("id", "label", "top_km", "bottom_km", "length_km",
                                   "cap_hr", "limit_time_loaded_min",
                                   "limit_time_empty_min", "following_m")}
            for s in segments.SEGMENTS
        ],
        "node_km": dict(segments.NODE_KM),
        "spur_join_km": dict(segments.SPUR_JOIN_KM),
        "spur_km": dict(physics.SPUR_KM),
    }


# The MODEL CODE is an input too, and this was learned the hard way while
# building the guard: a co-agent edited congestion/predictor.py mid-session
# (the BLB observed-p95 capacity fix) and BLB>POS 14 moved 34.3% at 790 DT
# with BOTH the calibration and network fingerprints unchanged — the numbers
# came from the same params through different code. Data fingerprints alone
# would have called that artifact fresh.
MODEL_SOURCES = ("predictor.py", "physics.py", "queueing.py", "bpr.py",
                 "config.py", "segments.py", "speed_limits.py")


def _model_snapshot():
    """Per-file digests of congestion/, so --check can NAME the file that moved.

    A comment-only edit trips this. That is the intended direction: a spurious
    "stale" costs one regeneration, a spurious "fresh" costs another round of
    the mispricing this guard exists to stop."""
    out = {}
    for fn in MODEL_SOURCES:
        p = os.path.join(ROOT, "congestion", fn)
        try:
            with open(p, "rb") as fh:
                out[fn] = "sha256:" + hashlib.sha256(fh.read()).hexdigest()[:16]
        except OSError:
            out[fn] = None
    return out


def provenance():
    """Everything --check needs to prove the frozen copy is (not) current."""
    cal = load_params() or {}
    routes = {}
    for route in ROUTES:
        snap = _route_param_snapshot(route)
        routes[route] = {"fingerprint": _sha(snap), "params": snap}
    net = _network_snapshot()
    model = _model_snapshot()
    return {
        "calibration_file": os.path.relpath(PARAMS_PATH, ROOT),
        "calibration_generated_at": cal.get("generated_at"),
        "calibration_source": cal.get("source"),
        "calibration_fingerprint": _sha({r: v["fingerprint"] for r, v in routes.items()}),
        "network_fingerprint": _sha(net),
        "model_fingerprint": _sha(model),
        "model_files": model,
        "network": net,
        "routes": routes,
        "skipped_fields": list(PROVENANCE_SKIP_FIELDS),
        "note": ("Inputs the curves are a function of. scripts/"
                 "export_saturation_curves.py --check recomputes these and exits "
                 "non-zero when this artifact predates them. THREE fingerprints, "
                 "because all three are real inputs: per-route calibration; the "
                 "speed-limit/segment network (stick routes price road time per "
                 "segment); and the congestion/ model code itself."),
    }


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
        "provenance": provenance(),
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
    # Provenance in the human-readable copy too. "Regenerate after any
    # recalibration" was already written above, and the artifact still went
    # 23 h stale and kept being served — so name the calibration this was
    # built FROM and the command that proves it is still current.
    pv = data.get("provenance") or {}
    if pv:
        lines += ["Built from **%s** generated %s (`%s`, `%s`)."
                  % (pv.get("calibration_file"), pv.get("calibration_generated_at"),
                     pv.get("calibration_fingerprint"), pv.get("network_fingerprint")),
                  "",
                  "Verify this file is still current — exits non-zero when it is not:",
                  "",
                  "```bash",
                  ".venv/bin/python scripts/export_saturation_curves.py --check",
                  "```",
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


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _y_ticks(ymax):
    """4–6 ticks from 0, choosing a round step."""
    raw = ymax / 5.0 if ymax > 0 else 1.0
    mag = 10 ** math.floor(math.log10(raw))
    step = mag
    for cand in (1, 2, 2.5, 5, 10):
        if ymax / (cand * mag) <= 6:
            step = cand * mag
            break
    ticks = []
    v = 0.0
    while v <= ymax + 1e-9:
        ticks.append(v)
        v += step
    return ticks


def _fmt_tick(v):
    if abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return ("%.1f" % v).rstrip("0").rstrip(".")


def write_svg(data, path):
    """Two-panel figure. Dark industrial theme, shared legend, no formula in the title."""
    W, H = 1180, 640
    C_BG, C_PANEL, C_LINE = "#0d1117", "#161b22", "#30363d"
    C_GRID, C_TXT, C_MUTED = "#21262d", "#e6edf3", "#8b949e"
    C_FIX, C_SCALE = "#58a6ff", "#f0883e"
    C_KNEE, C_FLOOR, C_BAND = "#d29922", "#f85149", "rgba(88,166,255,.14)"
    panels = list(data["routes"].items())
    n = max(1, len(panels))
    gap = 28
    margin = {"l": 28, "r": 28, "t": 78, "b": 72}
    inner_w = W - margin["l"] - margin["r"] - gap * (n - 1)
    pw = inner_w / n
    plot_pad = {"l": 52, "r": 44, "t": 36, "b": 36}

    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
        'font-family="ui-sans-serif,system-ui,-apple-system,Segoe UI,Helvetica,Arial,sans-serif">'
        % (W, H, W, H),
        '<rect width="%d" height="%d" fill="%s"/>' % (W, H, C_BG),
        '<text x="%d" y="32" fill="%s" font-size="20" font-weight="700" text-anchor="middle">'
        "Saturation</text>" % (W // 2, C_TXT),
        '<text x="%d" y="52" fill="%s" font-size="13" text-anchor="middle">'
        "Trips per dump truck per day vs fleet size</text>" % (W // 2, C_MUTED),
        "<defs>",
        '<filter id="sc-soft" x="-5%" y="-5%" width="110%" height="110%">'
        '<feDropShadow dx="0" dy="1" stdDeviation="2" flood-color="#000" flood-opacity=".35"/>'
        "</filter>",
        "</defs>",
    ]

    for i, (route, r) in enumerate(panels):
        px = margin["l"] + i * (pw + gap)
        py = margin["t"]
        ph = H - margin["t"] - margin["b"]
        x0 = px + plot_pad["l"]
        y0 = py + plot_pad["t"]
        plot_w = pw - plot_pad["l"] - plot_pad["r"]
        plot_h = ph - plot_pad["t"] - plot_pad["b"]
        cal = r["curve"]
        prop = r["curve_proportional"]
        ymax = max(c["trips_per_dt"] for c in cal + prop) * 1.12
        xmax = 800.0
        cid = "sc-clip-%d" % i

        def sx(n_dt):
            return x0 + (float(n_dt) / xmax) * plot_w

        def sy(v):
            return y0 + plot_h - (float(v) / ymax) * plot_h

        out.append('<g filter="url(#sc-soft)">')
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="12" '
                   'fill="%s" stroke="%s"/>' % (px, py, pw, ph, C_PANEL, C_LINE))
        out.append("</g>")
        name = route.replace(">", " → ")
        out.append('<text x="%.1f" y="%.1f" fill="%s" font-size="15" font-weight="700">%s</text>'
                   % (px + 16, py + 26, C_TXT, _esc(name)))

        out.append('<clipPath id="%s"><rect x="%.1f" y="%.1f" width="%.1f" height="%.1f"/></clipPath>'
                   % (cid, x0, y0, plot_w, plot_h))

        for gy in _y_ticks(ymax):
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1"/>'
                       % (x0, sy(gy), x0 + plot_w, sy(gy), C_GRID))
            out.append('<text x="%.1f" y="%.1f" fill="%s" font-size="11" text-anchor="end" '
                       'style="font-variant-numeric:tabular-nums">%s</text>'
                       % (x0 - 8, sy(gy) + 4, C_MUTED, _fmt_tick(gy)))
        for gx in range(0, 801, 200):
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1"/>'
                       % (sx(gx), y0, sx(gx), y0 + plot_h, C_GRID))
            out.append('<text x="%.1f" y="%.1f" fill="%s" font-size="11" text-anchor="middle" '
                       'style="font-variant-numeric:tabular-nums">%d</text>'
                       % (sx(gx), y0 + plot_h + 18, C_MUTED, gx))

        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.25"/>'
                   % (x0, y0, x0, y0 + plot_h, C_LINE))
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.25"/>'
                   % (x0, y0 + plot_h, x0 + plot_w, y0 + plot_h, C_LINE))
        out.append('<text x="%.1f" y="%.1f" fill="%s" font-size="10" font-weight="700" '
                   'letter-spacing=".06em" text-anchor="middle">FLEET (DT)</text>'
                   % (x0 + plot_w / 2, y0 + plot_h + 32, C_MUTED))

        out.append('<g clip-path="url(#%s)">' % cid)
        band = " ".join("%.1f,%.1f" % (sx(c["n_trucks"]), sy(c["p90"])) for c in cal)
        band += " " + " ".join("%.1f,%.1f" % (sx(c["n_trucks"]), sy(c["p10"]))
                               for c in reversed(cal))
        out.append('<polygon points="%s" fill="%s" stroke="none"/>' % (band, C_BAND))

        if 0 < 1.0 < ymax:
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                       'stroke-width="1" stroke-dasharray="3 4" stroke-opacity=".85"/>'
                       % (x0, sy(1.0), x0 + plot_w, sy(1.0), C_FLOOR))

        if r.get("knee_dt"):
            kx = sx(r["knee_dt"])
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" '
                       'stroke-width="1.25" stroke-dasharray="4 4" stroke-opacity=".9"/>'
                       % (kx, y0, kx, y0 + plot_h, C_KNEE))

        for key, color, dash in (
                ("curve", C_FIX, ""),
                ("curve_proportional", C_SCALE, ' stroke-dasharray="7 5"')):
            pts = " ".join("%.1f,%.1f" % (sx(c["n_trucks"]), sy(c["trips_per_dt"]))
                           for c in r[key])
            out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2.4" '
                       'stroke-linejoin="round" stroke-linecap="round"%s/>' % (pts, color, dash))
            last = r[key][-1]
            out.append('<circle cx="%.1f" cy="%.1f" r="3.2" fill="%s"/>'
                       % (sx(last["n_trucks"]), sy(last["trips_per_dt"]), color))
        out.append("</g>")

        if 0 < 1.0 < ymax:
            out.append('<text x="%.1f" y="%.1f" fill="%s" font-size="10" text-anchor="start">'
                       "1 / day</text>" % (x0 + plot_w + 6, sy(1.0) + 3, C_FLOOR))
        if r.get("knee_dt"):
            kx = sx(r["knee_dt"])
            label = "Knee %d DT" % int(r["knee_dt"])
            tw = 8 * len(label) + 10
            lx = min(max(kx - tw / 2, x0 + 4), x0 + plot_w - tw - 4)
            out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="18" rx="4" '
                       'fill="#161b22" stroke="%s"/>' % (lx, y0 + 6, tw, C_KNEE))
            out.append('<text x="%.1f" y="%.1f" fill="%s" font-size="10" font-weight="700" '
                       'text-anchor="middle">%s</text>'
                       % (lx + tw / 2, y0 + 19, C_KNEE, label))

        for key, color, dy in (("curve", C_FIX, -2), ("curve_proportional", C_SCALE, 12)):
            last = r[key][-1]
            out.append('<text x="%.1f" y="%.1f" fill="%s" font-size="11" font-weight="700" '
                       'style="font-variant-numeric:tabular-nums">%.2f</text>'
                       % (x0 + plot_w + 6, sy(last["trips_per_dt"]) + dy, color,
                          last["trips_per_dt"]))

    # Shared legend — two rows so the four items never collide.
    ly = H - 56
    out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>'
               % (margin["l"], ly, W - margin["r"], ly, C_LINE))
    row1 = [
        (margin["l"], C_FIX, "solid", "Fixed loaders"),
        (margin["l"] + 180, C_SCALE, "dash", "Loaders grow with fleet"),
        (margin["l"] + 420, C_KNEE, "dash", "Knee"),
        (margin["l"] + 540, "#58a6ff", "band", "P10–P90"),
    ]
    for row_y, items in ((ly + 24, row1),):
        for x, color, kind, label in items:
            if kind == "band":
                out.append('<rect x="%d" y="%d" width="18" height="10" rx="2" fill="%s" stroke="%s"/>'
                           % (x, row_y - 9, C_BAND, C_FIX))
            elif kind == "dash":
                out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="2.2" '
                           'stroke-dasharray="6 4"/>' % (x, row_y - 4, x + 22, row_y - 4, color))
            else:
                out.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="2.2"/>'
                           % (x, row_y - 4, x + 22, row_y - 4, color))
            out.append('<text x="%d" y="%d" fill="%s" font-size="12">%s</text>'
                       % (x + 30, row_y, C_TXT, _esc(label)))
    out.append("</svg>")
    open(path, "w").write("\n".join(out))


def main(out_dir=None):
    # out_dir exists so the freshness guard can be PROVEN both ways without
    # touching the committed artifact: build a copy elsewhere, --check it, and
    # see the check pass. A gate that has only ever been seen to fail is
    # indistinguishable from one that always fails.
    out_dir = out_dir or os.path.join(ROOT, "reports")
    os.makedirs(out_dir, exist_ok=True)
    data = build()
    jp = os.path.join(out_dir, "saturation_curves.json")
    json.dump(data, open(jp, "w"), indent=1)
    write_md(data, os.path.join(out_dir, "SATURATION_CURVES.md"))
    write_svg(data, os.path.join(out_dir, "saturation_curves.svg"))
    for route, r in data["routes"].items():
        print("%s: %d pts, knee %s DT, min %.2f trips/DT (calibrated basis)" % (
            route, len(r["curve"]), r["knee_dt"],
            min(c["trips_per_dt"] for c in r["curve"])))
    print("wrote %s/saturation_curves.{json,svg} + SATURATION_CURVES.md"
          % os.path.relpath(out_dir, ROOT))


def render_svg_from_json():
    jp = os.path.join(ROOT, "reports", "saturation_curves.json")
    data = json.load(open(jp))
    sp = os.path.join(ROOT, "reports", "saturation_curves.svg")
    write_svg(data, sp)
    print("rewrote", sp, "from frozen JSON", data.get("generated_at"))


# ── --check: is the frozen artifact still the current model? ────────────────


def _iso(ts):
    if not ts:
        return None
    try:
        return datetime.datetime.strptime(str(ts), "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _legacy_route_snapshot(r):
    """Pre-provenance artifacts still carry these route-level scalars.

    So a frozen copy written before --check existed is not opaque: the fields
    that moved can still be named, which is the whole point (a boolean tells
    the manager nothing about whether to regenerate)."""
    return {k: r.get(k) for k in ("n_loaders_calibrated", "trucks_per_loader",
                                  "road_free_min", "ops_min",
                                  "overhead_per_trip_min", "day_rate_anchor",
                                  "n_trucks_ref", "knee_dt")}


def _current_route_scalars(route):
    p = route_params(route)
    return {"n_loaders_calibrated": int(p.get("n_loaders") or 2),
            "trucks_per_loader": tpl_for(p),
            "road_free_min": p.get("road_free_min"),
            "ops_min": p.get("ops_min"),
            "overhead_per_trip_min": p.get("overhead_per_trip_min"),
            "day_rate_anchor": p.get("day_rate"),
            "n_trucks_ref": p.get("n_trucks_ref")}


def _diff_maps(old, new):
    """[(field, old, new)] for every key that moved. Missing != equal."""
    out = []
    for k in sorted(set(old or {}) | set(new or {})):
        a, b = (old or {}).get(k), (new or {}).get(k)
        if isinstance(a, float) and isinstance(b, float):
            if abs(a - b) <= 1e-9:
                continue
        elif a == b:
            continue
        out.append((k, a, b))
    return out


def _live_curves(route):
    """Recompute BOTH bases at CHECK_FLEETS under the current calibration."""
    p = route_params(route)
    tpl = tpl_for(p)
    faces = int(p.get("n_loaders") or 2)
    bases = {"fixed": lambda n: faces,
             "proportional": lambda n: max(1, round(n / tpl))}
    out = {}
    for name, fn in bases.items():
        pts = {}
        for n in CHECK_FLEETS:
            try:
                pts[n] = predict(route, float(n), fn(n))["trips_per_DT_per_day"]
            except (ValueError, ArithmeticError, KeyError):
                pts[n] = None
        out[name] = pts
    return out


def check(path=None, verbose=True):
    """Compare the frozen reference against the CURRENT calibration + network.

    Returns a dict; `stale` is the gate signal. Deliberately reports drift
    NUMBERS as well as the boolean: "stale" alone gives a reviewer no way to
    judge whether it is a rounding-level re-anchor or the 40% miss that
    prompted this check."""
    path = path or JSON_PATH
    res = {"reference_path": os.path.relpath(path, ROOT), "stale": False,
           "reasons": [], "changed": [], "drift": [], "max_abs_pct": 0.0}
    try:
        with open(path, encoding="utf-8") as fh:
            frozen = json.load(fh) or {}
    except (OSError, ValueError) as exc:
        res.update(stale=True, reasons=["reference unreadable: %s" % exc])
        if verbose:
            print("STALE — %s" % res["reasons"][0])
        return res

    cur = provenance()
    fp = frozen.get("provenance") or {}
    res["frozen_at"] = frozen.get("generated_at")
    res["calibration_at"] = cur.get("calibration_generated_at")
    res["calibration_source"] = cur.get("calibration_source")

    # data/congestion_params.json is GITIGNORED, so a fresh clone and the
    # deployed box have no calibration at all — which is exactly when
    # /api/congestion_curve falls back to this reference. Comparing a
    # DEFAULTS-derived fingerprint against a calibrated one there would report
    # "calibration changed" and mean nothing. Say what can and cannot be
    # verified instead; the network and model-code fingerprints are committed
    # and still check out everywhere.
    res["has_calibration"] = bool(load_params())
    if not res["has_calibration"]:
        res["reasons"].append(
            "no %s on this machine — calibration cannot be verified here "
            "(network + model-code fingerprints still can). Run --check where "
            "the calibration lives before regenerating."
            % os.path.relpath(PARAMS_PATH, ROOT))

    # 1. Timestamps. The cheapest and most legible signal: the calibration is
    #    newer than the artifact built from it.
    f_at, c_at = _iso(frozen.get("generated_at")), _iso(cur.get("calibration_generated_at"))
    if f_at and c_at and c_at > f_at:
        hrs = (c_at - f_at).total_seconds() / 3600.0
        res["stale"] = True
        res["reasons"].append(
            "reference frozen %s PREDATES calibration %s by %.1f h"
            % (frozen.get("generated_at"), cur.get("calibration_generated_at"), hrs))

    # 2. Fingerprints. Catch an in-place recalibration that reused a timestamp,
    #    and — the case timestamps CANNOT see — a speed-limit/segment edit,
    #    which moves stick-route curves without touching congestion_params.json.
    if not fp:
        res["stale"] = True
        res["reasons"].append(
            "no provenance block in the reference (built before --check existed) "
            "— fingerprints cannot be verified, only the scalars below")
    else:
        names = ["network_fingerprint", "model_fingerprint"]
        if res["has_calibration"]:
            names.insert(0, "calibration_fingerprint")
        for name in names:
            if fp.get(name) != cur.get(name):
                res["stale"] = True
                res["reasons"].append("%s changed: %s -> %s"
                                      % (name, fp.get(name), cur.get(name)))
        # Name the model file, not just the rolled-up digest.
        for fn, a, b in _diff_maps(fp.get("model_files"), cur.get("model_files")):
            res["changed"].append({"route": "(model code)", "field": "congestion/" + fn,
                                   "frozen": a, "current": b,
                                   "basis": "source digest"})

    # 3. What actually moved, per route. Needs a calibration to compare to;
    #    without one every field would "differ" against DEFAULTS.
    for route in ROUTES if res["has_calibration"] else ():
        if fp.get("routes", {}).get(route):
            old = fp["routes"][route].get("params") or {}
            new = cur["routes"][route]["params"]
            basis = "provenance params"
        else:
            old = _legacy_route_snapshot((frozen.get("routes") or {}).get(route) or {})
            new = dict(_current_route_scalars(route))
            new["knee_dt"] = old.get("knee_dt")   # knee is an OUTPUT; not an input diff
            basis = "route scalars (legacy artifact)"
        for field, a, b in _diff_maps(old, new):
            res["changed"].append({"route": route, "field": field,
                                   "frozen": a, "current": b, "basis": basis})
            res["stale"] = True

    # 4. Drift in the served numbers themselves. Same precondition: recomputing
    #    curves off DEFAULTS would produce a drift table about nothing.
    for route in ROUTES if res["has_calibration"] else ():
        fr = (frozen.get("routes") or {}).get(route) or {}
        live = _live_curves(route)
        for basis, key in (("fixed", "curve"), ("proportional", "curve_proportional")):
            by_n = {c["n_trucks"]: c["trips_per_dt"] for c in (fr.get(key) or [])}
            for n in CHECK_FLEETS:
                a, b = by_n.get(n), live[basis].get(n)
                if a is None or b is None:
                    continue
                pct = ((b - a) / a * 100.0) if a else 0.0
                res["drift"].append({"route": route, "basis": basis, "dt": n,
                                     "frozen": round(a, 3), "current": round(b, 3),
                                     "delta": round(b - a, 3), "pct": round(pct, 1)})
                res["max_abs_pct"] = max(res["max_abs_pct"], abs(pct))
    if res["max_abs_pct"] > DRIFT_WARN_PCT:
        res["stale"] = True
        res["reasons"].append("served trips/DT drifts up to %.1f%% vs the current model"
                              % res["max_abs_pct"])

    if verbose:
        _print_check(res)
    return res


def _print_check(res):
    print("reference   : %s   frozen %s" % (res["reference_path"], res.get("frozen_at")))
    print("calibration : %s   %s" % (os.path.relpath(PARAMS_PATH, ROOT),
                                     res.get("calibration_at")))
    if res.get("calibration_source"):
        print("              %s" % res["calibration_source"])
    print("")
    if res["reasons"]:
        for r in res["reasons"]:
            print("  ! %s" % r)
        print("")
    if res["changed"]:
        print("INPUTS THAT MOVED SINCE THE FREEZE")
        print("  %-12s %-24s %14s -> %-14s" % ("route", "field", "frozen", "current"))
        for c in res["changed"]:
            print("  %-12s %-24s %14s -> %-14s" % (c["route"], c["field"],
                                                   c["frozen"], c["current"]))
        print("")
    if res["drift"]:
        print("DRIFT IN SERVED trips/DT/day  (frozen reference vs current calibration)")
        print("  %-12s %-13s %5s %9s %9s %9s %8s"
              % ("route", "basis", "DT", "frozen", "current", "delta", "pct"))
        for d in res["drift"]:
            print("  %-12s %-13s %5d %9.3f %9.3f %+9.3f %+7.1f%%"
                  % (d["route"], d["basis"], d["dt"], d["frozen"], d["current"],
                     d["delta"], d["pct"]))
        print("")
        print("  max |drift| %.1f%%  (review threshold %.1f%%)"
              % (res["max_abs_pct"], DRIFT_WARN_PCT))
        print("")
    if res["stale"]:
        print("STALE — regenerate: .venv/bin/python scripts/export_saturation_curves.py")
        print("        until then /api/congestion_curve serves these curves as if current.")
    else:
        print("FRESH — reference matches the current calibration, network and model code.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--svg-only", action="store_true",
                    help="restyle the SVG from the frozen JSON; recomputes nothing")
    ap.add_argument("--check", action="store_true",
                    help="compare the frozen reference to the current calibration; "
                         "exit 1 when stale (gate-friendly)")
    ap.add_argument("--json", action="store_true", help="with --check: emit JSON")
    ap.add_argument("--ref", default=None,
                    help="with --check: reference JSON to test "
                         "(default reports/saturation_curves.json)")
    ap.add_argument("--out-dir", default=None,
                    help="write the artifacts somewhere other than reports/ "
                         "(use to prove --check passes without touching the "
                         "committed copy)")
    args = ap.parse_args()
    if args.check:
        r = check(path=args.ref, verbose=not args.json)
        if args.json:
            print(json.dumps(r, indent=1))
        sys.exit(1 if r["stale"] else 0)
    elif args.svg_only:
        render_svg_from_json()
    else:
        main(args.out_dir)
