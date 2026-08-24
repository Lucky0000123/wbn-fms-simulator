"""J77 — other tenants take road and never give tonnage.

The register (congestion/tenants.py) is the owner's, not the model's, so what
is testable is the WIRING: that tenant traffic can only slow us down, that it
reaches the segments those hauls actually occupy, that it is off unless asked
for, and that the Excel column is a degradation of the sheet's own number
rather than a second opinion about it.

Runs without the DB. Needs data/congestion_params.json for the calibrated
routes; skips those cases with a message rather than passing vacuously.
"""
from __future__ import annotations

import sys

from congestion.config import route_params
from congestion.predictor import predict
from congestion.segments import segment_trucks
from congestion import tenants as T

FAILS = []
SKIPS = []


def check(cond, label, detail=""):
    if cond:
        print("  ok   %s" % label)
    else:
        FAILS.append(label)
        print("  FAIL %s %s" % (label, detail))


def calibrated(route):
    return bool(route_params(route).get("calibrated"))


# ── 1. the register resolves: every fleet gets a rate and a road ────────────
rows = T.tenant_rows()
print("register:")
for r in rows:
    print("  %-11s %4s DT  %-13s %-6s trips/DT  %-8s /hr  %s"
          % (r["name"], r["dt"], r["route"], r["trips_per_dt"],
             r["loaded_lane_flow_per_hr"], r["rate_basis"]))

check(len(rows) == len(T.TENANTS), "every registered tenant is reported")
# A tenant that silently resolves to no rate contributes no road load, which
# is the exact failure this module exists to prevent: a 500-DT fleet would
# vanish and the answer would look like the clear-road one.
unresolved = [r["name"] for r in rows if not r.get("loaded_lane_flow_per_hr")]
check(not unresolved, "every tenant resolves to a road flow",
      "unresolved: %s" % unresolved)

owner = [r for r in rows if r["name"] == "KR>RSF"]
check(owner and owner[0]["trips_per_dt"] == 5.0,
      "an owner-stated rate is used verbatim, not re-modelled")

# ── 2. direction: the empty-carriageway leg takes no loaded-lane capacity ───
# HUAFEI->RSF climbs empty (no loaded-lane cost) and returns coastward on the
# loaded road. It must appear on S3+S4 (26 km -> 0) and NOT on S1/S2.
h = [r for r in rows if r["name"] == "HUAFEI>RSF"][0]
check(set(h["segments"]) == {"S3", "S4"},
      "HUAFEI>RSF occupies only the segments below RSF (KM26)",
      "got %s" % h["segments"])
kr = [r for r in rows if r["name"] == "KR>RSF"][0]
check(set(kr["segments"]) == {"S2", "S3"},
      "KR>RSF occupies KR(39)->RSF(26)", "got %s" % kr["segments"])
tf = [r for r in rows if r["name"] == "MHM"][0]
check(set(tf["segments"]) == {"S1", "S2", "S3"},
      "TF>FENI KM15 tenants run TF(67.8)->KM15(15), not below it",
      "got %s" % tf["segments"])
# S4 carries the HUAFEI return leg only — the TF tenants stop at KM15.
flow = T.tenant_segment_flow_hr()
check(abs(flow["S4"] - h["loaded_lane_flow_per_hr"]) < 0.01,
      "S4 carries the RSF return leg and nothing that stops at KM15",
      "S4=%s vs %s" % (flow["S4"], h["loaded_lane_flow_per_hr"]))

# ── 3. flow, not trucks: a faster tenant loads the road more per truck ──────
# 40 KR>RSF trucks at 5 trips/day must out-flow 40 TF trucks at ~2.2, or the
# unit is wrong and the model is understating exactly the fleet in question.
per_dt_kr = kr["loaded_lane_flow_per_hr"] / kr["dt"]
per_dt_tf = tf["loaded_lane_flow_per_hr"] / tf["dt"]
check(per_dt_kr > per_dt_tf * 1.5,
      "a tenant is priced at ITS OWN tempo, not ours",
      "%.4f vs %.4f per DT/hr" % (per_dt_kr, per_dt_tf))

# ── 4. tenants can only ever cost us trips/DT, never gain ──────────────────
plan = {"TF>HUAFEI": 500, "TF>POS 12": 300, "TF>FENI KM15": 200,
        "KR>POS 12": 150}
seg = segment_trucks(plan)
moved = 0
for route, n in plan.items():
    if not calibrated(route):
        SKIPS.append("no calibration for %s" % route)
        continue
    a = predict(route, n, None, mode="road", segment_fleet=seg)
    b = predict(route, n, None, mode="road", segment_fleet=seg,
                tenant_flow_hr=True)
    ra, rb = a["trips_per_DT_per_day"], b["trips_per_DT_per_day"]
    check(rb <= ra + 1e-9, "%s: tenants never raise trips/DT" % route,
          "clear %.3f -> tenants %.3f" % (ra, rb))
    check(b["road_vc"] >= a["road_vc"] - 1e-9,
          "%s: tenants never lower road v/c" % route,
          "%.3f -> %.3f" % (a["road_vc"], b["road_vc"]))
    check(b["tenant_traffic"] is True and a["tenant_traffic"] is False,
          "%s: the answer states which question it answered" % route)
    if rb < ra - 1e-9:
        moved += 1
check(moved > 0, "tenant traffic actually moves at least one planned route")

# ── 5. default OFF: no existing caller's number moves ──────────────────────
if calibrated("TF>HUAFEI"):
    base = predict("TF>HUAFEI", 500, None, mode="road", segment_fleet=seg)
    check(base["tenant_traffic"] is False and base["tenant_flow_hr"] is None,
          "tenant traffic is off unless asked for")

# ── 6. an off-mainline route is BLANK, not silently 'unaffected' ──────────
# BLB is a spur: the tenants are not on it. Reporting its clear-road rate under
# a "with other tenants" heading would read as "they cost this route nothing".
if calibrated("BLB>FENI KM0"):
    spur = predict("BLB>FENI KM0", 180, None, mode="road",
                   segment_fleet=seg, tenant_flow_hr=True)
    check(spur["tenant_traffic"] is False,
          "an off-mainline route does not claim to be tenant-priced")
    check(any("not priced on the shared mainline" in w
              for w in spur.get("warnings") or []),
          "and it says why")

# ── 7. the Excel column degrades the sheet's OWN number ───────────────────
# Shipped wrong twice on the way in: it read HIGHER than the clear-road column
# (two vintages, not one cause), and duplicate (path, contractor) rows
# overwrote each other so a P2 row printed a P3 row's rate as a GAIN.
from monthly_api import _tenant_trips_per_dt, _ten_key      # noqa: E402

sheet_rows = [
    {"key": "TF>HUAFEI", "contractor": "RIM", "dt_after": 60,
     "pred_after": 6439, "trips": 129},
    {"key": "TF>HUAFEI", "contractor": "RIM", "dt_after": 9,
     "pred_after": 966, "trips": 19},
    {"key": "TF>HUAFEI", "contractor": "SMA", "dt_after": 217,
     "pred_after": 23307, "trips": 512},
    {"key": "BLB>FENI KM0", "contractor": "RIM", "dt_after": 19,
     "pred_after": 4350, "trips": 87},
]
ten = _tenant_trips_per_dt(sheet_rows)
if not ten:
    SKIPS.append("no calibration: Excel column not exercised")
else:
    from monthly_api import _path_rates
    for row in sheet_rows:
        shown = _path_rates(row).get("trips_per_dt_after")
        got = ten.get(_ten_key(row))
        if got is None:
            continue
        check(got <= shown + 1e-9,
              "%s/%s: column <= the sheet's own Trips/DT"
              % (row["key"], row["contractor"]),
              "sheet %.2f -> column %.2f" % (shown, got))
    # Two rows, one road, different rates: each must keep its own.
    r0, r1 = sheet_rows[0], sheet_rows[1]
    s0 = _path_rates(r0).get("trips_per_dt_after")
    s1 = _path_rates(r1).get("trips_per_dt_after")
    if s0 != s1 and ten.get(_ten_key(r0)) and ten.get(_ten_key(r1)):
        check(ten[_ten_key(r0)] != ten[_ten_key(r1)],
              "duplicate (path, contractor) rows keep their own rates",
              "both %.2f" % ten[_ten_key(r0)])
    check(_ten_key(sheet_rows[3]) not in ten,
          "the BLB spur row gets no tenant value at all")

# ── 8. tenants add no tonnage, structurally ───────────────────────────────
# The register has no tonnage field and no contractor/pool field. If one is
# ever added, this fails and whoever added it has to say where it is credited.
banned = {"wmt", "tonnes", "tonnage", "target", "payload_t", "pool"}
for t in T.TENANTS:
    check(not (banned & set(t)), "%s carries no tonnage field" % t["name"],
          "has %s" % sorted(banned & set(t)))

print()
for s in SKIPS:
    print("  skip %s" % s)
if FAILS:
    print("\nFAILED %d:" % len(FAILS))
    for f in FAILS:
        print("  - %s" % f)
    sys.exit(1)
print("\nJ77 OK")
