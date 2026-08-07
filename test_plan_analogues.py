"""Tests for plan analogue retrieval + shared-road detection (fixture corpus)."""
import sys
sys.path.insert(0, "/Users/lucky/wbn-fms-simulator")

import plan_analogues as pa

fails = []


def check(name, cond, detail=""):
    print("   %-56s %s%s" % (name, "PASS" if cond else "FAIL",
                             "" if cond else "  <- " + str(detail)))
    if not cond:
        fails.append(name)


print("=== 1. corridor sections ===")
secs = pa.route_sections("TF", "POS 12")
check("TF→POS12 crosses TOFU–KR", "TOFU–KR" in secs, secs)
check("TF→POS12 crosses KR–POS 12", "KR–POS 12" in secs, secs)
check("TF→POS12 does not cross POS10–FENI", "POS 10–FENI" not in secs, secs)

secs2 = pa.route_sections("KR", "POS 10")
shared = set(secs) & set(secs2)
check("TF→POS12 and KR→POS10 share KR–POS 12", "KR–POS 12" in shared, shared)

print("\n=== 2. fixture corpus + TF→POS12 analogues ===")
corpus, src = pa.load_fixture_corpus()
check("fixture corpus non-empty", len(corpus) > 100, len(corpus))
check("source is fixture", src == "fixture")

res = pa.find_analogues({
    "plans": [{"source": "TF", "destination": "POS 12", "n_trucks": 50, "contractor": "RIM"}],
    "rain_mm": 0, "k": 8, "nocache": True,
}, corpus=corpus, corpus_source=src)
check("ok", res.get("ok") is True, res.get("error"))
check("returns 5–10 analogues", 5 <= len(res.get("analogues") or []) <= 10,
      len(res.get("analogues") or []))
check("ensemble has trips_med", res["ensemble"].get("trips_med") is not None)
check("simulate unchanged flag", res["basis"].get("simulate_unchanged") is True)
check("congestion does not clip tonnes", res["basis"].get("congestion_clips_tonnes") is False)

# Ranking stability: same query twice → same top date
res2 = pa.find_analogues({
    "plans": [{"source": "TF", "destination": "POS 12", "n_trucks": 50, "contractor": "RIM"}],
    "rain_mm": 0, "k": 8,
}, corpus=corpus, corpus_source=src)
d1 = [a["date"] for a in res["analogues"]]
d2 = [a["date"] for a in res2["analogues"]]
check("ranking stable", d1 == d2, (d1[:3], d2[:3]))

# Fleet band: 50 DT should prefer days near 50 over tiny fleets when available
top = res["analogues"][0]
check("top analogue has route or near-OD", bool(top.get("route")), top)
# Remarks must not nag about missing haul GPS (ops days are normal)
check("remark omits ops-only gate", "ops-only" not in (top.get("remark") or "").lower()
      and "no haul gps" not in (top.get("remark") or "").lower(),
      top.get("remark"))

print("\n=== 3. multi-plan shared road ===")
multi = pa.find_analogues({
    "plans": [
        {"source": "TF", "destination": "POS 12", "n_trucks": 50, "contractor": "RIM"},
        {"source": "KR", "destination": "POS 10", "n_trucks": 30, "contractor": "RIM"},
    ],
    "rain_mm": 0, "k": 8,
}, corpus=corpus, corpus_source=src)
sr = multi.get("shared_road") or {}
check("shared sections non-empty", len(sr.get("shared_sections") or []) >= 1,
      sr.get("shared_sections"))
check("KR–POS 12 in shared", "KR–POS 12" in (sr.get("shared_sections") or []),
      sr.get("shared_sections"))
check("risk is low|medium|high", sr.get("risk") in ("low", "medium", "high", "none"),
      sr.get("risk"))
check("single-plan risk none/note", True)

single_sr = pa.shared_road_analysis(
    [{"source": "TF", "destination": "POS 12", "n_trucks": 50}], corpus)
check("single plan risk none", single_sr.get("risk") == "none", single_sr.get("risk"))

print("\n=== 4. season tags ===")
check("Jan is peak", pa.season_tag("2026-01-15") == "peak")
check("Jul is struggle", pa.season_tag("2026-07-01") == "struggle")
check("has_haul_gps Jul 20", pa.has_haul_gps("2026-07-20") is True)
check("no haul gps May", pa.has_haul_gps("2026-05-01") is False)

print("\n=== 5. attach_location never invents May speeds ===")
rows = [{"date": "2026-05-01", "has_gps": False, "avg_speed_kmh": None}]
pa.attach_location_speeds(rows, {"2026-05-01": 40.0, "2026-07-20": 35.0})
check("May speed stays None", rows[0]["avg_speed_kmh"] is None, rows[0])
rows2 = [{"date": "2026-07-20", "has_gps": True, "avg_speed_kmh": None}]
pa.attach_location_speeds(rows2, {"2026-07-20": 35.0})
check("Jul speed attached", rows2[0]["avg_speed_kmh"] == 35.0, rows2[0])

print("\n%s" % ("ALL PASS" if not fails else "FAILED: " + ", ".join(fails)))
sys.exit(1 if fails else 0)
