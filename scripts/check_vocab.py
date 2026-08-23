#!/usr/bin/env python
"""Vocabulary convergence check — the metric Job 1 is measured against.

The operator picks a route in the Plan tab; the model predicts for a route.
If those two vocabularies differ, the number on screen silently describes a
different physical haul than the one selected. This script makes that
divergence countable instead of a matter of opinion.

It reports three things:

  1. DIRTY  — canonical names that still carry raw-table noise (a "TOS" prefix,
              CJK department tags, "-PT."/"-LVMI" vendor suffixes, or empty).
              Target: 0.
  2. SPLIT  — one physical place emitted under several canonical spellings
              (BSE-1 / BSE1 / BSE2, HUAFEIC01 / HUAFEI.C01). Target: 0 groups.
  3. DRIFT  — names the model trained on that the API never serves, and vice
              versa. Target: 0 on the model side.

Usage:
    python scripts/check_vocab.py            # canonicaliser + model CSV
    python scripts/check_vocab.py --api      # also diff against the live API

Exit code is 0 only when DIRTY and SPLIT are both zero, so it can gate a build.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.request
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prediction_pipeline import CORRIDOR_KM, canonical_area, distance_km  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_LIST = os.environ.get("RAW_AREAS", "/tmp/raw_areas.txt")
TRAINING_CSV = os.path.join(BASE, "data", "training_data.csv")
API = os.environ.get("SIM_API", "http://127.0.0.1:5055")

# A canonical name must not look like this. Empty is NOT dirty: it is the
# deliberate signal for "not a haul-road node" (a coal yard, a limestone shed),
# and extract_from_db drops those rows. Emptiness is audited separately below so
# it can never quietly swallow a real route.
DIRTY_RE = re.compile(r"^TOS(?![A-Z]*\s)|[^\x00-\x7F]|-(?:PT|LVMI|HUAFEI|WBN|BSE)\b")

# Places that must stay distinct — the guard against fixing DIRTY by
# over-merging everything into one bucket.
MUST_DIFFER = [("POS 12", "POS 10"), ("POS 12", "POS 16"),
               ("FENI KM0", "FENI KM15"), ("TF", "KR")]
MUST_MEASURE = [(("TF", "FENI KM0"), 67.8), (("KR", "POS 12"), 12.0),
                (("TF", "FENI KM15"), 52.8), (("TF", "POS 12"), 40.8),
                (("TF", "HUAFEI"), 63.7), (("TOFU", "HUAFEI"), 63.7),
                (("BLB", "POS 14"), 6.7), (("BLB", "POS14"), 6.7)]

# Real strings taken from HAULAGE_IWIP_CLEAN, with the node each one denotes.
# Kept here rather than in a fixture so the expectations sit next to the guards.
CASES = [
    ("TOS_TF", "TF"), ("TOSTOFU-WBN矿业部", "TF"), ("TOFU", "TF"),
    ("TOS_TF_STM_13-WBN矿业部", "TF"), ("TOS_TF_SMA_02_EXT-WBN矿业部", "TF"),
    ("TOS_KRENE", "KR"), ("TOS_KRENE_PPP_06-WBN矿业部", "KR"), ("KRENE", "KR"),
    ("TOSBLB-WBN矿业部", "BLB"), ("TOS_BLB", "BLB"),
    ("POS 12", "POS 12"), ("POS14", "POS 14"),
    ("POS16-WBN矿业部", "POS 16"),
    ("POS16-LVMI镍铁事业部", "POS 16"), ("POS15-WBN矿业部", "POS 15"),
    ("POSCBB-WBN矿业部", "POS CBB"), ("POS CBB", "POS CBB"),
    ("FENI A", "FENI KM0"), ("FENI U2", "FENI KM0"), ("FENI W", "FENI KM0"),
    ("FENI KM15", "FENI KM15"), ("FENI KM0", "FENI KM0"),
    ("BSE-1-BSE湿法冶金部", "BSE"), ("BSE1-BSE湿法冶金部", "BSE"),
    ("BSE2-BSE湿法冶金部", "BSE"), ("BSE5-BSE湿法冶金部", "BSE"),
    ("BSE101", "BSE"), ("BSE02-PT.BSE", "BSE"),
    ("HUAFEI.B01", "HUAFEI"), ("HUAFEI.C01", "HUAFEI"),
    ("HUAFEIC01-HUAFEI", "HUAFEI"), ("HUAFEIC.01-HUAFEI华飞", "HUAFEI"),
    ("华飞KM8-4-华飞镍钴", "HUAFEI"),
    ("CUU_KM10-WBN矿业部", "CUU KM10"), ("CUU_KM_10", "CUU KM10"),
    ("POS CUU", "CUU KM10"),
    ("李白2#煤堆场-LIPE镍铁事业部", ""),        # coal yard: not a haul-road node
    ("", ""),
    # Crew pads: the trailing code names the CONTRACTOR, not the place. A
    # hauler must never surface as an origin ("RIM -> POS 10" is nonsense).
    ("TOS_KRENE_01_RIM-WBN矿业部", "KR"),
    ("TOS_TF/TOFU_09_SMA-WBN矿业部", "TF"),
    ("TOS_CRUSHER_RIM-WBN矿业部", "CRUSHER"),
    ("TOS_RIM_01-WBN矿业部", ""),
    ("TOS_RIM_09-WBN矿业部", ""),
    ("PMA矿山-CMI镍铁事业部", "PMA"),          # a real mine, keeps its name
]


def selftest() -> int:
    fails = [(r, canonical_area(r), e) for r, e in CASES if canonical_area(r) != e]
    print("\n[0] canonical_area self-test: %d/%d pass" % (len(CASES) - len(fails), len(CASES)))
    for r, got, want in fails:
        print("      FAIL %-32r -> %-12r want %r" % (r, got, want))
    return len(fails)


def _norm_key(s: str) -> str:
    """Aggressive key used only to DETECT names that should have merged."""
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def load_raw() -> list:
    if not os.path.exists(RAW_LIST):
        return []
    with open(RAW_LIST, encoding="utf-8") as fh:
        return [l.rstrip("\n") for l in fh if l.strip()]


def model_vocab() -> set:
    if not os.path.exists(TRAINING_CSV):
        return set()
    with open(TRAINING_CSV, encoding="utf-8") as fh:
        return {r[c] for r in csv.DictReader(fh) for c in ("source", "destination") if r.get(c)}


def api_vocab() -> set:
    names = set()
    try:
        with urllib.request.urlopen(API + "/api/simulator/path-response", timeout=60) as r:
            for k in (json.load(r).get("paths") or {}):
                names.update(p.strip() for p in k.split(">") if p.strip())
    except Exception as exc:                                   # noqa: BLE001
        print("  (api path-response unavailable: %s)" % str(exc)[:80])
    try:
        with urllib.request.urlopen(API + "/api/simulator/capability", timeout=90) as r:
            for rt in (json.load(r).get("routes") or []):
                for c in ("origin", "dest"):
                    if rt.get(c):
                        names.add(str(rt[c]).strip())
    except Exception as exc:                                   # noqa: BLE001
        print("  (api capability unavailable: %s)" % str(exc)[:80])
    return names


def report(use_api: bool) -> int:
    raws = load_raw()
    canon = {r: canonical_area(r) for r in raws}
    produced = set(canon.values())

    print("=" * 68)
    print("VOCABULARY CONVERGENCE")
    print("=" * 68)
    if raws:
        print("raw DB names      : %d" % len(raws))
        print("canonical distinct: %d" % len(produced))
    unit_fails = selftest()

    # 1 ── DIRTY
    dirty = sorted(v for v in produced if v and DIRTY_RE.search(v))
    print("\n[1] DIRTY canonical outputs: %d   (target 0)" % len(dirty))
    for d in dirty[:20]:
        src = [k for k, v in canon.items() if v == d][:2]
        print("      %-28r  <- %s" % (d, ", ".join(map(repr, src))))
    dropped = sorted(k for k, v in canon.items() if not v)
    print("    dropped as non-haul-road: %d %s"
          % (len(dropped), [d[:24] for d in dropped[:4]]))

    # 2 ── SPLIT
    groups = defaultdict(set)
    for v in produced:
        if v:
            groups[_norm_key(v)].add(v)
    split = {k: v for k, v in groups.items() if len(v) > 1}
    print("\n[2] SPLIT groups (same place, several spellings): %d   (target 0)" % len(split))
    for k, v in list(split.items())[:12]:
        print("      %s -> %s" % (k, sorted(v)))

    # 3 ── DRIFT
    mv = model_vocab()
    if use_api and mv:
        av = api_vocab()
        only_model = sorted(mv - av)
        only_api = sorted(av - mv)
        print("\n[3] DRIFT model=%d api=%d shared=%d" % (len(mv), len(av), len(mv & av)))
        print("      model-only: %d %s" % (len(only_model), only_model[:8]))
        print("      api-only  : %d %s" % (len(only_api), only_api[:8]))
    elif mv:
        dirty_model = sorted(v for v in mv if v and DIRTY_RE.search(v))
        print("\n[3] model vocab: %d  (dirty: %d) %s"
              % (len(mv), len(dirty_model), dirty_model[:8]))

    # 4 ── guards
    print("\n[4] GUARDS (must not over-merge)")
    bad = 0
    for a, b in MUST_DIFFER:
        if canonical_area(a) == canonical_area(b):
            print("      FAIL %s and %s collapsed together" % (a, b)); bad += 1
    for (a, b), want in MUST_MEASURE:
        got = distance_km(a, b)
        if abs(got - want) > 0.01:
            print("      FAIL distance %s->%s = %s (want %s)" % (a, b, got, want)); bad += 1
    print("      %s" % ("all guards pass" if not bad else "%d guard failure(s)" % bad))

    ok = not dirty and not split and not bad and not unit_fails
    print("\nRESULT: %s" % ("PASS" if ok else "FAIL"))
    print("=" * 68)
    return 0 if ok else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", action="store_true", help="also diff against the live API")
    sys.exit(report(ap.parse_args().api))
