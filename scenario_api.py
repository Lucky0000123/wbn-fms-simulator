"""Scenario planning: P1 SAP -> P2 LIM-TOS -> P3 LIM-LD waterfall.

A *scenario* is a set of pit x material monthly ROM targets (t/day). The fleet
is NOT part of a scenario: every scenario runs on the same fixed fleet - the
per-contractor DT pools of the loaded yearly matrix (Scenario 1). What changes
between scenarios is where those trucks go.

The waterfall, in the owner's words (2026-08-18):
  1. allocate DTs until every SAP target is met,
  2. then until every LIM-TOS target is met,
  3. every truck still free hauls LIM-LD (Tofu limonite dump -> Huafei),
     capped at the 8 Mt H2 sales limit.

Hard rules:
  * BLB pit accepts RIM trucks only - never SMA or another contractor.
  * Free DTs are pooled per contractor: a spare SMA truck cannot cover a
    BLB (RIM) shortfall, but it can cover TOFU/KRENE work and LIM-LD.
  * DT counts per month never change; only the allocation does.

Storage: data/scenarios/{id}.json - one file per scenario, S1 is derived
live from the yearly matrix so it can never drift from the real plan.
"""

import io
import json
import os
import re
from collections import defaultdict
from datetime import datetime

from flask import Blueprint, jsonify, request

bp = Blueprint("scenario_api", __name__)

_ROOT = os.path.dirname(os.path.abspath(__file__))
_SCEN_DIR = os.path.join(_ROOT, "data", "scenarios")
_YEARLY_PATH = os.path.join(_ROOT, "data", "monthly_plans", "yearly_matrix.json")

# Matrix origin labels -> scenario pit labels (the mine-plan workbook vocabulary).
_PIT = {"BLB": "BLB", "KR": "KRENE", "KRENE": "KRENE", "TOFU": "TOFU", "TF": "TOFU"}
_PITS = ("BLB", "KRENE", "TOFU")
_MONTHS = (8, 9, 10, 11, 12)
_DAYS = {8: 31, 9: 30, 10: 31, 11: 30, 12: 31}
_MN = {"aug": 8, "august": 8, "sept": 9, "sep": 9, "september": 9,
       "oct": 10, "october": 10, "nov": 11, "november": 11,
       "dec": 12, "december": 12}

LIM_LD_CAP_T = 8_000_000  # H2 limonite-from-dump sales limit (owner, 2026-08-18)
RIM_ONLY_PITS = ("BLB",)


# ---------------------------------------------------------------- storage

def _safe_id(sid):
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(sid or ""))
    return sid[:32] or None


def _scen_path(sid):
    sid = _safe_id(sid)
    return os.path.join(_SCEN_DIR, sid + ".json") if sid else None


def _load_yearly():
    if not os.path.isfile(_YEARLY_PATH):
        return None
    with open(_YEARLY_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _yearly_rows(yearly):
    """Yearly-matrix entries in the allocator's vocabulary."""
    rows = []
    for e in (yearly or {}).get("entries") or []:
        pit = _PIT.get((e.get("origin") or "").upper())
        if not pit:
            continue
        rows.append({
            "pit": pit,
            "mat": (e.get("material") or "").upper(),
            "otype": (e.get("otype") or "").upper(),
            "dest": (e.get("dest") or "").upper(),
            "contractor": (e.get("contractor") or "").upper(),
            "wmt": {int(k): v for k, v in (e.get("wmt") or {}).items() if v},
            "dt": {int(k): v for k, v in (e.get("dt") or {}).items() if v},
        })
    return rows


def _route_rate(row, m):
    """Demonstrated t/DT/day for one matrix row, month m (fallback: its mean)."""
    w, d = row["wmt"].get(m), row["dt"].get(m)
    if w and d:
        return w / d
    vals = [row["wmt"][k] / row["dt"][k]
            for k in row["dt"] if row["dt"].get(k) and row["wmt"].get(k)]
    return (sum(vals) / len(vals)) if vals else None


def _s1_targets(rows):
    """Scenario 1 targets = the matrix's own SAP / LIM-TOS wmt by pit."""
    tgt = defaultdict(float)
    for r in rows:
        if r["mat"] == "LIM" and r["otype"] == "LD":
            continue  # LD is the P3 sink, not a target
        for m, w in r["wmt"].items():
            tgt[(r["pit"], r["mat"], m)] += w
    return dict(tgt)


def _scenario_ids():
    out = []
    if os.path.isdir(_SCEN_DIR):
        for f in sorted(os.listdir(_SCEN_DIR)):
            if f.endswith(".json"):
                out.append(f[:-5])
    return out


def _load_scenario(sid):
    """S1 is always derived live from the yearly matrix; others from disk."""
    if sid == "S1":
        yearly = _load_yearly()
        if not yearly:
            return None
        rows = _yearly_rows(yearly)
        tgt = _s1_targets(rows)
        return {
            "id": "S1", "label": "Scenario 1 - current plan",
            "source": "yearly matrix (%s)" % (yearly.get("source") or "pasted"),
            "derived": True,
            "targets": [{"pit": p, "mat": mt, "month": m, "wmt_day": round(v, 1)}
                        for (p, mt, m), v in sorted(tgt.items())],
        }
    p = _scen_path(sid)
    if not p or not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _save_scenario(sc):
    os.makedirs(_SCEN_DIR, exist_ok=True)
    p = _scen_path(sc["id"])
    # The J59 lesson: identical targets keep their stamp. A re-import of the
    # same workbook must not churn source/loaded_at, so git status stays a
    # usable signal.
    if os.path.isfile(p):
        try:
            with open(p, encoding="utf-8") as fh:
                old = json.load(fh)
            if old.get("targets") == sc.get("targets"):
                return
        except (OSError, ValueError):
            pass
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(sc, fh, indent=1)
        fh.write("\n")
    os.replace(tmp, p)


# ---------------------------------------------------------------- importer

def _parse_mine_plan_db(ws_rows, src_name):
    """Long-format 'Mine Plan DB' sheet: Scenario | Month | Nb Days | Mining Pit |
    Material | Type Ore | wmt ROM | ... One scenario dict per distinct label."""
    hdr = None
    for i, r in enumerate(ws_rows[:10]):
        low = [str(c or "").strip().lower() for c in r]
        if "scenario" in low and "month" in low:
            hdr = i
            break
    if hdr is None:
        return None, "no header row (need Scenario / Month / Mining Pit / Material / wmt ROM columns)"
    low = [str(c or "").strip().lower() for c in ws_rows[hdr]]

    def col(*names):
        for n in names:
            if n in low:
                return low.index(n)
        return None

    c_sc, c_m = col("scenario"), col("month")
    c_days, c_pit = col("nb days"), col("mining pit", "pit")
    c_mat, c_wmt = col("material"), col("wmt rom", "wmt")
    if None in (c_sc, c_m, c_pit, c_mat, c_wmt):
        return None, "missing one of: Scenario, Month, Mining Pit, Material, wmt ROM"
    acc = defaultdict(float)
    for r in ws_rows[hdr + 1:]:
        sc = str(r[c_sc] or "").strip()
        mon = _MN.get(str(r[c_m] or "").strip().lower())
        pit = _PIT.get(str(r[c_pit] or "").strip().upper())
        mat = str(r[c_mat] or "").strip().upper()
        try:
            wmt = float(r[c_wmt] or 0)
        except (TypeError, ValueError):
            wmt = 0
        if not sc or not mon or not pit or mat not in ("SAP", "LIM") or wmt <= 0:
            continue
        days = None
        if c_days is not None:
            try:
                days = float(r[c_days] or 0) or None
            except (TypeError, ValueError):
                days = None
        acc[(sc, pit, mat, mon)] += wmt / (days or _DAYS[mon])
    if not acc:
        return None, "found the header but no scenario rows under it"
    scens = {}
    for (sc, pit, mat, mon), v in acc.items():
        sid = "S" + re.sub(r"\D", "", sc) if re.search(r"\d", sc) else _safe_id(sc)
        rec = scens.setdefault(sid, {"id": sid, "label": sc, "source": src_name,
                                     "targets": []})
        rec["targets"].append({"pit": pit, "mat": mat, "month": mon,
                               "wmt_day": round(v, 1)})
    for rec in scens.values():
        rec["targets"].sort(key=lambda t: (t["month"], t["pit"], t["mat"]))
        rec["loaded_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    return list(scens.values()), None


# ---------------------------------------------------------------- allocator

def waterfall(sc, yearly=None, ld_cap=LIM_LD_CAP_T):
    """Run the P1 -> P2 -> P3 waterfall for one scenario.

    Fleet = yearly-matrix DT pools per contractor per month (fixed).
    Targets = scenario pit x material t/day; split across that pit's matrix
    routes by S1 wmt share, each at its demonstrated t/DT/day.
    Months the scenario does not cover fall back to S1 targets (August).
    """
    yearly = yearly or _load_yearly()
    if not yearly:
        return None, "no yearly matrix loaded yet"
    rows = _yearly_rows(yearly)
    if not rows:
        return None, "the yearly matrix has no usable rows"
    s1 = _s1_targets(rows)
    tgt = dict(s1) if sc["id"] == "S1" else {}
    filled_from_s1 = []
    if sc["id"] != "S1":
        for t in sc.get("targets") or []:
            tgt[(t["pit"], t["mat"], int(t["month"]))] = float(t["wmt_day"] or 0)
        scen_months = {int(t["month"]) for t in sc.get("targets") or []}
        for (pit, mat, m), v in s1.items():
            if m not in scen_months and (pit, mat, m) not in tgt:
                tgt[(pit, mat, m)] = v
                if m not in filled_from_s1:
                    filled_from_s1.append(m)
    work = [r for r in rows if not (r["mat"] == "LIM" and r["otype"] == "LD")]
    ld_rows = [r for r in rows if r["mat"] == "LIM" and r["otype"] == "LD"]
    ld_rate = {}
    for r in ld_rows:
        rt = _route_rate(r, 11)
        if rt:
            ld_rate[r["contractor"]] = rt
    ld_rate.setdefault("RIM", 120.0)
    ld_rate.setdefault("SMA", 100.0)

    months_out, violations = [], []
    ld_cum = 0.0
    ld_uncapped_total = 0.0
    for m in _MONTHS:
        pool = defaultdict(float)
        for r in rows:
            pool[r["contractor"]] += r["dt"].get(m, 0)
        if not sum(pool.values()):
            continue
        used = defaultdict(float)
        alloc_rows = []
        deficit = []
        for prio, mat in ((1, "SAP"), (2, "LIM")):
            for pit in _PITS:
                T = tgt.get((pit, mat, m)) or 0
                if T <= 0:
                    continue
                grp = [r for r in work if r["pit"] == pit and r["mat"] == mat]
                base = sum(r["wmt"].get(m, 0) for r in grp)
                if not grp:
                    deficit.append({"pit": pit, "mat": mat, "wmt_day": round(T),
                                    "why": "no matrix route hauls this"})
                    continue
                for r in grp:
                    share = (r["wmt"].get(m, 0) / base) if base else 1.0 / len(grp)
                    w = T * share
                    if w <= 0:
                        continue
                    rate = _route_rate(r, m)
                    if not rate:
                        deficit.append({"pit": pit, "mat": mat, "wmt_day": round(w),
                                        "why": "no demonstrated rate for %s>%s" % (pit, r["dest"])})
                        continue
                    if pit in RIM_ONLY_PITS and r["contractor"] != "RIM":
                        violations.append("%s row with %s contractor in month %d"
                                          % (pit, r["contractor"], m))
                        continue
                    d = w / rate
                    used[r["contractor"]] += d
                    alloc_rows.append({
                        "prio": prio, "pit": pit, "mat": mat, "otype": r["otype"],
                        "dest": r["dest"], "contractor": r["contractor"],
                        "wmt_day": round(w), "dt": round(d, 1),
                        "rate_t_dt_day": round(rate, 1),
                    })
        # Lending: overflow in one contractor covered by the other's spare,
        # never into a RIM-only pit.
        lends = []
        for c in list(used):
            over = used[c] - pool[c]
            if over <= 0.01:
                continue
            for c2 in pool:
                if c2 == c:
                    continue
                spare = pool[c2] - used[c2]
                take = min(over, max(0.0, spare))
                if take <= 0:
                    continue
                movable = [a for a in alloc_rows
                           if a["contractor"] == c and a["pit"] not in RIM_ONLY_PITS]
                if not movable:
                    continue
                used[c] -= take
                used[c2] += take
                lends.append({"from": c2, "to_work_of": c, "dt": round(take, 1),
                              "note": "spare %s trucks cover %s work outside %s"
                                      % (c2, c, "/".join(RIM_ONLY_PITS))})
                over -= take
            if over > 0.01:
                deficit.append({"pit": "*", "mat": "*", "wmt_day": None,
                                "why": "%s short %.0f DT even after lending" % (c, over)})
        free = {c: max(0.0, pool[c] - used[c]) for c in pool}
        ld_day = sum(free[c] * ld_rate.get(c, 100.0) for c in free)
        ld_month_uncapped = ld_day * _DAYS[m]
        ld_uncapped_total += ld_month_uncapped
        room = max(0.0, ld_cap - ld_cum) if ld_cap else ld_month_uncapped
        ld_month = min(ld_month_uncapped, room)
        ld_cum += ld_month
        months_out.append({
            "month": m, "days": _DAYS[m],
            "pool": {c: round(v) for c, v in pool.items()},
            "dt_p1": round(sum(a["dt"] for a in alloc_rows if a["prio"] == 1), 1),
            "dt_p2": round(sum(a["dt"] for a in alloc_rows if a["prio"] == 2), 1),
            "free": {c: round(v, 1) for c, v in free.items()},
            "dt_p3": round(sum(free.values()), 1),
            "rows": alloc_rows,
            "lends": lends,
            "deficit": deficit,
            "sap_t_day": round(sum(a["wmt_day"] for a in alloc_rows if a["prio"] == 1)),
            "limtos_t_day": round(sum(a["wmt_day"] for a in alloc_rows if a["prio"] == 2)),
            "ld_t_day_capacity": round(ld_day),
            "ld_t_month_capacity": round(ld_month_uncapped),
            "ld_t_month_planned": round(ld_month),
            "ld_capped": ld_month < ld_month_uncapped - 0.5,
        })
    total = {
        "sap_t": round(sum(mo["sap_t_day"] * mo["days"] for mo in months_out)),
        "limtos_t": round(sum(mo["limtos_t_day"] * mo["days"] for mo in months_out)),
        "ld_t_capacity": round(ld_uncapped_total),
        "ld_t_planned": round(ld_cum),
        "ld_cap": ld_cap,
        "ld_cap_reached": ld_cap and ld_cum >= ld_cap - 0.5,
        "ld_shortfall_t": round(max(0.0, (ld_cap or 0) - ld_cum)),
    }
    return {
        "id": sc["id"], "label": sc.get("label") or sc["id"],
        "months": months_out, "total": total,
        "months_filled_from_s1": sorted(filled_from_s1),
        "violations": violations,
        "priority_note": "P1 SAP -> P2 LIM-TOS -> P3 LIM-LD (Tofu dump -> Huafei). "
                         "Fixed fleet: the yearly matrix's DT per contractor per month. "
                         "BLB accepts RIM only.",
    }, None


# ---------------------------------------------------------------- full Excel (all scenarios)

_PIT_SRC = {"BLB": "BLB", "KRENE": "KR", "TOFU": "TF"}


def _wf_route_key(a):
    import monthly_api as ma
    src = _PIT_SRC.get(a["pit"], a["pit"])
    src = ma._ORIGIN_MAP.get(src, src)
    return (src, ma._canon_dest(a["dest"]), a["contractor"], a["mat"], a.get("otype") or "TOS")


def _matrix_route_key(e, mstr):
    import monthly_api as ma
    src = ma._ORIGIN_MAP.get((e.get("origin") or "").upper(), (e.get("origin") or "").upper())
    return (src, ma._canon_dest(e.get("dest")), (e.get("contractor") or "").upper(),
            (e.get("material") or "").upper(), (e.get("otype") or "").upper())


def _matrix_rows_for_month(yearly, mnum):
    """Every yearly-matrix row for one month (Plan / Excel vocabulary)."""
    import monthly_api as ma
    mstr = str(int(mnum))
    out = []
    for e in (yearly or {}).get("entries") or []:
        dt = (e.get("dt") or {}).get(mstr) or (e.get("dt") or {}).get(int(mnum)) or 0
        wmt = (e.get("wmt") or {}).get(mstr) or (e.get("wmt") or {}).get(int(mnum)) or 0
        if dt <= 0 and wmt <= 0:
            continue
        src = ma._ORIGIN_MAP.get((e.get("origin") or "").upper(), (e.get("origin") or "").upper())
        dst = ma._canon_dest(e.get("dest"))
        mat = (e.get("material") or "").upper()
        otype = (e.get("otype") or "").upper()
        if mat == "SAP":
            prio = 1
        elif mat == "LIM" and otype == "TOS":
            prio = 2
        elif mat == "LIM":
            prio = 3
        else:
            prio = 9
        out.append({
            "src": src, "dst": dst, "key": "%s>%s" % (src, dst),
            "contractor": (e.get("contractor") or "").upper(),
            "material": mat, "otype": otype, "prio": prio,
            "matrix_dt": float(dt), "matrix_wmt": float(wmt),
            "route_key": (src, dst, (e.get("contractor") or "").upper(), mat, otype),
        })
    return out


def _norm_otype(otype):
    o = (otype or "").upper()
    return o if o and o != "TOS" else ""


def _saved_old_rows(month):
    """Your plan as checked — latest saved Plan allocation for this month, if any."""
    import monthly_api as ma
    raw, _src = ma._find_saved_allocation(month)
    if not isinstance(raw, dict) or not raw.get("frozen"):
        return {}
    out = {}
    for r in raw.get("rows") or []:
        k = (r.get("key") or "", (r.get("contractor") or "").upper(),
             (r.get("material") or "").upper(), _norm_otype(r.get("otype")))
        out[k] = r
    return out


def _saved_old_lookup(saved_old, mr):
    """Match saved rows even when matrix uses otype TOS and Plan save used blank."""
    sk = (mr["key"], mr["contractor"], mr["material"], _norm_otype(mr.get("otype")))
    return saved_old.get(sk)


def _compute_moves(detail):
    """Same-contractor DT moves between paths (Plan export table)."""
    moves = []
    for cont in sorted({d["contractor"] for d in detail}):
        donors = [d for d in detail if d["contractor"] == cont
                  and (d.get("dt_after") or 0) < (d.get("dt_before") or 0)]
        receivers = [d for d in detail if d["contractor"] == cont
                       and (d.get("dt_after") or 0) > (d.get("dt_before") or 0)]
        for rec in sorted(receivers, key=lambda x: x.get("prio") or 9):
            need = round((rec.get("dt_after") or 0) - (rec.get("dt_before") or 0))
            for don in sorted(donors, key=lambda x: -(x.get("dt_before") or 0)):
                if need <= 0:
                    break
                avail = round((don.get("dt_before") or 0) - (don.get("dt_after") or 0)
                              - don.get("_given", 0))
                if avail <= 0:
                    continue
                take = min(need, avail)
                don["_given"] = don.get("_given", 0) + take
                need -= take
                tag = "LIM-LD → SAP" if don.get("prio") == 3 and rec.get("prio") == 1 else (
                    "LIM-TOS → SAP" if don.get("prio") == 2 and rec.get("prio") == 1 else "rebalance")
                moves.append({
                    "contractor": cont,
                    "from": don.get("key"),
                    "to": rec.get("key"),
                    "trucks": take,
                    "tag": tag,
                    "reason": tag,
                    "same_origin": don.get("src") == rec.get("src"),
                })
    return moves


def _build_synthetic_allocation(mo, yearly, mnum, sc_id, month):
    """Frozen Plan-tab allocation from scenario waterfall — same shape as saved_plans."""
    import monthly_api as ma
    wf_map = {_wf_route_key(a): a for a in (mo.get("rows") or [])}
    saved_old = _saved_old_rows(month)
    detail = []
    seen_ld = set()
    for mr in _matrix_rows_for_month(yearly, mnum):
        saved = _saved_old_lookup(saved_old, mr)
        if saved:
            dt_b = float(saved.get("dt_before") or 0)
        elif saved_old:
            dt_b = 0.0
        else:
            dt_b = float(mr["matrix_dt"])
        wf = wf_map.get(mr["route_key"])
        if mr["prio"] == 3:
            seen_ld.add(mr["contractor"])
            dt_a = 0.0
            tgt = 0
        elif wf:
            dt_a = float(wf["dt"])
            tgt = float(wf["wmt_day"] or 0)
        else:
            dt_a = 0.0
            tgt = 0.0
        d = dict(mr, dt_before=dt_b, dt_after=dt_a, target=round(tgt))
        if saved:
            if saved.get("pred_before") is not None:
                d["pred_before_saved"] = saved["pred_before"]
            if saved.get("achv_before") is not None:
                d["achv_before_saved"] = saved["achv_before"]
            if saved.get("trips_before") is not None:
                d["trips_before_saved"] = saved["trips_before"]
        detail.append(d)
    ld_day = float(mo.get("ld_t_day_capacity") or 0)
    free_pool = {k: float(v or 0) for k, v in (mo.get("free") or {}).items()}
    free_total = sum(free_pool.values())
    for contractor, fdt in free_pool.items():
        if fdt <= 0:
            continue
        ld_paths = [d for d in detail if d["prio"] == 3 and d["contractor"] == contractor]
        ld_tgt = round(ld_day * (fdt / free_total)) if ld_day and free_total else 0
        if not ld_paths:
            detail.append({
                "src": "TF", "dst": "HUAFEI", "key": "TF>HUAFEI",
                "contractor": contractor, "material": "LIM", "otype": "LD", "prio": 3,
                "matrix_dt": 0.0, "matrix_wmt": 0.0,
                "route_key": ("TF", "HUAFEI", contractor, "LIM", "LD"),
                "dt_before": 0.0, "dt_after": fdt,
                "target": ld_tgt,
            })
            ld_paths = [detail[-1]]
        tot_b = sum(p["dt_before"] for p in ld_paths)
        for p in ld_paths:
            if tot_b > 0:
                share = p["dt_before"] / tot_b
            else:
                share = 1.0 / len(ld_paths)
            p["dt_after"] = fdt * share
            p["target"] = round(ld_tgt * share) if ld_tgt else 0
    pool = mo.get("pool") or {}
    for contractor, want in pool.items():
        rows = [d for d in detail if d["contractor"] == contractor]
        got = sum(d["dt_after"] for d in rows)
        drift = round(float(want) - got)
        if drift and rows:
            ld_rows = [d for d in rows if d.get("prio") == 3 and (d.get("dt_after") or 0) > 0]
            tgt = ld_rows[0] if ld_rows else max(rows, key=lambda x: x.get("dt_after") or 0)
            tgt["dt_after"] = max(0.0, (tgt.get("dt_after") or 0) + drift)
    detail = [d for d in detail if d["dt_before"] > 0 or d["dt_after"] > 0]
    if not detail:
        return None

    def _route_list(which):
        return [{"src": d["src"], "dst": d["dst"], "contractor": d["contractor"],
                 "dt": d[which], "key": d["key"]} for d in detail]

    before_list = _route_list("dt_before")
    after_list = _route_list("dt_after")
    pred_b, rows_b = ma._plan_predict_for_routes(before_list)
    pred_a, rows_a = ma._plan_predict_for_routes(after_list)
    sim_b, _ = ma._simulate_for_paths(before_list)
    sim_a, _ = ma._simulate_for_paths(after_list)
    sim_rows_b = (sim_b or {}).get("results") or []
    sim_rows_a = (sim_a or {}).get("results") or []

    def _achv(sim_rows, idx):
        if idx >= len(sim_rows):
            return None
        v = sim_rows[idx].get("achievable_production_t")
        return float(v) * 2 if v is not None else None

    achv_b = achv_a = 0.0
    alloc_rows = []
    for i, d in enumerate(detail):
        pr_b = rows_b[i] if i < len(rows_b) else {}
        pr_a = rows_a[i] if i < len(rows_a) else {}
        pb = d.get("pred_before_saved")
        if pb is None:
            pb = pr_b.get("wmt")
        pa = pr_a.get("wmt")
        tr_b = d.get("trips_before_saved") or pr_b.get("trips")
        tr_a = pr_a.get("trips")
        ab = d.get("achv_before_saved")
        if ab is None:
            ab = _achv(sim_rows_b, i)
        aa = _achv(sim_rows_a, i)
        if pb is not None:
            achv_b += ab or 0
        if pa is not None:
            achv_a += aa or 0
        if (d.get("dt_after") or 0) <= 0:
            continue
        rid = "%s|%s" % (d["contractor"], d["key"])
        alloc_rows.append({
            "id": rid, "key": d["key"], "contractor": d["contractor"],
            "material": d["material"], "otype": d["otype"], "prio": d["prio"],
            "target": round(d["target"]), "foreign": False,
            "dt_before": round(d["dt_before"]), "dt_after": round(d["dt_after"]),
            "pred_before": round(pb) if pb is not None else None,
            "pred_after": round(pa) if pa is not None else None,
            "achv_before": round(ab) if ab is not None else None,
            "achv_after": round(aa) if aa is not None else None,
            "achv_sim": round(aa) if aa is not None else None,
            "trips": round(tr_a) if tr_a is not None else None,
            "trips_before": round(tr_b) if tr_b is not None else None,
        })
    fleet_b = round(sum(d["dt_before"] for d in detail))
    fleet_a = round(sum(d["dt_after"] for d in detail))
    dt_res = fleet_a - sum(r.get("dt_after") or 0 for r in alloc_rows)
    if dt_res and alloc_rows:
        alloc_rows[-1]["dt_after"] = (alloc_rows[-1].get("dt_after") or 0) + dt_res
    moves = _compute_moves(detail)

    def _bucket(prio):
        rs = [r for r in alloc_rows if r.get("prio") == prio]
        if not rs:
            return {"n": 0, "target": 0, "dt_before": 0, "dt_after": 0,
                    "pred_before": 0, "pred_after": 0, "achv_before": 0, "achv_after": 0,
                    "achv_sim": 0}
        return {
            "n": len(rs),
            "target": sum(r.get("target") or 0 for r in rs),
            "dt_before": sum(r.get("dt_before") or 0 for r in rs),
            "dt_after": sum(r.get("dt_after") or 0 for r in rs),
            "pred_before": sum(r.get("pred_before") or 0 for r in rs),
            "pred_after": sum(r.get("pred_after") or 0 for r in rs),
            "achv_before": sum(r.get("achv_before") or 0 for r in rs),
            "achv_after": sum(r.get("achv_after") or 0 for r in rs),
            "achv_sim": sum(r.get("achv_after") or 0 for r in rs),
        }

    buckets = {"sap": _bucket(1), "tos": _bucket(2), "ld": _bucket(3)}
    ld_tgt = round(ld_day)
    if buckets["ld"]["target"] <= 0 and ld_tgt:
        buckets["ld"]["target"] = ld_tgt
    goals = {
        "sap": buckets["sap"]["target"],
        "tos": buckets["tos"]["target"],
        "ld": buckets["ld"]["target"] or ld_tgt,
        "total": buckets["sap"]["target"] + buckets["tos"]["target"]
                 + (buckets["ld"]["target"] or ld_tgt),
    }
    moved = sum(m.get("trucks") or 0 for m in moves)
    return {
        "frozen": True,
        "horizon": "day",
        "target_label": "scenario mine plan",
        "old": {"pred": round(pred_b), "achv": round(achv_b), "dt": fleet_b},
        "new": {"pred": round(pred_a), "achv": round(achv_a), "dt": fleet_a,
                "target": goals["total"]},
        "fleet": {"before": fleet_b, "after": fleet_a},
        "goals": goals,
        "buckets": buckets,
        "rows": alloc_rows,
        "moves": moves,
        "moved_total": moved,
        "notes": "Scenario %s · same fleet · scenario targets only (P1→P2→P3 waterfall)"
                   % sc_id,
    }


def _scenario_month_card(sc, mo, year, mnum, yearly):
    import monthly_api as ma
    month = "%s-%02d" % (year, int(mnum))
    n = len(ma._days_in(month))
    raw = _build_synthetic_allocation(mo, yearly, mnum, sc["id"], month)
    if not raw:
        return None
    view = ma._alloc_view(raw, n, "scenario:%s" % sc["id"], include_detail=False)
    tgt_day = ((mo.get("sap_t_day") or 0) + (mo.get("limtos_t_day") or 0)
               + (mo.get("ld_t_day_capacity") or 0))
    return {
        "month": month,
        "name": ma._MONTH_LABELS.get(int(mnum), month),
        "n_days": n,
        "target_day": round(tgt_day),
        "target_month": round(tgt_day * n),
        "has_alloc": bool(view),
        "alloc": view,
        "alloc_raw": raw,
        "alloc_source": "scenario:%s" % sc["id"],
        "synthetic": True,
    }


def _scenario_year_cards(sc, year):
    """Year board cards for S2+ from the waterfall (S1 uses saved Plan allocations)."""
    import monthly_api as ma
    yearly = _load_yearly()
    if not yearly:
        return None, "no yearly matrix loaded yet"
    res, err = waterfall(sc, yearly)
    if err:
        return None, err
    mo_by = {mo["month"]: mo for mo in res.get("months") or []}
    mnums = set(int(m) for m in (yearly.get("months") or []))
    mnums.update(mo_by.keys())
    mnums.update(_MONTHS)
    cards = []
    for mnum in sorted(mnums):
        if mnum < 1 or mnum > 12:
            continue
        mo = mo_by.get(mnum)
        if not mo:
            continue
        card = _scenario_month_card(sc, mo, year, mnum, yearly)
        if card:
            cards.append(card)
    if not cards:
        return None, "no months to export for %s" % sc.get("id")
    return cards, None


def _scenario_results_for_export():
    ids = ["S1"] + [s for s in _scenario_ids() if s != "S1"]
    results = []
    for sid in ids:
        sc = _load_scenario(sid)
        if not sc:
            continue
        res, err = waterfall(sc)
        if not err:
            results.append(res)
    return results


def _write_compare_sheet(ws, results):
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    bold = Font(bold=True)
    head_fill = PatternFill("solid", fgColor="1F2937")
    head_font = Font(bold=True, color="FFFFFF")
    num = "#,##0"
    ws.append(["Mine-plan scenarios - same fleet, different allocation"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append(["Waterfall: P1 SAP -> P2 LIM-TOS -> P3 LIM-LD (Tofu dump -> Huafei), "
               "cap %s t. BLB accepts RIM only. Fleet = yearly matrix DT per contractor."
               % format(LIM_LD_CAP_T, ",")])
    ws.append([])
    hdr = ["", ""]
    for r in results:
        hdr += [r["label"], "", "", ""]
    ws.append(hdr)
    sub = ["Month", "Fleet (RIM+SMA)"]
    for _ in results:
        sub += ["P1 SAP DT", "P2 LIM-TOS DT", "P3 free DT", "LIM-LD t"]
    ws.append(sub)
    for c in range(1, len(sub) + 1):
        ws.cell(row=5, column=c).fill = head_fill
        ws.cell(row=5, column=c).font = head_font
        top = ws.cell(row=4, column=c)
        if top.value:
            top.font = bold
    if not results:
        return
    for i, mo0 in enumerate(results[0]["months"]):
        m = mo0["month"]
        pool = mo0["pool"]
        row = [_MONN.get(m, m), "%d (%d+%d)" % (sum(pool.values()),
                                                pool.get("RIM", 0), pool.get("SMA", 0))]
        for r in results:
            mo = r["months"][i] if i < len(r["months"]) else {}
            row += [round(mo.get("dt_p1", 0)), round(mo.get("dt_p2", 0)),
                    round(mo.get("dt_p3", 0)),
                    mo.get("ld_t_month_planned", 0)]
        ws.append(row)
    tot = ["Total", ""]
    for r in results:
        t = r["total"]
        tot += ["", "", "", t["ld_t_planned"]]
    ws.append(tot)
    ws.cell(row=ws.max_row, column=1).font = bold
    ws.append([])
    for label, key in (("SAP moved (t)", "sap_t"), ("LIM-TOS moved (t)", "limtos_t"),
                       ("LIM-LD planned (t)", "ld_t_planned"),
                       ("LIM-LD uncapped capacity (t)", "ld_t_capacity"),
                       ("8 Mt cap reached", "ld_cap_reached"),
                       ("Short of cap by (t)", "ld_shortfall_t")):
        row = [label, ""]
        for r in results:
            v = r["total"][key]
            row += ["", "", "", ("YES" if v else "no") if key == "ld_cap_reached" else v]
        ws.append(row)
        ws.cell(row=ws.max_row, column=1).font = bold
    for row in ws.iter_rows(min_row=6):
        for cell in row:
            if isinstance(cell.value, (int, float)) and abs(cell.value) >= 1000:
                cell.number_format = num
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 16
    for c in range(3, len(sub) + 1):
        ws.column_dimensions[get_column_letter(c)].width = 13


def _xlsx_scenarios_zip(year):
    """One monthly_plan_YYYY.xlsx per scenario — identical layout to /api/monthly/export-year."""
    import monthly_api as ma
    import zipfile
    buf = io.BytesIO()
    ids = ["S1"] + [s for s in _scenario_ids() if s != "S1"]
    written = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for sid in ids:
            sc = _load_scenario(sid)
            if not sc:
                continue
            if sid == "S1":
                _, cards = ma._year_cards(year)
            else:
                cards, err = _scenario_year_cards(sc, year)
                if err or not cards:
                    continue
            wb = ma._xlsx_year_book(year, cards)
            xbuf = io.BytesIO()
            wb.save(xbuf)
            fname = ("monthly_plan_%s.xlsx" % year if sid == "S1"
                     else "monthly_plan_%s_%s.xlsx" % (year, sid))
            zf.writestr(fname, xbuf.getvalue())
            written += 1
    if not written:
        return None, "no scenario workbooks could be built — load the matrix and import scenarios"
    buf.seek(0)
    return buf, None


# ---------------------------------------------------------------- routes

@bp.route("/api/scenarios")
def api_scenarios():
    ids = ["S1"] + [s for s in _scenario_ids() if s != "S1"]
    out = []
    for sid in ids:
        sc = _load_scenario(sid)
        if sc:
            out.append({"id": sc["id"], "label": sc.get("label") or sc["id"],
                        "source": sc.get("source"), "derived": bool(sc.get("derived")),
                        "loaded_at": sc.get("loaded_at")})
    return jsonify({"ok": True, "scenarios": out})


@bp.route("/api/scenarios/<sid>")
def api_scenario_one(sid):
    sc = _load_scenario(_safe_id(sid))
    if not sc:
        return jsonify({"ok": False, "error": "no such scenario"}), 404
    return jsonify({"ok": True, "scenario": sc})


@bp.route("/api/scenarios/<sid>", methods=["DELETE"])
def api_scenario_delete(sid):
    sid = _safe_id(sid)
    if sid == "S1":
        return jsonify({"ok": False, "error": "S1 is the live plan - it cannot be deleted"}), 400
    p = _scen_path(sid)
    if not p or not os.path.isfile(p):
        return jsonify({"ok": False, "error": "no such scenario"}), 404
    os.remove(p)
    return jsonify({"ok": True, "deleted": sid})


@bp.route("/api/scenarios/import", methods=["POST"])
def api_scenarios_import():
    """Upload the mine-plan workbook; every 'Scenario N' sheet-row group becomes a scenario."""
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "upload the mine-plan .xlsx"}), 400
    data = f.read()
    if not data:
        return jsonify({"ok": False, "error": "the file is empty"}), 400
    from openpyxl import load_workbook
    try:
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception:  # noqa: BLE001
        return jsonify({"ok": False, "error": "could not read that file as .xlsx"}), 400
    ws = None
    for name in wb.sheetnames:
        if "plan db" in name.lower():
            ws = wb[name]
            break
    if ws is None:
        ws = wb.active
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    scens, err = _parse_mine_plan_db(rows, f.filename)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    saved = []
    for sc in scens:
        if sc["id"] == "S1":
            continue  # never overwrite the live plan
        _save_scenario(sc)
        saved.append(sc["id"])
    return jsonify({"ok": True, "imported": saved,
                    "skipped_s1": any(s["id"] == "S1" for s in scens)})


@bp.route("/api/scenarios/<sid>/allocate")
def api_scenario_allocate(sid):
    sc = _load_scenario(_safe_id(sid))
    if not sc:
        return jsonify({"ok": False, "error": "no such scenario"}), 404
    res, err = waterfall(sc)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    return jsonify({"ok": True, "allocation": res})


@bp.route("/api/scenarios/compare")
def api_scenarios_compare():
    ids = request.args.get("ids")
    ids = [_safe_id(s) for s in ids.split(",")] if ids else (["S1"] + _scenario_ids())
    seen, out, errors = set(), [], []
    for sid in ids:
        if not sid or sid in seen:
            continue
        seen.add(sid)
        sc = _load_scenario(sid)
        if not sc:
            errors.append({"id": sid, "error": "no such scenario"})
            continue
        res, err = waterfall(sc)
        if err:
            errors.append({"id": sid, "error": err})
            continue
        out.append(res)
    return jsonify({"ok": True, "scenarios": out, "errors": errors,
                    "ld_cap": LIM_LD_CAP_T})


_MONN = {8: "Aug", 9: "Sept", 10: "Oct", 11: "Nov", 12: "Dec"}


# ------------------------------------------------- monthly-plan workbook

@bp.route("/api/scenarios/<sid>/export-monthly")
def api_scenario_export_monthly(sid):
    """One scenario as the monthly_plan_YYYY.xlsx workbook (Year dashboard +
    one old-vs-new sheet per month). Same builder as /api/scenarios/export-full
    - ONE renderer of the concept, per the capacity-card lesson."""
    import monthly_api as ma

    sid = _safe_id(sid)
    sc = _load_scenario(sid)
    if not sc:
        return jsonify({"ok": False, "error": "no such scenario"}), 404
    year = (request.args.get("year") or str(datetime.utcnow().year)).strip()
    if not re.fullmatch(r"\d{4}", year):
        return jsonify({"ok": False, "error": "year=YYYY"}), 400
    if sid == "S1":
        _, cards = ma._year_cards(year)
        if not cards:
            return jsonify({"ok": False, "error":
                            "nothing stored for %s - load a matrix and build the year first" % year}), 404
    else:
        cards, err = _scenario_year_cards(sc, year)
        if err:
            return jsonify({"ok": False, "error": err}), 400
    name = ("monthly_plan_%s.xlsx" % year if sid == "S1"
            else "monthly_plan_%s_%s.xlsx" % (year, sid))
    return ma._xlsx_send(ma._xlsx_year_book(year, cards), name)


@bp.route("/api/scenarios/export")
def api_scenarios_export():
    """One workbook: Compare sheet + a full-allocation sheet per scenario."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    from flask import send_file

    results = _scenario_results_for_export()
    if not results:
        return jsonify({"ok": False, "error": "no scenarios to export"}), 404

    bold = Font(bold=True)
    head_fill = PatternFill("solid", fgColor="1F2937")
    head_font = Font(bold=True, color="FFFFFF")
    num = "#,##0"

    wb = Workbook()
    ws = wb.active
    ws.title = "Compare"
    _write_compare_sheet(ws, results)

    for r in results:
        d = wb.create_sheet(r["id"][:28])
        d.append([r["label"] + " - full DT allocation"])
        d["A1"].font = Font(bold=True, size=13)
        if r["months_filled_from_s1"]:
            d.append(["Months taken from S1 (not in this scenario's file): "
                      + ", ".join(_MONN.get(m, str(m)) for m in r["months_filled_from_s1"])])
        d.append([])
        cols = ["Month", "Priority", "Pit", "Material", "Destination", "Contractor",
                "t/day", "DT", "t/DT/day"]
        d.append(cols)
        hr = d.max_row
        for c in range(1, len(cols) + 1):
            d.cell(row=hr, column=c).fill = head_fill
            d.cell(row=hr, column=c).font = head_font
        for mo in r["months"]:
            mn = _MONN.get(mo["month"], mo["month"])
            for a in mo["rows"]:
                d.append([mn, "P%d" % a["prio"], a["pit"],
                          a["mat"] + ("-" + a["otype"] if a["otype"] not in ("", "TOS") else ""),
                          a["dest"], a["contractor"], a["wmt_day"], a["dt"],
                          a["rate_t_dt_day"]])
            free_txt = " + ".join("%s %d" % (c, round(v)) for c, v in mo["free"].items())
            d.append([mn, "P3", "TOFU", "LIM-LD", "HUAFEI", free_txt,
                      mo["ld_t_day_capacity"], round(mo["dt_p3"], 1), ""])
            d.cell(row=d.max_row, column=2).font = bold
            for l in mo["lends"]:
                d.append([mn, "", "", "lend", "", "%s -> %s work" % (l["from"], l["to_work_of"]),
                          "", l["dt"], l["note"]])
            for df in mo["deficit"]:
                d.append([mn, "", df["pit"], df["mat"], "DEFICIT", "", df.get("wmt_day") or "",
                          "", df["why"]])
        for row in d.iter_rows(min_row=hr + 1):
            for cell in row:
                if isinstance(cell.value, (int, float)) and abs(cell.value) >= 1000:
                    cell.number_format = num
        widths = [8, 8, 8, 10, 14, 22, 11, 9, 40]
        for c, w in enumerate(widths, start=1):
            d.column_dimensions[get_column_letter(c)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    name = "scenario_compare_%s.xlsx" % datetime.utcnow().strftime("%Y%m%d")
    return send_file(buf, as_attachment=True, download_name=name,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.route("/api/scenarios/export-full")
def api_scenarios_export_full():
    """Zip of monthly_plan workbooks — one file per scenario, same layout as S1 export."""
    from flask import send_file
    year = (request.args.get("year") or str(datetime.utcnow().year)).strip()
    if not re.fullmatch(r"\d{4}", year):
        return jsonify({"ok": False, "error": "year=YYYY"}), 400
    buf, err = _xlsx_scenarios_zip(year)
    if err:
        return jsonify({"ok": False, "error": err}), 404
    name = "mine_plan_scenarios_%s_%s.zip" % (year, datetime.utcnow().strftime("%Y%m%d"))
    return send_file(buf, as_attachment=True, download_name=name,
                     mimetype="application/zip")
