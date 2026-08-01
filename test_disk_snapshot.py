"""Gate J68: disk-backed capability + path-response snapshots.

P3: after a process restart the first hit was still 14–20 s because memory
was empty. Persist to data/cap_snapshot.json and data/pr_snapshot.json;
on empty memory load disk first (fresh → no DB; stale → serve + bg refresh).
Priority: memory > disk > fixture.

(a) fresh DB load writes the data/ file
(b) simulated restart (memory clear) serves from disk with servedFrom=disk-snapshot
(c) file older than TTL still serves and schedules a background refresh

Offline unit tests always run (temp files + mocked loaders). Live HTTP checks
run when :5055 is in database mode and the disk files already exist.
"""
import json
import os
import sys
import tempfile
import time
import urllib.request

BASE = "http://127.0.0.1:5055"
FAILED = []


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name
          + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


print("=== offline: disk tier write / restart / stale refresh ===")
import simulator_api as sa

# Isolate from any real data/ files the live server may be using.
_tmpdir = tempfile.mkdtemp(prefix="j68_")
_cap_path = os.path.join(_tmpdir, "cap_snapshot.json")
_pr_path = os.path.join(_tmpdir, "pr_snapshot.json")
sa._CAP_DISK = _cap_path
sa._PATH_DISK = _pr_path

_fake_cap = [
    {"d": "2026-07-01", "o": "TF", "dd": "FENI KM0", "contractor": "RIM",
     "type": "ORE", "iwip": False, "sc": 1, "dt": 10.0, "trips": 40.0,
     "t": 2000.0, "planDt": 10.0, "_ptr": 80.0, "planWmt": 2200.0},
]
_fake_path = [
    {"o": "TF", "dd": "FENI KM0", "d": "2026-07-01",
     "dt": 10.0, "trips": 40.0, "t": 2000.0},
]
_fake_rain = {("2026-07-01", "TOFU"): 3.5}

_orig_cap_load = sa._cap_load_rows
_orig_path_load = sa._path_load
_cap_loads = {"n": 0}
_path_loads = {"n": 0}


def _mock_cap_load():
    _cap_loads["n"] += 1
    time.sleep(0.05)  # stand-in for the slow SQL hit
    return list(_fake_cap)


def _mock_path_load():
    _path_loads["n"] += 1
    time.sleep(0.05)
    return list(_fake_path), dict(_fake_rain)


sa._cap_load_rows = _mock_cap_load
sa._path_load = _mock_path_load

try:
    sa._cap_reset()
    for p in (_cap_path, _pr_path):
        if os.path.exists(p):
            os.remove(p)

    # (a) fresh load writes disk
    _cap_loads["n"] = 0
    t0 = time.time()
    rows = sa._cap_snapshot()
    check("cap fresh load returns rows", len(rows) == 1)
    check("cap fresh load hit DB mock once", _cap_loads["n"] == 1, _cap_loads["n"])
    check("cap disk file written after fresh load",
          os.path.isfile(_cap_path) and os.path.getsize(_cap_path) > 20,
          _cap_path)
    with open(_cap_path, encoding="utf-8") as f:
        disk = json.load(f)
    check("cap disk has at + rows",
          isinstance(disk.get("at"), (int, float)) and len(disk.get("rows") or []) == 1,
          disk.get("at"))

    _path_loads["n"] = 0
    prow, prain = sa._path_snapshot()
    check("path fresh load returns rows", len(prow) == 1 and prain.get(("2026-07-01", "TOFU")) == 3.5)
    check("path disk file written after fresh load",
          os.path.isfile(_pr_path) and os.path.getsize(_pr_path) > 20,
          _pr_path)

    # (b) simulated restart — memory empty, disk fresh → no DB, tag disk
    sa._cap_reset()  # clears memory; keeps disk
    _cap_loads["n"] = 0
    t0 = time.time()
    rows2 = sa._cap_snapshot()
    dt = time.time() - t0
    check("restart serves from disk without DB",
          _cap_loads["n"] == 0 and len(rows2) == 1,
          "loads=%d" % _cap_loads["n"])
    check("restart is fast (<0.5s)", dt < 0.5, "%.3fs" % dt)
    check("source tagged disk", sa._CAP_SNAP.get("source") == "disk",
          sa._CAP_SNAP.get("source"))
    tag = sa._snapshot_disk_tag(sa._CAP_SNAP)
    check("servedFrom=disk-snapshot with age",
          tag.get("servedFrom") == "disk-snapshot"
          and isinstance(tag.get("snapshotAgeSec"), (int, float)),
          tag)

    sa._path_reset()
    _path_loads["n"] = 0
    prow2, _ = sa._path_snapshot()
    check("path restart serves from disk without DB",
          _path_loads["n"] == 0 and len(prow2) == 1,
          "loads=%d" % _path_loads["n"])
    check("path source tagged disk", sa._PATH_SNAP.get("source") == "disk",
          sa._PATH_SNAP.get("source"))

    # (c) stale disk — still serves, schedules background refresh
    with open(_cap_path, encoding="utf-8") as f:
        stale = json.load(f)
    stale["at"] = time.time() - (sa._CAP_TTL + 30)
    with open(_cap_path, "w", encoding="utf-8") as f:
        json.dump(stale, f)
    sa._cap_reset()
    _cap_loads["n"] = 0
    sa._CAP_SNAP["refreshing"] = False
    rows3 = sa._cap_snapshot()
    check("stale disk still serves immediately",
          len(rows3) == 1 and sa._CAP_SNAP.get("source") == "disk")
    check("stale disk schedules background refresh",
          sa._CAP_SNAP.get("refreshing") is True
          or _cap_loads["n"] >= 1,  # may already have started
          "refreshing=%s loads=%d" % (sa._CAP_SNAP.get("refreshing"), _cap_loads["n"]))
    # Wait for bg refresh to finish and promote source to db
    for _ in range(40):
        if sa._CAP_SNAP.get("source") == "db" and not sa._CAP_SNAP.get("refreshing"):
            break
        time.sleep(0.05)
    check("background refresh replaces memory from DB",
          sa._CAP_SNAP.get("source") == "db" and _cap_loads["n"] >= 1,
          "source=%s loads=%d" % (sa._CAP_SNAP.get("source"), _cap_loads["n"]))
    with open(_cap_path, encoding="utf-8") as f:
        after = json.load(f)
    check("background refresh rewrites disk at",
          float(after.get("at") or 0) > float(stale.get("at") or 0),
          after.get("at"))

    # Fixture tier still works when there is no DB and no usable disk.
    # (Exercise the helper tag only — _register fixture path is unchanged.)
    check("fixture tag helper unchanged",
          sa._served_from_fixture({"ok": True}, "no database configured").get("servedFrom")
          == "fixture")

finally:
    sa._cap_load_rows = _orig_cap_load
    sa._path_load = _orig_path_load
    sa._cap_reset()
    # Leave module disk paths pointing at temp — restore to real data/ for live.
    _root = os.path.dirname(os.path.abspath(sa.__file__))
    sa._CAP_DISK = os.path.join(_root, "data", "cap_snapshot.json")
    sa._PATH_DISK = os.path.join(_root, "data", "pr_snapshot.json")


# Live HTTP (optional): files on disk from the running server's warm load.
try:
    with urllib.request.urlopen(BASE + "/health", timeout=5) as r:
        mode = json.loads(r.read()).get("dataMode")
except Exception as exc:  # noqa: BLE001
    print("\nno server on 5055 (%s) — offline checks only" % str(exc)[:60])
    mode = None

if mode == "database":
    print("\n=== live: disk files + servedFrom after memory reset via cold process ===")
    # The running server owns its memory. We can only assert files exist once
    # warm has happened, and that a direct in-process restart simulation against
    # the real files (read-only) tags disk — without mutating the server's state.
    cap_f = sa._CAP_DISK
    pr_f = sa._PATH_DISK
    # Nudge the live server to populate disk if warm already finished.
    try:
        urllib.request.urlopen(
            BASE + "/api/simulator/capability?from=2026-07-01&to=2026-07-31",
            timeout=120).read()
        urllib.request.urlopen(
            BASE + "/api/simulator/path-response?from=2026-07-01&to=2026-07-31",
            timeout=120).read()
    except Exception as exc:  # noqa: BLE001
        check("live endpoints reachable", False, str(exc)[:80])
    # Wait briefly for disk write from server warm / first load.
    for _ in range(60):
        if os.path.isfile(cap_f) and os.path.isfile(pr_f):
            break
        time.sleep(0.5)
    check("live cap_snapshot.json exists",
          os.path.isfile(cap_f) and os.path.getsize(cap_f) > 1000,
          cap_f if os.path.isfile(cap_f) else "missing")
    check("live pr_snapshot.json exists",
          os.path.isfile(pr_f) and os.path.getsize(pr_f) > 1000,
          pr_f if os.path.isfile(pr_f) else "missing")

    # In-process: clear OUR memory, load from the live server's disk files.
    sa._cap_reset()
    if os.path.isfile(cap_f):
        t0 = time.time()
        sa._cap_snapshot()
        dt = time.time() - t0
        tag = sa._snapshot_disk_tag(sa._CAP_SNAP)
        check("live disk load tags servedFrom=disk-snapshot",
              tag.get("servedFrom") == "disk-snapshot", tag)
        check("live disk load under 2s (no DB)",
              dt < 2.0 and sa._CAP_SNAP.get("source") == "disk",
              "dt=%.2f source=%s" % (dt, sa._CAP_SNAP.get("source")))
else:
    print("\n(no live database server — skipped HTTP/disk file asserts)")

print()
if FAILED:
    print("J68 FAILED: %d check(s). First: %s" % (len(FAILED), FAILED[0]))
    sys.exit(1)
print("disk-snapshot gate passes")
