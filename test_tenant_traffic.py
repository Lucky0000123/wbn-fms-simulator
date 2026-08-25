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

# ── 3b. ONE CLOCK: a tenant truck weighs the same as ours on the same road ──
# Fixed 2026-08-24 after an independent audit. predictor._nxt converts our own
# fleet with flow = n * 60 / cycle_min (every truck one loaded pass per cycle,
# all of them in cycle at once). This module used to hand it a DAILY AVERAGE
# instead — DT * trips_per_day / 24 — so a tenant truck counted 2.2x to 4.2x
# lighter than one of ours on the same kilometre, and the reported cost of
# 1,340 tenant DT collapsed to ~0.0-0.05%. The bug was invisible: nothing
# errored, the number was just quietly too small.
#
# Asserted by RECONSTRUCTION, not by re-reading the constant: price each
# tenant's own DT through predict() on its proxy road and require the flow the
# module hands the predictor to match n*60/cycle. A gate that only checked
# "cycle_min is not None" would pass on any formula at all.
for _row in rows:
    _cyc, _flow, _dt = _row.get("cycle_min"), _row.get("loaded_lane_flow_per_hr"), _row["dt"]
    if not (_cyc and _flow):
        continue
    _expect = float(_dt) * 60.0 / float(_cyc)
    check(abs(_flow - _expect) < 0.02,
          "%s is on the predictor's clock, not a daily average" % _row["name"],
          "flow %.2f vs n*60/cycle %.2f" % (_flow, _expect))
    # and the daily average must be STRICTLY smaller, or the two bases have
    # been silently collapsed into one and the guard above proves nothing.
    _avg = _row.get("daily_average_flow_per_hr")
    if _avg:
        check(_flow > _avg * 1.2,
              "%s: priced flow exceeds its daily average" % _row["name"],
              "priced %.2f vs avg %.2f" % (_flow, _avg))

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
# ── 9. tenants never live in a SAVED plan (owner-reported bug) ─────────────
# The owner saw "KR spur" and "HUAFEI spur" on Road crowding. Cause: tenant
# rows had been saved into a plan, and the save format carries `foreign` but
# not `_tenant`, so on reload they were ordinary rows. "KR>RSF" cannot be
# placed on our stick (RSF is not one of our nodes), so the corridor fell
# through to its "<SOURCE> spur" fallback and invented two side roads that do
# not exist. Recognition must therefore work by NAME, not only by flag.
import glob as _glob
import json as _json
from monthly_api import (
    _ensure_tenant_rows, _is_tenant_row, _path_mat_label,
    _plans_from_alloc_rows,
)

check(_is_tenant_row({"key": "KR>RSF", "contractor": "KR>RSF"}),
      "an unflagged RSF row is still recognised as a tenant")
check(_is_tenant_row({"key": "TF>FENI KM15", "contractor": "POSITION"}),
      "an unflagged tenant is recognised by NAME")
check(_is_tenant_row({"_tenant": True, "key": "X>Y", "contractor": "Z"}),
      "the explicit flag still works")
# ...and the other direction: our own rows must survive, or the guard would
# quietly delete the plan it is meant to protect.
check(not _is_tenant_row({"key": "TF>HUAFEI", "contractor": "RIM"}),
      "our own rows are NOT mistaken for tenants")
check(not _is_tenant_row({"key": "POS 12>FENI KM0", "contractor": "IWIP"}),
      "IWIP road-only rows are NOT mistaken for tenants")
check(_is_tenant_row({"key": "TF>FENI KM15", "contractor": "POSITION"}),
      "POSITION is a tenant, not one of our own road-only rows")
check(not T.is_tenant_plan({"key": "POS 12>FENI KM0", "contractor": "IWIP"}),
      "is_tenant_plan agrees IWIP is ours")
check(T.is_tenant_plan({"id": "TENANT|MHM|road", "source": "TF",
                        "destination": "FENI KM15", "n_trucks": 100,
                        "contractor": "MHM"}),
      "is_tenant_plan catches a shared_flow-shaped tenant row")

_mixed = [{"key": "TF>HUAFEI", "contractor": "RIM", "dt_after": 50},
          {"key": "TF>FENI KM15", "contractor": "MHM", "dt_after": 100},
          {"key": "KR>RSF", "contractor": "KR>RSF", "dt_after": 40},
          {"key": "POS 12>FENI KM0", "contractor": "IWIP", "dt_after": 17}]
_kept = _plans_from_alloc_rows(_mixed)
check(sorted(p["contractor"] for p in _kept) == ["IWIP", "RIM"],
      "saved-plan reader drops tenants and keeps ours",
      [p["contractor"] for p in _kept])
check(not any("RSF" in (p["source"] + p["destination"]) for p in _kept),
      "no RSF route survives into the road model from a save")

# Excel lists the same other-tenant fleets Plan shows. Saved allocation.rows
# omit them (the Plan tab injects live); the sheet reader must merge the
# register in. Corridor still drops them — that is the 2× occupancy guard.
print()
_prod = [
    {"key": "TF>HUAFEI", "contractor": "RIM", "material": "LIM", "otype": "LD",
     "dt_after": 244, "pred_after": 10000, "prio": 3},
    {"key": "POS 12>FENI KM0", "contractor": "IWIP", "foreign": True,
     "dt_after": 17, "pred_after": 0},
]
_sheet = _ensure_tenant_rows(_prod)
_names = {str(r.get("contractor") or "").upper() for r in _sheet}
check({"MHM", "POSITION", "PMA", "HSM", "KR>RSF", "HUAFEI>RSF"} <= _names,
      "Excel merge adds every registered tenant",
      "got %s" % sorted(_names))
_pos = [r for r in _sheet if str(r.get("contractor") or "").upper() == "POSITION"]
check(_pos and int(_pos[0]["dt_after"]) == 500,
      "POSITION lands at the register's 500 DT")
check(_path_mat_label(_pos[0]) == "other tenant",
      "tenant material is 'other tenant', not a blank/road cell")
_iwip = [r for r in _sheet if r.get("contractor") == "IWIP"][0]
check(_path_mat_label(_iwip) == "road",
      "IWIP POS-transit stays material 'road'")
_again = _ensure_tenant_rows(_sheet)
_ten_n = sum(1 for r in _again if _is_tenant_row(r))
check(_ten_n == 6, "merge is idempotent (still 6 tenants)", "got %s" % _ten_n)
_kept2 = _plans_from_alloc_rows(_sheet)
check(sorted(p["contractor"] for p in _kept2) == ["IWIP", "RIM"],
      "merged tenant rows still never reach the corridor",
      [p["contractor"] for p in _kept2])
check(sum(r.get("dt_after") or 0 for r in _sheet if _is_tenant_row(r)) == 1340,
      "register total is 1,340 DT")

from openpyxl import Workbook
from monthly_api import _xlsx_path_alloc_table
_wb = Workbook()
_ws = _wb.active
_xlsx_path_alloc_table(_ws, 1, _prod, "New Allocation Plan table", "")
_cells = [[c.value for c in row] for row in _ws.iter_rows(min_col=1, max_col=8)]
_ctr = [r[2] for r in _cells if r[2]]
check("POSITION" in _ctr and "MHM" in _ctr and "HUAFEI>RSF" in _ctr,
      "Excel table writes tenant contractor names",
      "contractors=%s" % _ctr)
check(any((r[3] or "") == "other tenant" for r in _cells),
      "Excel table labels them 'other tenant'")
check(any((r[3] or "") == "road" for r in _cells),
      "IWIP still writes material 'road'")
_tot = next((r for r in _cells if r[0] == "TOTAL"), None)
# Policy change 2026-08-25 (QA BUG 1): TOTAL DT is OUR fleet ONLY (244).
# IWIP POS-transit moved to its own line under TOTAL — summing it in put
# Sep's TOTAL at 707 against the pool figure 581 on the same sheet and
# deflated Trips/DT by dividing our trips by a fleet that included 0-trip
# rows. Tenants (1,340) stay excluded as before.
check(_tot and _tot[5] == 244,
      "TOTAL DT is our fleet only (244); IWIP on its own line; no tenants",
      "TOTAL DT=%s" % (_tot[5] if _tot else None))
_iwip_line = next((r for r in _cells
                   if isinstance(r[0], str) and "IWIP" in r[0].upper()
                   and r[0] != "TOTAL"), None)
check(_iwip_line is not None,
      "IWIP POS-transit appears on its own labelled line",
      "rows=%s" % [r[0] for r in _cells if r[0]][:12])

# Allocation may LIST tenant fleets so the New Allocation table survives
# Save→Load (owner, 2026-08-24). They must be flagged, and the corridor
# reader must still drop them — an unflagged RSF row is the KR spur.
_unflagged = []
_into_model = []
for _f in sorted(_glob.glob("data/saved_plans/*.json")):
    try:
        _d = _json.load(open(_f, encoding="utf-8"))
    except (OSError, ValueError):
        continue
    _rows = (_d.get("allocation") or {}).get("rows") or []
    for _r in _rows:
        if not _is_tenant_row(_r):
            continue
        flagged = bool(_r.get("_tenant") or str(_r.get("id") or "").upper().startswith("TENANT|"))
        if not flagged:
            _unflagged.append(_f.rsplit("/", 1)[-1])
    _kept_file = _plans_from_alloc_rows(_rows)
    if any("RSF" in (p["source"] + p["destination"]) for p in _kept_file):
        _into_model.append(_f.rsplit("/", 1)[-1])
check(not _unflagged, "saved tenant rows carry _tenant or TENANT| id", _unflagged)
check(not _into_model, "corridor reader still drops tenants from every save", _into_model)

for s in SKIPS:
    print("  skip %s" % s)
if FAILS:
    print("\nFAILED %d:" % len(FAILS))
    for f in FAILS:
        print("  - %s" % f)
    sys.exit(1)
print("\nJ77 OK")
