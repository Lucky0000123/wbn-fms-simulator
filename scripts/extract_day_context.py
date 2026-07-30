"""extract_day_context.py — Steps 7 to 10 for Day X.

Loader assignment, operator identity, availability and HRM presence. Each is
tested for whether it JOINS to the trips, not merely whether rows exist for the
day: a table full of Day X rows that cannot be tied to a truck proves nothing.

READ ONLY.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pymssql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import simulator_api as sim                                  # noqa: E402

DATA = os.path.join(ROOT, "data")
REPORTS = os.path.join(ROOT, "reports")


def conn(db):
    return pymssql.connect(server=sim._DB["server"], user=sim._DB["user"],
                           password=sim._DB["password"], database=db,
                           login_timeout=10, timeout=1800, charset="LATIN1")


def norm(s):
    return s.astype(str).str.strip().str.upper()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default="2026-07-19")
    day = ap.parse_args().day
    trips = pd.read_csv(os.path.join(DATA, "day_x_trips.csv"))
    day_trucks = set(norm(trips["TRUCK_ID"])) if len(trips) else set()
    print("DAY X = %s | trips %d | trucks %d" % (day, len(trips), len(day_trucks)))
    out = {"day": day,
           "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    w, f = conn("WBN_DATABASE"), conn("FMS_DB")
    try:
        # ---------------------------------------------------- STEP 7: loaders
        print("\n=== STEP 7: loader assignment ===")
        ha = pd.read_sql("""
            SELECT [DATE] AS date, SHIFT, CONTRACTOR, ACTIVITY, MATERIAL,
                   ORIGIN_AREA, DESTINATION_AREA, DISTANCE, TRUCK_ID,
                   EXCAVATOR_ID, RIT, TRUCK_FACTOR
            FROM EQUIPMENTS_HOURLY_ACTIVITIES
            WHERE CAST([DATE] AS date) = '%s'""" % day, w)
        print("EQUIPMENTS_HOURLY_ACTIVITIES rows: %d" % len(ha))
        res = {"rows": int(len(ha))}
        if len(ha):
            ha["truck"] = norm(ha["TRUCK_ID"])
            res["trucks"] = int(ha.truck.nunique())
            res["excavators"] = int(ha.EXCAVATOR_ID.nunique())
            res["truck_examples"] = sorted(ha.truck.dropna().unique())[:12]
            res["excavator_examples"] = sorted(
                ha.EXCAVATOR_ID.dropna().astype(str).unique())[:12]
            hit = day_trucks & set(ha.truck)
            res["trucks_matching_trips"] = len(hit)
            res["match_pct"] = round(100 * len(hit) / max(len(day_trucks), 1), 1)
            print("trucks %d | excavators %d" % (res["trucks"], res["excavators"]))
            print("truck IDs here : %s" % res["truck_examples"][:8])
            print("truck IDs trips: %s" % sorted(day_trucks)[:8])
            print("JOIN to Day X trips: %d of %d trucks (%.1f%%)"
                  % (len(hit), len(day_trucks), res["match_pct"]))
            if not hit:
                res["blocker"] = ("truck vocabularies differ: this table uses "
                                  "ADT-style codes, the weighbridge uses "
                                  "letter+3-digit fleet numbers; no mapping "
                                  "table found in either database")
                print("BLOCKED: %s" % res["blocker"])
            print("\nRIT and DISTANCE meaning:")
            print("  RIT      = trip count for that hour (median %.0f, max %.0f)"
                  % (pd.to_numeric(ha.RIT, errors="coerce").median(),
                     pd.to_numeric(ha.RIT, errors="coerce").max()))
            print("  DISTANCE = haul distance km (median %.1f)"
                  % pd.to_numeric(ha.DISTANCE, errors="coerce").median())
            ha.to_csv(os.path.join(DATA, "day_x_hourly_activities.csv"), index=False)
        out["loader_hourly_activities"] = res

        fa = pd.read_sql("""
            SELECT PLAN_DATE, SHIFT, TRUCK, PILE, EXCAVATOR, PIT, MATERIAL,
                   DESTINATION FROM FMS_TRUCK_ASSIGNMENTS
            WHERE CAST(PLAN_DATE AS date) = '%s'""" % day, f)
        r2 = {"rows": int(len(fa))}
        if len(fa):
            fa["truck"] = norm(fa["TRUCK"])
            hit = day_trucks & set(fa.truck)
            r2.update(trucks=int(fa.truck.nunique()),
                      excavators=int(fa.EXCAVATOR.nunique()),
                      trucks_matching_trips=len(hit))
        print("\nFMS_TRUCK_ASSIGNMENTS for Day X: %d rows" % len(fa))
        out["loader_fms_assignments"] = r2

        # -------------------------------------------------- STEP 8: operators
        print("\n=== STEP 8: operator identity ===")
        dw = pd.read_sql("""
            SELECT [DATE] AS date, SHIFT, CONTRACTOR, ACTIVITY_CAT, OPERATOR_ID,
                   UNIT_TYPE, UNIT_CLASS, UNIT_ID, LOCATION, ROAD_NAME,
                   ROAD_STA_KM, ROAD_END_KM, LOADING_POINT, LOADING_RIT,
                   DISTANCE_KM FROM DAY_WORKS
            WHERE CAST([DATE] AS date) = '%s'""" % day, w)
        print("DAY_WORKS rows: %d" % len(dw))
        r3 = {"rows": int(len(dw))}
        if len(dw):
            dw["unit"] = norm(dw["UNIT_ID"])
            r3.update(
                operators=int(dw.OPERATOR_ID.nunique()),
                units=int(dw.unit.nunique()),
                unit_types=sorted(map(str, dw.UNIT_TYPE.dropna().unique()))[:14],
                unit_examples=sorted(dw.unit.dropna().unique())[:10],
                units_matching_trips=len(day_trucks & set(dw.unit)),
                loading_points=sorted(map(str, dw.LOADING_POINT.dropna().unique()))[:12],
                has_road_km=int(dw.ROAD_STA_KM.notna().sum()),
            )
            print("operators %d | units %d | unit types %s"
                  % (r3["operators"], r3["units"], r3["unit_types"][:8]))
            print("unit IDs here : %s" % r3["unit_examples"][:6])
            print("JOIN to Day X trips: %d of %d trucks"
                  % (r3["units_matching_trips"], len(day_trucks)))
            print("rows with ROAD_STA_KM: %d" % r3["has_road_km"])
            print("loading points: %s" % r3["loading_points"][:8])
            if not r3["units_matching_trips"]:
                r3["blocker"] = ("UNIT_ID uses asset codes (VRVV11011-style), "
                                 "not fleet numbers; OPERATOR_ID holds names, "
                                 "not the numeric IDs in RES_EMPLOYEES")
                print("BLOCKED: %s" % r3["blocker"])
            dw.to_csv(os.path.join(DATA, "day_x_day_works.csv"), index=False)
        out["operators_day_works"] = r3

        wt = pd.read_sql("""
            SELECT EQUIPMENT_ID, DRIVER_ID, SHIFT, LOADING_DIFFERENCE_TIME,
                   DUMPING_DIFFERENCE_TIME, ORIGIN_AREA, DESTINATION, PIT
            FROM WAITING_TIME WHERE CAST([DATE] AS date) = '%s'""" % day, w)
        r4 = {"rows": int(len(wt))}
        if len(wt):
            wt["truck"] = norm(wt["EQUIPMENT_ID"])
            hit = day_trucks & set(wt.truck)
            r4.update(trucks=int(wt.truck.nunique()),
                      drivers=int(wt.DRIVER_ID.nunique()),
                      trucks_matching_trips=len(hit),
                      match_pct=round(100 * len(hit) / max(len(day_trucks), 1), 1),
                      median_load_min=float(pd.to_numeric(
                          wt.LOADING_DIFFERENCE_TIME, errors="coerce").median()),
                      median_dump_min=float(pd.to_numeric(
                          wt.DUMPING_DIFFERENCE_TIME, errors="coerce").median()))
            print("\nWAITING_TIME Day X: %d rows, %d trucks, %d drivers"
                  % (len(wt), r4["trucks"], r4["drivers"]))
            print("JOIN to trips: %d of %d trucks (%.1f%%)"
                  % (len(hit), len(day_trucks), r4["match_pct"]))
            print("measured load %.1f min | dump %.1f min"
                  % (r4["median_load_min"], r4["median_dump_min"]))
            wt.to_csv(os.path.join(DATA, "day_x_waiting_time.csv"), index=False)
        out["operators_waiting_time"] = r4

        # ----------------------------------------------- STEP 9: availability
        print("\n=== STEP 9: availability ===")
        st = pd.read_sql("""
            SELECT CONTRACTOR, SHIFT, ID_EQ, ACTIVITY, WORKING_HOURS,
                   STBY_HOURS, BD_HOURS, PM_HOURS, OPERATING_HOURS, STATUS
            FROM EQUIPMENTS_HOURLY_STATUS
            WHERE CAST([DATE] AS date) = '%s'""" % day, w)
        print("EQUIPMENTS_HOURLY_STATUS rows: %d" % len(st))
        r5 = {"rows": int(len(st))}
        if len(st):
            st["eqid"] = norm(st["ID_EQ"])
            for c in ("WORKING_HOURS", "STBY_HOURS", "BD_HOURS", "PM_HOURS"):
                st[c] = pd.to_numeric(st[c], errors="coerce").fillna(0)
            hit = day_trucks & set(st["eqid"])
            tot = st[["WORKING_HOURS", "STBY_HOURS", "BD_HOURS", "PM_HOURS"]].sum()
            denom = float(tot.sum())
            # Availability = hours the unit could work (all but breakdown and PM).
            avail = (denom - tot["BD_HOURS"] - tot["PM_HOURS"]) / denom if denom else 0
            # Utilisation = hours actually working out of available hours.
            util = tot["WORKING_HOURS"] / (denom - tot["BD_HOURS"] - tot["PM_HOURS"]) \
                if denom > tot["BD_HOURS"] + tot["PM_HOURS"] else 0
            r5.update(equipment=int(st["eqid"].nunique()),
                      equipment_matching_trips=len(hit),
                      hours={k: round(float(v), 1) for k, v in tot.items()},
                      availability_pct=round(100 * float(avail), 1),
                      utilisation_pct=round(100 * float(util), 1))
            print("equipment %d | matching Day X trucks: %d"
                  % (r5["equipment"], len(hit)))
            print("hours: %s" % r5["hours"])
            print("AVAILABILITY (1 - (BD+PM)/total) = %.1f%%" % r5["availability_pct"])
            print("UTILISATION  (working / available) = %.1f%%" % r5["utilisation_pct"])
            print("simulator assumes 85%% availability -> delta %+.1f pp"
                  % (r5["availability_pct"] - 85.0))
            # Same figures for only the trucks that actually hauled Day X.
            if hit:
                sub = st[st["eqid"].isin(hit)]
                t2 = sub[["WORKING_HOURS", "STBY_HOURS", "BD_HOURS", "PM_HOURS"]].sum()
                d2 = float(t2.sum())
                if d2:
                    a2 = (d2 - t2["BD_HOURS"] - t2["PM_HOURS"]) / d2
                    u2 = t2["WORKING_HOURS"] / max(d2 - t2["BD_HOURS"] - t2["PM_HOURS"], 1e-9)
                    r5["hauling_trucks_availability_pct"] = round(100 * float(a2), 1)
                    r5["hauling_trucks_utilisation_pct"] = round(100 * float(u2), 1)
                    print("for the %d trucks that hauled Day X: availability "
                          "%.1f%%, utilisation %.1f%%"
                          % (len(hit), 100 * a2, 100 * u2))
            st.to_csv(os.path.join(DATA, "day_x_equipment_status.csv"), index=False)
        out["availability"] = r5

        # ------------------------------------------------------- STEP 10: HRM
        print("\n=== STEP 10: HRM on the haul road ===")
        hrm = pd.read_sql("""
            SELECT SOURCE, ACTIVITY, [DATE], SHIFT, EQUIPMENT_ID, SECTIONKM,
                   DIRECTION, ZONE, DISTANCE_M, EQUIPMENT_TYPE, HOURS, LAT, LONG
            FROM FMS_HRM_SUPERVISION WHERE CAST([DATE] AS date) = '%s'""" % day, f)
        print("FMS_HRM_SUPERVISION rows: %d" % len(hrm))
        r6 = {"rows": int(len(hrm))}
        if len(hrm):
            r6.update(
                units=int(hrm.EQUIPMENT_ID.nunique()),
                types={str(k): int(v) for k, v in
                       hrm.EQUIPMENT_TYPE.value_counts().head(8).items()},
                with_gps=int(hrm.LAT.notna().sum()),
                roads=sorted(map(str, hrm.DIRECTION.dropna().unique()))[:10],
            )
            km = pd.to_numeric(hrm.SECTIONKM, errors="coerce")
            r6["km_range"] = [round(float(km.min()), 1), round(float(km.max()), 1)]
            print("units %d | types %s" % (r6["units"], r6["types"]))
            print("rows with GPS coords: %d | roads %s"
                  % (r6["with_gps"], r6["roads"]))
            print("section KM range: %s" % r6["km_range"])
            hrm["km_bucket"] = np.floor(km).astype("Int64")
            per = (hrm.dropna(subset=["km_bucket"])
                      .groupby(["DIRECTION", "km_bucket"])
                      .EQUIPMENT_ID.nunique().rename("units").reset_index())
            print("\nHRM units per KM section (top 12):")
            print(per.sort_values("units", ascending=False).head(12).to_string(index=False))
            r6["per_section_top"] = per.sort_values(
                "units", ascending=False).head(15).to_dict("records")
            hrm.to_csv(os.path.join(DATA, "day_x_hrm.csv"), index=False)
        out["hrm"] = r6
    finally:
        w.close(); f.close()

    with open(os.path.join(REPORTS, "day_x_context.json"), "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)
    print("\nwrote reports/day_x_context.json and the day_x_*.csv extracts")


if __name__ == "__main__":
    main()
