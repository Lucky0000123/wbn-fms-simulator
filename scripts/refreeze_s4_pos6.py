#!/usr/bin/env python
"""Re-freeze the four S4 (day-04) saves under the POS 6 split (owner, 2026-08-25).

Faithful copy of the e2e QA agent's PROVEN flow (/tmp/qa_e2e_stage1.py):
real buttons, real waits, one date after another. The split engine now reads
splitDest from planning_rules (POS 6), so the re-frozen allocations carry
TF>POS 6 split rows. Backups at /tmp/pos6_backups/.
"""
from __future__ import annotations

import json
import sys

BASE = "http://127.0.0.1:5055"
DATES = ["2026-09-04", "2026-10-04", "2026-11-04", "2026-12-04"]


def one(pg, date):
    pg.goto(BASE + "/simulator", wait_until="domcontentloaded")
    pg.wait_for_function(
        "()=>typeof _D!=='undefined'&&!!_D&&typeof _pathResp!=='undefined'&&!!_pathResp&&Object.keys(_pathResp||{}).length>5",
        timeout=120000)
    pg.click("#tabbtn-plan")
    pg.wait_for_selector("#plan-date", state="attached", timeout=15000)
    pg.evaluate("()=>{const el=document.getElementById('plan-date');el.value='%s';"
                "if(typeof planDateChange==='function')planDateChange();}" % date)
    pg.wait_for_function("()=>!document.getElementById('plan-load-btn').disabled", timeout=30000)
    pg.click("#plan-load-btn")
    pg.wait_for_function(
        "()=>(document.getElementById('plan-save-status')?.innerText||'').includes('Loaded plan for %s')" % date,
        timeout=60000)

    # Unlock (frozen saves), then Check capacity.
    if pg.evaluate("()=>[...document.querySelectorAll('.plan-unlock')].some(el=>!el.hidden)"):
        pg.evaluate("()=>[...document.querySelectorAll('.plan-unlock')].find(el=>!el.hidden).click()")
    pg.wait_for_function(
        "()=>{const b=document.getElementById('plan-run-scenario');return b&&!b.hidden&&!b.disabled;}",
        timeout=15000)
    pg.click("#plan-run-scenario")
    pg.wait_for_function("()=>typeof _planScenarioBusy!=='undefined'&&_planScenarioBusy===true", timeout=10000)
    pg.wait_for_function("()=>_planScenarioBusy===false", timeout=180000)
    pg.wait_for_function("()=>!!(_planLastSim&&_planLastSim.summary)", timeout=60000)

    # Allocate DT. POLL, not compound waits: the one-shot waits timed out on
    # every date (2026-08-25) while a 10 s poll of the same conditions saw the
    # allocation complete in ~15 s — wait_for_function can starve while the
    # page re-renders; the poll cannot.
    import time as _t
    pg.wait_for_function("()=>{const b=document.getElementById('plan-alloc-priority-btn');return b&&!b.disabled;}", timeout=30000)
    pg.click("#plan-alloc-priority-btn")
    _done = False
    _t0 = _t.time()
    while _t.time() - _t0 < 280:
        st = pg.evaluate(
            "()=>{const o=document.getElementById('plan-alloc-frontload');"
            "const b=document.getElementById('plan-alloc-priority-btn');"
            "let calc=null;try{const s=planDraftSnapshot();calc=s.allocation&&s.allocation.calculation_status;}catch(e){}"
            "return {ov:o?!o.hidden:null,busy:b?b.getAttribute('aria-busy'):null,"
            "fr:typeof planAllocFrozen==='function'&&planAllocFrozen(),calc};}")
        if (not st["ov"]) and st["busy"] != 'true' and st["fr"] and st["calc"] == 'complete':
            _done = True
            break
        _t.sleep(10)
    if not _done:
        raise RuntimeError("allocation did not complete in 280s")

    # Inspect the split before saving.
    split = pg.evaluate("""()=>{
      const s=planDraftSnapshot();
      const rows=(s.allocation&&s.allocation.rows)||[];
      return {pos6:rows.filter(r=>/POS 6$/.test(String(r.key||''))).map(r=>({k:r.key,c:r.contractor,dt:r.dt_after})),
              pos12ld:rows.filter(r=>/POS 12$/.test(String(r.key||''))&&(r.otype==='LD'||/LD/.test(String(r.material||'')+String(r.otype||'')))).map(r=>({k:r.key,c:r.contractor,dt:r.dt_after})),
              total:rows.reduce((a,r)=>a+(r.dt_after||0),0)};}""")

    # Save.
    pg.wait_for_function("()=>!document.getElementById('plan-save-btn').disabled", timeout=15000)
    pg.click("#plan-save-btn")
    pg.wait_for_function(
        "()=>(document.getElementById('plan-save-status')?.innerText||'').includes('Saved for %s')" % date,
        timeout=30000)
    return split


def main():
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1700, "height": 1100})
        pg.on("dialog", lambda d: d.accept())
        errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        for date in DATES:
            print("== %s" % date, flush=True)
            try:
                r = one(pg, date)
                out[date] = r
                print("   POS 6 split rows:", r["pos6"])
                print("   POS 12 LD rows remaining:", r["pos12ld"])
                print("   fleet total:", round(r["total"]))
            except Exception as exc:  # noqa: BLE001
                out[date] = {"error": str(exc)[:300]}
                print("   FAILED:", str(exc)[:300])
        b.close()
    json.dump(out, open("/tmp/pos6_refreeze.json", "w"), indent=1, default=str)
    print("console errors:", [e for e in errs if "tile" not in e][:5])
    bad = [d for d in out if out[d].get("error")]
    print("FAILED:" if bad else "ALL REFROZEN:", bad or DATES)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
