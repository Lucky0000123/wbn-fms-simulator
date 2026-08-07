#!/usr/bin/env python3
"""Rebuild data/congestion_seg_by_dir.csv from the Jul+ GPS archive (no VPN).

Run after accumulate_gps so the Plan stick / measuredSpeeds use the full banked
window, not only the last live extract from FMS_CONGESTION_SEG.
"""
from __future__ import annotations

import json
import sys

sys.path.insert(0, "/Users/lucky/wbn-fms-simulator")
import plan_corridor_hours as pch


def main() -> int:
    res = pch.rebuild_by_dir_from_archive()
    print(json.dumps(res, indent=2))
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
