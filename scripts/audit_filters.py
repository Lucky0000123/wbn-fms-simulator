"""Which endpoints actually respond to the top filter bar? Measure, don't read.

For every endpoint the UI calls, this issues the SAME request twice with DIFFERENT
filter values and compares the responses byte-for-byte. An endpoint whose output
does not move when the date range is halved is not filtering, whatever its source
says.

    .venv/bin/python scripts/audit_filters.py

Reports per endpoint x per filter: RESPONDS / IGNORES / ERROR, plus whether the
payload is identical to the committed fixture (which would mean it is served
statically even with a database configured).

This is deliberately black-box. The bug it was written to find -- three endpoints
wired straight to fixtures in serve.py while the UI sent them six filter
parameters -- is invisible from the front end and easy to miss in the back end,
because the code reads as a normal endpoint.
"""
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:5055"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FX = os.path.join(ROOT, "fixtures")

# (name, path, needs-a-date-arg?)
ENDPOINTS = [
    ("capability", "/api/simulator/capability", True),
    ("trucks", "/api/simulator/trucks", True),
    ("constraints", "/api/simulator/constraints", True),
    ("path-response", "/api/simulator/path-response", True),
    ("congestion-model", "/api/simulator/congestion-model", True),
    ("weighbridge", "/api/simulator/weighbridge", True),
    ("weighbridge-summary", "/api/weighbridge-summary", True),
    ("weighbridge-positions", "/api/simulator/weighbridge-positions", True),
    ("shift-context", "/api/simulator/shift-context", True),
    ("simulate/options", "/api/simulate/options", True),
    ("model-info", "/api/model-info", False),
    ("corridor-geometry", "/api/simulator/corridor-geometry", False),
]

# Two genuinely different filter states. If a response is identical under both,
# the endpoint is not using that parameter.
FILTER_SETS = {
    "date-range": ({"from": "2025-09-01", "to": "2026-07-22"},
                   {"from": "2026-04-01", "to": "2026-07-31"}),
    "iwip": ({"from": "2025-09-01", "to": "2026-07-22"},
             {"from": "2025-09-01", "to": "2026-07-22", "inclIwip": "1"}),
    "types": ({"from": "2025-09-01", "to": "2026-07-22"},
              {"from": "2025-09-01", "to": "2026-07-22", "types": "DIRECT"}),
    "source": ({"from": "2025-09-01", "to": "2026-07-22"},
               {"from": "2025-09-01", "to": "2026-07-22", "source": "TF"}),
    "dest": ({"from": "2025-09-01", "to": "2026-07-22"},
             {"from": "2025-09-01", "to": "2026-07-22", "dest": "FENI KM0"}),
}


def get(path, params, timeout=90):
    url = BASE + path + ("?" + urllib.parse.urlencode(params) if params else "")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status, r.read()
    except Exception as exc:                                       # noqa: BLE001
        return -1, str(exc).encode()


def digest(b):
    return hashlib.sha1(b).hexdigest()[:12]


def fixture_digest(name):
    """Hash of the committed fixture, normalised the way the app serves it."""
    p = os.path.join(FX, name + ".json")
    if not os.path.exists(p):
        return None
    try:
        return digest(json.dumps(json.load(open(p)), sort_keys=True).encode())
    except Exception:                                              # noqa: BLE001
        return None


def body_digest(raw):
    try:
        d = json.loads(raw)
    except Exception:                                              # noqa: BLE001
        return digest(raw)
    if isinstance(d, dict):
        # Timestamps legitimately move between calls and are not evidence of
        # filtering, so they are excluded from the comparison.
        for k in ("updated", "generated_at", "servedFromReason"):
            d.pop(k, None)
    return digest(json.dumps(d, sort_keys=True).encode())


def main():
    print("%-24s %-8s %s" % ("endpoint", "status", "  ".join(f"%-11s" % f for f in FILTER_SETS)))
    print("-" * 96)
    results = {}
    for name, path, _ in ENDPOINTS:
        row, status = {}, None
        for fname, (a, b) in FILTER_SETS.items():
            if name == "shift-context":                 # needs a date to do anything
                a = dict(a, date="2026-03-15"); b = dict(b, date="2026-03-15")
            sa, ra = get(path, a)
            sb, rb = get(path, b)
            status = sa
            if sa != 200 or sb != 200:
                row[fname] = "ERROR"
            else:
                row[fname] = "RESPONDS" if body_digest(ra) != body_digest(rb) else "IGNORES"
        results[name] = {"status": status, "filters": row}
        print("%-24s %-8s %s" % (name, status, "  ".join("%-11s" % row[f] for f in FILTER_SETS)))

    print()
    print("=== is the response just the committed fixture? (DB is configured) ===")
    for name, path, _ in ENDPOINTS:
        fxd = fixture_digest(name.split("/")[0] if "/" not in name else name)
        if fxd is None:
            continue
        _, raw = get(path, {"from": "2026-04-01", "to": "2026-07-31"})
        try:
            served = json.loads(raw)
        except Exception:                                          # noqa: BLE001
            continue
        fx_raw = json.load(open(os.path.join(FX, name + ".json")))
        # Compare CONTENT, not key sets. An earlier version compared only the
        # keys and therefore labelled path-response a "STATIC FIXTURE" while the
        # same run had just proved it RESPONDS to every filter -- a live payload
        # naturally has the same shape as the fixture it was captured from.
        # Volatile keys are stripped from both sides before comparing.
        def norm(o):
            if isinstance(o, dict):
                o = {k: v for k, v in o.items()
                     if k not in ("updated", "generated_at", "servedFrom",
                                  "servedFromReason", "date")}
            return json.dumps(o, sort_keys=True, default=str)
        tag = served.get("servedFrom") if isinstance(served, dict) else None
        identical = norm(served) == norm(fx_raw)
        verdict = ("STATIC FIXTURE (byte-identical, DB ignored)" if identical and tag is None
                   else "tagged fixture fallback" if tag
                   else "live / derived")
        results[name]["fixture"] = verdict
        print("  %-24s %s" % (name, verdict))

    out = os.path.join(ROOT, "reports", "filter_audit.json")
    with open(out, "w") as fh:
        json.dump(results, fh, indent=2)
    print("\nwrote %s" % out)

    ignoring = [n for n, r in results.items()
                if any(v == "IGNORES" for v in r["filters"].values())]
    print("endpoints ignoring at least one filter: %d of %d" % (len(ignoring), len(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
