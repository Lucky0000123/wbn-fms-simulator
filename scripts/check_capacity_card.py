#!/usr/bin/env python3
"""J71 — the capacity panel must quote the ENGINE, never a second model.

History, because the target moved:

  2026-08-12 (morning) — `planRenderOutcomes` built the A · Shift-outcomes
  capacity card from `predict.wmt`, the Step 1 path model, instead of the
  engine's `summary.planned_production_t`. On 800 DT (TF>FENI KM0) + 560 DT
  (TF>FENI KM15) the engine clipped 16,012 t and raised two capacity_warnings;
  the card read "Shortfall 0 t · vs planned 120%" and drew no warnings. The
  path model declines sub-linearly with DT while the engine's planned grows
  linearly, so the ratio IMPROVED as the plan got more absurd.

  2026-08-12 (afternoon) — the owner deleted the whole A · Shift-outcomes block
  and renumbered B->A. That removed the DEFECTIVE copy; the honest one had
  always been `psRender()` in plan_simulator.js, which computes
  `planned - achievable` from the engine and renders capacity_warnings. So the
  "two definitions of shortfall" problem is now resolved by elimination.

The invariant outlives both panels and is what this gate pins: whatever renders
capacity must take planned, achievable and the shortfall from the SAME
/api/simulate response, and must not quietly substitute a different model.

Driven through the browser with a real response for the J52 reason: a gate that
builds its own input cannot catch a bug in what the real caller sends.

Two directions, deliberately paired. A fleet inside the envelope must show no
shortfall line and no warnings; a fleet past the point ceiling must show the
engine's clip and every warning it returned. A check that only ever demanded
"shortfall > 0" would be passed by hardcoding one; only "== 0" by deleting the
feature.

Exit 0 = pass.
"""
import json
import re
import sys
import urllib.request

BASE = "http://127.0.0.1:5055"
ROUTE = ("TF", "FENI KM0")

fails = []


def chk(label, cond, got=""):
    print(("  PASS " if cond else "  FAIL ") + label + (f"   [{got}]" if got else ""))
    if not cond:
        fails.append(label)


def plans(dt):
    return [{"route": f"{ROUTE[0]}>{ROUTE[1]}", "source": ROUTE[0],
             "destination": ROUTE[1], "n_trucks": dt, "contractor": "RIM"}]


def simulate(dt):
    req = urllib.request.Request(
        BASE + "/api/simulate",
        data=json.dumps({"plans": plans(dt), "weather": "dry",
                         "shift_minutes": 720}).encode(),
        headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=180))


def num(text):
    """Pull the first number out of a KPI cell, tolerating thousands separators."""
    m = re.search(r"-?[\d,]+(?:\.\d+)?", text or "")
    return float(m.group(0).replace(",", "")) if m else None


def main():
    from playwright.sync_api import sync_playwright

    # Derive the breaching fleet rather than hardcoding it: the ceiling moves
    # with the data behind it.
    small, big = 60, None
    for dt in (400, 800, 1600, 3200):
        s = simulate(dt)["summary"]
        if s["planned_production_t"] - s["achievable_production_t"] > 1:
            big = dt
            break
    if big is None:
        print("  SKIP no fleet size reached the point ceiling on this data")
        return 0

    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.goto(BASE + "/simulator", wait_until="domcontentloaded", timeout=30000)
        pg.click("#tabbtn-plan")
        # Wait on the condition, not the clock: in fixture mode start-up fetches
        # stall for seconds and a fixed timeout looks like total page failure.
        pg.wait_for_selector("#ps-foot", state="attached", timeout=25000)
        pg.wait_for_function("() => typeof psRender === 'function'", timeout=25000)

        def render(dt):
            return pg.evaluate(
                """async ([base, pl]) => {
                    const r = await fetch(base + '/api/simulate', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({plans: pl, weather: 'dry',
                                              shift_minutes: 720})});
                    const sim = await r.json();
                    psRender(sim);
                    const t = id => (document.getElementById(id) || {}).textContent || '';
                    const foot = t('ps-foot');
                    const hz = (typeof planHorizonFactor === 'function') ? planHorizonFactor() : 1;
                    return {planned: t('ps-kpi-planned'), achv: t('ps-kpi-achv'),
                            foot: foot.replace(/\\s+/g, ' ').trim(),
                            blocked: /blocked by capacity/.test(foot),
                            body: (document.body.textContent || '')
                                    .replace(/\\s+/g, ' '),
                            hz: hz,
                            s: sim.summary};
                }""",
                [BASE, plans(dt)])

        for dt, kind in ((small, "inside envelope"), (big, "past ceiling")):
            r = render(dt)
            s = r["s"]
            planned, achv = s["planned_production_t"], s["achievable_production_t"]
            short = round(planned - achv)
            nwarn = len(s.get("capacity_warnings") or [])
            hz = r.get("hz") or 1
            shown_planned = round(planned * hz)
            shown_achv = round(achv * hz)
            shown_short = round((planned - achv) * hz)
            print(f"\n{kind}: {dt} DT · planned {planned:,.0f} · achievable {achv:,.0f} "
                  f"· engine shortfall {short:,} t · {nwarn} warning(s)"
                  f" · display ×{hz:g} → {shown_planned:,.0f} / {shown_achv:,.0f}")

            chk(f"{kind}: planned KPI == engine planned × horizon",
                num(r["planned"]) == shown_planned, f"{r['planned']} vs {shown_planned:,.0f}")
            chk(f"{kind}: achievable KPI == engine achievable × horizon",
                num(r["achv"]) == shown_achv, f"{r['achv']} vs {shown_achv:,.0f}")

            if kind == "inside envelope":
                chk("inside envelope: no 'blocked by capacity' line", not r["blocked"])
            else:
                chk("past ceiling: shows 'blocked by capacity'", r["blocked"])
                chk("past ceiling: blocked tonnage == (planned - achievable) × horizon",
                    f"{shown_short:,}" in r["foot"], f"want {shown_short:,} t in footer")
                chk("past ceiling: every capacity_warning is rendered",
                    all(w.split(".")[0][:40] in r["body"]
                        for w in (s.get("capacity_warnings") or [])),
                    f"{nwarn} warning(s)")

        chk("no page errors", not errors, "; ".join(errors[:2]))
        b.close()

    print("\nRESULT:", "PASS" if not fails else f"FAIL ({len(fails)})")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
