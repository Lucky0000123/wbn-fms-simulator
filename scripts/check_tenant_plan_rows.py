"""J78 — the other tenants show up in the plan, and are charged exactly once.

Owner (2026-08-24): "I didn't see all these new DT in my plan — how can we add
it in my plans, same as we are showing the IWIP trucks."

So the register (congestion/tenants.py, 1,340 DT) now draws ROAD-ONLY rows in
the Plan tab the same way the POS-transit IWIP trucks do. The rows are the easy
half. The half that can break silently, and what this gate exists for, is that
a tenant fleet has TWO representations and only ONE of them may reach pricing:

  * the ROW is what the owner sees — DT, route, its own trips/DT;
  * the FLOW (tenants=1 on the curve) is what the model prices, at the tenant's
    own tempo rather than ours.

If the rows also entered the segment background, the same fleet would be
charged twice, and the second charge would be at OUR tempo — the exact unit
error congestion/tenants.py was written to avoid (40 KR>RSF trucks turning 5
trips/day push three times the flow of 40 of ours at ~1.2). Nothing on screen
would look wrong; trips/DT would just quietly be too low.

Both directions are asserted, per the J71 lesson: the rows must be PRESENT and
carry the register's own numbers, AND they must be ABSENT from the segment
background and from the engine payload. A gate that only checked presence is
passed by hardcoding six rows; one that only checked absence is passed by
deleting the feature.

Needs playwright and a live server; skipped by the harness where either is
missing, like J56.
"""
import os
import sys

BASE = os.environ.get("SIM_BASE", "http://127.0.0.1:5055")
EXPECTED = {"MHM": 100, "POSITION": 500, "PMA": 150, "HSM": 50,
            "KR>RSF": 40, "HUAFEI>RSF": 500}
TOTAL_DT = 1340

fails = []


def chk(name, cond, extra=""):
    print(("  ok   " if cond else "  FAIL ") + name
          + (("  -- " + str(extra)) if extra and not cond else ""))
    if not cond:
        fails.append(name)


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1500, "height": 950})
        errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.goto(BASE + "/simulator", wait_until="domcontentloaded")
        pg.wait_for_function("typeof planRulesTenants==='function'", timeout=60000)

        info = pg.evaluate(
            "async()=>{const j=await planTenantsLoad();"
            "return j&&{n:(j.tenants||[]).length,dt:j.total_dt};}")
        chk("the register reaches the browser", bool(info) and info["n"] == len(EXPECTED), info)
        chk("register totals %d DT" % TOTAL_DT, bool(info) and info["dt"] == TOTAL_DT, info)
        chk("planTenantsOn() is true once loaded", pg.evaluate("planTenantsOn()"))

        pg.evaluate("async()=>{await planRulesTenants();}")
        rows = pg.evaluate(
            "()=>Object.keys(_planDraft||{}).filter(k=>_planDraft[k]._tenant)"
            ".map(k=>({id:k,...(_planDraft[k])}))")
        chk("every tenant draws a row", len(rows) == len(EXPECTED), len(rows))
        chk("every tenant row is foreign", all(r.get("foreign") for r in rows))
        chk("tenant DT sums to the register", sum(r.get("dt") or 0 for r in rows) == TOTAL_DT,
            sum(r.get("dt") or 0 for r in rows))
        by = {r.get("contractor"): r.get("dt") for r in rows}
        chk("each fleet carries its own DT", by == EXPECTED, by)
        kr = [r for r in rows if r.get("contractor") == "KR>RSF"]
        chk("the owner-stated 5 trips/DT survives to the row",
            bool(kr) and abs((kr[0].get("_tenantRate") or 0) - 5.0) < 1e-6,
            kr[0].get("_tenantRate") if kr else None)

        # Rebuilt, not accumulated: a second pass must not double the register.
        pg.evaluate("async()=>{await planRulesTenants();await planRulesTenants();}")
        again = pg.evaluate(
            "()=>Object.keys(_planDraft||{}).filter(k=>_planDraft[k]._tenant).length")
        chk("re-running rebuilds rather than accumulates", again == len(EXPECTED), again)

        # ── the double-count guards ──────────────────────────────────────
        pg.evaluate("async()=>{await planRulesPrepare();}")
        bg = pg.evaluate("()=>planSegOthersFor('__no_such_route__')||{}")
        chk("tenant routes stay OUT of the segment background",
            not any("RSF" in k for k in bg) and "TENANT" not in str(bg), list(bg.keys()))
        ps = pg.evaluate("()=>planDraftToPsPlans().map(p=>p.route)")
        chk("tenant routes stay OUT of the engine payload",
            not any("RSF" in r for r in ps), ps)

        # ...but the flow that replaces them IS asked for.
        urls = []
        pg.on("request", lambda r: urls.append(r.url) if "congestion_curve" in r.url else None)
        pg.evaluate("()=>{try{planHybridCurveFor('KR>POS 10',0,0,{proportional:true});}"
                    "catch(e){}}")
        pg.wait_for_timeout(3500)
        chk("the plan's own curve asks for tenant flow",
            any("tenants=1" in u for u in urls), urls[:2])

        # Naming: the tenants are not IWIP and must not be summed into it.
        pg.evaluate("()=>{try{planNavSync();}catch(e){}}")
        txt = pg.evaluate("()=>{const s=document.getElementById('plan-nav-summary');"
                          "return s?s.textContent:'';}")
        chk("the counter names the tenants separately from IWIP",
            "other tenants" in txt, txt)
        chk("tenant DT is not counted as our allocatable DT",
            "1340 DT" not in txt.replace(",", ""), txt)

        real = [e for e in errs if "favicon" not in e.lower()]
        chk("console clean", not real, real[:3])
        b.close()


if __name__ == "__main__":
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("SKIP: playwright not installed")
        sys.exit(0)
    main()
    print(("\nFAILED: " + ", ".join(fails)) if fails else "\nJ78 OK")
    sys.exit(1 if fails else 0)
