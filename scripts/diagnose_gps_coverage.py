"""Priority 2 diagnosis: why did only 24 of 101 hauling trucks appear in GPS?

Two very different explanations, with opposite consequences:

(a) Coverage gap - only some trucks carry working GPS devices. Then segment
    speeds are structurally limited to that subfleet forever, and the honest
    move is to report which trucks can never be covered.

(b) Retention window - the devices are fine, but the one day I picked sat at the
    edge of the 5-day window so most trucks' fixes had already been purged. Then
    scaling to recent days recovers them.

These are distinguishable: check the match rate on the MOST RECENT day, not Day X.
If it jumps, it was retention. If it stays near 24%, it is a real coverage gap.

Also asked here: is the gap correlated with contractor or vehicle type? A single
contractor with no telematics would be a clean, reportable finding.
"""
import os
import sys

sys.path.insert(0, "/Users/lucky/wbn-fms-simulator")
import pandas as pd
import simulator_api as sim


def conn(db):
    import pymssql
    return pymssql.connect(server=sim._DB["server"], user=sim._DB["user"],
                           password=sim._DB["password"], database=db,
                           login_timeout=10, timeout=1800, charset="LATIN1")


f = conn("FMS_DB")
w = conn("WBN_DATABASE")

print("=== what days does GPS actually hold right now? ===")
for tbl in ("FMS_GPS_Historical", "FMS_PLAYBACK_TRACK_24H"):
    q = """SELECT CAST(DATEADD(second, TS/1000, '1970-01-01') AS date) AS d,
                  COUNT(*) AS fixes, COUNT(DISTINCT PLATE) AS plates
           FROM [%s] WHERE PLATE IS NOT NULL
           GROUP BY CAST(DATEADD(second, TS/1000, '1970-01-01') AS date)
           ORDER BY d""" % tbl
    try:
        d = pd.read_sql(q, f)
        print("\n%s: %d day(s)" % (tbl, len(d)))
        for r in d.itertuples():
            print("   %s  %9s fixes  %4d plates" % (r.d, "{:,}".format(r.fixes), r.plates))
    except Exception as e:
        print("\n%s: FAILED %s" % (tbl, str(e)[:70]))

print("\n=== the decisive test: match rate on the MOST RECENT full GPS day ===")
# FMS_PLAYBACK_TRACK_24H is the live feed and holds far more than the archive:
# 859,198 fixes over 715 plates on its best day vs 274,092 over 555. Pick the
# richest day across BOTH tables rather than the newest, since the newest is a
# partial day still being written.
q = """SELECT TOP 1 CAST(DATEADD(second, TS/1000, '1970-01-01') AS date) AS d
       FROM FMS_PLAYBACK_TRACK_24H WHERE PLATE IS NOT NULL
       GROUP BY CAST(DATEADD(second, TS/1000, '1970-01-01') AS date)
       ORDER BY COUNT(*) DESC"""
latest = pd.read_sql(q, f).d.iloc[0]
print("richest GPS day in the live feed: %s" % latest)

# Trucks that hauled on that day, from the weighbridge.
q = """SELECT DISTINCT UPPER(LTRIM(RTRIM(TRUCK_ID))) AS truck
       FROM HAULAGE_IWIP_CLEAN
       WHERE CAST([DATE] AS date) = '%s' AND TRUCK_ID IS NOT NULL AND WMT > 0
       UNION
       SELECT DISTINCT UPPER(LTRIM(RTRIM(TRUCK_ID))) AS truck
       FROM HAULAGE
       WHERE CAST([DATE] AS date) = '%s' AND TRUCK_ID IS NOT NULL AND WMT > 0
    """ % (latest, latest)
try:
    hauled = pd.read_sql(q, w)
except Exception as e:
    print("weighbridge query failed: %s" % str(e)[:90])
    hauled = pd.DataFrame(columns=["truck"])
print("trucks that hauled on %s: %d" % (latest, len(hauled)))

q = """SELECT DISTINCT UPPER(LTRIM(RTRIM(PLATE))) AS truck
       FROM FMS_PLAYBACK_TRACK_24H
       WHERE CAST(DATEADD(second, TS/1000, '1970-01-01') AS date) = '%s'
         AND PLATE IS NOT NULL""" % latest
ingps = pd.read_sql(q, f)
print("distinct plates in GPS on %s: %d" % (latest, len(ingps)))

hs, gs = set(hauled.truck), set(ingps.truck)
both = hs & gs
print()
print("hauled AND in GPS: %d of %d = %.1f%%"
      % (len(both), len(hs), 100.0 * len(both) / max(len(hs), 1)))
print()
print("Day X gave 24 of 101 = 23.8%. If this is much higher, the Day X shortfall")
print("was retention, not a coverage gap.")

miss = sorted(hs - gs)
print("\n=== who is missing? ===")
print("missing count: %d" % len(miss))
print("sample: %s" % ", ".join(miss[:14]))

# Is the gap concentrated by contractor? Use the equipment master.
q = """SELECT UPPER(LTRIM(RTRIM(ID_EQ))) AS truck,
              MAX(CONTRACTOR) AS contractor, MAX(ACTIVITY) AS etype
       FROM EQUIPMENTS_HOURLY_STATUS GROUP BY UPPER(LTRIM(RTRIM(ID_EQ)))"""
try:
    mst = pd.read_sql(q, w)
    mst["in_gps"] = mst.truck.isin(gs)
    sub = mst[mst.truck.isin(hs)]
    if len(sub):
        print("\nmatch rate by contractor (trucks that hauled on %s):" % latest)
        g = (sub.groupby("contractor")
             .agg(trucks=("truck", "size"), in_gps=("in_gps", "sum")))
        g["pct"] = (100.0 * g.in_gps / g.trucks).round(1)
        print(g.sort_values("trucks", ascending=False).to_string())
except Exception as e:
    print("\nequipment master join failed: %s" % str(e)[:90])
