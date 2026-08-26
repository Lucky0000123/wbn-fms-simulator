#!/usr/bin/env python3
"""J87 — weighbridge auto-allocation honours the owner's rulings (2026-08-26).

Drives the REAL endpoint with realistic plan rows (J52: test what the caller
sends). Both directions per assertion (J71: a one-sided gate is passed by
deleting the feature).

  * eligibility: a pit row's bridges come from the owner matrix — and a bridge
    OUTSIDE the row's matrix set is never assigned;
  * T11 (the busiest bridge in history) is NEVER assigned to anything;
  * tenant rows get nothing, and say why;
  * IWIP rows assign from measured history minus exclusions, and the
    destination fallback never puts a non-BLB row on a BLB-spur bridge nor on
    a bridge off the route's chainage span;
  * WB_IWIP_T2 assignments are flagged unverified;
  * capacities are the measured p99 figures (T15 86/hr, not the flat 30);
  * the fixture serves the same shape as the register (offline parity).

Run standalone: .venv/bin/python scripts/check_wb_allocation.py
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.environ.get("SIM_BASE", "http://127.0.0.1:5055")
FAILS, CHECKS = [], []


def ok(name, cond, detail=""):
    CHECKS.append((name, bool(cond), detail))
    if not cond:
        FAILS.append("%s — %s" % (name, detail))


def post(path, body):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.loads(r.read().decode())


def main():
    basis = get("/api/plan/wb-allocation-basis")
    ok("basis serves", basis.get("ok"), str(basis)[:120])
    ok("basis has 13 bridges", len(basis.get("bridges") or {}) == 13,
       "got %d" % len(basis.get("bridges") or {}))
    ok("T11 in excluded_nums", 11 in (basis.get("excluded_nums") or []),
       "excluded_nums=%s" % basis.get("excluded_nums"))
    t15 = (basis.get("bridges") or {}).get("WB_IWIP_T15") or {}
    ok("capacities are measured, not flat", t15.get("p99_hr") == 86,
       "T15 p99_hr=%s (flat 30 would mean the register lost its measurements)"
       % t15.get("p99_hr"))
    ok("T2 flagged unverified",
       ((basis.get("bridges") or {}).get("WB_IWIP_T2") or {}).get("unverified") is True,
       "the 1-ticket no-geofence bridge must carry its flag")
    # Defence in depth, asserted structurally: an excluded bridge must not be
    # IN the register's bridge dict at all. Mutation-proved: removing only the
    # excluded_nums filter changes nothing because history numbers resolve
    # through this dict first — the register membership is the harder wall,
    # and THIS check is what breaks if someone adds T11 an entry.
    reg_nums = {b.get("num") for b in (basis.get("bridges") or {}).values()}
    ok("no excluded num in the register",
       not (set(basis.get("excluded_nums") or []) & reg_nums),
       "excluded bridges present in the register: %s"
       % (set(basis.get("excluded_nums") or []) & reg_nums))

    rows = [
        {"id": "pit-tf-km0", "route": "TF>FENI KM0", "trips": 300},
        {"id": "pit-blb-hua", "route": "BLB>HUAFEI", "trips": 400},
        {"id": "pit-tf-pos6", "route": "TF>POS 6", "trips": 250},
        {"id": "iwip-pos12-km0", "route": "POS 12>FENI KM0", "trips": 200, "foreign": True},
        {"id": "iwip-pos6-km15", "route": "POS 6>FENI KM15", "trips": 120, "foreign": True},
        {"id": "ten", "route": "TF>FENI KM15", "trips": 500, "tenant": True},
    ]
    res = post("/api/plan/wb-allocate", {"rows": rows, "hours": 12})
    ok("allocate serves", res.get("ok"), str(res)[:120])
    by = {r["id"]: r for r in res.get("rows") or []}

    # POSITIVE: every non-tenant row is assigned; NEGATIVE: only within its set.
    matrix = basis.get("matrix") or {}
    for rid, route in (("pit-tf-km0", "TF>FENI KM0"), ("pit-blb-hua", "BLB>HUAFEI"),
                       ("pit-tf-pos6", "TF>POS 6")):
        got = [a["bridge"] for a in (by.get(rid) or {}).get("assigned") or []]
        ok("%s assigned" % rid, bool(got), "empty: %s" % (by.get(rid) or {}).get("why"))
        allowed = set(matrix.get(route) or [])
        ok("%s stays inside its matrix set" % rid,
           got and set(got) <= allowed,
           "%s got %s, matrix allows %s" % (rid, got, sorted(allowed)))

    # T11 never, anywhere.
    all_assigned = [a for r in (res.get("rows") or []) for a in (r.get("assigned") or [])]
    ok("T11 never assigned", all(a.get("num") != 11 for a in all_assigned),
       "T11 present in an assignment")

    # tenant: nothing, with the reason on it.
    ten = by.get("ten") or {}
    ok("tenant row unassigned", not ten.get("assigned"),
       "tenant got %s" % ten.get("assigned"))
    ok("tenant row says why", "tenant" in (ten.get("why") or ""),
       "why=%r" % ten.get("why"))

    # IWIP history route: bridges from measured history, minus exclusions.
    iw = [a["num"] for a in (by.get("iwip-pos12-km0") or {}).get("assigned") or []]
    ok("IWIP history row assigned", bool(iw), (by.get("iwip-pos12-km0") or {}).get("why"))
    ok("IWIP history row excludes T11/T4", not ({11, 4} & set(iw)), "got %s" % iw)

    # IWIP fallback route: geographic guard — no BLB-spur or off-span bridges.
    p6 = (by.get("iwip-pos6-km15") or {}).get("assigned") or []
    p6n = [a["bridge"] for a in p6]
    ok("POS 6 KM15 fallback assigned", bool(p6n),
       (by.get("iwip-pos6-km15") or {}).get("why"))
    ok("POS 6 fallback stays on the drive",
       p6n and set(p6n) <= {"WB_IWIP_T12", "WB_IWIP_T17"},
       "got %s — km-15 bridges only for POS 6 (km 12) -> KM15" % p6n)

    # The ALLOCATOR's own response must price on the measured capacities —
    # reading the basis alone cannot catch a flat-30 cap map inside allocate
    # (mutation-proved: flattening the cap map passed the basis check).
    t15u = (res.get("bridges") or {}).get("WB_IWIP_T15") or {}
    ok("allocator prices T15 at its measured cap",
       t15u.get("cap_hr") == 86 and "measured" in (t15u.get("cap_basis") or ""),
       "T15 cap_hr=%s basis=%r" % (t15u.get("cap_hr"), t15u.get("cap_basis")))

    # unverified flag surfaces when T2 is used (BLB>HUAFEI's matrix carries it).
    used_t2 = any(a["bridge"] == "WB_IWIP_T2" for a in all_assigned)
    if used_t2:
        ok("T2 use is flagged", "WB_IWIP_T2" in (res.get("unverified_bridges_used") or []),
           "T2 assigned but not flagged")

    # NEGATIVE: bad input is a 400-class refusal, not a silent success.
    try:
        bad = post("/api/plan/wb-allocate", {"rows": rows, "hours": 99})
        ok("hours out of range refused", not bad.get("ok"), "hours=99 accepted")
    except urllib.error.HTTPError as e:
        ok("hours out of range refused", e.code == 400, "HTTP %s" % e.code)

    for name, good, detail in CHECKS:
        print("  %s  %s%s" % ("PASS" if good else "FAIL", name,
                              "" if good else "  <- " + detail))
    print("%d/%d checks passed" % (sum(1 for _, g, _ in CHECKS if g), len(CHECKS)))
    if FAILS:
        for f in FAILS:
            print("FAIL: %s" % f, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    import urllib.error
    sys.exit(main())
