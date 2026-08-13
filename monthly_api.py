"""Monthly plan roll-up + comparison (owner 2026-08-13).

"when we make a plan, and it is for one day ... we want to use continuous
plan for the whole month ... we have an Excel file in which we made a plan
for the whole month ... you have to compare these plans ... make an Excel
file out of this, which showing our prediction model plans and the normal
plans, and also the charts on that one. So better make a new page for that."

Design:
  • A month is built from ONE saved daily plan (data/saved_plans/DATE.json):
    the same holding plan runs every day of the month. Day = 2 × 12 h shifts,
    so the daily figure is the saved per-shift prediction × 2 (the plan page's
    meta.predict totals are per shift). Nothing is invented beyond that.
  • The "manual" plan (the owner's Excel, made from historical trips with no
    variables) is uploaded as .xlsx/.csv or pasted; per-day rows are matched
    by date. Its numbers are stored verbatim.
  • Comparison + export: one xlsx with a data sheet and native Excel charts
    (daily WMT lines, cumulative, and the daily gap), so it opens ready-made
    in the owner's normal workflow.

State lives in data/monthly_plans/YYYY-MM.json, one file per month, same
local-disk pattern as saved_plans.
"""

import calendar
import io
import json
import os
import re
from datetime import date, datetime

from flask import Blueprint, jsonify, request, send_file

bp = Blueprint("monthly_api", __name__)

_ROOT = os.path.dirname(os.path.abspath(__file__))
_SAVED_DIR = os.path.join(_ROOT, "data", "saved_plans")
_MONTH_DIR = os.path.join(_ROOT, "data", "monthly_plans")


def _month_path(month):
    # \d{2} alone let "2026-13" through to calendar.monthrange -> 500
    # (found in the failure-mode battery). Month must be 01-12.
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month or ""):
        return None
    return os.path.join(_MONTH_DIR, month + ".json")


def _load_state(month):
    p = _month_path(month)
    if not p or not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _save_state(month, state):
    p = _month_path(month)
    os.makedirs(_MONTH_DIR, exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1)
        f.write("\n")
    os.replace(tmp, p)


def _days_in(month):
    y, m = int(month[:4]), int(month[5:7])
    return [date(y, m, d).isoformat() for d in range(1, calendar.monthrange(y, m)[1] + 1)]


@bp.route("/api/monthly/state")
def api_monthly_state():
    month = (request.args.get("month") or "").strip()
    if not _month_path(month):
        return jsonify({"ok": False, "error": "supply month=YYYY-MM"}), 400
    st = _load_state(month)
    return jsonify({"ok": True, "month": month, "state": st, "exists": st is not None})


@bp.route("/api/monthly/months")
def api_monthly_months():
    out = []
    if os.path.isdir(_MONTH_DIR):
        for f in sorted(os.listdir(_MONTH_DIR), reverse=True):
            if f.endswith(".json"):
                out.append(f[:-5])
    return jsonify({"ok": True, "months": out})


@bp.route("/api/monthly/build", methods=["POST"])
def api_monthly_build():
    """Roll one saved daily plan across a month (prediction side)."""
    body = request.get_json(silent=True) or {}
    month = (body.get("month") or "").strip()
    src_date = (body.get("source_date") or "").strip()
    if not _month_path(month):
        return jsonify({"ok": False, "error": "supply month=YYYY-MM"}), 400
    sp = os.path.join(_SAVED_DIR, src_date + ".json")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", src_date) or not os.path.isfile(sp):
        return jsonify({"ok": False, "error": "no saved plan for %s" % src_date}), 404
    with open(sp, encoding="utf-8") as f:
        plan = json.load(f)
    meta = plan.get("meta") or {}
    pred = meta.get("predict") or {}
    per_shift_wmt = float(pred.get("wmt") or 0)
    per_shift_trips = float(pred.get("trips") or 0)
    achievable = meta.get("sim_achievable")
    if not per_shift_wmt:
        return jsonify({"ok": False, "error": "saved plan for %s carries no prediction totals - open it in the Plan tab and re-save" % src_date}), 400
    # Day = 2 x 12 h shifts. Same plan every day; rain is whatever the plan was
    # saved with (labelled, not hidden).
    day_wmt = per_shift_wmt * 2
    day_trips = per_shift_trips * 2
    days = [{"date": d, "wmt": round(day_wmt), "trips": round(day_trips)} for d in _days_in(month)]
    st = _load_state(month) or {"month": month}
    st["prediction"] = {
        "source_date": src_date,
        "per_shift_wmt": round(per_shift_wmt),
        "per_day_wmt": round(day_wmt),
        "dt": pred.get("dt"),
        "rain_mm": plan.get("rain_mm"),
        "sim_achievable_shift": achievable,
        "paths": [
            {"key": p.get("key"), "contractor": p.get("contractor"),
             "dt": p.get("dt"), "material": p.get("material"),
             "wbSel": p.get("wbSel")}
            for p in (plan.get("paths") or {}).values()
        ],
        "days": days,
        "built_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": ("Same holding plan every day; day = 2 x 12 h shifts x saved "
                 "per-shift prediction. Rain fixed at the saved plan's value."),
    }
    _save_state(month, st)
    return jsonify({"ok": True, "month": month, "state": st})


def _parse_manual_rows(rows, month):
    """[[cell,...],...] -> [{date, wmt, trips?}] for days in the month.

    Header detection is forgiving: a date-ish column plus a tonnage-ish column
    (wmt/tonnage/tons/production). Day numbers (1..31) also accepted."""
    days = _days_in(month)
    out, header = {}, None
    for r in rows:
        cells = ["" if c is None else str(c).strip() for c in r]
        if not any(cells):
            continue
        low = [c.lower() for c in cells]
        if header is None and any(re.search(r"date|day|tanggal", c) for c in low) \
           and any(re.search(r"wmt|ton|prod", c) for c in low):
            di = next(i for i, c in enumerate(low) if re.search(r"date|day|tanggal", c))
            wi = next(i for i, c in enumerate(low) if re.search(r"wmt|ton|prod", c))
            ti = next((i for i, c in enumerate(low) if re.search(r"trip", c)), None)
            header = (di, wi, ti)
            continue
        di, wi, ti = header if header else (0, 1, None)
        if len(cells) <= max(di, wi):
            continue
        dcell, wcell = cells[di], cells[wi]
        iso = None
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", dcell)
        if m:
            iso = m.group(0)
        elif re.fullmatch(r"\d{1,2}(\.0)?", dcell):
            n = int(float(dcell))
            if 1 <= n <= len(days):
                iso = days[n - 1]
        else:
            m = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", dcell)
            if m:  # d/m/yyyy
                try:
                    iso = date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
                except ValueError:
                    pass
        if not iso or not iso.startswith(month):
            continue
        try:
            wmt = float(re.sub(r"[^\d.\-]", "", wcell) or 0)
        except ValueError:
            continue
        rec = {"date": iso, "wmt": round(wmt)}
        if ti is not None and len(cells) > ti and cells[ti]:
            try:
                rec["trips"] = round(float(re.sub(r"[^\d.\-]", "", cells[ti])))
            except ValueError:
                pass
        out[iso] = rec
    return [out[d] for d in days if d in out]


@bp.route("/api/monthly/manual", methods=["POST"])
def api_monthly_manual():
    """Manual (Excel) plan: file upload (xlsx/csv) or pasted rows."""
    month = (request.form.get("month") or (request.get_json(silent=True) or {}).get("month") or "").strip()
    if not _month_path(month):
        return jsonify({"ok": False, "error": "supply month=YYYY-MM"}), 400
    rows, src_name = [], None
    f = request.files.get("file")
    if f and f.filename:
        src_name = f.filename
        data = f.read()
        if not data:
            return jsonify({"ok": False, "error": "the file is empty"}), 400
        if f.filename.lower().endswith((".xlsx", ".xlsm")):
            from openpyxl import load_workbook
            try:
                wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            except Exception:  # noqa: BLE001 — corrupt/renamed file, not an xlsx
                return jsonify({"ok": False, "error": "could not read that file as .xlsx - is it really an Excel file?"}), 400
            ws = wb.active
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
        else:  # csv / tsv
            text = data.decode("utf-8", "replace")
            lines = text.splitlines()
            if not lines:
                return jsonify({"ok": False, "error": "the file is empty"}), 400
            sep = "\t" if "\t" in lines[0] else ","
            rows = [line.split(sep) for line in lines]
    else:
        body = request.get_json(silent=True) or {}
        text = body.get("pasted") or ""
        src_name = "pasted"
        sep = "\t" if "\t" in text else ","
        rows = [line.split(sep) for line in text.splitlines()]
    days = _parse_manual_rows(rows, month)
    if not days:
        return jsonify({"ok": False, "error": "could not find any %s rows - need a date (or day number 1-31) column and a WMT/tonnage column" % month}), 400
    st = _load_state(month) or {"month": month}
    st["manual"] = {"source": src_name, "days": days,
                    "loaded_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")}
    _save_state(month, st)
    return jsonify({"ok": True, "month": month, "state": st, "parsedDays": len(days)})


@bp.route("/api/monthly/clear", methods=["POST"])
def api_monthly_clear():
    body = request.get_json(silent=True) or {}
    month = (body.get("month") or "").strip()
    which = body.get("which")  # 'prediction' | 'manual' | 'all'
    p = _month_path(month)
    if not p:
        return jsonify({"ok": False, "error": "supply month=YYYY-MM"}), 400
    st = _load_state(month)
    if st:
        if which == "all" and os.path.isfile(p):
            os.remove(p)
            st = None
        elif which in ("prediction", "manual"):
            st.pop(which, None)
            _save_state(month, st)
    return jsonify({"ok": True, "month": month, "state": st})


@bp.route("/api/monthly/export")
def api_monthly_export():
    """One xlsx: comparison sheet + native Excel charts."""
    month = (request.args.get("month") or "").strip()
    st = _load_state(month)
    if not st:
        return jsonify({"ok": False, "error": "nothing stored for %s" % month}), 404
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, LineChart, Reference
    from openpyxl.styles import Font
    from openpyxl.utils import get_column_letter

    pred = {d["date"]: d for d in ((st.get("prediction") or {}).get("days") or [])}
    man = {d["date"]: d for d in ((st.get("manual") or {}).get("days") or [])}
    days = _days_in(month)

    wb = Workbook()
    ws = wb.active
    ws.title = "Daily comparison"
    head = ["Date", "Prediction WMT (t/day)", "Manual plan WMT (t/day)",
            "Difference (t)", "Prediction cumulative (t)", "Manual cumulative (t)"]
    ws.append(head)
    for c in range(1, len(head) + 1):
        ws.cell(row=1, column=c).font = Font(bold=True)
    cp = cm = 0
    for d in days:
        pw = pred.get(d, {}).get("wmt")
        mw = man.get(d, {}).get("wmt")
        cp += pw or 0
        cm += mw or 0
        ws.append([d, pw, mw,
                   (pw - mw) if (pw is not None and mw is not None) else None,
                   cp if pred else None, cm if man else None])
    last = ws.max_row
    ws.append([])
    ws.append(["TOTAL", cp or None, cm or None,
               (cp - cm) if (pred and man) else None])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    for i, w in enumerate([12, 22, 22, 14, 24, 20], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Chart 1: daily lines
    lc = LineChart()
    lc.title = "Daily WMT - prediction vs manual plan"
    lc.y_axis.title = "t/day"
    lc.height, lc.width = 9, 28
    data = Reference(ws, min_col=2, max_col=3, min_row=1, max_row=last)
    cats = Reference(ws, min_col=1, min_row=2, max_row=last)
    lc.add_data(data, titles_from_data=True)
    lc.set_categories(cats)
    ws.add_chart(lc, "H2")

    # Chart 2: cumulative
    cc = LineChart()
    cc.title = "Cumulative WMT over the month"
    cc.y_axis.title = "t"
    cc.height, cc.width = 9, 28
    data2 = Reference(ws, min_col=5, max_col=6, min_row=1, max_row=last)
    cc.add_data(data2, titles_from_data=True)
    cc.set_categories(cats)
    ws.add_chart(cc, "H22")

    # Chart 3: daily gap
    bc = BarChart()
    bc.title = "Daily gap (prediction - manual)"
    bc.y_axis.title = "t"
    bc.height, bc.width = 9, 28
    data3 = Reference(ws, min_col=4, min_row=1, max_row=last)
    bc.add_data(data3, titles_from_data=True)
    bc.set_categories(cats)
    ws.add_chart(bc, "H42")

    # Sheet 2: the basis, spelled out
    ws2 = wb.create_sheet("Basis")
    p = st.get("prediction") or {}
    m = st.get("manual") or {}
    ws2.append(["Prediction side"])
    ws2.cell(row=1, column=1).font = Font(bold=True)
    ws2.append(["Built from saved daily plan", p.get("source_date")])
    ws2.append(["Per-shift WMT", p.get("per_shift_wmt")])
    ws2.append(["Per-day WMT (2 shifts)", p.get("per_day_wmt")])
    ws2.append(["Fleet (DT)", p.get("dt")])
    ws2.append(["Rain (mm, fixed)", p.get("rain_mm")])
    ws2.append(["Note", p.get("note")])
    ws2.append([])
    ws2.append(["Paths in the plan"])
    ws2.cell(row=ws2.max_row, column=1).font = Font(bold=True)
    has_perpath = any(row.get("manual_wmt_day") is not None or row.get("pred_wmt_day") is not None
                      for row in (p.get("paths") or []))
    if has_perpath:
        ws2.append(["Path", "Contractor", "DT", "Material", "Weighbridges",
                    "Plan WMT/day", "Engine WMT/day", "Engine - Plan"])
        for row in (p.get("paths") or []):
            mw, pw = row.get("manual_wmt_day"), row.get("pred_wmt_day")
            ws2.append([row.get("key"), row.get("contractor"), row.get("dt"),
                        row.get("material"), ",".join(row.get("wbSel") or []),
                        mw, pw,
                        (pw - mw) if (pw is not None and mw is not None) else None])
    else:
        ws2.append(["Path", "Contractor", "DT", "Material", "Weighbridges"])
        for row in (p.get("paths") or []):
            ws2.append([row.get("key"), row.get("contractor"), row.get("dt"),
                        row.get("material"), ",".join(row.get("wbSel") or [])])
    ws2.append([])
    ws2.append(["Manual side"])
    ws2.cell(row=ws2.max_row, column=1).font = Font(bold=True)
    ws2.append(["Source", m.get("source")])
    ws2.append(["Days parsed", len(m.get("days") or [])])
    ws2.column_dimensions["A"].width = 30
    ws2.column_dimensions["B"].width = 28

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name="monthly_plan_comparison_%s.xlsx" % month,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ── Yearly plan matrix (owner 2026-08-13) ────────────────────────────────────
# "i will not paste for whole month, but paste for one day plan, this is my
#  whole plan for this year ... its one day for each month and we have to
#  calculate for the whole month."
#
# The matrix is the mine-planning export: rows = ORIGIN/MATERIAL/ACTIVITY/
# ORIGIN_TYPE/DESTINATION/CONTRACTOR with merged-cell carry-down, a Values
# column alternating WMT/day and NB_DT_, and one column per month. Subtotal
# rows ("LIM WMT/day", "BLB WMT/day", "Total WMT/day") are skipped because
# their Values cell is not exactly WMT/day / NB_DT_. Parser verified against
# the owner's own totals: Aug 83,988/581 vs stated 83,989/579 (their subtotal
# rounding), Dec 208,408/1,281 vs 208,407/1,280.
#
# One matrix load fills BOTH sides of every month it covers:
#   manual side     = the matrix's own WMT/day × days in month (verbatim)
#   prediction side = the SAME fleet (NB_DT_) run through plan_simulator's
#                     measured engine (achievable t/shift × 2 shifts × days)

_MONTH_NAMES = {"january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
                "june": 6, "july": 7, "august": 8, "september": 9,
                "october": 10, "november": 11, "december": 12}

_YEARLY_PATH = os.path.join(_MONTH_DIR, "yearly_matrix.json")

# Matrix labels -> the engine's route vocabulary (route_lookup.csv).
_ORIGIN_MAP = {"TOFU": "TF"}


def _canon_dest(d):
    d = re.sub(r"\s+", " ", (d or "").strip().upper())
    d = d.replace("KM 0", "KM0").replace("KM 15", "KM15").replace("KM 10", "KM10")
    return d


def _num(s):
    s = re.sub(r"[^\d.]", "", str(s or ""))
    return float(s) if s else None


def _parse_yearly_matrix(rows):
    hdr = None
    for i, r in enumerate(rows):
        low = [str(c or "").strip().lower() for c in r]
        if "values" in low and any(c in _MONTH_NAMES for c in low):
            hdr = i
            break
    if hdr is None:
        return None, "no header row found (need a 'Values' column plus month columns like August, September...)"
    h = rows[hdr]
    low = [str(c or "").strip().lower() for c in h]
    vcol = low.index("values")
    mcols = {j: _MONTH_NAMES[c] for j, c in enumerate(low) if c in _MONTH_NAMES}
    if not mcols:
        return None, "no month columns found"
    carry = {"origin": "", "material": "", "activity": "", "otype": "", "dest": "", "contractor": ""}
    entries, pending = [], None
    for r in rows[hdr + 1:]:
        cells = [str(c or "").strip() for c in r] + [""] * 12
        v = cells[vcol]
        if v == "WMT/day":
            for k, idx in (("origin", 0), ("material", 1), ("activity", 2),
                           ("otype", 3), ("dest", 4), ("contractor", 5)):
                if cells[idx]:
                    carry[k] = cells[idx]
            pending = {"origin": carry["origin"], "material": carry["material"],
                       "activity": carry["activity"], "otype": carry["otype"],
                       "dest": carry["dest"], "contractor": carry["contractor"],
                       "wmt": {str(m): _num(cells[j]) for j, m in mcols.items()},
                       "dt": {}}
            entries.append(pending)
        elif v == "NB_DT_" and pending is not None:
            pending["dt"] = {str(m): _num(cells[j]) for j, m in mcols.items()}
            pending = None
    entries = [e for e in entries if any(e["wmt"].values()) or any(e["dt"].values())]
    if not entries:
        return None, "found the header but no WMT/day / NB_DT_ row pairs under it"
    return {"entries": entries, "months": sorted({int(m) for e in entries for m, v in e["wmt"].items() if v})}, None


@bp.route("/api/monthly/yearly", methods=["GET", "POST"])
def api_monthly_yearly():
    if request.method == "GET":
        if not os.path.isfile(_YEARLY_PATH):
            return jsonify({"ok": True, "exists": False})
        with open(_YEARLY_PATH, encoding="utf-8") as fh:
            return jsonify({"ok": True, "exists": True, "yearly": json.load(fh)})
    rows, src_name = [], "pasted"
    f = request.files.get("file")
    if f and f.filename:
        src_name = f.filename
        data = f.read()
        if not data:
            return jsonify({"ok": False, "error": "the file is empty"}), 400
        if f.filename.lower().endswith((".xlsx", ".xlsm")):
            from openpyxl import load_workbook
            try:
                wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            except Exception:  # noqa: BLE001
                return jsonify({"ok": False, "error": "could not read that file as .xlsx"}), 400
            ws = wb.active
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
        else:
            text = data.decode("utf-8", "replace")
            rows = [l.split("\t" if "\t" in text else ",") for l in text.splitlines()]
    else:
        body = request.get_json(silent=True) or {}
        text = body.get("pasted") or ""
        if not text.strip():
            return jsonify({"ok": False, "error": "paste the matrix or upload the file"}), 400
        rows = [l.split("\t" if "\t" in text else ",") for l in text.splitlines()]
    parsed, err = _parse_yearly_matrix(rows)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    parsed["source"] = src_name
    parsed["loaded_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(_MONTH_DIR, exist_ok=True)
    with open(_YEARLY_PATH, "w", encoding="utf-8") as fh:
        json.dump(parsed, fh, indent=1)
    return jsonify({"ok": True, "months": parsed["months"], "routes": len(parsed["entries"])})


@bp.route("/api/monthly/build-from-yearly", methods=["POST"])
def api_monthly_build_from_yearly():
    """One month, both sides, from the loaded yearly matrix."""
    body = request.get_json(silent=True) or {}
    month = (body.get("month") or "").strip()
    if not _month_path(month):
        return jsonify({"ok": False, "error": "supply month=YYYY-MM"}), 400
    if not os.path.isfile(_YEARLY_PATH):
        return jsonify({"ok": False, "error": "no yearly matrix loaded yet"}), 404
    with open(_YEARLY_PATH, encoding="utf-8") as fh:
        yearly = json.load(fh)
    mnum = str(int(month[5:7]))
    active = [e for e in yearly["entries"]
              if (e["wmt"].get(mnum) or 0) > 0 or (e["dt"].get(mnum) or 0) > 0]
    if not active:
        return jsonify({"ok": False, "error": "the matrix has no rows for month %s" % month}), 400
    # Group to engine routes: same origin+dest+contractor lines merge (the
    # matrix splits them by ACTIVITY/ORIGIN_TYPE, the road does not care).
    routes = {}
    for e in active:
        src = _ORIGIN_MAP.get(e["origin"].upper(), e["origin"].upper())
        dst = _canon_dest(e["dest"])
        key = (src, dst, e["contractor"].upper())
        rec = routes.setdefault(key, {"src": src, "dst": dst,
                                      "contractor": e["contractor"].upper(),
                                      "dt": 0.0, "wmt_day": 0.0, "materials": set()})
        rec["dt"] += e["dt"].get(mnum) or 0
        rec["wmt_day"] += e["wmt"].get(mnum) or 0
        if e.get("material"):
            rec["materials"].add(e["material"])
    plans = [{"route": "%s>%s" % (r["src"], r["dst"]), "source": r["src"],
              "destination": r["dst"], "n_trucks": int(round(r["dt"])),
              "contractor": r["contractor"]}
             for r in routes.values() if r["dt"] > 0]
    import plan_simulator
    sim = plan_simulator.simulate({"plans": plans})
    if sim.get("error"):
        return jsonify({"ok": False, "error": sim["error"]}), 500
    # Match results BY INDEX: simulate() preserves plan order, and a route key
    # is NOT unique (TF>HUAFEI runs for both RIM and SMA - a dict keyed by
    # route silently gave both rows the last row's tonnage; caught in testing).
    sim_rows = sim.get("results", [])
    pred_day = float(sim["summary"]["achievable_production_t"]) * 2   # 2 × 12 h shifts
    man_day = sum(r["wmt_day"] for r in routes.values())
    days = _days_in(month)
    paths = []
    route_list = [r for r in routes.values() if r["dt"] > 0]
    for i, r in enumerate(route_list):
        rt = "%s>%s" % (r["src"], r["dst"])
        sr = sim_rows[i] if i < len(sim_rows) else {}
        paths.append({"key": rt, "contractor": r["contractor"],
                      "dt": int(round(r["dt"])),
                      "material": "+".join(sorted(r["materials"])) or None,
                      "manual_wmt_day": round(r["wmt_day"]),
                      "pred_wmt_day": round(float(sr.get("achievable_production_t") or 0) * 2),
                      "cycle_basis": (sr.get("assumptions") or {}).get("cycle_time") or sr.get("cycle_source")})
    st = _load_state(month) or {"month": month}
    st["prediction"] = {
        "source_date": "yearly matrix (%s)" % (yearly.get("source") or "pasted"),
        "per_shift_wmt": round(pred_day / 2),
        "per_day_wmt": round(pred_day),
        "dt": int(round(sum(r["dt"] for r in routes.values()))),
        "rain_mm": None,
        "paths": paths,
        "days": [{"date": d, "wmt": round(pred_day)} for d in days],
        "built_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": ("Fleet (NB_DT_) from the yearly matrix run through the measured "
                 "plan engine; day = 2 x 12 h shifts. Same plan every day."),
    }
    st["manual"] = {
        "source": "yearly matrix (%s)" % (yearly.get("source") or "pasted"),
        "days": [{"date": d, "wmt": round(man_day)} for d in days],
        "loaded_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _save_state(month, st)
    return jsonify({"ok": True, "month": month, "state": st,
                    "manual_day": round(man_day), "pred_day": round(pred_day),
                    "routes": len(plans),
                    "warnings": sim["summary"].get("capacity_warnings") or []})
