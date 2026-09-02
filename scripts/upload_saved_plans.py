#!/usr/bin/env python3
"""Upload local saved plans into WBN_DATABASE.dbo.WBN_FMS_SIMULATOR_SAVED_PLANS.

The JSON in each data/saved_plans/YYYY-MM-DD.json is stored as-is. The Plan
tab, allocation, and path objects are not rewritten.

  .venv/bin/python scripts/upload_saved_plans.py           # upsert all local files
  .venv/bin/python scripts/upload_saved_plans.py --check   # list what SQL has
  .venv/bin/python scripts/upload_saved_plans.py --date 2026-09-03

Needs FMS_DB_* (same .env as the running app). Never commit .env.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.chdir(ROOT)

from load_fms_env import load_fms_env  # noqa: E402

load_fms_env()

import simulator_api as sa  # noqa: E402


def _files(only=None):
    names = []
    if not os.path.isdir(sa._SAVED_PLANS_DIR):
        return names
    for name in sorted(os.listdir(sa._SAVED_PLANS_DIR)):
        if not (name.endswith(".json") and len(name) == 15):
            continue
        date_s = name[:-5]
        if only and date_s != only:
            continue
        names.append(date_s)
    return names


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true", help="list SQL dates only")
    p.add_argument("--date", help="upload one YYYY-MM-DD file")
    args = p.parse_args()

    if not sa._db_ready():
        sys.exit("FMS_DB_* not set — cannot reach SQL Server")

    sa._SAVED_PLANS_SQL = True
    sa._SAVED_PLANS_SQL_ENSURED = False

    try:
        sql_dates = sa._saved_plan_sql_list()
    except Exception as e:
        sys.exit("SQL Server unreachable (VPN?). %s" % e)

    if args.check:
        dates = sql_dates
        print("table WBN_DATABASE.dbo.%s" % sa._SAVED_PLANS_SQL_TABLE)
        print("%d plan(s)" % len(dates))
        for d in sorted(dates, reverse=True):
            print(" ", d)
        return

    files = _files(args.date)
    if args.date and not files:
        sys.exit("no file data/saved_plans/%s.json" % args.date)
    if not files:
        sys.exit("no YYYY-MM-DD.json files in data/saved_plans/")

    ok = 0
    for date_s in files:
        plan = sa._saved_plan_disk_read(date_s)
        if not isinstance(plan, dict) or not plan.get("paths"):
            print("SKIP", date_s, "empty or unreadable")
            continue
        sa._saved_plan_sql_put(date_s, plan)
        n = len(plan.get("paths") or {})
        print("OK  ", date_s, "%d paths" % n)
        ok += 1
    print("uploaded %d / %d" % (ok, len(files)))


if __name__ == "__main__":
    main()
