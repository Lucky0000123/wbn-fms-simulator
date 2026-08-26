#!/usr/bin/env python3
"""Weighbridge base-point discovery + owner-matrix reconciliation (2026-08-25).

The owner supplied an eligibility matrix (data/weighbridge_matrix_owner_*.tsv,
gitignored: 13 bridges x 18 pit->plant pairs) and asked for automatic bridge
allocation: derive each bridge's BASE POINTS from the WHOLE weighbridge
history (which pits/plants it actually weighed), treat the matrix as the NEW
eligibility on top, then allocate bridges to plan rows.

This script is the ANALYSIS HALF: read-only, prints the measured record and
the reconciliation. No allocation is built until the findings are agreed
(measure, don't assume).

Canonicalisation: prediction_pipeline.canonical_area — the ONE normaliser.
"""
import io
import json
import os
import re
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))   # load_fms_env lives here
os.chdir(ROOT)

from load_fms_env import load_fms_env          # noqa: E402
load_fms_env()

from simulator_api import _conn, _db_ready      # noqa: E402
from prediction_pipeline import canonical_area  # noqa: E402

MATRIX_TSV = sorted(
    f for f in os.listdir(os.path.join(ROOT, "data"))
    if f.startswith("weighbridge_matrix_") and f.endswith(".tsv"))[-1]


def wb_num(raw):
    """Ticket WB_ID / matrix column -> the bridge NUMBER, the join key.

    Ticket WB_IDs and the matrix name the same bridges differently
    (simulator_api's digit-matching scheme): the trailing digits are the
    identity. WB_IWIP_T19 -> 19, 'T7' -> 7, '08' -> 8.
    """
    digits = re.findall(r"\d+", str(raw or "").strip().upper())
    return int(digits[-1]) if digits else None


def load_matrix():
    rows = [ln.split("\t") for ln in io.open(
        os.path.join(ROOT, "data", MATRIX_TSV), encoding="utf-8").read().splitlines()]
    hdr = rows[0]
    bridges = hdr[2:]
    elig = {}                      # (pit, plant) -> set of bridge numbers
    names = {}                     # bridge number -> matrix column name
    for b in bridges:
        names[wb_num(b)] = b
    for r in rows[1:]:
        if len(r) < 2:
            continue
        r = r + [""] * (len(hdr) - len(r))
        pit = canonical_area(r[0]) or r[0].strip().upper()
        plant = canonical_area(r[1]) or r[1].strip().upper()
        elig[(pit, plant)] = {wb_num(bridges[i]) for i, v in enumerate(r[2:])
                              if v.strip() == "1"}
    return elig, names


def main():
    if not _db_ready():
        print("DB not reachable — this analysis needs the full ticket history.")
        return 1

    elig, names = load_matrix()
    conn = _conn("WBN_DATABASE")
    cur = conn.cursor()

    # ---- 1. the WHOLE weighbridge history, by bridge x pit x plant ----
    cur.execute(
        "SELECT WB_ID, ORIGIN_AREA, DESTINATION_AREA, COUNT(*) n, SUM(WMT) t, "
        "MIN(CONVERT(date,[DATE])) f, MAX(CONVERT(date,[DATE])) l "
        "FROM HAULAGE_IWIP_CLEAN "
        "WHERE WB_ID<>'' AND WB_ID IS NOT NULL "
        "GROUP BY WB_ID, ORIGIN_AREA, DESTINATION_AREA")
    hist = defaultdict(lambda: defaultdict(lambda: [0, 0.0, None, None]))
    raw_ids = defaultdict(int)
    for wb, o, d, n, t, f, l in cur.fetchall():
        num = wb_num(wb)
        if num is None:
            continue
        raw_ids[str(wb).strip()] += n
        po = canonical_area(o) or str(o or "").strip().upper()
        pd = canonical_area(d) or str(d or "").strip().upper()
        cell = hist[num][(po, pd)]
        cell[0] += n
        cell[1] += float(t or 0)
        cell[2] = min(cell[2] or f, f)
        cell[3] = max(cell[3] or l, l)

    # ---- 2. bridge peak-hour throughput (allocation capacity basis) ----
    # HOUR is a first-class column on this table (schema checked 2026-08-25);
    # there is no TIME_LOADED here — that is HAULAGE_CLEAN's dispatch schema.
    cur.execute(
        "SELECT WB_ID, CONVERT(date,[DATE]) d, [HOUR] h, COUNT(*) "
        "FROM HAULAGE_IWIP_CLEAN WHERE WB_ID<>'' AND WB_ID IS NOT NULL "
        "GROUP BY WB_ID, CONVERT(date,[DATE]), [HOUR]")
    hourly = defaultdict(list)
    for wb, d, h, n in cur.fetchall():
        num = wb_num(wb)
        if num is not None:
            hourly[num].append(n)
    conn.close()

    def p99(v):
        if not v:
            return None
        v = sorted(v)
        return v[min(len(v) - 1, int(0.99 * len(v)))]

    # ---- 3. print the base points ----
    print("=" * 100)
    print("BRIDGE BASE POINTS — whole ticket history, canonicalised")
    print("=" * 100)
    all_nums = sorted(set(hist) | set(names))
    for num in all_nums:
        flows = sorted(hist.get(num, {}).items(), key=lambda kv: -kv[1][0])
        tot = sum(c[0] for _, c in flows)
        mat = names.get(num, "(NOT IN MATRIX)")
        cap = p99(hourly.get(num))
        first = min((c[2] for _, c in flows if c[2]), default=None)
        last = max((c[3] for _, c in flows if c[3]), default=None)
        print("\nWB %-3s %-14s  tickets %-8d  p99 %s/hr   %s .. %s"
              % (num, mat, tot, cap, first, last))
        for (o, d), (n, t, f, l) in flows[:8]:
            in_m = "matrix:YES" if num in elig.get((o, d), set()) else "matrix:no "
            print("    %-8s -> %-12s %7d tk %12.0f t  %s  last %s" % (o, d, n, t, in_m, l))
        if len(flows) > 8:
            print("    ... +%d more flows" % (len(flows) - 8))

    # ---- 4. reconciliation both directions ----
    print("\n" + "=" * 100)
    print("RECONCILIATION — matrix vs history (canonical pit prefix TF/KR/BLB, plants as matrix rows)")
    print("=" * 100)
    hist_pairs = defaultdict(set)         # (pit, plant) -> bridges seen
    for num, flows in hist.items():
        for (o, d), (n, _t, _f, l) in flows.items():
            if n >= 20:                    # noise floor: ignore <20 lifetime tickets
                hist_pairs[(o, d)].add(num)

    for (pit, plant), mset in sorted(elig.items()):
        hset = hist_pairs.get((pit, plant), set())
        new = sorted(mset - hset)
        gone = sorted(hset - mset)
        both = sorted(mset & hset)
        print("%-6s -> %-12s  agree:%-28s  matrix-only(NEW):%-16s  history-only(now forbidden):%s"
              % (pit, plant, both or "-", new or "-", gone or "-"))

    print("\nhistory pairs the matrix does not list at all (>=20 tickets):")
    for (o, d), bs in sorted(hist_pairs.items()):
        if (o, d) not in elig:
            print("   %-10s -> %-14s bridges %s" % (o, d, sorted(bs)))

    print("\nraw WB_ID formats in tickets (top 20):")
    for wb, n in sorted(raw_ids.items(), key=lambda kv: -kv[1])[:20]:
        print("   %-20s %8d" % (wb, n))

    if "--register" in sys.argv:
        write_register(elig, names, hist, hourly, p99)
    return 0


# ── --register: regenerate data/wb_register.json + the committed fixture ─────
# One generator, run against the live DB, so the register cannot drift from
# the analysis that justified it. Positions come from FMS_GEOFENCES snapped to
# the committed road survey (km only is persisted — coordinates never reach a
# committed file). history_pairs are recomputed under the CURRENT
# canonical_area, so the FENI KM15 line mapping (2026-08-26) flows through
# automatically instead of being hand-derived.

# Matrix bridge names that share a ticket number: geofence name -> matrix name.
_GEOFENCE_TO_MATRIX = {"WB_IWIP_T7A": "WB_IWIP_T7"}
# The day-count convention scenario routes need history under PLAN keys; keep
# every canonical pair with at least this many lifetime tickets.
_HIST_MIN_TICKETS = 20


def _bridge_positions():
    """{matrix_name: (road, km, off_m)} from FMS_GEOFENCES x the road survey."""
    import csv
    import math
    survey = []
    with open(os.path.join(ROOT, "data", "haul_road_chainage_public.csv")) as f:
        for r in csv.DictReader(f):
            survey.append((r["road"], float(r["km"]), float(r["lat"]), float(r["lng"])))
    conn = _conn("FMS_DB")
    cur = conn.cursor()
    cur.execute("SELECT NAME, CENTER_LAT, CENTER_LNG FROM FMS_GEOFENCES "
                "WHERE UPPER(NAME) LIKE 'WB%'")
    out = {}
    for name, lat, lng in cur.fetchall():
        if lat is None or lng is None:
            continue
        best = None
        for road, km, slat, slng in survey:
            d = math.hypot((lat - slat) * 111320,
                           (lng - slng) * 111320 * math.cos(math.radians(lat)))
            if best is None or d < best[2]:
                best = (road, km, d)
        out[_GEOFENCE_TO_MATRIX.get(str(name).strip(), str(name).strip())] = \
            (best[0], round(best[1], 1), round(best[2]))
    conn.close()
    return out


def write_register(elig, names, hist, hourly, p99):
    import datetime
    pos = _bridge_positions()
    excluded, in_matrix_nums = [], set()
    for nset in elig.values():
        in_matrix_nums |= nset
    for num in sorted(set(hist)):
        if num not in in_matrix_nums:
            excluded.append(num)

    # Build from the MATRIX COLUMN names, not the num->name dict: that dict
    # collapses the shared ticket number 7 to one name, which silently dropped
    # WB_RIM_T7 from the register on the first live regeneration (12 bridges,
    # and gate J87's "13 bridges" check is what would have caught it).
    hdr = io.open(os.path.join(ROOT, "data", MATRIX_TSV), encoding="utf-8") \
        .read().splitlines()[0].split("\t")[2:]
    bridges = {}
    for mat_name in hdr:
        num = wb_num(mat_name)
        flows = hist.get(num, {})
        tot = sum(c[0] for c in flows.values()) or None
        last = max((c[3] for c in flows.values() if c[3]), default=None)
        road_km = pos.get(mat_name)
        cap = p99(hourly.get(num))
        # A p99 from a handful of tickets is not a measurement — T2's single
        # lifetime ticket produced "p99 1/hr", which would price the bridge
        # at 1/30th of the fallback and silently defeat its matrix grant.
        if (tot or 0) < 500:
            cap = None
        b = {"num": num,
             "road": road_km[0] if road_km else None,
             "km": road_km[1] if road_km else None,
             "p99_hr": cap,
             "tickets": tot,
             "last_seen": str(last) if last else None}
        if mat_name == "WB_RIM_T7":
            # Ticket number 7 is dominated by WB_IWIP_T7A; RIM_T7's own
            # throughput is unmeasurable from tickets. Do not credit it the
            # IWIP bridge's history.
            b.update({"p99_hr": None, "tickets": None, "last_seen": None,
                      "note": "shares ticket number 7 with WB_IWIP_T7A; "
                              "own throughput unmeasurable from tickets"})
        if mat_name == "WB_IWIP_T2":
            b["unverified"] = True
            b["note"] = ("1 lifetime ticket, no geofence - used as the matrix "
                         "writes it, flagged (owner ruling 2026-08-26)")
        if mat_name == "WB_IWIP_T7":
            b["note"] = "geofence name WB_IWIP_T7A; shares ticket number 7 with WB_RIM_T7"
        bridges[mat_name] = b

    # Matrix per canonical route. names is {num: name}; RIM_T7/IWIP_T7 share
    # num 7 — resolve per pair: BLB rows take the RIM name (the matrix grants
    # RIM_T7 only on BLB rows), everything else the IWIP name.
    elig_names = {}
    for (pit, plant), nums in elig.items():
        route = "%s>%s" % (pit, plant)
        row_names = []
        for num in sorted(nums):
            if num == 7:
                row_names.append("WB_RIM_T7" if pit.startswith("BLB") else "WB_IWIP_T7")
            else:
                row_names.append(names.get(num, "WB_%d" % num))
        elig_names[route] = row_names

    hist_pairs = {"_basis": ("measured >=%d lifetime tickets, canonical areas "
                             "(FENI KM15 lines resolved by canonical_area)"
                             % _HIST_MIN_TICKETS)}
    agg = defaultdict(set)
    for num, flows in hist.items():
        for (o, d), (n, _t, _f, _l) in flows.items():
            if n >= _HIST_MIN_TICKETS:
                agg["%s>%s" % (o, d)].add(num)
    for route, nums in sorted(agg.items()):
        hist_pairs[route] = sorted(nums)

    register = {
        "generated_at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "basis": ("owner eligibility matrix (%s) + HAULAGE_IWIP_CLEAN whole "
                  "ticket history + FMS_GEOFENCES positions snapped to the "
                  "committed road survey. Generated by "
                  "scripts/wb_matrix_analysis.py --register" % MATRIX_TSV),
        "policy": {
            "objective": "min-max bridge utilisation over the eligible set",
            "capacity": "measured p99 tickets/hour per bridge; fallback_cap_hr when unmeasured",
            "fallback_cap_hr": 30,
            "pit_rows": "owner matrix eligibility, keyed origin>destination (canonical)",
            "iwip_rows": ("measured historical bridges minus excluded; when that is empty "
                          "(new route, e.g. POS 6 transit) fall back to the destination "
                          "plant's matrix bridges (union over pits)"),
            "tenant_rows": "never allocated - not our fleet (owner ruling 2026-08-26)",
            "excluded_rule": "bridges with ticket history but granted NOWHERE in the matrix are never assigned",
        },
        "bridges": bridges,
        "matrix": elig_names,
        "history_pairs": hist_pairs,
        "excluded_nums": excluded,
        "excluded_note": ("bridges with ticket history but granted nowhere in the owner "
                          "matrix; T11's exclusion is DELIBERATE (owner ruling 2026-08-26)"),
    }
    for path in (os.path.join(ROOT, "data", "wb_register.json"),
                 os.path.join(ROOT, "fixtures", "wb-allocation-basis.json")):
        io.open(path, "w", encoding="utf-8").write(
            json.dumps(register, indent=1, ensure_ascii=False))
        print("wrote", path)


if __name__ == "__main__":
    sys.exit(main())
