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
    if not re.fullmatch(r"\d{4}-\d{2}", month or ""):
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
        if f.filename.lower().endswith((".xlsx", ".xlsm")):
            from openpyxl import load_workbook
            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            ws = wb.active
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
        else:  # csv / tsv
            text = data.decode("utf-8", "replace")
            sep = "\t" if "\t" in text.splitlines()[0] else ","
            rows = [line.split(sep) for line in text.splitlines()]
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
