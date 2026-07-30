"""Verify the handover's factual claims against the repo, rather than trusting prose.

A handover that is confidently wrong is worse than a short one. Every claim below
is checked against the live filesystem, the app's own url_map and the harness.
"""
import io
import os
import re
import subprocess
import sys

sys.path.insert(0, "/Users/lucky/wbn-fms-simulator")
os.chdir("/Users/lucky/wbn-fms-simulator")

H = io.open("reports/HANDOVER.md", encoding="utf-8").read()
bad = []


def claim(name, cond, detail=""):
    print(("  OK    " if cond else "  WRONG ") + name + ("" if cond else "  <- " + detail))
    if not cond:
        bad.append(name)


print("=== files the handover names must exist ===")
# Pull every backticked path that looks like a file in this repo.
paths = set(re.findall(r"`([A-Za-z0-9_./-]+\.(?:py|sh|md|json|csv|parquet|pkl|html|css|js|txt))`", H))
SHORTHAND = {"trip_level_base.csv/.parquet", "trip_level_base.parquet/csv"}
paths = {p for p in paths if p not in SHORTHAND}
missing = sorted(p for p in paths
                 if not os.path.exists(p)
                 and not os.path.exists(os.path.join("data", os.path.basename(p)))
                 and not os.path.exists(os.path.join("reports", os.path.basename(p)))
                 and not os.path.exists(os.path.join("fixtures", os.path.basename(p)))
                 and not os.path.exists(os.path.join("scripts", os.path.basename(p)))
                 and not os.path.exists(os.path.join("static/js", os.path.basename(p)))
                 and not os.path.exists(os.path.join("templates", os.path.basename(p))))
claim("every named file exists (%d checked)" % len(paths), not missing,
      "missing: %s" % missing)

claim("trip_level_base shorthand resolves to two real files",
      os.path.exists("data/trip_level_base.csv")
      and os.path.exists("data/trip_level_base.parquet"))
claim("templates/simulator.html exists", os.path.exists("templates/simulator.html"))

print("\n=== endpoint table matches the app's url_map ===")
import serve
live = {str(r) for r in serve.app.url_map.iter_rules() if "static" not in str(r)}
documented = set(re.findall(r"\| `(/[a-z0-9/_-]+)`", H)) | \
    set(re.findall(r"`(/api/[a-z0-9/_-]+)`", H)) | {"/", "/simulator", "/health"}
undocumented = sorted(live - documented)
claim("all %d live routes appear in the doc" % len(live), not undocumented,
      "undocumented: %s" % undocumented)
phantom = sorted(p for p in documented if p.startswith("/api") and p not in live)
claim("no phantom endpoints documented", not phantom, "not real: %s" % phantom)
claim("endpoint count claim (18) matches", len(live) == 18, "live=%d" % len(live))

print("\n=== gate count and names ===")
gates = re.findall(r'chk \$\? "([A-Z][0-9]+)', io.open("scripts/verify_phase2.sh").read())
claim("harness defines 54 gates", len(gates) == 54, "found %d" % len(gates))
for g in ("J52", "J53", "J54", "G24", "C13"):
    claim("%s documented" % g, g in H)

print("\n=== numbers that must match their source files ===")
import json
import pandas as pd

tm = json.load(open("data/trip_metadata.json"))
claim("483,425 trips", "483,425" in H and tm["rows"] == 483425, "meta=%d" % tm["rows"])
claim("535,411 raw", "535,411" in H and tm["raw_rows"] == 535411)
claim("65 routes kept", tm["routes_kept"] == 65 and "65 routes kept" in H)
claim("3,187 trucks", tm["trucks"] == 3187 and "3,187 trucks" in H)

cr = json.load(open("data/cycle_model_report.json"))
claim("cycle CV R2 0.6565", abs(cr["winner_cv_r2"] - 0.6565) < 1e-4 and "0.6565" in H)
claim("cycle MAE 29.50", abs(cr["winner_cv_mae_min"] - 29.5018) < 1e-3 and "29.50" in H)
claim("beats_baseline is False and doc says so",
      cr["beats_baseline"] is False and "`beats_baseline` is False" in H)
claim("utilisation 0.3998", abs(cr["utilisation"]["utilisation"] - 0.3998) < 1e-4
      and "0.3998" in H)

mm = json.load(open("data/model_metadata.json"))
claim("trips/DT model_type matches metadata",
      mm["model_type"] in H, "metadata says %r" % mm["model_type"])
claim("R2 0.8535 matches", abs(mm["r2"] - 0.8535) < 1e-4 and "0.8535" in H)

ce = json.load(open("data/capacity_evidence.json"))
claim("capacity percentile p99", ce["capacity_percentile"] == 0.99 and "p99" in H)
claim("14 loading / 9 dumping points",
      ce["loading_points"] == 14 and ce["dumping_points"] == 9
      and "14 loading, 9 dumping" in H)
claim("min 200 observed hours", ce["min_observed_hours"] == 200 and "200 observed hours" in H)

ch = pd.read_csv("data/haul_road_chainage.csv")
claim("3,122 chainage markers", len(ch) == 3122 and "3,122" in H, "%d rows" % len(ch))

ra = pd.read_csv("data/route_availability.csv")
n_meas = int((ra.basis == "measured").sum())
claim("23 of 65 routes measured",
      n_meas == 23 and len(ra) == 65 and "23 of 65" in H,
      "%d measured of %d" % (n_meas, len(ra)))

cs = pd.read_csv("data/gps_archive/congestion_seg_hourly.csv")
claim("archive holds 36,046 rows", len(cs) == 36046 and "36,046" in H, "%d" % len(cs))

print("\n=== plan_simulator invariants the doc asserts ===")
import plan_simulator as ps
claim("DEFAULT_AVAILABILITY is 1.0", ps.DEFAULT_AVAILABILITY == 1.0)
claim("MEASURED_MECHANICAL_AVAILABILITY is 0.720",
      abs(ps.MEASURED_MECHANICAL_AVAILABILITY - 0.720) < 1e-9)
claim("_roster exists", hasattr(ps, "_roster"))
claim("reset_cache exists", hasattr(ps, "reset_cache"))
r = ps._roster(30, "BLB>FENI KM0")
claim("BLB roster is (39, 0.7705, measured)",
      r[0] == 39 and abs(r[1] - 0.7705) < 1e-4 and r[2] == "measured", "%r" % (r,))
p = ps._roster(30, "POS 12>FENI KM0")
claim("POS 12 roster is (42, 0.72, fleet_prior)",
      p[0] == 42 and p[2] == "fleet_prior", "%r" % (p,))

print("\n=== git facts ===")
head = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                      capture_output=True, text=True).stdout.strip()
claim("HEAD hash in doc matches actual", head[:7] in H, "actual %s" % head)
tags = subprocess.run(["git", "tag", "-l"], capture_output=True, text=True).stdout.split()
claim("both tags documented",
      all(t in H for t in tags) and set(tags) == {"pre-cycle-fix", "fms-modules-v1"},
      "tags=%r" % tags)
br = subprocess.run(["git", "branch", "--format=%(refname:short)"],
                    capture_output=True, text=True).stdout.split()
claim("main is the only local branch", br == ["main"], "%r" % br)

print("\n=== symlink claim ===")
claim("CLAUDE.md really is a symlink to AGENTS.md",
      os.path.islink("CLAUDE.md") and os.readlink("CLAUDE.md") == "AGENTS.md",
      "islink=%s target=%r" % (os.path.islink("CLAUDE.md"),
                               os.readlink("CLAUDE.md") if os.path.islink("CLAUDE.md") else None))

print("\n=== port + env var names ===")
claim("port 5055 documented", "5055" in H)
srv = io.open("serve.py", encoding="utf-8").read()
claim("serve.py really uses 5055", "5055" in srv)
for v in ("FMS_DB_HOST", "FMS_DB_USER", "FMS_DB_PASS", "FMS_DB_PWD"):
    claim("%s documented" % v, v in H)

print("\n=== no credentials leaked into the handover ===")
leaked = [w for w in ("Wbn@", "sa_fms", "admin123", "password=") if w in H]
claim("no credential literals", not leaked, "found %r" % leaked)
claim("host 10.211.10.1 is documented (not secret, it is a private RFC1918 addr)",
      "10.211.10.1" in H)

print()
if bad:
    print("HANDOVER HAS %d WRONG CLAIM(S):" % len(bad))
    for b in bad:
        print("   - " + b)
    sys.exit(1)
print("every checked claim in the handover is accurate")
