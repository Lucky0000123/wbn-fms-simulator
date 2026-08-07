#!/usr/bin/env python3
"""Materialise SIM_PLAN_* tables in FMS_DB from WBN capability spine (+ optional GPS).

Usage (VPN + FMS_DB_* env):
  python scripts/build_plan_memory.py

Offline dry-run (fixture only, no DB write):
  python scripts/build_plan_memory.py --fixture-only
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _load_env():
    from scripts.load_fms_env import load_fms_env
    load_fms_env()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture-only", action="store_true",
                    help="Build corpus from fixtures/capability.json; skip DB writes")
    ap.add_argument("--no-gps", action="store_true",
                    help="Skip FMS location speed attach")
    args = ap.parse_args()

    import plan_analogues as pa
    import plan_memory as pm

    _load_env()

    if args.fixture_only:
        corpus, src = pa.load_fixture_corpus()
        print("corpus %d rows from %s (dry-run, no write)" % (len(corpus), src))
        # Sample TF>POS 12
        sample = [c for c in corpus if c["route"] == "TF>POS 12"][:3]
        print("sample TF>POS 12:", sample)
        return 0

    try:
        import pymssql
    except ImportError:
        print("pymssql missing", file=sys.stderr)
        return 1

    host = os.environ.get("FMS_DB_HOST", "")
    user = os.environ.get("FMS_DB_USER", "")
    pwd = os.environ.get("FMS_DB_PASS", "")
    if not (host and user and pwd):
        print("FMS_DB_* env not set — use --fixture-only or configure env", file=sys.stderr)
        return 1

    # Load WBN capability rows via simulator_api helpers when possible
    import simulator_api as sim

    rows = None
    rain_by_date = {}
    if sim._db_ready():
        try:
            print("loading capability rows from WBN…")
            rows = sim._cap_load_rows()
            print("  raw rows:", len(rows))
        except Exception as e:  # noqa: BLE001
            print("  WBN load failed:", e)
        try:
            _path_rows, rain = sim._path_load()
            for (d, _a), h in (rain or {}).items():
                rain_by_date[str(d)[:10]] = max(rain_by_date.get(str(d)[:10], 0.0), float(h))
            print("  rain days:", len(rain_by_date))
        except Exception as e:  # noqa: BLE001
            print("  rain skipped:", e)

    if not rows:
        disk = sim._cap_disk_read()
        if disk and disk.get("rows"):
            rows = disk["rows"]
            print("using disk cap_snapshot.json rows:", len(rows))
        else:
            print("no DB/disk rows — building from fixture")
            corpus, src = pa.load_fixture_corpus()
            print("corpus:", len(corpus), "source:", src)
            n_local = pm.write_local_day_kpi(corpus)
            print("wrote local data/plan_day_kpi.json rows:", n_local)
            return 0

    corpus, src = pa.load_corpus(cap_rows=rows, rain_by_date=rain_by_date)
    print("corpus:", len(corpus), "source:", src)

    if not args.no_gps:
        try:
            fms = sim._conn("FMS_DB")
            try:
                dates = [c["date"] for c in corpus]
                speeds = pm.fetch_gps_speed_by_date(fms, dates)
                print("  gps speed days:", len(speeds))
                pa.attach_location_speeds(corpus, speeds)
            finally:
                fms.close()
        except Exception as e:  # noqa: BLE001
            print("  gps attach skipped:", e)

    # Always write local disk memory (VPN-safe fallback for the API).
    n_local = pm.write_local_day_kpi(corpus)
    print("wrote local data/plan_day_kpi.json rows:", n_local)

    try:
        import pymssql
        fms = pymssql.connect(
            server=os.environ["FMS_DB_HOST"],
            user=os.environ["FMS_DB_USER"],
            password=os.environ["FMS_DB_PASS"],
            database="FMS_DB",
            login_timeout=20,
            timeout=180,
            charset="LATIN1",
        )
        try:
            pm.ensure_tables(fms)
            n = pm.replace_day_kpi(fms, corpus, batch_size=1500)
            print("wrote SIM_PLAN_DAY_KPI rows:", n)
        finally:
            fms.close()
    except Exception as e:  # noqa: BLE001
        print("FMS_DB write failed (local cache still usable):", e)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
