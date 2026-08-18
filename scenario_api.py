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
