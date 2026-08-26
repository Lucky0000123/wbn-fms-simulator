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
    return 0


if __name__ == "__main__":
    sys.exit(main())
