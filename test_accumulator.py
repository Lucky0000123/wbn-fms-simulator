"""Gate: the forward accumulator must stay idempotent and must not lose rows.

Why this gate exists. GPS retention is a rolling few days, so the archive is the
only copy that grows. Two failure modes would be silent and unrecoverable:
  - a non-idempotent append duplicates rows on every scheduled run, quietly
    corrupting any future speed-density fit with repeated observations;
  - an append that rewrites instead of appending destroys history that cannot be
    re-fetched, because the source rows are already deleted upstream.

Both are tested here against the real store with a stubbed connection, so no VPN
is needed and the gate runs in a clean checkout wherever the archive exists.
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, "/Users/lucky/wbn-fms-simulator")
import pandas as pd

import scripts.accumulate_gps as ag

fails = []


def check(name, cond, detail=""):
    print(("  PASS  " if cond else "  FAIL  ") + name + ("" if cond else "  <- " + detail))
    if not cond:
        fails.append(name)


print("=== status must work with no database ===")
# The VPN drops constantly, so reporting what is banked must never need it.
s = ag.status()
check("status() returns a dict with row counts",
      isinstance(s, dict) and "segment_rows" in s and "gps_rows" in s,
      "%r" % s)

if not os.path.exists(ag.SEG_STORE):
    print("\nno archive yet; nothing further to verify")
    print("all accumulator gates pass")
    sys.exit(0)

before = pd.read_csv(ag.SEG_STORE)
backup = tempfile.mktemp(suffix=".csv")
shutil.copy(ag.SEG_STORE, backup)
try:
    print("\n=== appending must be idempotent ===")
    # Feed rows already banked plus 5 genuinely new hours.
    new = before.head(5).copy()
    new["HOUR_TS"] = new.HOUR_TS + 999_000_000
    feed = pd.concat([before.head(100), new], ignore_index=True)

    orig = pd.read_sql
    pd.read_sql = lambda q, c: feed.copy()
    try:
        n1 = ag.accumulate_segments(None)
        n2 = ag.accumulate_segments(None)
    finally:
        pd.read_sql = orig

    after = pd.read_csv(ag.SEG_STORE)
    check("first run adds exactly the new rows", n1 == 5, "added %d, expected 5" % n1)
    check("a repeat run adds nothing", n2 == 0,
          "added %d; a scheduled job would duplicate rows every run" % n2)
    check("existing rows are preserved, not overwritten",
          len(after) == len(before) + 5,
          "%d rows vs expected %d; history that cannot be re-fetched was lost"
          % (len(after), len(before) + 5))
    check("no duplicate keys in the store",
          not after.duplicated(subset=["HOUR_TS", "SEG_ID", "DIR"]).any(),
          "duplicated (hour, segment, direction) keys would bias any later fit")
finally:
    shutil.copy(backup, ag.SEG_STORE)
    os.unlink(backup)
    restored = pd.read_csv(ag.SEG_STORE)
    check("the store is restored after the test",
          len(restored) == len(before),
          "%d vs %d" % (len(restored), len(before)))

print()
if fails:
    print("FAILED: " + "; ".join(fails))
    sys.exit(1)
print("all accumulator gates pass")
