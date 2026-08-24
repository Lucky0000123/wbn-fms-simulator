#!/usr/bin/env python
"""Hunt the other tenants (MHM, POSITION, PMA, HSM) and RSF in the DBs.

Owner (2026-08-24) gave tenant fleets that share our haul road but add no
tonnage to us. Before assuming their trips/DT, look for them in history:
CONTRACTOR/COMPANY codes on the dispatch view, and RSF as an area name on
the ticket table and the geofences.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

NEEDLES = ("MHM", "POSITION", "PMA", "HSM", "RSF", "POSCO")


def conn(db):
    from load_fms_env import load_fms_env
    load_fms_env()
    import pymssql
    return pymssql.connect(server=os.environ["FMS_DB_HOST"],
                           user=os.environ["FMS_DB_USER"],
                           password=os.environ["FMS_DB_PASS"],
                           database=db, login_timeout=10, timeout=300)


def show(title, cur):
    print("\n=== %s" % title)
    rows = cur.fetchall()
    if not rows:
        print("  (none)")
    for r in rows[:60]:
        print("  " + " | ".join("" if v is None else str(v) for v in r))


def main():
    c = conn("WBN_DATABASE")
    cur = c.cursor()

    cur.execute("SELECT CONTRACTOR, COMPANY, COUNT(*), MIN(DATE), MAX(DATE), "
                "SUM(CAST(NB_DT AS float)), SUM(CAST(RIT AS float)) "
                "FROM dbo.[DISPATCH RESULTS LITE 2] GROUP BY CONTRACTOR, COMPANY "
                "ORDER BY COUNT(*) DESC")
    show("dispatch view: every CONTRACTOR x COMPANY", cur)

    like = " OR ".join("ORIGIN LIKE '%%%s%%' OR DESTINATION LIKE '%%%s%%'" % (n, n)
                       for n in NEEDLES)
    cur.execute("SELECT ORIGIN, DESTINATION, COUNT(*), MIN(DATE), MAX(DATE), "
                "SUM(CAST(NB_DT AS float)), SUM(CAST(RIT AS float)) "
                "FROM dbo.[DISPATCH RESULTS LITE 2] WHERE %s "
                "GROUP BY ORIGIN, DESTINATION ORDER BY COUNT(*) DESC" % like)
    show("dispatch view: routes naming a tenant or RSF", cur)

    like2 = " OR ".join("ORIGIN_AREA LIKE '%%%s%%' OR DESTINATION_AREA LIKE '%%%s%%'" % (n, n)
                        for n in NEEDLES)
    cur.execute("SELECT ORIGIN_AREA, DESTINATION_AREA, COUNT(*), MIN(DATE), MAX(DATE), "
                "COUNT(DISTINCT TRUCK_ID) FROM HAULAGE_CLEAN WHERE %s "
                "GROUP BY ORIGIN_AREA, DESTINATION_AREA ORDER BY COUNT(*) DESC" % like2)
    show("HAULAGE_CLEAN: areas naming a tenant or RSF", cur)
    c.close()

    try:
        f = conn("FMS_DB")
        fc = f.cursor()
        like3 = " OR ".join("NAME LIKE '%%%s%%'" % n for n in NEEDLES)
        fc.execute("SELECT NAME, CENTER_LAT, CENTER_LNG FROM FMS_GEOFENCES WHERE %s" % like3)
        show("FMS_GEOFENCES: geofences naming a tenant or RSF", fc)
        f.close()
    except Exception as exc:  # noqa: BLE001
        print("\n=== FMS_DB geofences: %s" % str(exc)[:200])


if __name__ == "__main__":
    main()
