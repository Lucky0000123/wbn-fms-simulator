"""Drive the app the way a planning engineer would, and record what it says.

This is NOT the gate suite. The gates assert invariants; this exercises the
workflow end to end and CAPTURES THE NUMBERS so a human can judge whether they
are reasonable. A section can render perfectly and still be wrong, and only
reading the figures catches that.

    .venv/bin/python scripts/e2e_validation.py [--out DIR] [--label MODE]

Writes per-section screenshots and a JSON of every figure it read, so
reports/e2e_validation.md can quote measurements rather than impressions.

Run it twice -- once with FMS_DB_* set, once without -- to cover the dual-mode
requirement. `--label` tags the output so the two runs do not overwrite.
"""
import argparse
import json
import os
import re
import sys

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "http://127.0.0.1:5055"

SECTIONS = [
    ("2", "pa-breakdown-chart", "Trip time breakdown"),
    ("3", "pa-speed-chart", "Speed per section"),
    ("4", "pa-drop-chart", "Congestion and shared points"),
    ("5", "pa-gauges", "Queue risk"),
    ("6", "ps-rows", "Production estimate"),
    ("7", "pa-history-chart", "Historical reference"),
    ("8", "pa-fleet-rows", "Fleet sizing"),
    ("9", "pa-map", "Corridor map"),
]

ISSUES = []


def issue(where, what):
    ISSUES.append({"where": where, "what": what})
    print("    ISSUE [%s] %s" % (where, what))


def txt(pg, sel):
    try:
        return " ".join((pg.eval_on_selector(sel, "e => e.textContent") or "").split())
    except Exception:                                              # noqa: BLE001
        return ""


def nrows(pg, sel):
    try:
        return pg.eval_on_selector_all(sel + " tr", "e => e.length")
    except Exception:                                              # noqa: BLE001
        return 0


def settle(pg):
    """Wait for the assessment to finish rather than sleeping a fixed time."""
    try:
        pg.wait_for_function(
            "() => {const b=document.getElementById('pa-breakdown-rows');"
            " return b && b.querySelectorAll('tr').length > 0;}", timeout=40000)
    except Exception:                                              # noqa: BLE001
        pass
    pg.wait_for_timeout(3500)          # charts + map tiles


def add_haul(pg, prefix, trucks):
    idx = pg.evaluate(
        """(s) => {const o=[...document.querySelectorAll('#ps-route option')];
           return o.findIndex(x => x.textContent.trim().startsWith(s));}""", prefix)
    if idx < 0:
        return False
    pg.select_option("#ps-route", index=idx)
    pg.fill("#ps-trucks", str(trucks))
    pg.click("text=Add haul")
    try:
        pg.wait_for_function(
            "() => {const b=document.getElementById('ps-rows');"
            " return b && !b.textContent.includes('Simulating');}", timeout=40000)
    except Exception:                                              # noqa: BLE001
        pass
    return True


def api_sim(pg, plans, weather="dry", shift=720):
    """Read the engine directly, so the recorded figures are the engine's own."""
    return pg.evaluate(
        """async ([plans, weather, shift]) => {
             const r = await fetch('/api/simulate', {method:'POST',
               headers:{'Content-Type':'application/json'},
               body: JSON.stringify({plans, weather, shift_minutes: shift})});
             return await r.json(); }""", [plans, weather, shift])


def capture_sections(pg, out, tag):
    """Screenshot each section card and note whether it actually populated."""
    state = {}
    for num, anchor, name in SECTIONS:
        el = pg.query_selector("#" + anchor)
        if not el:
            issue(tag, "section %s (%s): anchor #%s missing" % (num, name, anchor))
            state[num] = {"rendered": False}
            continue
        try:
            pg.eval_on_selector("#" + anchor,
                                "e => {const c = e.closest('.card'); if (c) c.id = 'shot';}")
            pg.eval_on_selector("#shot", "e => e.scrollIntoView()")
            pg.wait_for_timeout(700)
            pg.query_selector("#shot").screenshot(
                path=os.path.join(out, "%s_s%s.png" % (tag, num)))
            pg.eval_on_selector("#shot", "e => e.removeAttribute('id')")
        except Exception as exc:                                   # noqa: BLE001
            issue(tag, "section %s screenshot failed: %s" % (num, str(exc)[:60]))
        # Did it actually draw anything?
        drew = pg.evaluate(
            """(a) => {const e=document.getElementById(a); if(!e) return 0;
                 return e.querySelectorAll('canvas, svg, tr, .leaflet-container').length
                        + (e.tagName==='TBODY' ? e.querySelectorAll('tr').length : 0);}""",
            anchor)
        state[num] = {"rendered": drew > 0, "elements": drew}
        if not drew:
            issue(tag, "section %s (%s) rendered nothing" % (num, name))
    return state


def run(pg, out, tag):
    res = {"tag": tag}
    pg.goto(BASE + "/simulator", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3000)
    res["dataMode"] = pg.evaluate(
        "async () => (await (await fetch('/health')).json()).dataMode")
    print("  dataMode: %s" % res["dataMode"])

    pg.click("#tabbtn-plansim")
    pg.wait_for_selector("#ps-route", timeout=20000)
    pg.wait_for_function(
        "() => document.querySelectorAll('#ps-route option').length > 1", timeout=40000)

    # ---------- TEST 1: single plan ----------
    print("  TEST 1  single plan, 30 trucks BLB>FENI KM0, dry")
    if not add_haul(pg, "BLB>FENI KM0", 30):
        issue(tag, "BLB>FENI KM0 not offered in the route list")
    pg.click("text=Run assessment")
    settle(pg)
    res["t1_sections"] = capture_sections(pg, out, tag + "_t1")
    res["t1_api"] = api_sim(pg, [{"route": "BLB>FENI KM0", "source": "BLB",
                                  "destination": "FENI KM0", "n_trucks": 30}])
    # NOT truncated. An earlier version cut these to 400 chars and then tested
    # the truncated string for the congestion coefficient, which sits ~430 chars
    # in -- so it reported the claim MISSING when it was present. A checker that
    # says absent-when-present is worse than no checker: it sends you hunting a
    # defect that does not exist. Truncate at display time, never before a test.
    res["t1_notes"] = {
        "s2": txt(pg, "#pa-breakdown-note"),
        "s3": txt(pg, "#pa-speed-note"),
        "s4": txt(pg, "#pa-cong-note"),
        "s5": txt(pg, "#pa-gauge-note"),
        "s7": txt(pg, "#pa-history-note"),
        "s9": txt(pg, "#pa-map-note"),
    }
    res["t1_counts"] = {
        "s2_rows": nrows(pg, "#pa-breakdown-rows"),
        "s4_shared_rows": nrows(pg, "#pa-shared-rows"),
        "s4_drop_rows": nrows(pg, "#pa-drop-rows"),
        "s5_gauges": pg.eval_on_selector_all("#pa-gauges > div", "e => e.length"),
        "s5_canvases": pg.eval_on_selector_all("#pa-gauges canvas", "e => e.length"),
        "s6_rows": nrows(pg, "#ps-rows"),
        "s7_rows": nrows(pg, "#pa-history-rows"),
        "s8_rows": nrows(pg, "#pa-fleet-rows"),
        "s9_map_rows": nrows(pg, "#pa-map-rows"),
        "s9_polylines": pg.evaluate(
            "() => {try{let n=0;_paLayer.eachLayer(l=>{if(l.getLatLngs)n++});return n;}catch(e){return -1;}}"),
    }
    # The congestion claim the brief asks about, verified as TEXT on screen.
    s4 = res["t1_notes"]["s4"]
    res["t1_s4_has_slope"] = ("-0.0233" in s4 or "−0.0233" in s4)
    res["t1_s4_has_n"] = bool(re.search(r"36,046|35,006", s4))
    res["t1_s4_has_pct"] = "4.8%" in s4

    # ---------- TEST 2: shared dumping point ----------
    print("  TEST 2  add 20 trucks POS 12>FENI KM0 (shares the FENI tip)")
    if not add_haul(pg, "POS 12>FENI KM0", 20):
        issue(tag, "POS 12>FENI KM0 not offered")
    pg.click("text=Run assessment")
    settle(pg)
    res["t2_sections"] = capture_sections(pg, out, tag + "_t2")
    res["t2_api"] = api_sim(pg, [
        {"route": "BLB>FENI KM0", "source": "BLB", "destination": "FENI KM0", "n_trucks": 30},
        {"route": "POS 12>FENI KM0", "source": "POS 12", "destination": "FENI KM0", "n_trucks": 20}])
    res["t2_shared_text"] = txt(pg, "#pa-shared-rows")[:300]
    res["t2_gauge_note"] = txt(pg, "#pa-gauge-note")[:300]
    res["t2_counts"] = {
        "s5_gauges": pg.eval_on_selector_all("#pa-gauges > div", "e => e.length"),
        "s5_canvases": pg.eval_on_selector_all("#pa-gauges canvas", "e => e.length"),
        "s6_rows": nrows(pg, "#ps-rows"),
    }
    if "no loading or dumping point is shared" in res["t2_shared_text"].lower():
        issue(tag, "two plans into FENI KM0 but section 4 reports nothing shared")

    # ---------- TEST 3: wet weather ----------
    print("  TEST 3  same two plans, weather = wet")
    pg.select_option("#ps-weather", "wet")
    settle(pg)
    res["t3_sections"] = capture_sections(pg, out, tag + "_t3")
    plans2 = [{"route": "BLB>FENI KM0", "source": "BLB", "destination": "FENI KM0", "n_trucks": 30},
              {"route": "POS 12>FENI KM0", "source": "POS 12", "destination": "FENI KM0", "n_trucks": 20}]
    res["t3_api_wet"] = api_sim(pg, plans2, weather="wet")
    res["t3_api_dry"] = api_sim(pg, plans2, weather="dry")
    pg.select_option("#ps-weather", "dry")

    # ---------- shift extrapolation warning ----------
    res["shift_600_warns"] = bool(
        (api_sim(pg, [{"route": "BLB>FENI KM0", "source": "BLB",
                       "destination": "FENI KM0", "n_trucks": 30}], shift=600)
         .get("summary") or {}).get("shift_minutes_extrapolated"))

    res["console_errors"] = CONSOLE[:]
    return res


CONSOLE = []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/e2e")
    ap.add_argument("--label", default="run")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1366, "height": 900})
        pg.on("console", lambda m: CONSOLE.append((m.type, m.text[:160]))
              if m.type in ("error",) else None)
        pg.on("pageerror", lambda e: CONSOLE.append(("pageerror", str(e)[:160])))
        res = run(pg, a.out, a.label)
        b.close()

    # CDN failures are an offline condition, not an app defect.
    res["console_errors"] = [c for c in res.get("console_errors", [])
                             if not any(k in c[1].lower()
                                        for k in ("echarts", "jsdelivr", "unpkg", "leaflet", "cesium"))]
    res["issues"] = ISSUES
    path = os.path.join(a.out, "%s_results.json" % a.label)
    with open(path, "w") as fh:
        json.dump(res, fh, indent=2, default=str)
    print("\n  wrote %s" % path)
    print("  issues: %d" % len(ISSUES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
