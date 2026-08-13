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
  • Comparison + export: Key sheet (the three numbers) plus one sheet per
    month with Production & capacity (Plan Check capacity / simulate), SAP
    targets + required DT, and the daily three-line chart. Achievable is
    /api/simulate, never averaged with the path-model prediction. Excel is
    a white report — no cell fills.

State lives in data/monthly_plans/YYYY-MM.json, one file per month, same
local-disk pattern as saved_plans.
"""

import calendar
import io
import json
import math
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
            if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])\.json", f):
                out.append(f[:-5])
    return jsonify({"ok": True, "months": out})


def _simulate_holding(plan):
    """Same engine as Plan → Check capacity. Returns simulate payload or None."""
    raw = plan.get("paths") or {}
    items = raw.values() if isinstance(raw, dict) else raw
    plans = []
    for p in items:
        if not isinstance(p, dict) or p.get("foreign"):
            continue
        key = (p.get("key") or "").strip()
        if ">" not in key:
            continue
        src, dst = key.split(">", 1)
        dt = float(p.get("dt") or 0)
        if dt <= 0:
            continue
        plans.append({"route": key, "source": p.get("source") or src,
                      "destination": p.get("dest") or dst,
                      "n_trucks": int(round(dt)),
                      "contractor": p.get("contractor") or ""})
    if not plans:
        return None
    import plan_simulator
    return plan_simulator.simulate({"plans": plans})


def _achv_day_from_pred(p):
    """Plan-tab achievable (shift) × 2, or the stored per-day field."""
    if not p:
        return None
    if p.get("per_day_achv_wmt") is not None:
        return p["per_day_achv_wmt"]
    sh = p.get("sim_achievable_shift")
    if sh is None:
        return None
    try:
        return round(float(sh) * 2)
    except (TypeError, ValueError):
        return None


def _fill_achv_from_plan(p):
    """Run Plan Check capacity on stored paths; write achievable onto the prediction."""
    if not p or _achv_day_from_pred(p) is not None:
        return _achv_day_from_pred(p)
    paths = p.get("paths") or []
    if not paths:
        return None
    sim = _simulate_holding({"paths": {str(i): row for i, row in enumerate(paths)}})
    if not sim or sim.get("error"):
        return None
    sh = (sim.get("summary") or {}).get("achievable_production_t")
    if sh is None:
        return None
    try:
        day = round(float(sh) * 2)
    except (TypeError, ValueError):
        return None
    p["per_day_achv_wmt"] = day
    p["sim_achievable_shift"] = sh
    results = sim.get("results") or []
    for i, row in enumerate(paths):
        if not isinstance(row, dict):
            continue
        if i < len(results) and row.get("achv_wmt_day") is None:
            row["achv_wmt_day"] = round(float(results[i].get("achievable_production_t") or 0) * 2)
    for d in p.get("days") or []:
        if d.get("wmt_achv") is None:
            d["wmt_achv"] = day
    return day


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
    achv_shift = meta.get("sim_achievable")
    if achv_shift is None:
        sim = _simulate_holding(plan)
        if sim and not sim.get("error"):
            achv_shift = (sim.get("summary") or {}).get("achievable_production_t")
    if not per_shift_wmt:
        return jsonify({"ok": False, "error": "saved plan for %s carries no prediction totals - open it in the Plan tab and re-save" % src_date}), 400
    # Day = 2 x 12 h shifts. Same plan every day; rain is whatever the plan was
    # saved with (labelled, not hidden).
    day_wmt = per_shift_wmt * 2
    day_trips = per_shift_trips * 2
    day_achv = round(float(achv_shift) * 2) if achv_shift is not None else None
    days = [{"date": d, "wmt": round(day_wmt), "trips": round(day_trips),
             "wmt_achv": day_achv} for d in _days_in(month)]
    st = _load_state(month) or {"month": month}
    st["prediction"] = {
        "source_date": src_date,
        "per_shift_wmt": round(per_shift_wmt),
        "per_day_wmt": round(day_wmt),
        "per_day_achv_wmt": day_achv,
        "dt": pred.get("dt"),
        "rain_mm": plan.get("rain_mm"),
        "sim_achievable_shift": achv_shift,
        "paths": [
            {"key": p.get("key"), "contractor": p.get("contractor"),
             "dt": p.get("dt"), "material": p.get("material"),
             "wbSel": p.get("wbSel")}
            for p in ((plan.get("paths") or {}).values()
                      if isinstance(plan.get("paths"), dict)
                      else (plan.get("paths") or []))
            if isinstance(p, dict)
        ],
        "days": days,
        "built_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": ("Same holding plan every day; day = 2 x 12 h shifts x saved "
                 "per-shift prediction. Achievable is Plan Check capacity "
                 "(simulate) x 2. Rain fixed at the saved plan's value."),
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


# Line colours match the monthly page (Prediction blue / Achievable green / Target amber).
# Cells stay white — no fills. Colour is line/text only.
_XLSX_PRED, _XLSX_ACHV, _XLSX_TGT = "2563EB", "059669", "D97706"
_XLSX_NAVY, _XLSX_MUTED, _XLSX_INK = "1F4E79", "64748B", "1F2937"


def _xlsx_send(wb, name):
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(
        buf, as_attachment=True, download_name=name,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


def _xlsx_font(bold=False, size=11, color=None):
    from openpyxl.styles import Font
    return Font(name="Calibri", bold=bold, size=size, color=color or _XLSX_INK)


def _xlsx_sides():
    from openpyxl.styles import Border, Side
    thin = Side(style="thin", color="D0D5DD")
    med = Side(style="medium", color=_XLSX_NAVY)
    return Border(left=thin, right=thin, top=thin, bottom=thin), Border(
        left=thin, right=thin, top=thin, bottom=med)


def _xlsx_sheet_setup(ws):
    from openpyxl.worksheet.page import PageMargins
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = None
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_margins = PageMargins(left=0.5, right=0.5, top=0.6, bottom=0.5,
                                  header=0.25, footer=0.25)
    ws.print_options.horizontalCentered = True
    ws.oddFooter.left.text = "WBN FMS · monthly plan"
    ws.oddFooter.right.text = "Page &P of &N"


def _xlsx_headers(ws, row, headers, start=1):
    from openpyxl.styles import Alignment
    _box, head = _xlsx_sides()
    for i, h in enumerate(headers, start=start):
        c = ws.cell(row=row, column=i, value=h)
        c.font = _xlsx_font(True, 10, _XLSX_NAVY)
        c.alignment = Alignment(wrap_text=True, vertical="center",
                                horizontal="right" if i > start else "left")
        c.border = head
    ws.row_dimensions[row].height = 26


def _xlsx_num(cell, value, bold=False):
    cell.value = value
    cell.font = _xlsx_font(bold, 11)
    cell.number_format = "#,##0"
    cell.border = _xlsx_sides()[0]


def _xlsx_text(cell, value, bold=False, color=None, size=11):
    cell.value = value
    cell.font = _xlsx_font(bold, size, color)
    cell.border = _xlsx_sides()[0]


def _xlsx_widths(ws, widths, start=1):
    from openpyxl.utils import get_column_letter
    for i, w in enumerate(widths, start=start):
        letter = get_column_letter(i)
        ws.column_dimensions[letter].width = max(
            ws.column_dimensions[letter].width or 0, w)


def _xlsx_paint_lines(chart, colors):
    for s, col in zip(chart.series, colors):
        s.graphicalProperties.line.solidFill = col
        s.graphicalProperties.line.width = 18000
        s.marker.symbol = "circle"
        s.marker.size = 6
        s.marker.graphicalProperties.solidFill = col
        s.marker.graphicalProperties.line.solidFill = col


def _xlsx_line_chart(ws, title, y_title, min_col, max_col, header_row, last_row, anchor,
                     height=12, width=20):
    from openpyxl.chart import LineChart, Reference
    lc = LineChart()
    lc.title = title
    lc.y_axis.title = y_title
    lc.y_axis.scaling.min = 0
    lc.height, lc.width = height, width
    lc.legend.position = "t"
    lc.style = 10
    data = Reference(ws, min_col=min_col, max_col=max_col,
                     min_row=header_row, max_row=last_row)
    cats = Reference(ws, min_col=1, min_row=header_row + 1, max_row=last_row)
    lc.add_data(data, titles_from_data=True)
    lc.set_categories(cats)
    _xlsx_paint_lines(lc, (_XLSX_PRED, _XLSX_ACHV, _XLSX_TGT)[:max_col - min_col + 1])
    ws.add_chart(lc, anchor)
    return lc


def _xlsx_board_header(ws, heading, sub):
    """Year-board chrome: title + one-line note. No definition blurbs, no fills."""
    from openpyxl.utils import get_column_letter
    _xlsx_sheet_setup(ws)
    ws["A1"] = heading
    ws["A1"].font = _xlsx_font(True, 18, _XLSX_NAVY)
    ws.merge_cells("A1:F1")
    ws["A2"] = sub
    ws["A2"].font = _xlsx_font(False, 11, _XLSX_MUTED)
    ws.merge_cells("A2:F2")
    ws.row_dimensions[1].height = 26
    for i, w in enumerate([18, 18, 18, 16, 12, 12], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    return 4


def _xlsx_kpi_strip(ws, row, kpis):
    """Same three (or four) KPIs as the monthly year board: big coloured number, muted label."""
    for i, (label, value, color) in enumerate(kpis):
        ws.cell(row=row, column=1 + i, value=label).font = _xlsx_font(True, 9, _XLSX_MUTED)
        cell = ws.cell(row=row + 1, column=1 + i, value=value)
        cell.font = _xlsx_font(True, 22, color)
        cell.number_format = "#,##0"
    ws.row_dimensions[row + 1].height = 32
    return row + 3


def _xlsx_month_cards(ws, row, cards, year):
    """One compact card per month — same numbers as the year-board cards."""
    ws.cell(row=row, column=1, value="Months").font = _xlsx_font(True, 13, _XLSX_NAVY)
    row += 1
    for i, c in enumerate(cards):
        col = 1 + i
        name = "%s %s" % (c.get("name") or "", year)
        meta = "%s days" % (c.get("n_days") or "—")
        if c.get("dt") is not None:
            meta += " · %s DT" % format(int(c["dt"]), ",")
        if not c.get("built"):
            meta += " · not built yet"
        ws.cell(row=row, column=col, value=name.strip()).font = _xlsx_font(True, 12, _XLSX_INK)
        ws.cell(row=row + 1, column=col, value=meta).font = _xlsx_font(False, 9, _XLSX_MUTED)
        ws.cell(row=row + 2, column=col, value="Prediction").font = _xlsx_font(False, 9, _XLSX_MUTED)
        cell_p = ws.cell(row=row + 3, column=col, value=c.get("pred_month"))
        cell_p.font = _xlsx_font(True, 14, _XLSX_PRED)
        cell_p.number_format = "#,##0"
        ws.cell(row=row + 4, column=col, value="Achievable").font = _xlsx_font(False, 9, _XLSX_MUTED)
        cell_a = ws.cell(row=row + 5, column=col, value=c.get("achv_month"))
        cell_a.font = _xlsx_font(True, 14, _XLSX_ACHV)
        cell_a.number_format = "#,##0"
        ws.cell(row=row + 6, column=col, value="Target").font = _xlsx_font(False, 9, _XLSX_MUTED)
        cell_t = ws.cell(row=row + 7, column=col, value=c.get("target_month"))
        cell_t.font = _xlsx_font(True, 14, _XLSX_TGT)
        cell_t.number_format = "#,##0"
    return row + 9


def _daily_triples(st):
    """[(date, pred, achv, target), ...] — Achievable from Plan simulate, never averaged."""
    p = (st or {}).get("prediction") or {}
    m = (st or {}).get("manual") or {}
    pred = {d["date"]: d for d in (p.get("days") or [])}
    man = {d["date"]: d for d in (m.get("days") or [])}
    month = (st or {}).get("month")
    if not month:
        return [], p, m
    if _achv_day_from_pred(p) is None:
        _fill_achv_from_plan(p)
    achv_flat = _achv_day_from_pred(p)
    rows = []
    for d in _days_in(month):
        pd_ = pred.get(d, {})
        aw = pd_.get("wmt_achv")
        if aw is None:
            aw = achv_flat
        rows.append((d, pd_.get("wmt"), aw, man.get(d, {}).get("wmt")))
    return rows, p, m


def _simulate_for_paths(paths):
    """Re-run Check capacity (cycle clock). Never send path-model trips."""
    plans = []
    for p in paths or []:
        key = (p.get("key") or "").strip()
        if ">" not in key:
            continue
        src, dst = key.split(">", 1)
        plans.append({"route": key, "source": src, "destination": dst,
                      "n_trucks": int(round(p.get("dt") or 0)),
                      "contractor": p.get("contractor")})
    if not plans:
        return None, []
    try:
        import plan_simulator
        sim = plan_simulator.simulate({"plans": plans})
    except Exception:
        return None, plans
    if sim.get("error"):
        return None, plans
    return sim, plans


def _xlsx_section(ws, row, title, sub=None):
    ws.cell(row=row, column=1, value=title).font = _xlsx_font(True, 13, _XLSX_NAVY)
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=8)
    if sub:
        ws.cell(row=row + 1, column=1, value=sub).font = _xlsx_font(False, 9, _XLSX_MUTED)
        ws.merge_cells(start_row=row + 1, start_column=1, end_row=row + 1, end_column=8)
        return row + 2
    return row + 1


def _xlsx_fill_month(ws, st, title):
    """One month: KPIs, Production & capacity, SAP targets / required DT, daily chart."""
    from openpyxl.styles import Alignment
    _xlsx_sheet_setup(ws)
    rows, p, m = _daily_triples(st)
    paths = list(p.get("paths") or [])
    sim, _plans = _simulate_for_paths(paths)
    sim_rows = (sim or {}).get("results") or []
    sim_sum = (sim or {}).get("summary") or {}
    n_days = len(rows) or 1

    ws["A1"] = title
    ws["A1"].font = _xlsx_font(True, 16, _XLSX_NAVY)
    ws.merge_cells("A1:L1")
    ws["A2"] = ("Same day every day. Prediction = path model · Achievable = Plan "
                "Check capacity (/api/simulate) · Target = matrix. Never averaged.")
    ws["A2"].font = _xlsx_font(False, 10, _XLSX_MUTED)
    ws.merge_cells("A2:L2")

    tot_p = sum((pw or 0) for _, pw, _, _ in rows)
    tot_a = sum((aw or 0) for _, _, aw, _ in rows)
    tot_t = sum((tw or 0) for _, _, _, tw in rows)
    pred_day = (p.get("per_day_wmt") if p.get("per_day_wmt") is not None
                else (tot_p / n_days if n_days else None))
    achv_day = (p.get("per_day_achv_wmt") if p.get("per_day_achv_wmt") is not None
                else (tot_a / n_days if n_days else None))
    tgt_day = (tot_t / n_days) if tot_t else None
    planned_day = None
    if sim_sum.get("planned_production_t") is not None:
        planned_day = float(sim_sum["planned_production_t"]) * 2
    shortfall_day = None
    if planned_day is not None and achv_day is not None:
        shortfall_day = max(0.0, planned_day - float(achv_day))

    r = _xlsx_section(ws, 4, "A · Production & capacity",
                      "Plan Check capacity engine. Day = 2 x 12 h shifts. "
                      "Predicted is the path model; Achievable and Engine planned are simulate.")
    kpi_heads = ["Trucks (DT)", "Predicted t/day", "Achievable t/day",
                 "Target t/day", "Engine planned t/day", "Shortfall t/day",
                 "Predicted t/month", "Achievable t/month", "Target t/month"]
    kpi_vals = [p.get("dt"), pred_day, achv_day, tgt_day, planned_day,
                shortfall_day if shortfall_day else None,
                tot_p or None, tot_a or None, tot_t or None]
    kpi_cols = (_XLSX_INK, _XLSX_PRED, _XLSX_ACHV, _XLSX_TGT, _XLSX_INK,
                "B91C1C" if (shortfall_day or 0) > 1 else _XLSX_MUTED,
                _XLSX_PRED, _XLSX_ACHV, _XLSX_TGT)
    for i, h in enumerate(kpi_heads):
        ws.cell(row=r, column=1 + i, value=h).font = _xlsx_font(True, 8, _XLSX_MUTED)
        cell = ws.cell(row=r + 1, column=1 + i, value=kpi_vals[i])
        cell.font = _xlsx_font(True, 14, kpi_cols[i])
        cell.number_format = "#,##0"
    r += 3

    cap_heads = ["Path", "Contractor", "Material", "DT", "Cycle min",
                 "Eff. cycle min", "Trips/DT", "Predicted t/day",
                 "Engine planned t/day", "Achievable t/day", "Target t/day",
                 "Capacity", "Roster"]
    _xlsx_headers(ws, r, cap_heads)
    box = _xlsx_sides()[0]
    tot_dt = tot_pred = tot_plan = tot_achv = tot_tgt = 0
    for i, prow in enumerate(paths):
        r += 1
        sr = sim_rows[i] if i < len(sim_rows) else {}
        key = prow.get("key")
        dt = prow.get("dt") or 0
        pred = prow.get("pred_wmt_day")
        achv = prow.get("achv_wmt_day")
        tgt = prow.get("manual_wmt_day")
        planned = None
        if sr.get("planned_production_t") is not None:
            planned = float(sr["planned_production_t"]) * 2
        trips_dt = sr.get("trips_per_shift_per_truck")
        cap_note = sr.get("capacity_note") or prow.get("envelope_flag") or ""
        if cap_note and ":" in cap_note:
            cap_note = cap_note.split(":")[0]
        if sr.get("capacity_ratio") is not None:
            cap_note = "%s · %d%%" % (cap_note, round(100 * sr["capacity_ratio"]))
        vals = [
            key, prow.get("contractor"), prow.get("material"), dt,
            sr.get("predicted_cycle_time_min"), sr.get("effective_cycle_min"),
            trips_dt, pred, planned, achv, tgt, cap_note,
            sr.get("trucks_to_roster"),
        ]
        for col, val in enumerate(vals, start=1):
            cell = ws.cell(row=r, column=col, value=val)
            cell.border = box
            cell.font = _xlsx_font(col == 1, 10)
            if col in (4, 5, 6, 7, 8, 9, 10, 11, 13) and val is not None:
                cell.number_format = "#,##0.0" if col in (5, 6, 7) else "#,##0"
                cell.alignment = Alignment(horizontal="right")
            if col == 12:
                over = (sr.get("capacity_ratio") or 0) > 1
                cell.font = _xlsx_font(over, 9, "B91C1C" if over else _XLSX_MUTED)
                cell.alignment = Alignment(wrap_text=True, vertical="center")
        tot_dt += dt or 0
        tot_pred += pred or 0
        tot_plan += planned or 0
        tot_achv += achv or 0
        tot_tgt += tgt or 0
        ws.row_dimensions[r].height = 18
    if paths:
        r += 1
        _xlsx_text(ws.cell(row=r, column=1), "TOTAL", True, _XLSX_NAVY)
        for col in range(2, 14):
            ws.cell(row=r, column=col).border = box
        _xlsx_num(ws.cell(row=r, column=4), tot_dt or None, True)
        _xlsx_num(ws.cell(row=r, column=8), tot_pred or None, True)
        _xlsx_num(ws.cell(row=r, column=9), tot_plan or None, True)
        _xlsx_num(ws.cell(row=r, column=10), tot_achv or None, True)
        _xlsx_num(ws.cell(row=r, column=11), tot_tgt or None, True)
        if shortfall_day and shortfall_day > 1:
            _xlsx_text(ws.cell(row=r, column=12),
                       "%s t/day blocked by capacity" % format(round(shortfall_day), ","),
                       True, "B91C1C", 9)

    warns = sim_sum.get("capacity_warnings") or p.get("extrapolated") or []
    if warns:
        r += 2
        r = _xlsx_section(ws, r, "Capacity warnings")
        for w in warns:
            ws.cell(row=r, column=1, value=str(w)).font = _xlsx_font(False, 9, "B91C1C")
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=12)
            ws.cell(row=r, column=1).alignment = Alignment(wrap_text=True)
            ws.row_dimensions[r].height = 28
            r += 1

    r += 2
    sap_rows = _sap_table_rows(st, paths, sim_rows)
    r = _xlsx_section(
        ws, r, "SAP targets — fixed supply",
        "LIM is buffer — no target. Goal: predicted = achievable = target. "
        "Required DT is solved with the same path engine as Plan (rain = 0). "
        "Achievable is the contractor-path simulate figure (not material-split).")
    sap_heads = ["Path (SAP)", "Contractor", "Target t/day", "Predicted t/day",
                 "Achievable t/day", "Allocated DT", "Required DT", "Status"]
    _xlsx_headers(ws, r, sap_heads)
    if not sap_rows:
        r += 1
        _xlsx_text(ws.cell(row=r, column=1),
                   "No SAP rows in the matrix for this month (LIM-only, or matrix not loaded).",
                   False, _XLSX_MUTED, 10)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    for sap in sap_rows:
        r += 1
        status = sap["status"]
        if status == "on target":
            status_col = "059669"
        elif status.startswith("target above"):
            status_col = "B91C1C"
        else:
            status_col = "D97706"
        vals = [sap["path"], sap["contractor"], sap["target"], sap["pred"],
                sap["achv"], sap["alloc_dt"], sap["req_dt"], status]
        for col, val in enumerate(vals, start=1):
            cell = ws.cell(row=r, column=col, value=val)
            cell.border = box
            cell.font = _xlsx_font(col == 1 or col == 8, 10,
                                   status_col if col == 8 else _XLSX_INK)
            if col in (3, 4, 5, 6, 7) and val is not None:
                cell.number_format = "#,##0"
                cell.alignment = Alignment(horizontal="right")

    r += 3
    daily_head = _xlsx_section(
        ws, r, "Daily WMT",
        "Same day every day — the lines are flat on purpose.")
    _xlsx_headers(ws, daily_head, ["Date", "Prediction t", "Achievable t", "Target t"])
    dr = daily_head
    for d, pw, aw, tw in rows:
        dr += 1
        _xlsx_text(ws.cell(row=dr, column=1), d)
        _xlsx_num(ws.cell(row=dr, column=2), pw)
        _xlsx_num(ws.cell(row=dr, column=3), aw)
        _xlsx_num(ws.cell(row=dr, column=4), tw)
    last_daily = dr
    dr += 1
    _xlsx_text(ws.cell(row=dr, column=1), "TOTAL", True, _XLSX_NAVY)
    _xlsx_num(ws.cell(row=dr, column=2), tot_p or None, True)
    _xlsx_num(ws.cell(row=dr, column=3), tot_a or None, True)
    _xlsx_num(ws.cell(row=dr, column=4), tot_t or None, True)
    if last_daily > daily_head:
        _xlsx_line_chart(ws, "Daily WMT", "t/day", 2, 4, daily_head, last_daily,
                         "F%d" % daily_head, height=12, width=18)

    _xlsx_widths(ws, [22, 14, 14, 12, 12, 14, 12, 16, 20, 16, 14, 36, 10])
    ws.freeze_panes = "A8"
    ws.row_dimensions[1].height = 24
    return tot_p, tot_a, tot_t


def _xlsx_month_book(month, st):
    from openpyxl import Workbook
    wb = Workbook()
    key = wb.active
    key.title = "Key"
    rows, _p, _m = _daily_triples(st)
    tot_p = sum((pw or 0) for _, pw, _, _ in rows)
    tot_a = sum((aw or 0) for _, _, aw, _ in rows)
    tot_t = sum((tw or 0) for _, _, _, tw in rows)
    label = "%s %s" % (calendar.month_name[int(month[5:7])], month[:4])
    r = _xlsx_board_header(
        key, label,
        "Same day every day. Prediction · Achievable · Target — never averaged.")
    kpis = [
        ("prediction · month t", tot_p or None, _XLSX_PRED),
        ("achievable · month t", tot_a or None, _XLSX_ACHV),
        ("target · month t", tot_t or None, _XLSX_TGT),
    ]
    if tot_p and tot_t:
        kpis.append(("prediction − target", tot_p - tot_t,
                     "059669" if tot_p >= tot_t else "B91C1C"))
    r = _xlsx_kpi_strip(key, r, kpis)
    chart_row = r
    table_row = chart_row + 28
    key.cell(row=table_row, column=1, value="Daily totals").font = _xlsx_font(True, 13, _XLSX_NAVY)
    table_row += 1
    _xlsx_headers(key, table_row, ["Date", "Prediction t", "Achievable t", "Target t"])
    rr = table_row
    for d, pw, aw, tw in rows:
        rr += 1
        _xlsx_text(key.cell(row=rr, column=1), d)
        _xlsx_num(key.cell(row=rr, column=2), pw)
        _xlsx_num(key.cell(row=rr, column=3), aw)
        _xlsx_num(key.cell(row=rr, column=4), tw)
    last = rr
    rr += 1
    _xlsx_text(key.cell(row=rr, column=1), "TOTAL", True, _XLSX_NAVY)
    _xlsx_num(key.cell(row=rr, column=2), tot_p or None, True)
    _xlsx_num(key.cell(row=rr, column=3), tot_a or None, True)
    _xlsx_num(key.cell(row=rr, column=4), tot_t or None, True)
    if last > table_row:
        _xlsx_line_chart(key, "Daily WMT (flat — the same plan every day)", "t/day",
                         2, 4, table_row, last, "A%d" % chart_row,
                         height=14, width=24)
    month_ws = wb.create_sheet(label[:31])
    _xlsx_fill_month(month_ws, st, "%s — production, capacity & SAP" % label)
    return wb


def _xlsx_year_book(year, cards):
    """Key = year board (KPIs, month cards, big chart) then the totals table underneath."""
    from openpyxl import Workbook
    wb = Workbook()
    key = wb.active
    key.title = "Key"
    tot_p = sum(c.get("pred_month") or 0 for c in cards)
    tot_a = sum(c.get("achv_month") or 0 for c in cards)
    tot_t = sum(c.get("target_month") or 0 for c in cards)
    n_built = sum(1 for c in cards if c.get("pred_month") is not None)
    r = _xlsx_board_header(
        key, "Year board",
        "Year %s · %s month%s · same day every day of each month."
        % (year, n_built, "" if n_built == 1 else "s"))
    r = _xlsx_kpi_strip(key, r, [
        ("prediction · year t", tot_p or None, _XLSX_PRED),
        ("achievable · year t", tot_a or None, _XLSX_ACHV),
        ("target · year t", tot_t or None, _XLSX_TGT),
    ])
    r = _xlsx_month_cards(key, r, cards, year)
    chart_row = r
    table_row = chart_row + 28
    key.cell(row=table_row, column=1, value="Totals").font = _xlsx_font(True, 13, _XLSX_NAVY)
    table_row += 1
    _xlsx_headers(key, table_row,
                  ["Month", "Prediction t", "Achievable t", "Target t", "DT", "Days"])
    rr = table_row
    for c in cards:
        rr += 1
        _xlsx_text(key.cell(row=rr, column=1), c.get("name"))
        _xlsx_num(key.cell(row=rr, column=2), c.get("pred_month"))
        _xlsx_num(key.cell(row=rr, column=3), c.get("achv_month"))
        _xlsx_num(key.cell(row=rr, column=4), c.get("target_month"))
        _xlsx_num(key.cell(row=rr, column=5), c.get("dt"))
        _xlsx_num(key.cell(row=rr, column=6), c.get("n_days"))
    last = rr
    if last > table_row:
        _xlsx_line_chart(key, "Year · monthly tonnes", "t / month",
                         2, 4, table_row, last, "A%d" % chart_row,
                         height=14, width=24)
    used = {"Key"}
    for c in cards:
        st = _load_state(c["month"])
        if not st:
            continue
        st["month"] = c["month"]
        name = (c.get("name") or c["month"])[:31]
        base, n = name, 2
        while name in used:
            name = ("%s %d" % (base, n))[:31]
            n += 1
        used.add(name)
        ws = wb.create_sheet(name)
        _xlsx_fill_month(ws, st, "%s %s — production, capacity & SAP"
                         % (c.get("name") or "", year))
    return wb


@bp.route("/api/monthly/export")
def api_monthly_export():
    """One xlsx: Key page + month sheet (production, capacity, SAP, daily chart)."""
    month = (request.args.get("month") or "").strip()
    st = _load_state(month)
    if not st:
        return jsonify({"ok": False, "error": "nothing stored for %s" % month}), 404
    if not st.get("month"):
        st["month"] = month
    return _xlsx_send(_xlsx_month_book(month, st),
                      "monthly_plan_%s.xlsx" % month)


@bp.route("/api/monthly/export-year")
def api_monthly_export_year():
    """Year workbook: Key + year chart + one production/capacity/SAP sheet per month."""
    year = (request.args.get("year") or str(date.today().year)).strip()
    if not re.fullmatch(r"\d{4}", year):
        return jsonify({"ok": False, "error": "year=YYYY"}), 400
    _yearly, cards = _year_cards(year)
    if not cards:
        return jsonify({"ok": False, "error": "nothing stored for %s — load a matrix and build the year first" % year}), 404
    return _xlsx_send(_xlsx_year_book(year, cards),
                      "monthly_plan_%s.xlsx" % year)



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


_MONTH_LABELS = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
                 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}


def _load_yearly():
    if not os.path.isfile(_YEARLY_PATH):
        return None
    with open(_YEARLY_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _routes_for_month(yearly, mnum):
    """Matrix rows for one calendar month, merged to engine routes."""
    mnum = str(int(mnum))
    routes = {}
    for e in yearly.get("entries") or []:
        if not ((e.get("wmt") or {}).get(mnum) or 0) and not ((e.get("dt") or {}).get(mnum) or 0):
            continue
        src = _ORIGIN_MAP.get((e.get("origin") or "").upper(), (e.get("origin") or "").upper())
        dst = _canon_dest(e.get("dest"))
        key = (src, dst, (e.get("contractor") or "").upper())
        rec = routes.setdefault(key, {"src": src, "dst": dst,
                                      "contractor": (e.get("contractor") or "").upper(),
                                      "dt": 0.0, "wmt_day": 0.0, "materials": set()})
        rec["dt"] += (e.get("dt") or {}).get(mnum) or 0
        rec["wmt_day"] += (e.get("wmt") or {}).get(mnum) or 0
        if e.get("material"):
            rec["materials"].add(e["material"])
    return [r for r in routes.values() if r["dt"] > 0]


def _fetch_sim_json(path):
    """Same payloads the Plan tab fetches. Prefer live app, then local server, then fixture."""
    from flask import current_app, has_app_context
    if has_app_context():
        try:
            rv = current_app.test_client().get(path)
            if rv.status_code == 200:
                data = rv.get_json()
                if data:
                    return data
        except Exception:
            pass
    try:
        import urllib.request
        with urllib.request.urlopen("http://127.0.0.1:5055" + path, timeout=30) as resp:
            return json.load(resp)
    except Exception:
        pass
    fx = os.path.join(_ROOT, "fixtures", path.rsplit("/", 1)[-1] + ".json")
    if os.path.isfile(fx):
        with open(fx, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def _path_model_context():
    pr = _fetch_sim_json("/api/simulator/path-response") or {}
    cap = _fetch_sim_json("/api/simulator/capability") or {}
    paths = pr.get("paths") or {}
    fleet = (cap.get("kpi") or {}).get("tripsPerDT")
    contr_by = {}
    for c in cap.get("contractorProd") or []:
        name = (c.get("contractor") or "").upper()
        if name:
            contr_by[name] = c
    return paths, fleet, contr_by


def _path_row_wmt(src, dst, contractor, dt, n_comb, paths, fleet, contr_by):
    """One contractor-path through the Plan Step 1 path model (day grain, rain=0)."""
    k = "%s>%s" % (src, dst)
    m = paths.get(k) or {}
    dt = float(dt or 0)
    n_comb = float(n_comb or dt) or dt
    c = contr_by.get((contractor or "").upper()) or {}
    if fleet and c.get("tripsPerDT"):
        cf = max(0.5, min(1.5, float(c["tripsPerDT"]) / float(fleet)))
    else:
        cf = 1.0
    pay = c.get("tf") or m.get("tf")
    day_rate = m.get("dayRate") or m.get("avgTr")
    cap_trips = m.get("dayTripsCap")
    if not day_rate or not pay or dt <= 0:
        return {"wmt": None, "trips": None,
                "flag": "no measured day history — using cycle × payload",
                "cf": cf, "pay": pay, "cap_trips": cap_trips, "avg_dt": m.get("avgDt")}
    tr = float(day_rate) * cf
    linear = tr * n_comb
    flag = None
    if cap_trips and cap_trips > 0 and linear > cap_trips:
        tr *= cap_trips / linear
        flag = "at demonstrated ceiling (%d trips/day)" % round(cap_trips)
    floor = 0.3 * float(day_rate) * cf
    if tr < floor:
        tr = floor
    dt_max = m.get("dtMaxDayAll") or m.get("dtMaxAll") or m.get("dtMax")
    if dt_max and n_comb > dt_max:
        flag = "beyond measured fleet (max ever %d DT)" % round(dt_max)
    trips = dt * tr
    return {"wmt": trips * float(pay), "trips": trips, "flag": flag,
            "cf": cf, "pay": pay, "cap_trips": cap_trips, "avg_dt": m.get("avgDt")}


def _plan_predict_for_routes(route_list):
    """Plan tab Step 1 WMT for one typical day (rain=0, no WB / other-traffic knobs).

    Identical ingredients to planTripsPerDT + planPayload + planContractorFactor:
      trips/DT = dayRate × contractor factor, saturating at dayTripsCap on the
      combined fleet for that path, 30% floor; tonnes = trips × contractor t/trip.
    """
    paths, fleet, contr_by = _path_model_context()
    combined = {}
    for r in route_list:
        k = "%s>%s" % (r["src"], r["dst"])
        combined[k] = combined.get(k, 0.0) + float(r["dt"] or 0)
    rows = []
    pred_day = 0.0
    for r in route_list:
        k = "%s>%s" % (r["src"], r["dst"])
        dt = float(r["dt"] or 0)
        pr = _path_row_wmt(r["src"], r["dst"], r.get("contractor"), dt,
                           combined[k] or dt, paths, fleet, contr_by)
        if pr.get("wmt") is not None:
            pred_day += pr["wmt"]
        rows.append(pr)
    return pred_day, rows


def _required_dt_day(src, dst, contractor, target_day, others_dt, paths, fleet, contr_by):
    """Invert the path model for a day target. Same solver as planDtForWmt (rain=0)."""
    if not target_day or target_day <= 0:
        return None, None
    seed = _path_row_wmt(src, dst, contractor, 1, others_dt + 1, paths, fleet, contr_by)
    pay = seed.get("pay")
    cap = seed.get("cap_trips")
    if pay:
        max_wmt = (float(cap) * float(pay)) if cap else None
        if max_wmt is not None and target_day > max_wmt * 0.999:
            return None, "target above path ceiling (%.0f t/day max)" % max_wmt
    dt = max(1.0, float(seed.get("avg_dt") or 30))
    last_wmt = None
    for _ in range(60):
        row = _path_row_wmt(src, dst, contractor, dt, others_dt + dt,
                            paths, fleet, contr_by)
        wmt = row.get("wmt")
        if not wmt or wmt <= 0:
            return None, row.get("flag") or "could not size"
        last_wmt = wmt
        nxt = dt * target_day / wmt
        if not math.isfinite(nxt) or nxt > 1e6:
            return None, "could not size"
        if abs(nxt - dt) < 0.01:
            dt = nxt
            break
        dt = dt + 0.6 * (nxt - dt)
    if last_wmt is not None and last_wmt < target_day * 0.995:
        return None, "target above path ceiling"
    return max(1, int(math.ceil(dt))), None


def _sap_entries_for_month(yearly, mnum):
    """Un-merged matrix rows whose material is SAP (fixed supply)."""
    mnum = str(int(mnum))
    rows = {}
    for e in (yearly or {}).get("entries") or []:
        mat = (e.get("material") or "").strip().upper()
        if mat != "SAP":
            continue
        if not ((e.get("wmt") or {}).get(mnum) or 0) and not ((e.get("dt") or {}).get(mnum) or 0):
            continue
        src = _ORIGIN_MAP.get((e.get("origin") or "").upper(), (e.get("origin") or "").upper())
        dst = _canon_dest(e.get("dest"))
        contr = (e.get("contractor") or "").upper()
        key = (src, dst, contr)
        rec = rows.setdefault(key, {"src": src, "dst": dst, "contractor": contr,
                                    "dt": 0.0, "wmt_day": 0.0})
        rec["dt"] += (e.get("dt") or {}).get(mnum) or 0
        rec["wmt_day"] += (e.get("wmt") or {}).get(mnum) or 0
    return [r for r in rows.values() if r["wmt_day"] > 0 or r["dt"] > 0]


def _sap_table_rows(st, paths, sim_rows):
    """SAP board for Excel: target, predicted, achievable, allocated / required DT."""
    month = (st or {}).get("month")
    yearly = _load_yearly()
    sap_src = []
    if yearly and month:
        sap_src = _sap_entries_for_month(yearly, month[5:7])
    if not sap_src:
        for p in paths or []:
            mat = (p.get("material") or "").upper()
            if "SAP" not in mat:
                continue
            key = p.get("key") or ""
            if ">" not in key:
                continue
            src, dst = key.split(">", 1)
            sap_src.append({"src": src, "dst": dst,
                            "contractor": (p.get("contractor") or "").upper(),
                            "dt": float(p.get("dt") or 0),
                            "wmt_day": float(p.get("manual_wmt_day") or 0)})
    if not sap_src:
        return []
    ctx = _path_model_context()
    path_models, fleet, contr_by = ctx
    path_dt = {}
    path_achv = {}
    for i, p in enumerate(paths or []):
        k = p.get("key")
        path_dt[k] = path_dt.get(k, 0.0) + float(p.get("dt") or 0)
        contr = (p.get("contractor") or "").upper()
        path_achv[(k, contr)] = p.get("achv_wmt_day")
        if i < len(sim_rows or []) and sim_rows[i].get("achievable_production_t") is not None:
            path_achv[(k, contr)] = float(sim_rows[i]["achievable_production_t"]) * 2
    out = []
    for s in sap_src:
        route = "%s>%s" % (s["src"], s["dst"])
        alloc = float(s["dt"] or 0)
        target = float(s["wmt_day"] or 0)
        n_comb = path_dt.get(route) or alloc
        others = max(0.0, n_comb - alloc)
        pred_row = _path_row_wmt(s["src"], s["dst"], s["contractor"], alloc,
                                 n_comb or alloc, path_models, fleet, contr_by)
        pred = pred_row.get("wmt")
        req, why = _required_dt_day(s["src"], s["dst"], s["contractor"], target,
                                    others, path_models, fleet, contr_by)
        achv = path_achv.get((route, s["contractor"]))
        if req is None:
            status = why or "target above path ceiling"
        elif pred is not None and pred >= target * 0.995:
            status = "on target"
        else:
            extra = max(0, req - int(round(alloc)))
            status = "add %s DT" % format(extra, ",")
        out.append({
            "path": route.replace(">", " → "),
            "contractor": s["contractor"],
            "target": round(target) if target else None,
            "pred": round(pred) if pred is not None else None,
            "achv": round(achv) if achv is not None else None,
            "alloc_dt": int(round(alloc)),
            "req_dt": req,
            "status": status,
        })
    return out


def _three_for_month(month, yearly):
    """Target (matrix) · Prediction (path model) · Achievable (simulate).

    Same fleet every day of the month; day = 2 × 12 h shifts. The three
    numbers are never averaged.
      • target      = matrix WMT/day (verbatim)
      • prediction  = measured trips/DT × DT, hard-capped at demonstrated
                      day trips (Plan tab path model — the bet on tomorrow)
      • achievable  = /api/simulate achievable_production_t × 2
                      (effective cycle, then loader / dump point capacity)
    """
    mnum = str(int(month[5:7]))
    route_list = _routes_for_month(yearly, mnum)
    if not route_list:
        return None, "the matrix has no rows for month %s" % month
    plans = [{"route": "%s>%s" % (r["src"], r["dst"]), "source": r["src"],
              "destination": r["dst"], "n_trucks": int(round(r["dt"])),
              "contractor": r["contractor"]}
             for r in route_list]
    import plan_simulator
    sim = plan_simulator.simulate({"plans": plans})
    if sim.get("error"):
        return None, sim["error"]
    sim_rows = sim.get("results") or []
    pred_sum, pred_rows = _plan_predict_for_routes(route_list)
    target_day = sum(r["wmt_day"] for r in route_list)
    pred_day = achv_day = 0.0
    paths, extrapolated, conditions = [], [], []
    for i, r in enumerate(route_list):
        rt = "%s>%s" % (r["src"], r["dst"])
        sr = sim_rows[i] if i < len(sim_rows) else {}
        planned_shift = float(sr.get("planned_production_t") or 0)
        achv_shift = float(sr.get("achievable_production_t") or 0)
        pr = pred_rows[i] if i < len(pred_rows) else {}
        if pr.get("wmt") is not None:
            row_pred = pr["wmt"]
            flag = pr.get("flag")
        else:
            row_pred = planned_shift * 2
            flag = pr.get("flag") or "no measured day history — using cycle × payload"
        row_achv = achv_shift * 2
        pred_day += row_pred
        achv_day += row_achv
        if flag:
            extrapolated.append("%s (%s %d DT): %s" % (rt, r["contractor"], round(r["dt"]), flag))
        if flag and flag.startswith("at demonstrated ceiling"):
            locked = max(0.0, (planned_shift * 2) - row_pred)
            if locked > 1:
                conditions.append({
                    "route": rt, "contractor": r["contractor"],
                    "locked_wmt_day": round(locked),
                    "condition": flag,
                })
        paths.append({"key": rt, "contractor": r["contractor"],
                      "dt": int(round(r["dt"])),
                      "material": "+".join(sorted(r["materials"])) or None,
                      "manual_wmt_day": round(r["wmt_day"]),
                      "pred_wmt_day": round(row_pred),
                      "achv_wmt_day": round(row_achv),
                      "envelope_flag": flag,
                      "cycle_basis": (sr.get("assumptions") or {}).get("cycle_time") or sr.get("cycle_source")})
    days = _days_in(month)
    src = "yearly matrix (%s)" % (yearly.get("source") or "pasted")
    st = _load_state(month) or {"month": month}
    st["prediction"] = {
        "source_date": src,
        "per_shift_wmt": round(pred_day / 2),
        "per_day_wmt": round(pred_day),
        "per_day_achv_wmt": round(achv_day),
        "dt": int(round(sum(r["dt"] for r in route_list))),
        "rain_mm": None,
        "paths": paths,
        "days": [{"date": d, "wmt": round(pred_day),
                  "wmt_achv": round(achv_day), "wmt_upside": round(achv_day)}
                 for d in days],
        "built_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": ("Same matrix fleet every day. Prediction is the Plan tab path "
                 "model (measured trips/DT × contractor factor × fleet, capped "
                 "at demonstrated day trips). Achievable is Plan Check capacity "
                 "(simulate). Target is the matrix WMT/day. Day = 2 × 12 h shifts."),
        "extrapolated": extrapolated,
        "per_day_upside_wmt": round(achv_day),
        "upside_conditions": sorted(conditions, key=lambda c: -c["locked_wmt_day"]),
    }
    st["manual"] = {
        "source": src,
        "days": [{"date": d, "wmt": round(target_day)} for d in days],
        "loaded_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _save_state(month, st)
    n = len(days)
    return st, {
        "month": month, "n_days": n, "routes": len(plans),
        "target_day": round(target_day), "pred_day": round(pred_day),
        "achv_day": round(achv_day),
        "target_month": round(target_day * n),
        "pred_month": round(pred_day * n),
        "achv_month": round(achv_day * n),
        "dt": int(round(sum(r["dt"] for r in route_list))),
        "extrapolated": extrapolated,
        "warnings": (sim.get("summary") or {}).get("capacity_warnings") or [],
    }


@bp.route("/api/monthly/build-from-yearly", methods=["POST"])
def api_monthly_build_from_yearly():
    """One month: target + prediction + achievable from the loaded yearly matrix."""
    body = request.get_json(silent=True) or {}
    month = (body.get("month") or "").strip()
    if not _month_path(month):
        return jsonify({"ok": False, "error": "supply month=YYYY-MM"}), 400
    yearly = _load_yearly()
    if not yearly:
        return jsonify({"ok": False, "error": "no yearly matrix loaded yet"}), 404
    st, meta = _three_for_month(month, yearly)
    if st is None:
        return jsonify({"ok": False, "error": meta}), 400
    return jsonify({"ok": True, "month": month, "state": st,
                    "manual_day": meta["target_day"], "pred_day": meta["pred_day"],
                    "achv_day": meta["achv_day"], "routes": meta["routes"],
                    "extrapolated": meta["extrapolated"], "warnings": meta["warnings"]})


@bp.route("/api/monthly/build-year", methods=["POST"])
def api_monthly_build_year():
    """Paste once → every month in the matrix, same daily plan × days."""
    body = request.get_json(silent=True) or {}
    year = str(body.get("year") or date.today().year).strip()
    if not re.fullmatch(r"\d{4}", year):
        return jsonify({"ok": False, "error": "supply year=YYYY"}), 400
    yearly = _load_yearly()
    if not yearly:
        return jsonify({"ok": False, "error": "no yearly matrix loaded yet"}), 404
    months = yearly.get("months") or []
    if not months:
        return jsonify({"ok": False, "error": "the matrix has no month columns"}), 400
    cards, errors = [], []
    for mnum in months:
        month = "%s-%02d" % (year, int(mnum))
        st, meta = _three_for_month(month, yearly)
        if st is None:
            errors.append({"month": month, "error": meta})
            continue
        cards.append(meta)
    return jsonify({"ok": True, "year": year, "cards": cards, "errors": errors})


def _year_cards(year):
    """Month cards for the year board and the year Excel download."""
    yearly = _load_yearly()
    mnums = set(int(m) for m in (yearly or {}).get("months") or [])
    if os.path.isdir(_MONTH_DIR):
        for f in os.listdir(_MONTH_DIR):
            if re.fullmatch(r"%s-(0[1-9]|1[0-2])\.json" % year, f):
                mnums.add(int(f[5:7]))
    cards = []
    for mnum in sorted(mnums):
        month = "%s-%02d" % (year, mnum)
        st = _load_state(month)
        n = len(_days_in(month))
        p = (st or {}).get("prediction") or {}
        man = (st or {}).get("manual") or {}
        pred_day = p.get("per_day_wmt")
        achv_day = _achv_day_from_pred(p)
        if achv_day is None and p.get("paths"):
            achv_day = _fill_achv_from_plan(p)
            if achv_day is not None:
                _save_state(month, st)
        tgt_days = man.get("days") or []
        tgt_day = tgt_days[0].get("wmt") if tgt_days else None
        cards.append({
            "month": month, "name": _MONTH_LABELS[mnum], "n_days": n,
            "dt": p.get("dt"),
            "pred_day": pred_day, "achv_day": achv_day, "target_day": tgt_day,
            "pred_month": round(pred_day * n) if pred_day is not None else None,
            "achv_month": round(achv_day * n) if achv_day is not None else None,
            "target_month": round(tgt_day * n) if tgt_day is not None else None,
            "built": bool(p and man),
        })
    return yearly, cards


@bp.route("/api/monthly/year-board")
def api_monthly_year_board():
    """Cards + year totals for the loaded matrix (and any stored months)."""
    year = (request.args.get("year") or str(date.today().year)).strip()
    if not re.fullmatch(r"\d{4}", year):
        return jsonify({"ok": False, "error": "year=YYYY"}), 400
    yearly, cards = _year_cards(year)
    return jsonify({
        "ok": True, "year": year,
        "has_matrix": yearly is not None,
        "source": (yearly or {}).get("source"),
        "routes": len((yearly or {}).get("entries") or []),
        "matrix_months": (yearly or {}).get("months") or [],
        "cards": cards,
    })


@bp.route("/api/monthly/record-attempt", methods=["POST"])
def api_monthly_record_attempt():
    """First-principles 'what if we really run it': no history ceiling."""
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
    routes = {}
    for e in active:
        src = _ORIGIN_MAP.get(e["origin"].upper(), e["origin"].upper())
        dst = _canon_dest(e["dest"])
        key = (src, dst, e["contractor"].upper())
        rec = routes.setdefault(key, {"src": src, "dst": dst,
                                      "contractor": e["contractor"].upper(),
                                      "dt": 0.0, "wmt_day": 0.0})
        rec["dt"] += e["dt"].get(mnum) or 0
        rec["wmt_day"] += e["wmt"].get(mnum) or 0
    route_list = [r for r in routes.values() if r["dt"] > 0]
    # Cycle + payload from measured route history.
    import csv as _csv
    cyc, pay = {}, {}
    try:
        with open(os.path.join(_ROOT, "data", "route_lookup.csv"), encoding="utf-8") as fh:
            for r in _csv.DictReader(fh):
                cyc[r["route"]] = float(r["mean_cycle_min"] or 0) or None
                pay[r["route"]] = float(r["median_payload_t"] or 0) or None
    except OSError:
        pass
    for r in route_list:
        r["payload"] = pay.get("%s>%s" % (r["src"], r["dst"]))
    out = _record_physics(route_list, {k: v for k, v in cyc.items() if v})
    if out is None:
        return jsonify({"ok": False, "error": "point_capacity.csv missing"}), 500
    man_day = sum(r["wmt_day"] for r in route_list)
    out["manual_day"] = round(man_day)
    out["month"] = month
    return jsonify({"ok": True, **out})


# ── "Record attempt" physics (owner 2026-08-13) ──────────────────────────────
# "no matter what was the history and if we want to run this plan, i want to
#  know what will happen ... what if we want to make new record, dont limit
#  your thinking ... think we really put this plan in work what will happen?"
#
# So: NO historical trip ceiling. Every truck is assumed to run the route's
# free-flow cycle all day (demand = DT x 1440 / cycle). The only limits left
# are physical infrastructure, each taken at its RECORD rate - the best hour
# ever measured at that point, sustained for 24 hours straight, which no
# operation has ever done. This is the most generous physically-grounded
# ceiling that exists. What cannot be served queues, and the queue is
# reported as trucks standing idle.

def _record_physics(route_list, cyc_lookup):
    import csv as _csv
    cap = {}
    try:
        with open(os.path.join(_ROOT, "data", "point_capacity.csv"), encoding="utf-8") as fh:
            for r in _csv.DictReader(fh):
                cap[(r["point"].upper(), r["kind"])] = {
                    "cap_hr": float(r["capacity_trips_hr"] or 0),
                    "peak_hr": float(r["peak_trips_hr"] or 0),
                }
    except OSError:
        return None
    # Free-flow demand per route.
    demands = []
    from collections import defaultdict as _dd
    load_d, dump_d = _dd(float), _dd(float)
    for r in route_list:
        cycle = cyc_lookup.get("%s>%s" % (r["src"], r["dst"]))
        est = cycle is None
        if est:
            # unmeasured route: median of routes out of the same source
            same = [v for k, v in cyc_lookup.items() if k.startswith(r["src"] + ">")]
            cycle = sorted(same)[len(same) // 2] if same else 120.0
        dem = r["dt"] * 1440.0 / cycle
        demands.append({"r": r, "cycle": cycle, "demand": dem, "cycle_estimated": est})
        load_d[r["src"]] += dem
        dump_d[r["dst"]] += dem
    # Served fraction at each point, at RECORD pace (best hour ever x 24).
    def frac(point, kind, demand):
        c = cap.get((point.upper(), kind))
        if not c or not c["peak_hr"]:
            return 1.0, None                      # no measured device: assume open
        day_cap = c["peak_hr"] * 24.0
        return (min(1.0, day_cap / demand) if demand > 0 else 1.0), day_cap
    bottlenecks = []
    lfrac, dfrac = {}, {}
    for p, dem in load_d.items():
        f, day_cap = frac(p, "loading", dem)
        lfrac[p] = f
        if f < 0.999 and day_cap:
            bottlenecks.append({"point": p, "kind": "loading", "demand": round(dem),
                                "record_day_cap": round(day_cap), "served_pct": round(f * 100),
                                "queued_trucks_per_hour": round((dem - day_cap) / 24.0, 1)})
    for p, dem in dump_d.items():
        f, day_cap = frac(p, "dumping", dem)
        dfrac[p] = f
        if f < 0.999 and day_cap:
            bottlenecks.append({"point": p, "kind": "dumping", "demand": round(dem),
                                "record_day_cap": round(day_cap), "served_pct": round(f * 100),
                                "queued_trucks_per_hour": round((dem - day_cap) / 24.0, 1)})
    paths, total_wmt, total_served, total_demand = [], 0.0, 0.0, 0.0
    for d in demands:
        r = d["r"]
        f = min(lfrac.get(r["src"], 1.0), dfrac.get(r["dst"], 1.0))
        served = d["demand"] * f
        payload = r.get("payload") or 50.0
        wmt = served * payload
        total_wmt += wmt
        total_served += served
        total_demand += d["demand"]
        assumptions = []
        if d.get("cycle_estimated"):
            assumptions.append("cycle estimated from other %s routes (this one unmeasured)" % r["src"])
        if (r["dst"].upper(), "dumping") not in cap:
            assumptions.append("no capacity data for %s dump - assumed open" % r["dst"])
        if not r.get("payload"):
            assumptions.append("payload assumed 50 t (route unmeasured)")
        paths.append({"key": "%s>%s" % (r["src"], r["dst"]), "contractor": r["contractor"],
                      "dt": int(round(r["dt"])), "cycle_min": round(d["cycle"]),
                      "demand_trips_day": round(d["demand"]), "served_trips_day": round(served),
                      "served_pct": round(f * 100), "wmt_day": round(wmt),
                      "assumptions": assumptions})
    return {"per_day_wmt": round(total_wmt), "demand_trips": round(total_demand),
            "served_trips": round(total_served), "paths": paths,
            "bottlenecks": sorted(bottlenecks, key=lambda b: b["served_pct"]),
            "note": ("NO history ceiling. Demand = every truck running the free-flow "
                     "cycle all day. Limits = each loading/dumping point at its RECORD "
                     "rate (best hour ever measured, held for 24 h straight). Trucks "
                     "beyond a point's record rate queue - they do not vanish.")}


# ── SAP-fixed rebalance advisor (owner 2026-08-13) ───────────────────────────
# "we can't reduce the tonnages of our SAP material ... come up with a plan
#  which will keep our SAP material quantity same. And if you want to add more
#  trucks in this, you can add there. And give me suggestions from where we can
#  reduce the trucks from Lemonite ... we can't switch the contractors."
#
# HARD CONSTRAINTS honoured:
#   1. SAP rows: tonnage NEVER goes down. Trucks may be ADDED to SAP rows that
#      still have measured headroom (below the fleet where the road saturates).
#   2. Contractor stays on its own route - no row changes contractor or route.
#   3. Only LIM rows may give up trucks, and only trucks that are past the
#      route's saturation point (they add ~nothing where they are).
# The advisor therefore only DOCUMENTS waste and headroom - it moves LIM's
# stranded trucks to SAP rows of the SAME contractor where the road still pays.

def _day_stats_from_snapshot():
    """Per-route day model: trimmed-mean rate, demonstrated cap, fleet max."""
    stats = {}
    try:
        import simulator_api as _sa
        rows_snap, _rain = _sa._path_snapshot()
        from collections import defaultdict as _dd
        day_agg = _dd(lambda: [0.0, 0.0])
        env = _dd(float)
        for r in rows_snap:
            k = (r["o"], r["dd"])
            day_agg[(k, r.get("d"))][0] += r.get("dt") or 0
            day_agg[(k, r.get("d"))][1] += r.get("trips") or 0
            env[k] = max(env[k], r.get("dt") or 0)
        by_path = _dd(list)
        for (k, _dte), (dtv, tr) in day_agg.items():
            if dtv > 0 and tr > 0:
                by_path[k].append((dtv, tr))
        for k, pts in by_path.items():
            if len(pts) < 5:
                continue
            rates = sorted(t / d for d, t in pts)
            core = rates[int(len(rates) * .2):max(int(len(rates) * .2) + 1, int(len(rates) * .8))]
            stats["%s>%s" % k] = {
                "rate": sum(core) / len(core),
                "cap": max(t for _d, t in pts),
                "dt_max": max(max(d for d, _t in pts), env[k]),
            }
    except Exception:  # noqa: BLE001
        pass
    return stats


@bp.route("/api/monthly/rebalance", methods=["POST"])
def api_monthly_rebalance():
    """SAP-fixed truck reallocation suggestions for one matrix month."""
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
        return jsonify({"ok": False, "error": "no matrix rows for %s" % month}), 400
    # Row per origin+dest+contractor+MATERIAL (material drives the constraint).
    rows = {}
    for e in active:
        src = _ORIGIN_MAP.get(e["origin"].upper(), e["origin"].upper())
        dst = _canon_dest(e["dest"])
        mat = (e.get("material") or "").upper()
        key = (src, dst, e["contractor"].upper(), mat)
        rec = rows.setdefault(key, {"src": src, "dst": dst, "route": "%s>%s" % (src, dst),
                                    "contractor": e["contractor"].upper(), "material": mat,
                                    "dt": 0.0, "wmt_day": 0.0})
        rec["dt"] += e["dt"].get(mnum) or 0
        rec["wmt_day"] += e["wmt"].get(mnum) or 0
    rows = [r for r in rows.values() if r["dt"] > 0]
    stats = _day_stats_from_snapshot()
    if not stats:
        return jsonify({"ok": False, "error": "no measured day history available (DB down?)"}), 503
    # Combined fleet per route (saturation is a road property).
    from collections import defaultdict as _dd
    comb = _dd(float)
    for r in rows:
        comb[r["route"]] += r["dt"]
    # Per-route saturation fleet N* = cap/rate.
    def n_star(route):
        s = stats.get(route)
        return (s["cap"] / s["rate"]) if s and s["rate"] > 0 else None
    # 1) LIM donors: trucks beyond saturation on their route (stranded).
    donors = []
    for r in rows:
        if r["material"] != "LIM":
            continue
        ns = n_star(r["route"])
        if ns is None:
            continue
        over = comb[r["route"]] - ns
        if over <= 0:
            continue
        # This row's share of the stranded trucks (pro-rata by its fleet).
        share = r["dt"] / comb[r["route"]] if comb[r["route"]] else 0
        stranded = min(r["dt"], over * share)
        if stranded >= 1:
            donors.append({"row": r, "stranded_dt": stranded, "n_star": ns})
    # 2) SAP receivers: same-contractor rows with measured headroom.
    receivers = []
    for r in rows:
        if r["material"] != "SAP":
            continue
        s = stats.get(r["route"])
        ns = n_star(r["route"])
        if s is None or ns is None:
            continue
        head = ns - comb[r["route"]]
        if head >= 1:
            receivers.append({"row": r, "headroom_dt": head, "rate": s["rate"],
                              "dt_max": s["dt_max"]})
    receivers.sort(key=lambda x: -x["rate"])            # best-paying road first
    # 3) Match: same contractor only; SAP tonnage only goes UP.
    moves = []
    pay_default = 49.9
    for d in donors:
        rem = d["stranded_dt"]
        for rc in receivers:
            if rem < 1:
                break
            if rc["row"]["contractor"] != d["row"]["contractor"]:
                continue
            take = min(rem, rc["headroom_dt"])
            if take < 1:
                continue
            gain = take * rc["rate"] * pay_default
            beyond = comb[rc["row"]["route"]] + take > rc["dt_max"]
            moves.append({
                "contractor": d["row"]["contractor"],
                "from_route": d["row"]["route"], "from_material": "LIM",
                "to_route": rc["row"]["route"], "to_material": "SAP",
                "trucks": int(take),
                "lim_wmt_lost_day": 0,
                "sap_wmt_gain_day": round(gain),
                "note": ("these %d trucks sit past %s's saturation (N*≈%d) and add "
                         "almost nothing there; on %s they still earn the full rate "
                         "(%.1f trips/DT·day)%s"
                         % (int(take), d["row"]["route"], round(d["n_star"]),
                            rc["row"]["route"], rc["rate"],
                            " — takes the road past its biggest measured fleet, label as trial" if beyond else "")),
            })
            rc["headroom_dt"] -= take
            rem -= take
    total_gain = sum(m["sap_wmt_gain_day"] for m in moves)
    return jsonify({
        "ok": True, "month": month,
        "constraints": ["SAP tonnage never reduced (only increased)",
                        "contractors stay on their own routes",
                        "only LIM trucks past their road's saturation point move"],
        "donors": [{"route": d["row"]["route"], "contractor": d["row"]["contractor"],
                    "dt": round(d["row"]["dt"]), "stranded_dt": round(d["stranded_dt"]),
                    "n_star": round(d["n_star"])} for d in donors],
        "moves": moves,
        "sap_gain_day": round(total_gain),
        "lim_loss_day": 0,
        "note": ("LIM tonnage is UNCHANGED by these moves: the donated trucks are "
                 "the ones already past the road's demonstrated saturation - the "
                 "road cannot serve them, so removing them does not remove trips. "
                 "SAP gains are earned at the receiving road's measured day rate."),
    })


# ── Priority allocation (owner 2026-08-13) ───────────────────────────────────
# "we have fixed amount of SAP material and TOS LIM material ... First
#  priority is our SAP ... Second priority is the TOS LIM ... and the third
#  is the rest of the Lemonite left [LD]. We don't get more trucks, so we
#  have to allocate the trucks in a way that we will fulfill our first two
#  priorities ... if we are moving trucks, we can move in between same
#  contractor, first try to move from same plans [same origin], if still we
#  are less ... look for other plans with same contractor."
#
# Fleet is FIXED at the matrix's month total per contractor. Allocation:
#   P1  SAP rows      — target = matrix WMT/day; DT solved from the route's
#                       measured day rate, capped at the saturation fleet
#                       N* = cap/rate (beyond it trucks add ~nothing).
#   P2  LIM from TOS  — same treatment, after SAP is satisfied.
#   P3  LIM from LD   — buffer: absorbs every truck still left (flagged when
#                       that pushes past the route's own N*).
# Moves honour: same contractor only; same-origin donors first, then other
# plans of the same contractor.

@bp.route("/api/monthly/allocate", methods=["POST"])
def api_monthly_allocate():
    body = request.get_json(silent=True) or {}
    month = (body.get("month") or "").strip()
    if not _month_path(month):
        return jsonify({"ok": False, "error": "supply month=YYYY-MM"}), 400
    if not os.path.isfile(_YEARLY_PATH):
        return jsonify({"ok": False, "error": "no yearly matrix loaded yet"}), 404
    with open(_YEARLY_PATH, encoding="utf-8") as fh:
        yearly = json.load(fh)
    mnum = str(int(month[5:7]))
    stats = _day_stats_from_snapshot()
    if not stats:
        return jsonify({"ok": False, "error": "no measured day history (DB down?)"}), 503
    import csv as _csv
    pay = {}
    try:
        with open(os.path.join(_ROOT, "data", "route_lookup.csv"), encoding="utf-8") as fh:
            for r in _csv.DictReader(fh):
                pay[r["route"]] = float(r["median_payload_t"] or 0) or None
    except OSError:
        pass

    # Rows for the month, keyed by origin/material/otype/dest/contractor.
    rows = []
    for e in yearly["entries"]:
        wmt = e["wmt"].get(mnum) or 0
        dt = e["dt"].get(mnum) or 0
        if wmt <= 0 and dt <= 0:
            continue
        src = _ORIGIN_MAP.get(e["origin"].upper(), e["origin"].upper())
        dst = _canon_dest(e["dest"])
        route = "%s>%s" % (src, dst)
        mat = (e.get("material") or "").upper()
        otype = (e.get("otype") or "").upper()
        prio = 1 if mat == "SAP" else (2 if otype == "TOS" else 3)
        rows.append({"origin": e["origin"].upper(), "route": route, "src": src,
                     "dst": dst, "mat": mat, "otype": otype,
                     "contractor": e["contractor"].upper(),
                     "prio": prio, "target": wmt, "matrix_dt": dt})
    if not rows:
        return jsonify({"ok": False, "error": "no matrix rows for %s" % month}), 400

    def route_rate(route):
        s = stats.get(route)
        return (s["rate"], s["cap"] / s["rate"] if s["rate"] > 0 else None,
                s["dt_max"]) if s else (None, None, None)

    # Required DT for a row's target at its route's measured day rate.
    for r in rows:
        rate, n_star, dt_max = route_rate(r["route"])
        p = pay.get(r["route"]) or 49.9
        r["rate"], r["n_star"], r["dt_max"], r["payload"] = rate, n_star, dt_max, p
        if rate and rate > 0 and r["target"] > 0:
            need = r["target"] / (rate * p)
            r["req_dt"] = need
            r["capped"] = n_star is not None and need > n_star
            if r["capped"]:
                r["req_dt"] = n_star            # beyond N* trucks add ~nothing
        else:
            r["req_dt"] = r["matrix_dt"]        # no history: keep the plan's DT
            r["capped"] = False

    # Allocate per contractor with the fixed month fleet.
    from collections import defaultdict as _dd
    fleet = _dd(float)
    for r in rows:
        fleet[r["contractor"]] += r["matrix_dt"]
    alloc_out, moves, shortfalls = [], [], []
    for cont in sorted(fleet):
        crows = [r for r in rows if r["contractor"] == cont]
        remaining = fleet[cont]
        # P1 then P2 get their requirement (ceil'd); P3 shares the rest.
        for prio in (1, 2):
            for r in sorted([x for x in crows if x["prio"] == prio],
                            key=lambda x: -x["target"]):
                give = min(remaining, (int(r["req_dt"]) + (r["req_dt"] % 1 > 0.01)))
                r["alloc_dt"] = round(give)
                remaining -= give
                if give + 0.5 < r["req_dt"]:
                    shortfalls.append("%s %s (P%d): needs %d DT, only %d left in %s's fleet"
                                      % (r["route"], r["mat"], prio, round(r["req_dt"]),
                                         round(give), cont))
        p3 = [x for x in crows if x["prio"] == 3]
        p3_matrix = sum(x["matrix_dt"] for x in p3) or 1
        for r in p3:
            r["alloc_dt"] = round(remaining * (x_share := r["matrix_dt"] / p3_matrix))
        used = sum(x.get("alloc_dt", 0) for x in crows)
        # rounding drift goes to the biggest P3 row (or biggest row at all)
        drift = round(fleet[cont]) - used
        if drift and crows:
            tgt = max(p3 or crows, key=lambda x: x.get("alloc_dt", 0))
            tgt["alloc_dt"] = max(0, tgt.get("alloc_dt", 0) + drift)

        # Moves: same contractor; same-origin donors first.
        donors = [x for x in crows if x.get("alloc_dt", 0) < x["matrix_dt"]]
        receivers = [x for x in crows if x.get("alloc_dt", 0) > x["matrix_dt"]]
        for rec in sorted(receivers, key=lambda x: x["prio"]):
            need = rec["alloc_dt"] - rec["matrix_dt"]
            for same_origin in (True, False):
                if need <= 0:
                    break
                for don in donors:
                    if need <= 0:
                        break
                    if (don["origin"] == rec["origin"]) != same_origin:
                        continue
                    avail = don["matrix_dt"] - don.get("alloc_dt", 0) - don.get("_given", 0)
                    if avail <= 0:
                        continue
                    take = min(need, avail)
                    don["_given"] = don.get("_given", 0) + take
                    need -= take
                    moves.append({"contractor": cont,
                                  "from": "%s (%s %s)" % (don["route"], don["mat"], don["otype"]),
                                  "to": "%s (%s %s)" % (rec["route"], rec["mat"], rec["otype"]),
                                  "trucks": round(take),
                                  "same_origin": same_origin})

    # Expected outcome of the NEW allocation per row (ceiling model).
    comb = _dd(float)
    for r in rows:
        comb[r["route"]] += r.get("alloc_dt", 0)
    for r in rows:
        rate, n_star = r["rate"], r["n_star"]
        a = r.get("alloc_dt", 0)
        if rate and a > 0:
            eff_n = comb[r["route"]]
            served_frac = 1.0
            if n_star and eff_n > n_star:
                over = (eff_n - n_star) / n_star
                served = max(stats[r["route"]]["cap"] / (1 + 0.15 * over * over),
                             0.3 * rate * eff_n)
                served_frac = served / (rate * eff_n)
            r["pred_wmt"] = round(a * rate * served_frac * r["payload"])
        else:
            r["pred_wmt"] = None
        r["met"] = r["pred_wmt"] is not None and r["target"] > 0 \
            and r["pred_wmt"] >= r["target"] * 0.95
    prio_sum = {p: {"target": round(sum(r["target"] for r in rows if r["prio"] == p)),
                    "pred": round(sum(r["pred_wmt"] or 0 for r in rows if r["prio"] == p))}
                for p in (1, 2, 3)}
    return jsonify({
        "ok": True, "month": month,
        "priorities": ["P1 SAP (fixed supply)", "P2 LIM from TOS", "P3 LIM from LD (buffer)"],
        "fleet": {c: round(v) for c, v in fleet.items()},
        "rows": [{k: r.get(k) for k in
                  ("origin", "route", "mat", "otype", "contractor", "prio", "target",
                   "matrix_dt", "alloc_dt", "pred_wmt", "met", "capped", "n_star", "dt_max")}
                 for r in sorted(rows, key=lambda x: (x["prio"], x["contractor"]))],
        "moves": moves,
        "shortfalls": shortfalls,
        "prio_summary": prio_sum,
        "note": ("Fleet fixed at the matrix month total per contractor. Required DT "
                 "= target / (measured day rate x payload), capped at the route's "
                 "saturation fleet N* (beyond it trucks add ~nothing). P1+P2 are "
                 "filled first; P3 (LD limonite) absorbs every remaining truck. "
                 "Moves stay within one contractor, same-origin donors first."),
    })
