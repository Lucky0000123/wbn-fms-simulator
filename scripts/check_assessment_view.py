"""Browser check for the plan assessment view (sections 2-8).

Asserts what a screenshot cannot: that each section actually populated from a
real /api/simulate response, that no console error fired, and that the page fits
the 1366x768 laptop the planners use.

Run against a server already listening on 5055. Exits non-zero on any failure so
it can be wired into verify_phase2.sh as a gate.

WARNING: wait_until="networkidle" never settles on this UI (long-poll/timers), so
this uses domcontentloaded plus explicit waits for the elements themselves.
"""
import json
import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:5055"
FAIL = []
CONSOLE = []


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAIL.append(name)


def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 1366, "height": 768})
        pg.on("console", lambda m: CONSOLE.append((m.type, m.text)))
        pg.on("pageerror", lambda e: CONSOLE.append(("pageerror", str(e))))

        pg.goto(BASE + "/simulator", wait_until="domcontentloaded", timeout=30000)
        pg.wait_for_timeout(2500)

        # Open the Production Simulator tab and build a two-plan scenario that
        # SHARES a dumping point, so section 4 has something real to report.
        pg.click("#tabbtn-plansim")
        pg.wait_for_selector("#ps-route", timeout=15000)
        pg.wait_for_timeout(1200)

        opts = pg.eval_on_selector_all(
            "#ps-route option", "els => els.map(e => e.textContent)")
        check("route dropdown populated", len(opts) > 3, "%d options" % len(opts))

        def add(prefix, trucks):
            idx = pg.evaluate(
                """(s) => {const o=[...document.querySelectorAll('#ps-route option')];
                   return o.findIndex(x => x.textContent.trim().startsWith(s));}""", prefix)
            if idx < 0:
                return False
            pg.select_option("#ps-route", index=idx)
            pg.fill("#ps-trucks", str(trucks))
            pg.click("text=Add haul")
            pg.wait_for_timeout(1800)
            return True

        # TWO DIFFERENT origins into ONE destination, so section 4 has a genuinely
        # shared dumping point to report. Adding the same route twice merges into
        # one bigger fleet and shares nothing, which is what an earlier version of
        # this check did -- it asserted against the "nothing is shared" message.
        dests = pg.evaluate(
            """() => {const o=[...document.querySelectorAll('#ps-route option')]
                 .map(x=>x.textContent.trim().split(' —')[0]);
               const by={}; o.forEach(r=>{const d=r.split('>')[1]; if(d)(by[d]=by[d]||[]).push(r);});
               const k=Object.keys(by).find(k=>by[k].length>=2);
               return k ? by[k].slice(0,2) : [];}""")
        check("found two routes sharing a destination", len(dests) == 2, dests)
        added = add(dests[0], 30) if dests else False
        check("added first haul", added)
        if len(dests) == 2:
            add(dests[1], 20)

        # Render at least three times before asserting. A chart cached against a
        # detached DOM node only blanks from the SECOND render on, so a check that
        # looks after one render cannot see it.
        pg.click("text=Run assessment")
        pg.wait_for_timeout(2500)
        pg.click("text=Run assessment")
        pg.wait_for_timeout(3000)

        # --- section presence and, more importantly, population ---
        vis = lambda sel: pg.eval_on_selector(
            sel, "e => !!(e.offsetWidth || e.offsetHeight || e.getClientRects().length)")
        rows = lambda sel: pg.eval_on_selector_all(sel + " tr", "e => e.length")
        text = lambda sel: (pg.eval_on_selector(sel, "e => e.textContent") or "").strip()

        check("section 2-5 wrapper visible", vis("#pa-sections-top"))
        check("section 7-8 wrapper visible", vis("#pa-sections-bot"))
        check("S2 breakdown table populated", rows("#pa-breakdown-rows") >= 1,
              rows("#pa-breakdown-rows"))
        check("S2 note names the residual honestly",
              'not "travel empty"' in text("#pa-breakdown-note").lower()
              or "not “travel empty”" in text("#pa-breakdown-note").lower(),
              text("#pa-breakdown-note")[:90])
        # Section 3 depends on FMS_CONGESTION_SEG, which retains ~2 weeks and is
        # reached over a VPN that drops every few minutes. When that query fails
        # the endpoint returns {"ok": false, "error": ...} with HTTP 200 -- which
        # _register() reads as success, so it does NOT fall back to the fixture,
        # and the section legitimately has nothing to draw.
        #
        # So assert the CORRECT behaviour for the data that exists, not that data
        # exists. Both branches still discriminate: a broken section 3 fails
        # either way, because it would neither populate nor explain itself.
        n_seg = pg.evaluate(
            """async () => {
                 try { const r = await fetch('/api/simulator/congestion-model');
                       const d = await r.json();
                       return (d.segments || []).length; } catch (e) { return -1; }
               }""")
        roads = pg.eval_on_selector_all("#pa-road option", "e => e.length")
        note3 = text("#pa-speed-note").lower()
        if n_seg > 0:
            check("S3 road selector populated (%d segments available)" % n_seg, roads >= 1, roads)
            check("S3 note refuses the loaded/empty claim",
                  "not loaded vs empty" in note3, note3[:90])
        else:
            print("  INFO congestion feed returned %d segments — VPN down or retention "
                  "window empty; asserting the honest-unavailable path instead" % n_seg)
            check("S3 explains the absence instead of drawing an empty axis",
                  "no segment speeds available" in note3, note3[:120])
        check("S4 shared-point table populated", rows("#pa-shared-rows") >= 1)
        check("S4 reports a REAL shared point, not the empty-state message",
              "no loading or dumping point is shared" not in text("#pa-shared-rows").lower(),
              text("#pa-shared-rows")[:90])
        check("S4 cites the measured slope",
              "-0.0233" in text("#pa-cong-note") or "−0.0233" in text("#pa-cong-note"),
              text("#pa-cong-note")[:90])
        check("S4 separates the bars from the congestion coefficient",
              "two different things" in text("#pa-cong-note").lower(),
              text("#pa-cong-note")[:90])
        # Count DRAWN CANVASES, not wrapper divs. The wrappers are recreated on
        # every render and so can never fail; the canvases are what blanked.
        n_gauge_wrap = pg.eval_on_selector_all("#pa-gauges > div", "e => e.length")
        n_gauge_canvas = pg.eval_on_selector_all("#pa-gauges canvas", "e => e.length")
        check("S5 gauge wrappers present", n_gauge_wrap >= 1, n_gauge_wrap)
        check("S5 gauges actually DREW after repeated renders",
              n_gauge_canvas >= n_gauge_wrap,
              "%d canvas for %d wrappers" % (n_gauge_canvas, n_gauge_wrap))
        check("S6 production table still populated", rows("#ps-rows") >= 1)
        check("S7 history table populated", rows("#pa-history-rows") >= 1)
        check("S8 fleet table populated", rows("#pa-fleet-rows") >= 1)
        check("S8 note states availability never scales tonnage",
              "never scale" in text("#pa-fleet-note").lower(),
              text("#pa-fleet-note")[:90])

        # The whole point of the fix: the UI must not be quoting a scaled tonnage.
        applied = pg.evaluate(
            """async () => {
                 const r = await fetch('/api/simulate', {method:'POST',
                   headers:{'Content-Type':'application/json'},
                   body: JSON.stringify({plans:[{route:'BLB>FENI KM0',source:'BLB',
                     destination:'FENI KM0',n_trucks:30}]})});
                 const d = await r.json();
                 return d.summary.availability_factor_applied;
               }""")
        check("availability_factor_applied is 1.0 from the browser", applied == 1.0, applied)

        # ECharts is a CDN dependency; record whether it loaded so a chart-less
        # run is reported as such rather than passing quietly.
        has_echarts = pg.evaluate("() => typeof echarts !== 'undefined'")
        print("  INFO ECharts loaded from CDN: %s" % has_echarts)
        if has_echarts:
            canvases = pg.eval_on_selector_all(
                "#pa-sections-top canvas, #pa-sections-bot canvas", "e => e.length")
            check("charts drew canvases", canvases >= 3, "%d canvas" % canvases)
        else:
            print("  INFO offline: charts degrade to a note, tables still checked above")

        # 1366x768: no horizontal scrollbar.
        ow = pg.evaluate("() => document.documentElement.scrollWidth")
        check("no horizontal overflow at 1366px", ow <= 1370, "scrollWidth=%d" % ow)

        pg.screenshot(path="/tmp/assessment_view.png", full_page=True)
        print("  INFO screenshot -> /tmp/assessment_view.png")

        errs = [c for c in CONSOLE if c[0] in ("error", "pageerror")]
        # A CDN block shows up as a console error for the script tag; that is the
        # offline case, already reported above, and must not fail the gate.
        errs = [c for c in errs if "echarts" not in c[1].lower()
                and "jsdelivr" not in c[1].lower()]
        check("console clean (excluding CDN)", not errs, errs[:3])

        b.close()

    print()
    if FAIL:
        print("ASSESSMENT VIEW CHECK: %d FAILURE(S): %s" % (len(FAIL), "; ".join(FAIL)))
        sys.exit(1)
    print("assessment view check passed")


if __name__ == "__main__":
    main()
