"""Load FMS_DB_* from local .env first, then SSD fallback.

Used by offline scripts so the LUCKY_SSD volume is optional after sync.
Maps FMS_DB_PWD -> FMS_DB_PASS. Does not print secrets.
"""
from __future__ import annotations

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CANDIDATES = (
    os.path.join(ROOT, ".env"),
    os.path.join(ROOT, "secrets", "fms.env"),
    "/Volumes/LUCKY_SSD/LV_APP/fms-dashboard/backend/.env",
)


def load_fms_env(overwrite: bool = False) -> str | None:
    """Load first existing env file. Returns path used, or None."""
    for path in CANDIDATES:
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k == "FMS_DB_PWD":
                    if overwrite or "FMS_DB_PASS" not in os.environ:
                        os.environ["FMS_DB_PASS"] = v
                    continue
                if k.startswith("FMS_DB_") or k.startswith("WBN_"):
                    if overwrite or k not in os.environ:
                        os.environ[k] = v
        return path
    return None


if __name__ == "__main__":
    p = load_fms_env()
    print("loaded", p or "NONE")
    print("FMS_DB_HOST", "SET" if os.environ.get("FMS_DB_HOST") else "MISSING")
    print("FMS_DB_USER", "SET" if os.environ.get("FMS_DB_USER") else "MISSING")
    print("FMS_DB_PASS", "SET" if os.environ.get("FMS_DB_PASS") else "MISSING")
