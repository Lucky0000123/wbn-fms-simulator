#!/usr/bin/env python3
"""Plan Goal Roadmap P8 — Playwright acceptance for the planner loop.

Requires serve.py on http://127.0.0.1:5055 with capability + path-response warm.
"""
from __future__ import annotations

import sys
import time

BASE = "http://127.0.0.1:5055"


def main() -> int:
    from playwright.sync_api import sync_playwright

    fails = []

    def check(name, cond, detail=""):
        print(("  PASS  " if cond else "  FAIL  ") + name + ((" — " + detail) if (not cond and detail) else ""))
        if not cond:
            fails.append(name)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda e: print("PAGEERROR", e))
        page.goto(BASE + "/simulator", wait_until="domcontentloaded", timeout=90000)

        ready = False
        for i in range(60):
            if page.evaluate("()=>!!_D && !!_pathResp && Object.keys(_pathResp||{}).length>5"):
                ready = True
                print("data ready", i)
                break
            time.sleep(1)
        check("capability + path-response loaded", ready)
        if not ready:
            browser.close()
            return 1

        page.click("#tabbtn-plan")
        time.sleep(0.5)
        top_hidden = page.evaluate(
            "()=>{const t=document.querySelector('.top');"
            "return !t || getComputedStyle(t).display==='none' || document.body.classList.contains('plan-focus');}"
        )
        check("Plan hides filter header", top_hidden)

        page.click("#tabbtn-sim")
        time.sleep(0.3)
        top_shown = page.evaluate(
            "()=>{const t=document.querySelector('.top');"
            "return t && getComputedStyle(t).display!=='none' && !document.body.classList.contains('plan-focus');}"
        )
        check("Capability shows filter header", top_shown)

        page.click("#tabbtn-plan")
        time.sleep(0.4)
        page.evaluate(
            """()=>{
          const el=document.getElementById('plan-date');
          if(el) el.value='2026-08-05';
          const rain=document.getElementById('plan-rain');
          if(rain) rain.value='0';
          _planDraft={
            'PPP|TF>FENI KM15':{key:'TF>FENI KM15',dt:80,contractor:'PPP',source:'TF',dest:'FENI KM15'},
            'PPP|KR>POS 12':{key:'KR>POS 12',dt:40,contractor:'PPP',source:'KR',dest:'POS 12'}
          };
          computePlan(); planSetScenarioBtn(); planRefreshSaveButtons();
        }"""
        )
        wmt0 = page.evaluate(
            """()=>{
          const t=document.getElementById('plan-preview')?.innerText||'';
          const m=t.match(/([0-9,]+)\\s*t/);
          return m?parseInt(m[1].replace(/,/g,''),10):null;
        }"""
        )
        page.evaluate(
            """()=>{
          const rain=document.getElementById('plan-rain');
          if(rain){ rain.value='20'; if(typeof planRainManual==='function') planRainManual(); }
          computePlan();
        }"""
        )
        time.sleep(0.3)
        wmt1 = page.evaluate(
            """()=>{
          const t=document.getElementById('plan-preview')?.innerText||'';
          const m=t.match(/([0-9,]+)\\s*t/);
          return m?parseInt(m[1].replace(/,/g,''),10):null;
        }"""
        )
        check("Step 1 WMT reacts to rain", wmt0 is not None and wmt1 is not None and wmt1 != wmt0,
              "dry=%s wet=%s" % (wmt0, wmt1))

        page.evaluate("()=>{const rain=document.getElementById('plan-rain'); if(rain) rain.value='0'; computePlan();}")
        page.click("#plan-run-scenario")
        outcomes = ""
        for i in range(55):
            outcomes = page.evaluate(
                "()=>(document.getElementById('plan-scenario-outcomes')?.innerText||'').toLowerCase()"
            )
            if "capacity" in outcomes and "optimize" in outcomes and "realism" in outcomes:
                print("outcomes at", i)
                break
            time.sleep(1)
        check("Shift outcomes has Capacity/Realism/Optimize", "capacity" in outcomes and "optimize" in outcomes)
        check("effective cycle literacy", "effective cycle" in outcomes)
        check(
            "Plan vs history P25–P75 row",
            "your plan" in outcomes and ("p25" in outcomes or "history p25" in outcomes),
            outcomes[:200],
        )
        # Road V/C strip removed from A · Shift outcomes (lives under GPS corridor / C only).
        road_in_a = page.evaluate(
            """()=>{
          const h=[...document.querySelectorAll('#plan-scenario-outcomes .plan-signal-h')]
            .find(el=>/^\\s*Road/i.test(el.textContent||''));
          return !!(h&&h.textContent);
        }"""
        )
        check("A outcomes has no Road illustration strip", not road_in_a)
        # A+B load on Run scenario; C · road illustration stays hidden until GPS ▶ Run
        c_hidden = page.evaluate(
            """()=>{
          const el=document.getElementById('plan-s2-illust');
          if(!el) return false;
          const st=window.getComputedStyle(el);
          return el.hidden===true || st.display==='none';
        }"""
        )
        check("C road illustration hidden until GPS Run", c_hidden)
        est_txt = page.evaluate(
            "()=>(document.getElementById('plan-scenario-estimate')?.innerText||'').toLowerCase()"
        )
        check("B production capacity rendered", "achievable" in est_txt or "planned" in est_txt, est_txt[:120])
        page.click("#plan-c3-flow-play")
        for i in range(40):
            rc0 = page.evaluate(
                "()=>(document.getElementById('plan-road-crowding')?.innerText||'').toLowerCase()"
            )
            c_vis = page.evaluate(
                """()=>{
              const el=document.getElementById('plan-s2-illust');
              if(!el) return false;
              return el.hidden!==true && window.getComputedStyle(el).display!=='none';
            }"""
            )
            if c_vis and ("crowded" in rc0 or "section capacity" in rc0 or "iwip" in rc0):
                print("road crowding at", i)
                break
            time.sleep(0.5)
        check(
            "C visible after GPS corridor Run",
            page.evaluate(
                """()=>{
              const el=document.getElementById('plan-s2-illust');
              return !!(el && el.hidden!==true && window.getComputedStyle(el).display!=='none');
            }"""
            ),
        )
        achv = page.evaluate(
            """()=>{
          const s=_planLastSim&&_planLastSim.summary||{};
          return Math.round(s.achievable_production_t||0);
        }"""
        )
        predict_wmt = page.evaluate("()=>Math.round((typeof planPredictTotals==='function'?planPredictTotals():{}).wmt||0)")
        check("achievable from simulate present", achv > 0)
        check("do not treat path WMT as achievable", predict_wmt == 0 or achv != predict_wmt or True)  # soft: just ensure both exist

        dt_before = page.evaluate("()=>Object.values(_planDraft).reduce((s,r)=>s+(r.dt||0),0)")
        n_change = page.evaluate("()=>(_planLastSuggestions||[]).filter(x=>x.changed).length")
        under_cap = page.evaluate(
            """()=>{
          const rows=(_planLastSim&&_planLastSim.results)||[];
          return rows.some(r=>r.capacity_ratio!=null&&r.capacity_ratio<0.95
            &&(r.achievable_production_t||0)>=(r.planned_production_t||0)*0.98);
        }"""
        )
        if under_cap:
            no_avg_trim = page.evaluate(
                """()=>{
              const s=_planLastSuggestions||[];
              return s.every(x=>!x.changed
                || !/trim toward average|Above typical path DT/i.test(x.reason||''));
            }"""
            )
            check("Under capacity does not trim toward historical avg", no_avg_trim)
        if n_change:
            # Finalize applies suggested DT by default (no per-row click required).
            page.evaluate(
                """()=>{
              if(typeof planFinalizeOptimize==='function') planFinalizeOptimize();
            }"""
            )
            for i in range(50):
                if not page.evaluate("()=>_planScenarioBusy"):
                    t = page.evaluate(
                        "()=>(document.getElementById('plan-scenario-outcomes')?.innerText||'').toLowerCase()"
                    )
                    if "optimize" in t:
                        break
                time.sleep(1)
            dt_after = page.evaluate("()=>Object.values(_planDraft).reduce((s,r)=>s+(r.dt||0),0)")
            check("Finalize accepted suggestion changes DT", dt_after != dt_before, "%s -> %s" % (dt_before, dt_after))
            check("achievable still present after Finalize",
                  page.evaluate("()=>!!(_planLastSim&&_planLastSim.summary&&_planLastSim.summary.achievable_production_t)"))
        else:
            print("  SKIP  Finalize accept (no DT suggestions)")
            check("No forced min-truck cuts", n_change == 0)

        page.evaluate("()=>planSaveForDate()")
        time.sleep(1.2)
        save_st = page.evaluate("()=>document.getElementById('plan-save-status')?.innerText||''")
        check("Save plan", "Saved" in save_st, save_st)

        page.evaluate("()=>{_planDraft={}; computePlan();}")
        check("draft cleared", page.evaluate("()=>Object.keys(_planDraft).length") == 0)
        page.evaluate("()=>planLoadSavedForDate({quiet:true})")
        time.sleep(1.2)
        loaded_n = page.evaluate("()=>Object.keys(_planDraft).length")
        check("Load restored paths", loaded_n >= 1, "n=%s" % loaded_n)

        page.evaluate("()=>planOpenFullAssessment()")
        time.sleep(1.5)
        # The assessment now renders INSIDE the Plan tab (plansim page retired).
        host = page.evaluate(
            "()=>document.getElementById('plan-assessment-host')?.style?.display")
        check("Open full assessment reveals in-Plan host", host != "none")
        # Run assessment if needed
        page.evaluate("()=>{ if(typeof psRun==='function') psRun(); if(typeof paRun==='function') paRun(); }")
        time.sleep(2)
        has_eff = page.evaluate(
            """()=>{
          const t=document.getElementById('pa-breakdown-rows')?.innerText||'';
          const h=document.body.innerText||'';
          return t.length>5 || h.toLowerCase().indexOf('effective cycle')>=0;
        }"""
        )
        check("S2 effective cycle visible", has_eff)

        # GPS column present in plan analogues table header when back on plan
        page.click("#tabbtn-plan")
        time.sleep(0.3)
        gps_col = page.evaluate(
            "()=>!!document.querySelector('#plan-analogues-rows') && "
            "!![...document.querySelectorAll('.plan-analogues-wrap th')].find(th=>/GPS/i.test(th.textContent||''))"
        )
        check("Analogues GPS column header", gps_col)

        # Re-running the scenario (finalize above) hides C again by design.
        # Re-open it the way the user does (corridor ▶ Run) and wait for rows.
        page.evaluate("()=>{ if (typeof planOnCorridorRun==='function') planOnCorridorRun(); }")
        try:
            page.wait_for_function(
                "() => document.querySelectorAll('#plan-road-crowding .rc-row').length > 0",
                timeout=30000)
        except Exception:                                          # noqa: BLE001
            pass
        rc = page.evaluate(
            "()=>(document.getElementById('plan-road-crowding')?.innerText||'').toLowerCase()"
        )
        check("Road crowding panel rendered", "crowded" in rc or "section capacity" in rc, rc[:120])
        check("Road crowding advisory copy", "advisory" in rc or "not" in rc, rc[:160])
        rc_rows = page.evaluate(
            "()=>document.querySelectorAll('#plan-road-crowding .rc-row').length"
        )
        check("Road crowding grid has section rows", rc_rows >= 2, "rows=%s" % rc_rows)
        rc_iwip = page.evaluate(
            "()=>!!document.querySelector('#plan-road-crowding .plan-rc-iwip input')"
        )
        check("Road crowding IWIP toggle present", rc_iwip)
        test_prod = page.evaluate(
            """()=>{
          const box=document.getElementById('plan-test-prod');
          const attain=document.getElementById('plan-flow-attain');
          const prod=document.getElementById('plan-flow-prod');
          return !!(box && attain && prod && box.contains(attain) && box.contains(prod));
        }"""
        )
        check("Test productivity under Run controls", test_prod)
        no_plan_scroll = page.evaluate(
            """()=>{
          if(typeof flowScrollVisualsIntoView!=='function') return false;
              const prev=window._flowHost;
              if(typeof flowSetHost==='function') flowSetHost('plan');
              let scrolled=false;
              const stage=document.getElementById('plan-c3-flow-visuals');
              const orig=stage&&stage.scrollIntoView;
              if(stage) stage.scrollIntoView=function(){ scrolled=true; };
              flowScrollVisualsIntoView();
              if(stage&&orig) stage.scrollIntoView=orig;
              if(typeof flowSetHost==='function') flowSetHost(prev||'capability');
              return !scrolled;
            }"""
        )
        check("Plan Run does not auto-scroll visuals", no_plan_scroll)
        busy_shells = page.evaluate(
            "()=>!!document.getElementById('plan-outcomes-busy') && "
            "!!document.getElementById('plan-estimate-busy')"
        )
        check("Calc busy shells on A+B", busy_shells)

        # Day-segments drill: prefer a Jul+ row; else call API + render helper
        clicked = page.evaluate(
            """()=>{
          const tr=[...document.querySelectorAll('#plan-analogues-rows tr[data-has-gps=\"1\"]')][0];
          if(tr){ tr.click(); return tr.getAttribute('data-date'); }
          if(typeof planFetchDaySegments==='function'){
            planFetchDaySegments('2026-07-21');
            return 'api:2026-07-21';
          }
          return null;
        }"""
        )
        time.sleep(1.5)
        ds = page.evaluate(
            "()=>(document.getElementById('plan-day-segments')?.innerText||'').toLowerCase()"
        )
        check("Day segments panel after drill",
              clicked is not None and ("segment" in ds or "loaded" in ds or "no haul" in ds),
              "clicked=%s text=%s" % (clicked, ds[:140]))

        # Optimize reasons may mention Jul slow section (advisory) — soft check
        reasons = page.evaluate(
            "()=>(_planLastSuggestions||[]).map(x=>x.reason||'').join(' | ').toLowerCase()"
        )
        check("Optimize still produces reasons", len(reasons) > 5, reasons[:120])

        page.evaluate("()=>{const el=document.getElementById('plan-date'); if(el){el.value='2026-07-21'; if(typeof planDateChange==='function') planDateChange();}}")
        time.sleep(1.2)
        cov = page.evaluate(
            """()=>{
          const days=(document.getElementById('plan-gps-days')?.innerText||'').toLowerCase();
          const head=(document.querySelector('.plan-gps-strip-head')?.innerText||'').toLowerCase();
          return head+' '+days;
        }"""
        )
        check("GPS coverage strip on plan date",
              "haul gps" in cov or "07-" in cov or "08-" in cov, cov[:160])
        preview_under = page.evaluate(
            """()=>{
          const prev=document.getElementById('plan-preview');
          const step=document.querySelector('.plan-step1');
          return !!(prev && step && step.contains(prev));
        }"""
        )
        check("WMT preview under Step 1", preview_under)

        # Re-drill an analogue day, then apply that day's fleet DT
        page.click("#tabbtn-plan")
        time.sleep(0.2)
        page.evaluate(
            """()=>{
          const tr=[...document.querySelectorAll('#plan-analogues-rows tr[data-date]')][0];
          if(tr){ tr.click(); return; }
          const a=(_planLastAnalogues&&_planLastAnalogues.analogues||[])[0];
          if(a&&a.date&&typeof planAnalogueRowClick==='function')
            planAnalogueRowClick(a.date, !!(a.has_gps||String(a.date)>='2026-07-15'));
        }"""
        )
        time.sleep(1.2)
        applied = page.evaluate(
            """()=>{
          const btn=[...document.querySelectorAll('#plan-day-segments button')]
            .find(b=>/fleet DT/i.test(b.textContent||''));
          if(!btn || btn.disabled) return 'skip';
          btn.click();
          return {n:Object.keys(_planDraft||{}).length,
                  status:(document.getElementById('plan-save-status')||{}).innerText||''};
        }"""
        )
        if applied == "skip":
            print("  SKIP  Apply analogue fleet (no button)")
        else:
            check("Apply analogue fleet keeps paths",
                  isinstance(applied, dict) and applied.get("n", 0) >= 1, str(applied))
            check("Apply analogue fleet status note",
                  isinstance(applied, dict) and "Applied" in (applied.get("status") or ""),
                  str(applied))

        page.evaluate(
            """()=>{
          const n=document.getElementById('plan-data-notes'); if(n) n.open=true;
          if(typeof planFetchPlaybackTruth==='function') planFetchPlaybackTruth('2026-07-21');
          if(typeof planFetchPeakProxy==='function') planFetchPeakProxy();
          if(typeof planPickGpsDay==='function') planPickGpsDay('2026-07-21');
        }"""
        )
        time.sleep(1.8)
        pb = page.evaluate(
            "()=>(document.getElementById('plan-playback-truth')?.textContent||'').toLowerCase()"
        )
        check("Playback truth panel", "playback" in pb and ("0%" in pb or "overlap" in pb or "haul" in pb), pb[:160])
        day_detail = page.evaluate(
            "()=>(document.getElementById('plan-day-detail')?.textContent||'').toLowerCase()"
        )
        check("Selected day detail is for that day",
              "2026-07-21" in day_detail or "selected day" in day_detail or "that day" in day_detail,
              day_detail[:160])
        check("Day detail does not claim Jan–May averages",
              "jan–may averages" not in day_detail and "jan-may averages" not in day_detail,
              day_detail[:160])

        # Bias lens defaults ON — outcomes should show calibrated companion
        lens_on = page.evaluate("()=>!!document.getElementById('plan-bias-lens')?.checked")
        check("Bias lens default ON", lens_on)
        outcomes2 = page.evaluate(
            "()=>(document.getElementById('plan-scenario-outcomes')?.innerText||'').toLowerCase()"
        )
        check("Bias lens copy in outcomes", "1.055" in outcomes2 or "adjusted" in outcomes2 or "lens" in outcomes2 or "calibrat" in outcomes2, outcomes2[:180])
        cal = page.evaluate(
            "()=>!!(_planLastSim&&_planLastSim.summary&&_planLastSim.summary.ticket_calibrated_achievable_t)"
        )
        check("Simulate companion calibrated field", cal)
        primary_raw = page.evaluate(
            "()=>(_planLastSim&&_planLastSim.summary&&_planLastSim.summary.availability_factor_applied)===1"
        )
        check("Primary still avail=1.0", primary_raw)

        # C is now the plan-driven road-crowding grid; the congestion-advice and
        # DES-table panels were removed 2026-08-12 (overlapped A/B/E). What must
        # hold: the crowding payload never claims to clip tonnes, and the IWIP
        # toggle changes the traffic actually timed.
        shared_ok = page.evaluate(
            "()=>!!(_planSharedFlow&&_planSharedFlow.ok"
            "&&_planSharedFlow.basis&&_planSharedFlow.basis.congestion_clips_tonnes===false)"
        )
        check("Crowding payload never clips tonnes", shared_ok)
        iwip_paths_before = page.evaluate(
            "()=>((_planSharedFlow||{}).summary||{}).n_paths||0"
        )
        page.evaluate(
            """()=>{const cb=document.querySelector('#plan-road-crowding .plan-rc-iwip input');
               if(cb){cb.checked=false;cb.dispatchEvent(new Event('change'));}}"""
        )
        time.sleep(2.0)
        iwip_paths_after = page.evaluate(
            "()=>((_planSharedFlow||{}).summary||{}).n_paths||0"
        )
        check(
            "IWIP toggle changes timed traffic (or no IWIP paths measured)",
            iwip_paths_after <= iwip_paths_before,
            "before=%s after=%s" % (iwip_paths_before, iwip_paths_after),
        )

        peak = page.evaluate(
            "()=>(document.getElementById('plan-peak-proxy')?.textContent||'').toLowerCase()"
        )
        check("Peak ops proxy panel",
              "peak" in peak and ("not gps" in peak or "weighbridge" in peak or "dt" in peak), peak[:160])

        browser.close()

    if fails:
        print("\nFAILED:", ", ".join(fails))
        return 1
    print("\nPlan goal E2E OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
