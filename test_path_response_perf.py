"""Gate J66: path-response is snapshotted and honour date filters under 3s.

Tab 1 QC (2026-07-31): /api/simulator/path-response took 15–18 s cold and the
rain panel ignored Apply. Same pattern as capability — snapshot LITE 3 once,
filter in Python. Mutation: call _path_load() every request → cold latency
returns and this gate fails.
"""
import json
import sys
import time
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:5055"
FAILED = []


def check(name, ok, detail=""):
    print(("  PASS " if ok else "  FAIL ") + name + (("  -- " + str(detail)) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def get(params=None, timeout=120):
    url = BASE + "/api/simulator/path-response"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    t0 = time.time()
    with urllib.request.urlopen(url, timeout=timeout) as r:
        body = json.loads(r.read())
    return body, time.time() - t0


try:
    with urllib.request.urlopen(BASE + "/health", timeout=10) as r:
        mode = json.loads(r.read()).get("dataMode")
except Exception as exc:  # noqa: BLE001
    print("no server on 5055 (%s) -- skipping" % str(exc)[:60])
    sys.exit(0)

if mode != "database":
    d, dt = get({"from": "2026-01-01", "to": "2026-06-30"})
    print("=== no-DB mode: fixture fallback ===")
    check("returns ok", d.get("ok") is True)
    check("tagged fixture or has paths",
          d.get("servedFrom") == "fixture" or bool(d.get("paths")),
          d.get("servedFrom"))
    sys.exit(1 if FAILED else 0)

print("=== path-response must be fast after warm ===")
# First call may pay for the snapshot if warm-up has not finished; second must
# be the Apply path. Use Apr (not July-only): a single month often has <25 rows
# per route so the n>=25 fit gate yields zero paths and cannot prove filter.
d1, t1 = get({"from": "2025-09-01", "to": "2026-07-31"})
d2, t2 = get({"from": "2026-04-01", "to": "2026-07-31"})
d3, t3 = get({"from": "2026-07-01", "to": "2026-07-31"})
print("     timings: first=%.2fs  second=%.2fs  third=%.2fs" % (t1, t2, t3))
print("     nRows:   wide=%s  apr=%s  july=%s" % (
    d1.get("nRows"), d2.get("nRows"), d3.get("nRows")))
check("live (not fixture)", d1.get("servedFrom") is None, d1.get("servedFrom"))
check("has paths", len(d1.get("paths") or {}) >= 10, len(d1.get("paths") or {}))
check("second+third under 3s (snapshot filter path)",
      t2 < 3.0 and t3 < 3.0, "t2=%.2f t3=%.2f" % (t2, t3))
# Row count must shrink with the window (direct proof the SQL snapshot is filtered).
nr1, nr2, nr3 = d1.get("nRows") or 0, d2.get("nRows") or 0, d3.get("nRows") or 0
check("date filter shrinks nRows",
      nr1 > nr2 > nr3 > 0,
      "nRows=%s/%s/%s" % (nr1, nr2, nr3))
# Overlapping fitted paths (wide vs Apr) must also shrink sample size n.
n1 = {k: (d1["paths"][k].get("n") or 0) for k in (d1.get("paths") or {})}
n2 = {k: (d2["paths"][k].get("n") or 0) for k in (d2.get("paths") or {})}
overlap = [k for k in n2 if k in n1]
check("date filter moves sample sizes",
      any(n2[k] < n1[k] for k in overlap) if overlap else False,
      "overlap=%d" % len(overlap))
check("response echoes from/to",
      d3.get("from") == "2026-07-01" and d3.get("to") == "2026-07-31",
      "%s..%s" % (d3.get("from"), d3.get("to")))

print()
if FAILED:
    print("J66 FAILED: %d check(s). First: %s" % (len(FAILED), FAILED[0]))
    sys.exit(1)
print("path-response perf gate passes")
