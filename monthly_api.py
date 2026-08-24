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
    • Comparison + export: Key sheet (target, old predicted plan, optimized
    predicted plan) plus one sheet per month. Default Excel hides achievable.
    ⬇ with achievable (achv=1) adds old / optimized simulate next to predicted,
    matching Plan Allocate (Your plan vs after Allocate). Never averaged.
    Charts sit under their tables. White report except coverage badges.

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
    n = len(_days_in(month))
    alloc, src = _resolve_allocation(month, st)
    view = _alloc_view(alloc, n, src, include_detail=True)
    return jsonify({
        "ok": True, "month": month, "state": st, "exists": st is not None,
        "alloc": view,
    })


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
             "otype": p.get("otype"), "targetWmt": p.get("targetWmt"),
             "dt_before": ((p.get("_preAlloc") or {}) if isinstance(p.get("_preAlloc"), dict) else {}).get("dt"),
             "wbSel": p.get("wbSel")}
            for p in ((plan.get("paths") or {}).values()
                      if isinstance(plan.get("paths"), dict)
                      else (plan.get("paths") or []))
            if isinstance(p, dict)
        ],
        "days": days,
        "built_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": ("Same holding plan every day; day = 2 x 12 h shifts x saved "
                 "per-shift prediction. Target is the matrix. "
                 "Rain fixed at the saved plan's value."),
    }
    day_alloc = plan.get("allocation")
    if isinstance(day_alloc, dict) and day_alloc.get("frozen"):
        st["prediction"]["allocation"] = day_alloc
        st["saved_day_allocation"] = day_alloc
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


# Line colours for charts: gold target, slate old plan, navy optimized.
# Table numbers are always ink (black) — never red.
_XLSX_PRED, _XLSX_TGT = "1F2937", "EAB308"
_XLSX_NAVY, _XLSX_MUTED, _XLSX_INK = "1F4E79", "64748B", "1F2937"
_XLSX_ACHV = "1F2937"
# Target, old predicted, optimized predicted — (hex, dotted). No red.
_XLSX_CLOCKS = (
    ("EAB308", False),
    ("64748B", True),
    ("1F4E79", False),
)
# Same three, then old achievable (dotted green) and optimized achievable.
_XLSX_CLOCKS_ACHV3 = (
    _XLSX_CLOCKS[0],       # target
    _XLSX_CLOCKS[2],       # optimized predicted
    ("059669", False),     # optimized achievable
)
_XLSX_CLOCKS_ACHV = _XLSX_CLOCKS + (
    ("86EFAC", True),
    ("059669", False),
)


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


def _xlsx_card_border(color):
    """Thin box with a coloured top bar — the Year / month scorecard look."""
    from openpyxl.styles import Border, Side
    thin = Side(style="thin", color="D0D5DD")
    bar = Side(style="medium", color=color or _XLSX_NAVY)
    return Border(left=thin, right=thin, top=bar, bottom=thin)


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


def _xlsx_headers(ws, row, headers, start=1, center=False):
    from openpyxl.styles import Alignment
    _box, head = _xlsx_sides()
    mid = Alignment(wrap_text=True, vertical="center", horizontal="center")
    for i, h in enumerate(headers, start=start):
        c = ws.cell(row=row, column=i, value=h)
        c.font = _xlsx_font(True, 10, _XLSX_NAVY)
        if center:
            c.alignment = mid
        else:
            c.alignment = Alignment(wrap_text=True, vertical="center",
                                    horizontal="right" if i > start else "left")
        c.border = head
    ws.row_dimensions[row].height = 26


def _xlsx_mid():
    from openpyxl.styles import Alignment
    return Alignment(horizontal="center", vertical="center", wrap_text=True)


def _xlsx_num(cell, value, bold=False, center=False):
    cell.value = value
    cell.font = _xlsx_font(bold, 11)
    cell.number_format = "#,##0"
    cell.border = _xlsx_sides()[0]
    if center:
        cell.alignment = _xlsx_mid()


def _xlsx_text(cell, value, bold=False, color=None, size=11, center=False):
    cell.value = value
    cell.font = _xlsx_font(bold, size, color)
    cell.border = _xlsx_sides()[0]
    if center:
        cell.alignment = _xlsx_mid()


def _xlsx_widths(ws, widths, start=1):
    from openpyxl.utils import get_column_letter
    for i, w in enumerate(widths, start=start):
        letter = get_column_letter(i)
        ws.column_dimensions[letter].width = max(
            ws.column_dimensions[letter].width or 0, w)


def _xlsx_paint_lines(chart, specs):
    """specs: hex strings or (hex, dotted) tuples. Dotted = old plan only.
    Target (gold, solid) is a hard line — thicker, no dash."""
    for s, spec in zip(chart.series, specs):
        if isinstance(spec, (tuple, list)):
            col = spec[0]
            dotted = bool(spec[1]) if len(spec) > 1 else False
        else:
            col, dotted = spec, False
        hard = (not dotted) and str(col).upper() == _XLSX_TGT
        s.graphicalProperties.line.solidFill = col
        s.graphicalProperties.line.width = 20000 if dotted else (35000 if hard else 28000)
        if dotted:
            s.graphicalProperties.line.dashStyle = "sysDash"
        s.marker.symbol = "diamond" if hard else "circle"
        s.marker.size = 8 if hard else (5 if dotted else 7)
        s.marker.graphicalProperties.solidFill = col
        s.marker.graphicalProperties.line.solidFill = col


def _xlsx_rate(cell, value, bold=False, center=True):
    cell.value = value
    cell.font = _xlsx_font(bold, 10)
    cell.number_format = "0.00"
    cell.border = _xlsx_sides()[0]
    if center:
        cell.alignment = _xlsx_mid()


def _xlsx_total_border(cell):
    from openpyxl.styles import Border, Side
    med = Side(style="medium", color=_XLSX_NAVY)
    thin = Side(style="thin", color="D0D5DD")
    cell.border = Border(left=thin, right=thin, top=med, bottom=thin)


def _xlsx_line_chart(ws, title, y_title, min_col, max_col, header_row, last_row, anchor,
                     height=7.5, width=15, cat_col=1, colors=None):
    from openpyxl.chart import LineChart, Reference
    lc = LineChart()
    lc.title = title
    lc.y_axis.title = y_title
    lc.y_axis.scaling.min = 0
    lc.y_axis.numFmt = "#,##0"
    lc.height, lc.width = height, width
    lc.legend.position = "t"
    lc.style = None
    data = Reference(ws, min_col=min_col, max_col=max_col,
                     min_row=header_row, max_row=last_row)
    cats = Reference(ws, min_col=cat_col, min_row=header_row + 1, max_row=last_row)
    lc.add_data(data, titles_from_data=True)
    lc.set_categories(cats)
    n = max_col - min_col + 1
    palette = colors or ((_XLSX_PRED, _XLSX_TGT) + _XLSX_CLOCKS)
    _xlsx_paint_lines(lc, palette[:n])
    ws.add_chart(lc, anchor)
    return lc


def _xlsx_five_clock_block(ws, row, title, sub, points, start=1, chart_col="I", achv=False):
    """Month (or day) × clocks + % of target. Chart sits UNDER the table.
    achv=True adds old / optimized achievable (simulate), same as Plan Allocate."""
    from openpyxl.utils import get_column_letter
    r = _xlsx_section(ws, row, title, sub)
    if achv:
        heads = ["Month", "Target", "Optimized predicted plan", "Optimized achievable"]
        keys = ["target", "new_pred", "new_achv"]
    else:
        heads = ["Month", "Target", "Old predicted plan", "Optimized predicted plan"]
        keys = ["target", "old_pred", "new_pred"]
    heads.append("Optimized %")
    if achv:
        heads.append("Achievable %")
    if points and points[0].get("label") == "Date":
        heads[0] = "Date"
    _xlsx_headers(ws, r, heads, start=start, center=True)
    header_row = r
    rr = r
    n_clocks = len(keys)
    pct_col = start + 1 + n_clocks
    achv_pct_col = pct_col + 1
    for p in points:
        rr += 1
        _xlsx_text(ws.cell(row=rr, column=start), p.get("name"), center=True)
        for i, key in enumerate(keys):
            cell = ws.cell(row=rr, column=start + 1 + i)
            _xlsx_num(cell, p.get(key), center=True)
        tgt, np_ = p.get("target"), p.get("new_pred")
        _xlsx_paint_cov(ws.cell(row=rr, column=pct_col), _cov_pct(np_, tgt))
        if achv:
            _xlsx_paint_cov(ws.cell(row=rr, column=achv_pct_col),
                            _cov_pct(p.get("new_achv"), tgt))
    data_last = rr
    tot = {k: 0 for k in keys}
    n_have = {k: 0 for k in keys}
    for p in points:
        for k in keys:
            v = p.get(k)
            if v is not None:
                tot[k] += v
                n_have[k] += 1
    if data_last > header_row:
        rr += 1
        lab = ws.cell(row=rr, column=start, value="TOTAL")
        lab.font = _xlsx_font(True, 11, _XLSX_NAVY)
        lab.alignment = _xlsx_mid()
        _xlsx_total_border(lab)
        for i, k in enumerate(keys):
            cell = ws.cell(row=rr, column=start + 1 + i, value=tot[k] if n_have[k] else None)
            cell.font = _xlsx_font(True, 11, _XLSX_INK)
            cell.number_format = "#,##0"
            cell.alignment = _xlsx_mid()
            _xlsx_total_border(cell)
        tgt, np_ = tot["target"], tot["new_pred"]
        c5 = ws.cell(row=rr, column=pct_col)
        _xlsx_paint_cov(c5, _cov_pct(np_, tgt) if n_have["target"] else None)
        _xlsx_total_border(c5)
        if achv:
            c6 = ws.cell(row=rr, column=achv_pct_col)
            _xlsx_paint_cov(c6, _cov_pct(tot.get("new_achv"), tgt) if n_have["target"] else None)
            _xlsx_total_border(c6)
        chart_row = rr + 2
        anchor = "%s%d" % (get_column_letter(start), chart_row)
        _xlsx_line_chart(
            ws, title, "tonnes", start + 1, start + n_clocks, header_row, data_last,
            anchor, height=8, width=18 if achv else 16, cat_col=start,
            colors=_XLSX_CLOCKS_ACHV3 if achv else _XLSX_CLOCKS)
        return chart_row + 16
    return rr + 2


def _xlsx_board_header(ws, heading, sub, start=1):
    """Year-board chrome: title, then a one-line reading note."""
    from openpyxl.utils import get_column_letter
    _xlsx_sheet_setup(ws)
    ws.cell(row=1, column=start, value=heading).font = _xlsx_font(True, 18, _XLSX_NAVY)
    ws.merge_cells(start_row=1, start_column=start, end_row=1, end_column=start + 5)
    ws.cell(row=2, column=start, value=sub).font = _xlsx_font(False, 10, _XLSX_MUTED)
    ws.merge_cells(start_row=2, start_column=start, end_row=2, end_column=start + 5)
    ws.row_dimensions[1].height = 26
    ws.row_dimensions[2].height = 18
    for i, w in enumerate([24, 24, 28, 22, 16, 16], start=start):
        ws.column_dimensions[get_column_letter(i)].width = w
    return 4


def _xlsx_kpi_strip(ws, row, kpis, start=1):
    """Scorecard: colour bar on the label, large figure below.
    Each item is (label, value, color) or (label, value, color, unit).
    Pass value as a 0–100 coverage figure with unit='pct' to format as percent."""
    from openpyxl.styles import Alignment
    mid = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for i, item in enumerate(kpis):
        label, value, _color = item[0], item[1], item[2]
        unit = item[3] if len(item) > 3 else None
        col = start + i
        if unit == "pct":
            lab_txt = label
        elif unit:
            lab_txt = "%s\n%s" % (label, unit)
        else:
            lab_txt = label
        lab = ws.cell(row=row, column=col, value=lab_txt)
        lab.font = _xlsx_font(True, 8, _XLSX_NAVY)
        lab.alignment = mid
        lab.border = _xlsx_card_border(_XLSX_NAVY)
        cell = ws.cell(row=row + 1, column=col)
        cell.alignment = mid
        cell.border = _xlsx_sides()[0]
        if unit == "pct":
            _xlsx_paint_cov(cell, value, size=20)
            cell.border = _xlsx_sides()[0]
            cell.alignment = mid
        else:
            cell.value = value
            cell.font = _xlsx_font(True, 20, _XLSX_INK)
            cell.number_format = "#,##0"
    ws.row_dimensions[row].height = 28
    ws.row_dimensions[row + 1].height = 32
    return row + 3


def _xlsx_month_cards(ws, row, cards, year, start=2):
    """Month matrix: names across, Predicted / Target down column A."""
    box = _xlsx_sides()[0]
    mid = _xlsx_mid()
    ws.cell(row=row, column=start, value="Months").font = _xlsx_font(True, 13, _XLSX_NAVY)
    ws.row_dimensions[row].height = 19
    names_row = row + 1
    meta_row = row + 2
    for i, c in enumerate(cards):
        col = start + i
        name = ("%s %s" % (c.get("name") or "", year)).strip()
        meta = "%s days" % (c.get("n_days") or "—")
        if c.get("dt") is not None:
            meta += " · %s DT" % format(int(c["dt"]), ",")
        if not c.get("built"):
            meta += " · not built yet"
        cell_n = ws.cell(row=names_row, column=col, value=name)
        cell_n.font = _xlsx_font(True, 12, _XLSX_INK)
        cell_n.alignment = mid
        cell_n.border = box
        cell_m = ws.cell(row=meta_row, column=col, value=meta)
        cell_m.font = _xlsx_font(False, 9, _XLSX_MUTED)
        cell_m.alignment = mid
        cell_m.border = box
    metric_rows = (
        (row + 3, "Old predicted plan", "pred_month", _XLSX_INK),
        (row + 4, "Target", "target_month", _XLSX_INK),
    )
    for mrow, label, key, color in metric_rows:
        lab = ws.cell(row=mrow, column=1, value=label)
        lab.font = _xlsx_font(False, 9, _XLSX_MUTED)
        lab.alignment = mid
        lab.border = box
        ws.row_dimensions[mrow].height = 20
        for i, c in enumerate(cards):
            cell = ws.cell(row=mrow, column=start + i, value=c.get(key))
            cell.font = _xlsx_font(True, 14, color)
            cell.number_format = "#,##0"
            cell.alignment = mid
            cell.border = box
    return row + 6


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


def _xlsx_saved_day_allocation(ws, r, alloc):
    """Plan-tab Allocate snapshot carried from the saved daily plan."""
    box = _xlsx_sides()[0]
    mid = _xlsx_mid()
    old = alloc.get("old") or {}
    new = alloc.get("new") or {}
    fleet = alloc.get("fleet") or {}
    r = _xlsx_section(
        ws, r, "Saved daily allocation (Plan tab)",
        "Your plan (old) stays as checked. New Allocation Plan is the optimized fleet. "
        "Predicted = path model. Target = matrix.")
    goals = alloc.get("goals") or {}
    buckets = alloc.get("buckets") or {}
    labels = [("sap", "SAP · must-move"), ("tos", "LIM-TOS"), ("ld", "Other LIM · LD")]
    r = _xlsx_section(
        ws, r, "Old plan vs optimized plan",
        "Same GP targets. Old = Your plan as checked. New = after Allocate DT.")
    _xlsx_headers(ws, r, ["", "SAP", "LIM-TOS", "Other LIM"], center=True)
    metric_rows = [
        ("Target t/day", "target", _XLSX_INK, False),
        ("Old predicted plan", "pred_before", _XLSX_INK, False),
        ("Optimized predicted plan", "pred_after", _XLSX_INK, True),
        ("Old DT", "dt_before", _XLSX_INK, False),
        ("New DT", "dt_after", _XLSX_INK, True),
    ]
    for lab, key, color, bold in metric_rows:
        r += 1
        lab_c = ws.cell(row=r, column=1, value=lab)
        lab_c.font = _xlsx_font(False, 10, _XLSX_MUTED)
        lab_c.border = box
        lab_c.alignment = mid
        for i, (bkey, _) in enumerate(labels):
            b = buckets.get(bkey) or {}
            val = b.get(key) if key != "target" else (b.get("target") or goals.get(bkey))
            cell = ws.cell(row=r, column=2 + i, value=val)
            cell.border = box
            cell.alignment = mid
            cell.font = _xlsx_font(bold, 14 if bold else 12, color)
            if isinstance(val, (int, float)):
                cell.number_format = "#,##0"
    r += 2
    old = alloc.get("old") or {}
    new = alloc.get("new") or {}
    fleet = alloc.get("fleet") or {}
    note = (
        "Fleet %s DT old · %s DT new (same trucks). "
        "Totals — old predicted plan %s · optimized predicted plan %s."
        % (fleet.get("before") or old.get("dt") or "—",
           fleet.get("after") or new.get("dt") or "—",
           old.get("pred") if old.get("pred") is not None else "—",
           new.get("pred") if new.get("pred") is not None else "—")
    )
    ws.cell(row=r, column=1, value=note).font = _xlsx_font(False, 9, _XLSX_MUTED)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    r += 2
    rows = alloc.get("rows") or []
    if rows:
        r = _xlsx_path_alloc_table(
            ws, r, rows, "New Allocation Plan table",
            "Old = Your plan as checked. New = after Allocate DT. "
            "WMT/DT is tonnes per truck-trip (payload).")
    return r


def _xlsx_pct_cell(cell, value):
    cell.value = None if value is None else value / 100.0
    cell.font = _xlsx_font(True, 11)
    cell.number_format = "0.0%"
    cell.border = _xlsx_sides()[0]
    cell.alignment = _xlsx_mid()


def _xlsx_cov_tone(pct):
    """Coverage % is ink on a clear cell — no red/gold/green pills in Excel."""
    if pct is None:
        return None, None
    return _XLSX_INK, None


def _xlsx_paint_cov(cell, pct, size=11):
    """Percent of target as a plain black figure (no traffic-light fill)."""
    _xlsx_pct_cell(cell, pct)
    cell.font = _xlsx_font(True, size, _XLSX_INK)
    return cell


def _pick_achv(d, old=True, grain="month"):
    """Raw simulate achievable; fall back to the capped companion if raw is missing."""
    d = d or {}
    if old:
        v = d.get("old_achv_raw_" + grain)
        return v if v is not None else d.get("old_achv_" + grain)
    v = d.get("new_achv_raw_" + grain)
    return v if v is not None else d.get("new_achv_" + grain)


def _pick_mat_achv(m, before=True, grain="month"):
    m = m or {}
    if before:
        v = m.get("achv_before_raw_" + grain)
        return v if v is not None else m.get("achv_before_" + grain)
    v = m.get("achv_after_raw_" + grain)
    return v if v is not None else m.get("achv_after_" + grain)


def _ten_key(row):
    """Key into _tenant_trips_per_dt.

    Identity of a ROW, not of a road: id() of the row dict, because the same
    (path, contractor) legitimately appears more than once in one month —
    TF>HUAFEI/RIM is both a P2 LIM-TOS row and a P3 LIM-LD row, at different
    rates. Keying on (path, contractor) let the second row's answer overwrite
    the first, and the P2 row then printed the P3 row's 2.15 over its own
    2.11: a +1.9% GAIN from added traffic.

    The ROAD key (path, contractor) is still what the engine ratio is cached
    under inside _tenant_trips_per_dt — that one really is a road property.
    ONE home for each, so the lookup and the build cannot drift apart.
    """
    return id(row)


def _tenant_trips_per_dt(rows):
    """{(path, contractor) -> Trips/DT with the OTHER TENANTS on the road}.

    Owner, 2026-08-24: several tenants (MHM, POSITION, PMA, HSM, KR>RSF,
    HUAFEI>RSF — 1,340 DT) run our haul road and give us no tonnage. Every
    Trips/DT this workbook has ever shown was therefore the clear-road answer.
    This adds one column with the same routes re-priced under that traffic.

    It does NOT move tonnage, targets, DT or the allocation. Tenant trucks are
    road load only, so the honest report is "here is the rate you would
    actually turn", beside the plan, not a silently re-planned month.

    ## Why this is a RATIO applied to the sheet's own number

    The first version printed the engine's tenant-priced rate directly and it
    came out HIGHER than the clear-road column beside it (BLB>FENI KM0 4.61
    against 4.58) — adding traffic appearing to speed trucks up. The two
    numbers had two causes, not one: the sheet's Trips/DT comes from the
    FROZEN allocation saved on the plan date, which predates the current
    hybrid calibration, while the new column was a fresh engine call. The
    tenant effect (~-1%) was smaller than the drift between the two vintages,
    so the drift showed and the tenants did not.

    So the engine is asked BOTH questions — same route, same fleet, same
    contractor, same segment map, tenants off then on — and only their RATIO
    is used, applied to whatever the sheet already shows. The column is then
    exactly "your own number, degraded by the tenant traffic and nothing
    else", and it can never disagree with its neighbour for a reason the
    caption does not name. Re-freezing the saved allocations under the hybrid
    model is a separate open thread (HANDOFF §14) and this must not pre-empt
    it silently.

    Returns {} when the congestion package or its calibration is unavailable
    (fixture mode, fresh clone) — the caller then omits the column rather than
    printing a blank one that looks like zero traffic.
    """
    try:
        from congestion.config import route_params
        from congestion.predictor import predict
        from congestion.segments import segment_trucks
    except ImportError:
        return {}
    combined = {}
    for row in rows or []:
        k = row.get("key")
        dt = _finite(row.get("dt_after"))
        if k and dt:
            combined[k] = combined.get(k, 0.0) + float(dt)
    if not combined:
        return {}
    # Every route the plan runs is on the road together, so the segment map is
    # built from the WHOLE plan and both calls share it. Only the tenant flag
    # differs between them.
    seg = segment_trucks(combined)
    out = {}
    # Cache the RATIO per (road, contractor), never the finished value: the
    # ratio is a property of the road and the fleet, but the value it is
    # applied to is the ROW's own rate. Caching the value made the second
    # TF>HUAFEI/SMA row (217 DT, 2.36) print the first row's answer (52 DT,
    # 2.37) and so appear to GAIN 0.4% from added traffic.
    ratios = {}
    for row in rows or []:
        k = row.get("key")
        shown = _path_rates(row).get("trips_per_dt_after")
        # The engine ratio is cached per (road, contractor): RIM and SMA run
        # the same road at different overheads, and caching on the path alone
        # gave both of them whichever was priced first (TF>HUAFEI SMA printed
        # RIM's 2.17 against its own 2.36).
        ck = (k, (row.get("contractor") or "").strip().upper())
        if not k or not shown:
            continue
        if ck not in ratios:
            ratios[ck] = None
            try:
                if route_params(k).get("calibrated"):
                    kw = dict(segment_fleet=seg, mode="road",
                              contractor=ck[1] or None)
                    clear = predict(k, combined[k], None, **kw)
                    withn = predict(k, combined[k], None,
                                    tenant_flow_hr=True, **kw)
                    base = clear.get("trips_per_DT_per_day")
                    tenv = withn.get("trips_per_DT_per_day")
                    # A route not on the shared mainline (the BLB spur) comes
                    # back with tenant_traffic False and its clear-road answer.
                    # Leave it blank rather than repeating the neighbouring
                    # column, so "no tenant traffic here" cannot be misread as
                    # "tenants made no difference".
                    if base and tenv and withn.get("tenant_traffic"):
                        ratios[ck] = float(tenv) / float(base)
            except (ValueError, ArithmeticError, KeyError, TypeError, OSError):
                ratios[ck] = None
        if ratios[ck]:
            # THREE decimals, not two. At official capacities the tenants cost
            # 0.1-1.5% of trips/DT, and 2 dp rounds that straight back onto the
            # neighbouring column: TF>FENI KM15 — the road carrying 800 of the
            # 1,340 tenant DT — printed an identical number to its own rate, so
            # the one row the reader checks first said the tenants did nothing.
            # A column whose answer is always invisible is not a column.
            out[_ten_key(row)] = round(float(shown) * ratios[ck], 3)
    return out


def _xlsx_path_alloc_table(ws, r, rows, title, sub, achv=False):
    """Old vs new path table: WMT, DT, trips, plus trips/DT and WMT/DT.
    achv=True appends the engine's achievable (t/day) old vs new."""
    box = _xlsx_sides()[0]
    mid = _xlsx_mid()
    rows = list(rows or [])
    rows.sort(key=lambda x: (x.get("prio") or 9, x.get("key") or ""))
    if not rows:
        return r
    # One extra column: the same paths priced with the other tenants' trucks
    # on the road (congestion/tenants.py). Empty dict -> no column at all.
    ten = _tenant_trips_per_dt(rows)
    if ten:
        try:
            from congestion.tenants import TENANTS as _TEN_REG
            _n_dt = sum(t["dt"] for t in _TEN_REG)
            _names = ", ".join(t["name"] for t in _TEN_REG)
        except ImportError:
            _n_dt, _names = 0, ""
        # State the basis in the sheet. A lower Trips/DT with no explanation
        # beside it is how a reader concludes the model changed its mind.
        sub = (sub or "") + (
            " · 'Trips/DT w/ other tenants' re-prices the SAME fleet with the "
            "other tenants' %s DT on the shared road (%s). They carry no "
            "tonnage for us and take no trucks from us — only road. Tonnes, "
            "targets and DT in this table are unchanged. Both fleets are on ONE "
            "clock: a tenant truck occupies the loaded lane for one pass per "
            "road cycle, exactly as ours does, so they take the busiest section "
            "(POS 12–KM15) to about 70%% of its capacity. Remaining caveat: that "
            "capacity (600/hr S1-S3, 400/hr S4) is derived from posted speed "
            "limits and an assumed 50 m following distance, NOT a counted "
            "traffic survey — if the real lane carries less, this cost grows "
            "sharply, because delay rises with the fourth power of v/c. Blank = "
            "that route is off the shared mainline (the BLB spur), not that the "
            "tenants made no difference."
            % (_n_dt, _names))
    r = _xlsx_section(ws, r, title, sub)
    if achv:
        # Achievable view drops every "old" column (owner, 2026-08-19):
        # Target · DT · Trips · Predicted · rates · Achievable, new plan only.
        heads = [
            "P", "Path", "Contractor", "Material", "Target WMT/day",
            "DT", "Trips", "Predicted WMT", "WMT/DT", "Trips/DT",
            "Achievable",
        ]
    else:
        heads = [
            "P", "Path", "Contractor", "Material", "Target WMT/day",
            "DT old", "DT new",
            "Trips old", "Trips new",
            "WMT old", "WMT new",
            "WMT/DT old", "WMT/DT new",
            "Trips/DT old", "Trips/DT new",
        ]
    if ten:
        heads.append("Trips/DT w/ other tenants")
    _xlsx_headers(ws, r, heads, center=True)
    tot = {
        "tgt": 0, "dt_b": 0, "dt_a": 0, "tr_b": 0, "tr_a": 0,
        "pr_b": 0, "pr_a": 0,
    }
    for row in rows:
        r += 1
        rates = _path_rates(row)
        mat = "%s%s" % (row.get("material") or "",
                        (" · " + row["otype"]) if row.get("otype") else "")
        av_new = _finite(row.get("achv_sim"))
        if av_new is None:
            av_new = _finite(row.get("achv_after"))
        if achv:
            vals = [
                "P%s" % (row.get("prio") or ""), row.get("key"), row.get("contractor"),
                mat, row.get("target"),
                row.get("dt_after"), rates["trips_after"], row.get("pred_after"),
                rates["wmt_per_trip_after"], rates["trips_per_dt_after"],
                av_new,
            ]
        else:
            vals = [
                "P%s" % (row.get("prio") or ""), row.get("key"), row.get("contractor"),
                mat, row.get("target"),
                row.get("dt_before"), row.get("dt_after"),
                rates["trips_before"], rates["trips_after"],
                row.get("pred_before"), row.get("pred_after"),
                rates["wmt_per_trip_before"], rates["wmt_per_trip_after"],
                rates["trips_per_dt_before"], rates["trips_per_dt_after"],
            ]
        ten_col = len(vals) + 1 if ten else None
        if ten:
            vals.append(ten.get(_ten_key(row)))
        for col, val in enumerate(vals, start=1):
            cell = ws.cell(row=r, column=col, value=val)
            cell.border = box
            cell.alignment = mid
            cell.font = _xlsx_font(col in (2, 7, 9, 11), 9)
            if ten_col and col == ten_col:
                if isinstance(val, (int, float)):
                    # 3 dp: the tenant effect is sub-1% on most roads and a
                    # "0.00" format hides it behind the column it is meant to
                    # be compared against.
                    cell.number_format = "0.000"
                cell.font = _xlsx_font(True, 9, _XLSX_NAVY)
                continue
            if achv:
                if col in (9, 10) and isinstance(val, (int, float)):
                    cell.number_format = "0.00"
                elif col >= 5 and isinstance(val, (int, float)):
                    cell.number_format = "#,##0"
                if col in (6, 7, 8):
                    cell.font = _xlsx_font(True, 9, _XLSX_INK)
                if col == 11:
                    cell.font = _xlsx_font(True, 9, _XLSX_INK)
            else:
                if col in (12, 13, 14, 15) and isinstance(val, (int, float)):
                    cell.number_format = "0.00"
                elif col >= 5 and isinstance(val, (int, float)):
                    cell.number_format = "#,##0"
                if col in (6, 8, 10, 12, 14):
                    cell.font = _xlsx_font(False, 9, _XLSX_INK)
                if col in (7, 9, 11, 13, 15):
                    cell.font = _xlsx_font(True, 9, _XLSX_INK)
        tot["tgt"] += row.get("target") or 0
        tot["dt_b"] += row.get("dt_before") or 0
        tot["dt_a"] += row.get("dt_after") or 0
        tot["pr_b"] += row.get("pred_before") or 0
        tot["pr_a"] += row.get("pred_after") or 0
        tot["av_b"] = tot.get("av_b", 0) + (_finite(row.get("achv_before")) or 0)
        av_a = _finite(row.get("achv_sim"))
        if av_a is None:
            av_a = _finite(row.get("achv_after"))
        tot["av_a"] = tot.get("av_a", 0) + (av_a or 0)
        if rates["trips_before"] is not None:
            tot["tr_b"] += rates["trips_before"]
        elif rates["trips_per_dt_before"] is not None and row.get("dt_before"):
            tot["tr_b"] += rates["trips_per_dt_before"] * (row.get("dt_before") or 0)
        if rates["trips_after"] is not None:
            tot["tr_a"] += rates["trips_after"]
        elif rates["trips_per_dt_after"] is not None and row.get("dt_after"):
            tot["tr_a"] += rates["trips_per_dt_after"] * (row.get("dt_after") or 0)
    r += 1
    tpd_b = round(tot["tr_b"] / tot["dt_b"], 2) if tot["dt_b"] else None
    tpd_a = round(tot["tr_a"] / tot["dt_a"], 2) if tot["dt_a"] else None
    pay_b = round(tot["pr_b"] / tot["tr_b"], 2) if tot["tr_b"] else None
    pay_a = round(tot["pr_a"] / tot["tr_a"], 2) if tot["tr_a"] else None
    if achv:
        tot_vals = [
            "TOTAL", "%s paths" % len(rows), "", "",
            tot["tgt"] or None, tot["dt_a"] or None,
            int(round(tot["tr_a"])) if tot["tr_a"] else None,
            tot["pr_a"] or None, pay_a, tpd_a,
            int(round(tot.get("av_a") or 0)) or None,
        ]
    else:
        tot_vals = [
            "TOTAL", "%s paths" % len(rows), "", "",
            tot["tgt"] or None, tot["dt_b"] or None, tot["dt_a"] or None,
            int(round(tot["tr_b"])) if tot["tr_b"] else None,
            int(round(tot["tr_a"])) if tot["tr_a"] else None,
            tot["pr_b"] or None, tot["pr_a"] or None,
            pay_b, pay_a, tpd_b, tpd_a,
        ]
    if ten:
        # DT-weighted over EVERY row, exactly the denominator tpd_a uses.
        # Summing only the rows that have a tenant value put the two totals on
        # different fleets: the BLB spur and the IWIP rows dropped out and the
        # "with tenants" total read 2.92 against a clear-road 2.74 — 6.6% HIGH
        # for a column that can only ever be lower. A row the tenants do not
        # touch keeps its own rate, because that IS its rate under this traffic.
        t_tr = 0.0
        for x in rows:
            dt_x = _finite(x.get("dt_after")) or 0
            if not dt_x:
                continue
            rate = ten.get(_ten_key(x))
            if rate is None:
                rate = _path_rates(x).get("trips_per_dt_after")
            t_tr += (rate or 0) * dt_x
        # 3 dp for the same reason as the per-row value: at 2 dp the total sat
        # on top of the clear-road total while every one of its own rows had
        # moved down.
        tot_vals.append(round(t_tr / tot["dt_a"], 3) if tot["dt_a"] else None)
    for col, val in enumerate(tot_vals, start=1):
        cell = ws.cell(row=r, column=col, value=val)
        cell.font = _xlsx_font(True, 9, _XLSX_NAVY)
        cell.alignment = mid
        _xlsx_total_border(cell)
        _rate_col = (col in (9, 10) if achv else col in (12, 13, 14, 15))
        _ten_total = bool(ten) and col == len(tot_vals)
        if _ten_total:
            _rate_col = True
        if _rate_col and isinstance(val, (int, float)):
            cell.number_format = "0.000" if _ten_total else "0.00"
        elif col >= 5 and isinstance(val, (int, float)):
            cell.number_format = "#,##0"
    r += 1
    pct_lab = ws.cell(row=r, column=1, value="% of target")
    pct_lab.font = _xlsx_font(True, 9, _XLSX_MUTED)
    pct_lab.alignment = mid
    pct_lab.border = box
    last_col = (11 if achv else 15) + (1 if ten else 0)
    for col in range(2, last_col + 1):
        ws.cell(row=r, column=col).border = box
        ws.cell(row=r, column=col).alignment = mid
    pred_col = 8 if achv else 11
    _xlsx_pct_cell(ws.cell(row=r, column=pred_col), _cov_pct(tot["pr_a"], tot["tgt"]))
    ws.cell(row=r, column=pred_col).font = _xlsx_font(True, 9, _XLSX_PRED)
    if achv:
        _xlsx_pct_cell(ws.cell(row=r, column=11), _cov_pct(tot.get("av_a"), tot["tgt"]))
        ws.cell(row=r, column=11).font = _xlsx_font(True, 9, _XLSX_ACHV)
    return r + 1


def _split_route_key(key):
    """'BLB>FENI KM13' → (BLB, FENI KM13)."""
    k = (key or "").strip()
    if ">" not in k:
        return k, ""
    src, dst = k.split(">", 1)
    return src.strip(), dst.strip()


def _path_mat_label(row):
    mat = (row.get("material") or "").strip()
    otype = (row.get("otype") or "").strip()
    if mat.upper() == "SAP":
        return "SAP"
    if mat and otype:
        return "%s - %s" % (mat, otype)
    return mat or otype


def _card_alloc_detail(c):
    """Saved Allocate snapshot for a year-board card, with path rows."""
    month = c.get("month")
    st = _load_state(month) or {"month": month}
    st["month"] = month
    if c.get("alloc_raw"):
        raw, src = c["alloc_raw"], c.get("alloc_source")
    else:
        raw, src = _resolve_allocation(month, st, day=c.get("_alloc_day"))
    n = c.get("n_days") or len(_days_in(month))
    return _alloc_view(raw, n, src, include_detail=True), n


def _collect_year_path_rows(cards):
    """One row per allocated path per month. WMT new is t/day; predicted/month = × NB days."""
    out = []
    for c in cards:
        alloc, n = _card_alloc_detail(c)
        if not alloc:
            continue
        for row in alloc.get("rows") or []:
            dt = _finite(row.get("dt_after"))
            wmt = _finite(row.get("pred_after"))
            if not dt and not wmt:
                continue
            rates = _path_rates(row)
            origin, dest = _split_route_key(row.get("key"))
            achv_new = _finite(row.get("achv_sim"))
            if achv_new is None:
                achv_new = _finite(row.get("achv_after"))
            out.append({
                "month": c.get("name") or c.get("month"),
                "month_key": c.get("month") or "",
                "prio": row.get("prio") or 9,
                "origin": origin,
                "dest": dest,
                "key": row.get("key"),
                "contractor": row.get("contractor"),
                "material": _path_mat_label(row),
                "target": _finite(row.get("target")),
                "dt": dt,
                "trips": rates["trips_after"],
                "wmt": wmt,
                "wmt_per_trip": rates["wmt_per_trip_after"],
                "trips_per_dt": rates["trips_per_dt_after"],
                "achv": achv_new,
                "n_days": n,
                "pred_month": int(round(wmt * n)) if wmt is not None and n else None,
                "achv_month": int(round(achv_new * n)) if achv_new is not None and n else None,
            })
    out.sort(key=lambda x: (x["month_key"], x["prio"], x.get("key") or ""))
    return out


def _xlsx_all_paths_table(ws, r, cards, achv=False):
    """All months × allocated paths. NB Days then Predicted / month = WMT × days."""
    from openpyxl.styles import Alignment, PatternFill
    rows = _collect_year_path_rows(cards)
    if not rows:
        return r
    r = _xlsx_section(
        ws, r, "Paths — all months",
        "Optimized plan only. WMT is t/day. Predicted / month = WMT × NB Days. "
        "WMT/DT is tonnes per truck-trip (payload)."
        + (" Achievable is /api/simulate, t/day." if achv else ""))
    heads = [
        "Month", "Priority", "Origin", "Destination", "Path", "Contractor", "Material",
        "Target WMT/day", "DT", "Trips", "WMT",
        "WMT/DT", "Trips/DT",
    ]
    if achv:
        heads.append("Achievable")
    heads += ["NB Days", "Predicted / month"]
    _xlsx_headers(ws, r, heads, center=True)
    navy = PatternFill("solid", fgColor=_XLSX_NAVY)
    for col in range(1, len(heads) + 1):
        cell = ws.cell(row=r, column=col)
        cell.fill = navy
        cell.font = _xlsx_font(True, 9, "FFFFFF")
    header_row = r
    box = _xlsx_sides()[0]
    mid = _xlsx_mid()
    tot = {"tgt": 0, "dt": 0, "tr": 0, "wmt": 0, "achv": 0, "pm": 0}
    pred_col = 15 if achv else 14
    n_cols = pred_col
    for row in rows:
        r += 1
        vals = [
            row["month"], "P%s" % row["prio"], row["origin"], row["dest"],
            row["key"], row["contractor"], row["material"],
            row["target"], row["dt"], row["trips"], row["wmt"],
            row["wmt_per_trip"], row["trips_per_dt"],
        ]
        if achv:
            vals.append(row["achv"])
        vals += [row["n_days"], row["pred_month"]]
        for col, val in enumerate(vals, start=1):
            cell = ws.cell(row=r, column=col, value=val)
            cell.border = box
            cell.alignment = mid if col != 5 else Alignment(
                horizontal="left", vertical="center")
            cell.font = _xlsx_font(col == 5, 9)
            if col in (12, 13) and isinstance(val, (int, float)):
                cell.number_format = "0.00"
            elif col >= 8 and isinstance(val, (int, float)):
                cell.number_format = "#,##0"
            if 9 <= col <= 13:
                cell.font = _xlsx_font(True, 9, _XLSX_PRED)
            if achv and col == 14:
                cell.font = _xlsx_font(True, 9, _XLSX_ACHV)
            if col == pred_col:
                cell.font = _xlsx_font(True, 9, _XLSX_PRED)
        tot["tgt"] += row["target"] or 0
        tot["dt"] += row["dt"] or 0
        tot["tr"] += row["trips"] or 0
        tot["wmt"] += row["wmt"] or 0
        tot["achv"] += row["achv"] or 0
        tot["pm"] += row["pred_month"] or 0
    r += 1
    pay = round(tot["wmt"] / tot["tr"], 2) if tot["tr"] else None
    tpd = round(tot["tr"] / tot["dt"], 2) if tot["dt"] else None
    tot_vals = [
        "TOTAL", "%s paths" % len(rows), "", "", "", "", "",
        tot["tgt"] or None, tot["dt"] or None,
        int(round(tot["tr"])) if tot["tr"] else None,
        tot["wmt"] or None, pay, tpd,
    ]
    if achv:
        tot_vals.append(int(round(tot["achv"])) if tot["achv"] else None)
    tot_vals += [None, tot["pm"] or None]
    for col, val in enumerate(tot_vals, start=1):
        cell = ws.cell(row=r, column=col, value=val)
        cell.font = _xlsx_font(True, 9, _XLSX_NAVY)
        cell.alignment = mid
        _xlsx_total_border(cell)
        if col in (12, 13) and isinstance(val, (int, float)):
            cell.number_format = "0.00"
        elif col >= 8 and isinstance(val, (int, float)):
            cell.number_format = "#,##0"
        if col == pred_col:
            cell.font = _xlsx_font(True, 9, _XLSX_PRED)
        if achv and col == 14:
            cell.font = _xlsx_font(True, 9, _XLSX_ACHV)
    from openpyxl.utils import get_column_letter
    ws.auto_filter.ref = "A%d:%s%d" % (
        header_row, get_column_letter(n_cols), r - 1)
    ws.freeze_panes = "A%d" % (header_row + 1)
    _xlsx_widths(ws, [
        10, 10, 10, 14, 22, 12, 14,
        14, 10, 12, 12, 12, 12,
        14 if achv else 10, 12, 16,
    ])
    return r + 2


def _xlsx_append_paths_sheet(wb, year, cards, used, prefix="", achv=False,
                             after_sheet=None):
    """Sheet after Year: every allocated path in every month."""
    if not _collect_year_path_rows(cards):
        return
    name = _xlsx_unique_sheet_name(prefix + "Paths", used)
    if after_sheet and after_sheet in wb.sheetnames:
        pos = wb.sheetnames.index(after_sheet) + 1
    else:
        pos = 1 if wb.sheetnames else 0
    ws = wb.create_sheet(name, pos)
    _xlsx_sheet_setup(ws)
    ws["A1"] = "Paths · %s" % year
    ws["A1"].font = _xlsx_font(True, 16, _XLSX_NAVY)
    ws.merge_cells("A1:P1")
    ws["A2"] = (
        "One row per route per month. Filter Month. "
        "Predicted / month = WMT (t/day) × NB Days."
        + (" Achievable is /api/simulate." if achv else ""))
    ws["A2"].font = _xlsx_font(False, 10, _XLSX_MUTED)
    ws.merge_cells("A2:P2")
    _xlsx_all_paths_table(ws, 4, cards, achv=achv)
    ws.row_dimensions[1].height = 24


def _xlsx_fill_month_alloc(ws, month, title, alloc, st=None, achv=False):
    """One month: old vs optimized predicted plan, materials, path table. No DT-move list.
    achv=True adds the engine's achievable everywhere predicted appears."""
    _xlsx_sheet_setup(ws)
    n_days = len(_days_in(month))
    src = alloc.get("source_date") or ""
    ws["A1"] = title
    ws["A1"].font = _xlsx_font(True, 16, _XLSX_NAVY)
    ws.merge_cells("A1:Q1")
    if achv:
        ws["A2"] = (
            "Target = matrix. Optimized predicted plan = after Allocate DT. "
            "Achievable = /api/simulate (effective cycle + loader clip). "
            "Not averaged with predicted."
            + ((" Saved %s." % src) if src else "")
            + " Month = day × %s days." % n_days)
    else:
        ws["A2"] = (
            "Target = matrix. Old predicted plan = Your plan as checked. "
            "Optimized predicted plan = after Allocate DT."
            + ((" Saved %s." % src) if src else "")
            + " Month = day × %s days." % n_days)
    ws["A2"].font = _xlsx_font(False, 10, _XLSX_MUTED)
    ws.merge_cells("A2:Q2")

    box = _xlsx_sides()[0]
    mid = _xlsx_mid()
    r = 4
    cov = alloc.get("cov_new_pred")
    if achv:
        month_kpis = [
            ("Target", alloc.get("target_month"), _XLSX_TGT, "Month tonnes"),
            ("Optimized predicted plan", alloc.get("new_pred_month"), _XLSX_PRED, "Month tonnes"),
            ("Optimized achievable", _pick_achv(alloc, False, "month"), _XLSX_ACHV, "Month tonnes"),
            ("Optimized vs target", cov, "059669" if (cov or 0) >= 100 else "D97706", "pct"),
        ]
        day_kpis = [
            ("Target", alloc.get("target_day"), _XLSX_TGT, "t / day"),
            ("Optimized predicted plan", alloc.get("new_pred_day"), _XLSX_PRED, "t / day"),
            ("Optimized achievable", _pick_achv(alloc, False, "day"), _XLSX_ACHV, "t / day"),
            ("Fleet after allocate", alloc.get("dt_after"), _XLSX_INK, "DT"),
        ]
    else:
        month_kpis = [
            ("Target", alloc.get("target_month"), _XLSX_TGT, "Month tonnes"),
            ("Old predicted plan", alloc.get("old_pred_month"), _XLSX_MUTED, "Month tonnes"),
            ("Optimized predicted plan", alloc.get("new_pred_month"), _XLSX_PRED, "Month tonnes"),
            ("Optimized vs target", cov, "059669" if (cov or 0) >= 100 else "D97706", "pct"),
        ]
        day_kpis = [
            ("Target", alloc.get("target_day"), _XLSX_TGT, "t / day"),
            ("Old predicted plan", alloc.get("old_pred_day"), _XLSX_MUTED, "t / day"),
            ("Optimized predicted plan", alloc.get("new_pred_day"), _XLSX_PRED, "t / day"),
            ("Fleet after allocate", alloc.get("dt_after"), _XLSX_INK, "DT"),
        ]
    r = _xlsx_kpi_strip(ws, r, month_kpis, start=1)
    r = _xlsx_kpi_strip(ws, r, day_kpis, start=1)

    mats = alloc.get("materials") or {}
    r = _xlsx_section(
        ws, r, "Materials — t / day",
        "Same three clocks as the year sheet. Coverage is optimized predicted plan ÷ target.")
    labels = [("sap", "SAP"), ("tos", "LIM-TOS"), ("ld", "LIM-LD")]
    _xlsx_headers(ws, r, ["", "SAP", "LIM-TOS", "LIM-LD", "Together"], center=True)
    if achv:
        metric = [
            ("Target t/day", lambda k: (mats.get(k) or {}).get("target_day"), alloc.get("target_day"), _XLSX_INK, False),
            ("Optimized predicted plan", lambda k: (mats.get(k) or {}).get("pred_after_day"), alloc.get("new_pred_day"), _XLSX_INK, True),
            ("Optimized achievable",
             lambda k: _pick_mat_achv(mats.get(k) or {}, False, "day"),
             _pick_achv(alloc, False, "day"), _XLSX_INK, True),
            ("New DT", lambda k: (mats.get(k) or {}).get("dt_after"), alloc.get("dt_after"), _XLSX_INK, True),
        ]
    else:
        metric = [
            ("Target t/day", lambda k: (mats.get(k) or {}).get("target_day"), alloc.get("target_day"), _XLSX_INK, False),
            ("Old predicted plan", lambda k: (mats.get(k) or {}).get("pred_before_day"), alloc.get("old_pred_day"), _XLSX_INK, False),
            ("Optimized predicted plan", lambda k: (mats.get(k) or {}).get("pred_after_day"), alloc.get("new_pred_day"), _XLSX_INK, True),
            ("Old DT", lambda k: (mats.get(k) or {}).get("dt_before"), alloc.get("dt_before"), _XLSX_INK, False),
            ("New DT", lambda k: (mats.get(k) or {}).get("dt_after"), alloc.get("dt_after"), _XLSX_INK, True),
        ]
    for lab, fn, tot, color, bold in metric:
        r += 1
        lab_c = ws.cell(row=r, column=1, value=lab)
        lab_c.font = _xlsx_font(False, 10, _XLSX_MUTED)
        lab_c.border = box
        lab_c.alignment = mid
        for i, (k, _) in enumerate(labels):
            cell = ws.cell(row=r, column=2 + i, value=fn(k))
            cell.border = box
            cell.alignment = mid
            cell.font = _xlsx_font(bold, 13 if bold else 11, color)
            if isinstance(fn(k), (int, float)):
                cell.number_format = "#,##0"
        tot_c = ws.cell(row=r, column=5, value=tot)
        tot_c.border = box
        tot_c.alignment = mid
        tot_c.font = _xlsx_font(True, 13, color)
        if isinstance(tot, (int, float)):
            tot_c.number_format = "#,##0"
    r += 1
    lab_c = ws.cell(row=r, column=1, value="Optimized % of target")
    lab_c.font = _xlsx_font(True, 10, _XLSX_NAVY)
    lab_c.border = box
    lab_c.alignment = mid
    for i, (k, _) in enumerate(labels):
        _xlsx_paint_cov(ws.cell(row=r, column=2 + i), (mats.get(k) or {}).get("cov_pred"), size=13)
    _xlsx_paint_cov(ws.cell(row=r, column=5), alloc.get("cov_new_pred"), size=13)
    ws.row_dimensions[r].height = 22
    r += 2
    left_lab = ws.cell(row=r, column=1, value="Leaving vs target · month t")
    left_lab.font = _xlsx_font(False, 10, _XLSX_MUTED)
    left_lab.border = box
    for i, (k, _) in enumerate(labels):
        _xlsx_num(ws.cell(row=r, column=2 + i), (mats.get(k) or {}).get("left_pred_month"), center=True)
    _xlsx_num(ws.cell(row=r, column=5), alloc.get("left_new_pred_month"), True, center=True)

    rows = list(alloc.get("rows") or [])
    if rows:
        r += 2
        r = _xlsx_path_alloc_table(
            ws, r, rows, "Paths — old predicted plan vs optimized predicted plan",
            "P1 SAP · P2 LIM-TOS · P3 LIM-LD. WMT is predicted tonnes. DT is trucks. "
            "Trips are predicted trips. WMT/DT is tonnes per truck-trip (payload)."
            + (" Achievable is /api/simulate (effective cycle + loader clip), t/day." if achv else ""),
            achv=achv)

    cap = alloc.get("capacity") or {}
    if cap:
        # Two labelled numbers, never merged: LIM-LD capacity is never clipped,
        # only the tonnage credited against the target stops at it.
        r += 2
        r = _xlsx_section(
            ws, r, "LIM-LD capacity vs credited production",
            "Capacity is what the free fleet could move and is never clipped. "
            "Credited is what counts against the target. The difference is "
            "unused/excess capacity — reported, never folded into production.")
        _xlsx_headers(ws, r, ["", "DT", "t/day", "t/month"], start=1, center=True)
        for lab, dt_k, day_k, mon_k in (
                ("Capacity (never clipped)", "ld_dt_capacity",
                 "ld_t_day_capacity", "ld_t_month_capacity"),
                ("Credited against target", "ld_dt_credited",
                 "ld_t_day_credited", "ld_t_month_credited"),
                ("Unused / excess capacity", "ld_dt_unused",
                 "ld_t_day_excess", "ld_t_month_excess")):
            r += 1
            _xlsx_text(ws.cell(row=r, column=1), lab)
            _xlsx_num(ws.cell(row=r, column=2), cap.get(dt_k), center=True)
            _xlsx_num(ws.cell(row=r, column=3), cap.get(day_k), center=True)
            _xlsx_num(ws.cell(row=r, column=4), cap.get(mon_k), center=True)
        r += 1
        if not cap.get("feasible", True):
            ws.cell(row=r, column=1, value=(
                "NOT FEASIBLE: targets this month need %s DT more than the pool "
                "holds. Credited tonnage is what the fielded trucks can move, "
                "not what was asked." % cap.get("infeasible_dt"))
            ).font = _xlsx_font(True, 10, _XLSX_INK)
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=10)
            r += 1

    # Hour grid sits ABOVE the 30-day daily table so it is not buried under
    # a chart. Same table as Plan → C · Road crowding by hour.
    r = _xlsx_month_corridor_block(ws, r + 2, alloc=alloc)

    r += 2
    days = _days_in(month)
    points = [{
        "name": d,
        "label": "Date",
        "target": alloc.get("target_day"),
        "old_pred": alloc.get("old_pred_day"),
        "new_pred": alloc.get("new_pred_day"),
        "old_achv": _pick_achv(alloc, True, "day") if achv else None,
        "new_achv": _pick_achv(alloc, False, "day") if achv else None,
    } for d in days]
    r = _xlsx_five_clock_block(
        ws, r, "Daily WMT (flat — the same plan every day)",
        "Target, old predicted plan, optimized predicted plan"
        + (" · old / optimized achievable." if achv else ". Same day every day."),
        points, start=1, chart_col="A", achv=achv)

    _xlsx_widths(ws, [16, 22, 14, 14, 14, 11, 11, 11, 11, 12, 12, 12, 12, 12, 12, 12, 12])
    ws.freeze_panes = "A4"
    ws.row_dimensions[1].height = 24
    return alloc.get("new_pred_month"), alloc.get("target_month")


def _xlsx_fill_month(ws, st, title, achv=False):
    """One month: KPIs, Production & capacity, SAP targets / required DT, daily chart.
    achv=True adds the engine's achievable (Plan Step 2 /api/simulate)."""
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
    ws["A2"] = ("Same day every day. Old predicted plan = path model · Target = matrix."
                + (" Achievable = /api/simulate (effective cycle + loader clip), same as Plan Step 2."
                   if achv else ""))
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

    r = 4
    month_kpis = [
        ("Target", tot_t or None, _XLSX_TGT, "Month tonnes"),
        ("Old predicted plan", tot_p or None, _XLSX_MUTED, "Month tonnes"),
    ]
    if achv:
        month_kpis.append(("Achievable", tot_a or None, _XLSX_ACHV, "Month tonnes"))
    month_kpis.append(("Trucks", p.get("dt"), _XLSX_INK, "DT"))
    r = _xlsx_kpi_strip(ws, r, month_kpis, start=1)
    day_kpis = [
        ("Target", tgt_day, _XLSX_TGT, "t / day"),
        ("Old predicted plan", pred_day, _XLSX_MUTED, "t / day"),
    ]
    if achv:
        day_kpis.append(("Achievable", achv_day, _XLSX_ACHV, "t / day"))
    r = _xlsx_kpi_strip(ws, r, day_kpis, start=1)
    box = _xlsx_sides()[0]
    mid = _xlsx_mid()
    r = _xlsx_section(ws, r, "Production",
                      "Day = 2 × 12 h shifts. Old predicted plan is the path model. Target is the matrix.")

    cap_heads = ["Path", "Contractor", "Material", "DT", "Cycle min",
                 "Eff. cycle min", "Trips/DT", "Old predicted plan t/day"]
    if achv:
        cap_heads.append("Achievable t/day")
    cap_heads += ["Target t/day", "Roster"]
    _xlsx_headers(ws, r, cap_heads, center=True)
    tot_dt = tot_pred = tot_tgt = tot_path_achv = 0
    pred_col = 8
    achv_col = 9 if achv else None
    tgt_col = 10 if achv else 9
    roster_col = tgt_col + 1
    for i, prow in enumerate(paths):
        r += 1
        sr = sim_rows[i] if i < len(sim_rows) else {}
        key = prow.get("key")
        dt = prow.get("dt") or 0
        pred = prow.get("pred_wmt_day")
        tgt = prow.get("manual_wmt_day")
        trips_dt = sr.get("trips_per_shift_per_truck")
        path_achv = prow.get("achv_wmt_day")
        if path_achv is None and sr.get("achievable_production_t") is not None:
            path_achv = float(sr["achievable_production_t"]) * 2
        vals = [
            key, prow.get("contractor"), prow.get("material"), dt,
            sr.get("predicted_cycle_time_min"), sr.get("effective_cycle_min"),
            trips_dt, pred,
        ]
        if achv:
            vals.append(path_achv)
        vals += [tgt, sr.get("trucks_to_roster")]
        for col, val in enumerate(vals, start=1):
            cell = ws.cell(row=r, column=col, value=val)
            cell.border = box
            cell.font = _xlsx_font(col == 1, 10)
            cell.alignment = mid
            if col in (4, 5, 6, 7, pred_col, tgt_col, roster_col) + ((achv_col,) if achv_col else ()) and val is not None:
                cell.number_format = "#,##0.0" if col in (5, 6, 7) else "#,##0"
        tot_dt += dt or 0
        tot_pred += pred or 0
        tot_tgt += tgt or 0
        tot_path_achv += path_achv or 0
        ws.row_dimensions[r].height = 18
    if paths:
        r += 1
        _xlsx_text(ws.cell(row=r, column=1), "TOTAL", True, _XLSX_NAVY, center=True)
        for col in range(2, roster_col + 1):
            ws.cell(row=r, column=col).border = box
            ws.cell(row=r, column=col).alignment = mid
        _xlsx_num(ws.cell(row=r, column=4), tot_dt or None, True, center=True)
        _xlsx_num(ws.cell(row=r, column=pred_col), tot_pred or None, True, center=True)
        if achv:
            ac = ws.cell(row=r, column=achv_col)
            _xlsx_num(ac, tot_path_achv or None, True, center=True)
        _xlsx_num(ws.cell(row=r, column=tgt_col), tot_tgt or None, True, center=True)

    warns = sim_sum.get("capacity_warnings") or p.get("extrapolated") or []
    if warns:
        r += 2
        r = _xlsx_section(ws, r, "Capacity warnings")
        for w in warns:
            ws.cell(row=r, column=1, value=str(w)).font = _xlsx_font(False, 9, _XLSX_MUTED)
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=12)
            ws.cell(row=r, column=1).alignment = Alignment(wrap_text=True)
            ws.row_dimensions[r].height = 28
            r += 1

    r += 2
    sap_rows = _sap_table_rows(st, paths, sim_rows)
    r = _xlsx_section(
        ws, r, "Priority targets — P1 SAP · P2 LIM from TOS",
        "Supplied LD tonnage is the P3 target. Predicted = path model.")
    sap_heads = ["P", "Path", "Mat · type", "Contractor", "Target t/day", "Old predicted plan t/day",
                 "Allocated DT", "Required DT", "Status"]
    _xlsx_headers(ws, r, sap_heads, center=True)
    if not sap_rows:
        r += 1
        _xlsx_text(ws.cell(row=r, column=1),
                   "No P1/P2 rows in the matrix for this month.",
                   False, _XLSX_MUTED, 10)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=10)
    for sap in sap_rows:
        r += 1
        vals = ["P%s" % sap.get("prio", 1), sap["path"],
                "%s · %s" % (sap.get("mat") or "", sap.get("otype") or "—"),
                sap["contractor"], sap["target"], sap["pred"],
                sap["alloc_dt"], sap["req_dt"], status]
        for col, val in enumerate(vals, start=1):
            cell = ws.cell(row=r, column=col, value=val)
            cell.border = box
            cell.font = _xlsx_font(col == 2 or col == 9, 10, _XLSX_INK)
            cell.alignment = mid
            if col in (5, 6, 7, 8) and val is not None:
                cell.number_format = "#,##0"

    alloc = (st or {}).get("allocation") or {}
    if alloc.get("new") or alloc.get("old"):
        r += 2
        r = _xlsx_section(
            ws, r, "After priority allocation",
            "Original production above is the matrix fleet. "
            "These clocks are after moving DT to P1 then P2 inside each contractor.")
        r = _xlsx_kpi_strip(ws, r, [
            ("Target", (alloc.get("new") or alloc.get("old") or {}).get("target"),
             _XLSX_TGT, "t / day"),
            ("Old predicted plan", (alloc.get("old") or {}).get("pred"),
             _XLSX_MUTED, "t / day"),
            ("Optimized predicted plan", (alloc.get("new") or {}).get("pred"),
             _XLSX_PRED, "t / day"),
        ] + ([
            ("Old achievable", (alloc.get("old") or {}).get("achv"),
             _XLSX_MUTED, "t / day"),
            ("Optimized achievable",
             (alloc.get("new") or {}).get("achv_sim")
             if (alloc.get("new") or {}).get("achv_sim") is not None
             else (alloc.get("new") or {}).get("achv"),
             _XLSX_ACHV, "t / day"),
        ] if achv else []), start=1)
        if alloc.get("shortfalls"):
            r += 1
            r = _xlsx_section(ws, r, "Fleet shortfalls")
            for s in alloc["shortfalls"]:
                ws.cell(row=r, column=1, value=str(s)).font = _xlsx_font(False, 9, _XLSX_MUTED)
                ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=10)
                r += 1

    day_alloc = (st or {}).get("saved_day_allocation") or {}
    if day_alloc.get("frozen"):
        r += 2
        r = _xlsx_saved_day_allocation(ws, r, day_alloc)

    r += 3
    daily_heads = ["Date", "Old predicted plan"]
    if achv:
        daily_heads.append("Achievable")
    daily_heads.append("Target")
    daily_head = _xlsx_section(
        ws, r, "Daily WMT",
        "Same day every day — the lines are flat on purpose."
        + (" Achievable is /api/simulate." if achv else ""))
    _xlsx_headers(ws, daily_head, daily_heads, center=True)
    dr = daily_head
    tgt_dcol = 4 if achv else 3
    for d, pw, aw, tw in rows:
        dr += 1
        _xlsx_text(ws.cell(row=dr, column=1), d, center=True)
        pred_c = ws.cell(row=dr, column=2)
        _xlsx_num(pred_c, pw, center=True)
        if achv:
            achv_c = ws.cell(row=dr, column=3)
            _xlsx_num(achv_c, aw, center=True)
        tgt_c = ws.cell(row=dr, column=tgt_dcol)
        _xlsx_num(tgt_c, tw, center=True)
    last_daily = dr
    dr += 1
    _xlsx_text(ws.cell(row=dr, column=1), "TOTAL", True, _XLSX_NAVY, center=True)
    tot_p_c = ws.cell(row=dr, column=2)
    _xlsx_num(tot_p_c, tot_p or None, True, center=True)
    if achv:
        tot_a_c = ws.cell(row=dr, column=3)
        _xlsx_num(tot_a_c, tot_a or None, True, center=True)
    tot_t_c = ws.cell(row=dr, column=tgt_dcol)
    _xlsx_num(tot_t_c, tot_t or None, True, center=True)
    if last_daily > daily_head:
        pal = (_XLSX_MUTED, _XLSX_ACHV, _XLSX_TGT) if achv else (_XLSX_MUTED, _XLSX_TGT)
        _xlsx_line_chart(ws, "Daily WMT", "t/day", 2, tgt_dcol, daily_head, last_daily,
                         "A%d" % (dr + 2), colors=pal)

    last_chart_row = dr + 18
    r = _xlsx_month_corridor_block(ws, last_chart_row, alloc=day_alloc if day_alloc.get("frozen") else None,
                                  paths=paths)

    _xlsx_widths(ws, [22, 14, 14, 13, 12, 14, 13, 16, 20, 16, 14, 10])
    ws.freeze_panes = "A4"
    ws.row_dimensions[1].height = 24
    return tot_p, tot_a, tot_t


def _xlsx_month_book(month, st):
    from openpyxl import Workbook
    wb = Workbook()
    n = len(_days_in(month))
    raw, src = _resolve_allocation(month, st)
    alloc = _alloc_view(raw, n, src, include_detail=True)
    label = "%s %s" % (calendar.month_name[int(month[5:7])], month[:4])
    key = wb.active
    if alloc:
        key.title = "Key"
        _xlsx_fill_month_alloc(key, month, "%s — old vs new" % label, alloc, st)
        return wb
    key.title = "Key"
    rows, _p, _m = _daily_triples(st)
    tot_p = sum((pw or 0) for _, pw, _, _ in rows)
    tot_a = sum((aw or 0) for _, _, aw, _ in rows)
    tot_t = sum((tw or 0) for _, _, _, tw in rows)
    r = _xlsx_board_header(
        key, label,
        "Same day every day. Old predicted plan · Target.")
    kpis = [
        ("Target", tot_t or None, _XLSX_TGT, "Month tonnes"),
        ("Old predicted plan", tot_p or None, _XLSX_MUTED, "Month tonnes"),
    ]
    if tot_p and tot_t:
        kpis.append(("Prediction vs target", tot_p - tot_t,
                     "059669" if tot_p >= tot_t else "B91C1C", "tonnes"))
    r = _xlsx_kpi_strip(key, r, kpis, start=1)
    table_row = r
    key.cell(row=table_row, column=1, value="Daily totals").font = _xlsx_font(True, 13, _XLSX_NAVY)
    table_row += 1
    _xlsx_headers(key, table_row, ["Date", "Old predicted plan", "Target"], start=1)
    rr = table_row
    for d, pw, aw, tw in rows:
        rr += 1
        _xlsx_text(key.cell(row=rr, column=1), d)
        pc = key.cell(row=rr, column=2)
        _xlsx_num(pc, pw)
        tc = key.cell(row=rr, column=3)
        _xlsx_num(tc, tw)
    last = rr
    rr += 1
    _xlsx_text(key.cell(row=rr, column=1), "TOTAL", True, _XLSX_NAVY)
    pc = key.cell(row=rr, column=2)
    _xlsx_num(pc, tot_p or None, True)
    tc = key.cell(row=rr, column=3)
    _xlsx_num(tc, tot_t or None, True)
    if last > table_row:
        _xlsx_line_chart(key, "Daily WMT (flat — the same plan every day)", "t/day",
                         2, 3, table_row, last, "A%d" % (rr + 2), cat_col=1,
                         colors=(_XLSX_MUTED, _XLSX_TGT))
    month_ws = wb.create_sheet(label[:31])
    _xlsx_fill_month(month_ws, st, "%s — production, capacity & SAP" % label)
    return wb


def _xlsx_unique_sheet_name(base, used):
    name = (base or "Sheet")[:31]
    n = 2
    while name in used:
        name = ("%s %d" % (base, n))[:31]
        n += 1
    used.add(name)
    return name


def _xlsx_plan_source_block(ws, r, cards):
    """WHICH PLAN THIS WORKBOOK IS. Printed on the Year sheet, above the totals.

    The Year TOTAL used to sum months that came from different scenarios with
    no disclosure anywhere on the sheet (month sheets said "Saved 2026-09-04"
    in row 2; the Year sheet said nothing). One workbook is now one scenario,
    and it says so here — scenario, day, and the exact saved file per month,
    plus any month that has no plan for this scenario rather than a silent
    hole where another day's plan used to be substituted."""
    first = cards[0] if cards else {}
    note = first.get("_source_note")
    scen = first.get("_scenario")
    if not note and not scen:
        return r
    r = _xlsx_section(ws, r, "Plan source — one workbook, one scenario", note)
    _xlsx_headers(ws, r, ["Month", "Saved plan read", "Target (t)"], start=1)
    for c in cards:
        r += 1
        a = c.get("alloc") or {}
        _xlsx_text(ws.cell(row=r, column=1), c.get("name"))
        _xlsx_text(ws.cell(row=r, column=2),
                   c.get("alloc_source_date") or a.get("source_date")
                   or c.get("alloc_source") or "—")
        _xlsx_num(ws.cell(row=r, column=3), a.get("target_month") or c.get("target_month"))
    r += 2
    missing = first.get("_missing_months") or []
    ws.cell(row=r, column=1, value=(
        "Months with no %s plan: %s — not substituted from another day."
        % (scen or "scenario", ", ".join(str(m) for m in missing))
        if missing else
        "Every month in this year has a %s plan; nothing was substituted."
        % (scen or "scenario"))).font = _xlsx_font(False, 9, _XLSX_MUTED)
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    r += 1
    cap = (first.get("alloc") or {}).get("capacity") or {}
    if cap:
        ws.cell(row=r, column=1, value=(
            "LIM-LD: capacity is reported in full and never clipped; only the "
            "tonnage CREDITED against the target stops at it. See each month "
            "sheet for that month's capacity / credited / unused split."
        )).font = _xlsx_font(False, 9, _XLSX_MUTED)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
        r += 1
    return r + 1



def _plans_from_alloc_rows(rows):
    """Allocation / holding rows → shared_flow plans. Includes IWIP on the plan."""
    plans = []
    for i, r in enumerate(rows or []):
        if not isinstance(r, dict):
            continue
        dt = r.get("dt_after")
        if dt is None:
            dt = r.get("n_trucks") if r.get("n_trucks") is not None else r.get("dt")
        if not (dt or 0) > 0:
            continue
        key = str(r.get("key") or "")
        if ">" in key:
            src, dst = key.split(">", 1)
        else:
            src = r.get("source") or r.get("origin")
            dst = r.get("destination") or r.get("dest")
        if not src or not dst:
            continue
        plans.append({
            "id": r.get("id") or ("r%d" % i),
            "source": src, "destination": dst,
            "n_trucks": int(round(dt)),
            "contractor": r.get("contractor"),
        })
    return plans


def _corridor_run(plans):
    """Time the given trucks onto the stick. Advisory — never clips tonnes."""
    if not plans:
        return None
    try:
        import plan_shared_flow as _sf
        res = _sf.shared_flow(plans, shift_hours=12, rain_mm=0, start_hour=7,
                              whole_day=True)
    except Exception:  # noqa: BLE001 — a report must not die on an advisory panel
        return None
    if not res.get("ok"):
        return None
    return res, sum(p["n_trucks"] for p in plans)


def _corridor_for_alloc(alloc):
    """Hourly corridor from the SAME rows the month sheet already printed."""
    if not isinstance(alloc, dict):
        return None
    plans = _plans_from_alloc_rows(alloc.get("rows") or [])
    got = _corridor_run(plans)
    if got:
        return got
    src = alloc.get("source_date") or alloc.get("alloc_source_date")
    if not src:
        return None
    return _corridor_for_month({"alloc_source_date": src})


def _corridor_for_month(card):
    """Per-section road occupancy for ONE finalised month, or None.

    The corridor sits DOWNSTREAM of the plan (owner, 2026-08-24): once a
    month's allocation is finalised, the corridor's only job is to distribute
    THOSE trucks across sections and hours. It does not re-derive or
    second-guess the plan's tonnage — that was settled upstream.

    Rain is forced to the normal-day basis. The owner plans normal days and
    applies rain deliberately as a scenario; the wet response is physically
    derived but has never been validated on site (zero wet days in every
    measurement window), so it must not silently shape a published number.

    IWIP / POS-transit rows that are already on the allocated plan ARE
    included — they share the road when this plan runs. Extra measured
    Other-trips (the Plan-tab checkbox, not saved on the allocation) are not.
    """
    # Prefer rows already on the card/view so the grid cannot drift from
    # the path table above it. Fall back to the named saved file.
    rows = (card.get("alloc") or {}).get("rows") or card.get("rows") or []
    plans = _plans_from_alloc_rows(rows)
    got = _corridor_run(plans)
    if got:
        return got
    src = card.get("alloc_source_date") or (card.get("alloc") or {}).get("source_date")
    if not src:
        return None
    path = os.path.join(_ROOT, "data", "saved_plans", "%s.json" % str(src)[:10])
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            saved = json.load(fh)
    except (OSError, ValueError):
        return None
    plans = _plans_from_alloc_rows((saved.get("allocation") or {}).get("rows") or [])
    return _corridor_run(plans)


def _xlsx_road_corridor_block(ws, r, cards):
    """Page-one road corridor: trucks per section, and WHEN each section peaks.

    Advisory, and labelled as such on the sheet — this never clips simulate
    tonnes (J53). What is measured and what is not is stated on the face of the
    block rather than in a footnote nobody reads: the release shape comes from
    273,222 weighbridge loads over 234 days; the section split from 463,060
    measured traversals; the capacity from the official speed-limit sheets.
    Presence trails the loading peak by each section's transit time, which is
    physics, not a fitted lag.
    """
    from openpyxl.styles import Font
    ws.cell(row=r, column=1, value="Road corridor — trucks on each section")
    ws.cell(row=r, column=1).font = Font(bold=True, size=12)
    r += 1
    ws.cell(row=r, column=1, value=(
        "Summary only. The hour-by-hour table (07:00–06:00, same as Plan → "
        "Road crowding) is on each month tab: Sep, Oct, Nov, Dec."))
    ws.cell(row=r, column=1).font = Font(italic=True, size=9)
    r += 1
    # Peak here is the BIN-FREE instantaneous maximum; the month grid shows the
    # MEAN concurrent within each hour. Both are real and they are not the same
    # number — the peak legitimately exceeds every cell of the grid. Say so on
    # the face of the table: two panels quoting one concept is how this project
    # has been misread before.
    ws.cell(row=r, column=1, value=(
        "Peak = most trucks on the section at any instant. The month tabs show the "
        "AVERAGE across each hour, so the peak sits above every cell there."))
    ws.cell(row=r, column=1).font = Font(italic=True, size=9)
    r += 1
    ws.cell(row=r, column=1, value=(
        "Advisory. Distribution of the FINALISED plan across the road — it never "
        "changes plan tonnage. Normal-day basis (0-1 mm rain)."))
    ws.cell(row=r, column=1).font = Font(italic=True, size=9)
    r += 2
    for c, h in enumerate(["Month", "Section", "Peak trucks (any instant)",
                           "Average trucks (per hour)",
                           "Busiest hour", "Share of road capacity"], start=1):
        ws.cell(row=r, column=c, value=h).font = Font(bold=True)
    r += 1
    any_row = False
    for card in cards:
        got = _corridor_for_month(card)
        if not got:
            continue
        res, dt = got
        first = True
        for s in (res.get("sections") or []):
            occ = s.get("occupancy") or []
            if not occ:
                continue
            peak = max(occ)
            hr = (int(res.get("start_hour") or 7) + occ.index(peak)) % 24
            ws.cell(row=r, column=1,
                    value=("%s (%d DT)" % (card.get("name") or "", dt)) if first else "")
            ws.cell(row=r, column=2, value=s.get("section"))
            ws.cell(row=r, column=3, value=round(s.get("peak_concurrent") or peak, 1))
            ws.cell(row=r, column=4, value=round(sum(occ) / len(occ), 1))
            ws.cell(row=r, column=5, value="%02d:00" % hr)
            vc = s.get("ratio")
            ws.cell(row=r, column=6, value=(round(vc, 3) if vc is not None else None))
            first = False
            any_row = True
            r += 1
    if not any_row:
        ws.cell(row=r, column=1, value="No finalised allocation to distribute.")
        return r + 1
    return r + 1


# Presence colours match the Plan-tab Road crowding card (stock ÷ how many
# trucks FIT). The verdict above the grid uses the v/c FLOW ratio.
_RC_OPEN, _RC_WATCH, _RC_HIGH, _RC_IDLE = "BBF7D0", "FDE68A", "FCA5A5", "F8FAFC"
_RC_DAY_H, _RC_NIGHT_H = "E2E8F0", "DBEAFE"


def _xlsx_road_corridor_hourly(ws, r, res, dt, source=None):
    """The Plan-tab hour grid: mean concurrent trucks per section × hour.

    Same engine as /api/plan/shared-flow (whole day, 2 × 12 h, rain 0).
    Advisory — never clips simulate tonnes (J53).
    """
    from openpyxl.styles import Alignment, PatternFill

    n_hour_cols = 24
    r = _xlsx_section(ws, r, "Road crowding by hour")
    if not res or not res.get("ok"):
        ws.cell(row=r, column=1, value="No finalised allocation to time onto the road.")
        ws.cell(row=r, column=1).font = _xlsx_font(False, 9, _XLSX_MUTED)
        return r + 1

    # Name the quantity. These cells are the MEAN concurrent trucks within each
    # hour, not the instantaneous peak the Year sheet reports, so the two pages
    # legitimately differ and must each say which they are.
    ws.cell(row=r, column=1, value=(
        "Average trucks on the section during each hour (the Year sheet's peak is "
        "an instantaneous maximum and sits above every cell here)."))
    ws.cell(row=r, column=1).font = _xlsx_font(False, 9, _XLSX_MUTED)
    r += 1

    secs = res.get("sections") or []
    start_h = int(res.get("start_hour") or 7) % 24
    bin_h = float(res.get("bin_hours") or 1) or 1
    n_bins = max((len(s.get("occupancy") or []) for s in secs), default=0)
    if n_bins <= 0:
        ws.cell(row=r, column=1, value="Corridor engine returned no hourly bins.")
        ws.cell(row=r, column=1).font = _xlsx_font(False, 9, _XLSX_MUTED)
        return r + 1
    n_bins = min(n_bins, n_hour_cols)
    hours = [((start_h + int(round(b * bin_h))) % 24) for b in range(n_bins)]
    shift_len = int(round(float(res.get("shift_hours") or 12) / bin_h))

    mid = _xlsx_mid()
    box = _xlsx_sides()[0]
    day_fill = PatternFill("solid", fgColor=_RC_DAY_H)
    night_fill = PatternFill("solid", fgColor=_RC_NIGHT_H)
    fills = {
        "high": PatternFill("solid", fgColor=_RC_HIGH),
        "watch": PatternFill("solid", fgColor=_RC_WATCH),
        "open": PatternFill("solid", fgColor=_RC_OPEN),
        "idle": PatternFill("solid", fgColor=_RC_IDLE),
    }

    # Band row: Day 07–18 / Night 19–06
    band = ws.cell(row=r, column=1, value="Corridor")
    band.font = _xlsx_font(True, 9, _XLSX_NAVY)
    band.border = box
    day_end = min(shift_len, n_bins)
    if day_end > 0:
        c = ws.cell(row=r, column=2, value="Day shift 07–18")
        c.font = _xlsx_font(True, 8, _XLSX_NAVY)
        c.fill = day_fill
        c.alignment = mid
        c.border = box
        if day_end > 1:
            ws.merge_cells(start_row=r, start_column=2, end_row=r,
                           end_column=1 + day_end)
            for col in range(3, 2 + day_end):
                ws.cell(row=r, column=col).fill = day_fill
                ws.cell(row=r, column=col).border = box
    if n_bins > shift_len:
        c = ws.cell(row=r, column=2 + shift_len, value="Night shift 19–06")
        c.font = _xlsx_font(True, 8, _XLSX_NAVY)
        c.fill = night_fill
        c.alignment = mid
        c.border = box
        night_n = n_bins - shift_len
        if night_n > 1:
            ws.merge_cells(start_row=r, start_column=2 + shift_len, end_row=r,
                           end_column=1 + n_bins)
            for col in range(3 + shift_len, 2 + n_bins):
                ws.cell(row=r, column=col).fill = night_fill
                ws.cell(row=r, column=col).border = box
    r += 1

    heads = ["Corridor"] + ["%02d" % h for h in hours]
    _xlsx_headers(ws, r, heads, start=1, center=True)
    for b, h in enumerate(hours):
        cell = ws.cell(row=r, column=2 + b)
        cell.fill = night_fill if b >= shift_len else day_fill
    r += 1

    for s in secs:
        occ = list(s.get("occupancy") or [])
        cap = float(s.get("cap_trucks_bin") or 0) or 0.0
        name = s.get("section") or ""
        shared = s.get("shared")
        lab = name + ("  (shared)" if shared else "")
        lab_c = ws.cell(row=r, column=1, value=lab)
        lab_c.font = _xlsx_font(True, 9, _XLSX_INK)
        lab_c.border = box
        lab_c.alignment = Alignment(vertical="center")
        for b in range(n_bins):
            val = occ[b] if b < len(occ) else 0
            try:
                num = float(val or 0)
            except (TypeError, ValueError):
                num = 0.0
            cell = ws.cell(row=r, column=2 + b)
            cell.border = box
            cell.alignment = mid
            cell.font = _xlsx_font(False, 9)
            if num <= 0:
                cell.value = None
                cell.fill = fills["idle"]
                continue
            cell.value = int(round(num))
            cell.number_format = "0"
            ratio = (num / cap) if cap > 0 else 0.0
            if ratio >= 1.0:
                cell.fill = fills["high"]
            elif ratio >= 0.7:
                cell.fill = fills["watch"]
            else:
                cell.fill = fills["open"]
        r += 1

    _xlsx_widths(ws, [5.5] * n_bins, start=2)
    return r + 1


def _xlsx_month_corridor_block(ws, r, alloc=None, card=None, paths=None):
    """Hourly grid for one month sheet. alloc/card preferred; paths as fallback."""
    got = None
    source = None
    if alloc:
        got = _corridor_for_alloc(alloc)
        source = alloc.get("source_date")
    if not got and card:
        got = _corridor_for_month(card)
        source = card.get("alloc_source_date") or (card.get("alloc") or {}).get("source_date")
    if not got and paths:
        got = _corridor_run(_plans_from_alloc_rows(paths))
    if not got:
        return _xlsx_road_corridor_hourly(ws, r, None, 0)
    res, dt = got
    return _xlsx_road_corridor_hourly(ws, r, res, dt, source=source)

def _xlsx_fill_year_dashboard(ws, year, cards, title_prefix="", achv=False):
    """Year dashboard sheet: KPIs, five-clock charts, coverage table.
    achv=True adds old / optimized achievable (Plan simulate) next to predicted."""
    Y = _year_alloc_totals(cards)
    n_alloc = sum(1 for c in cards if c.get("has_alloc") or c.get("alloc"))
    head = "Year dashboard · %s" % year
    if title_prefix:
        head = "%s · %s" % (title_prefix, head)
    r = _xlsx_board_header(
        ws, head,
        ("%s month%s with Allocate snapshots. Target, old predicted plan, optimized predicted plan."
         % (n_alloc, "" if n_alloc == 1 else "s"))
        + (" Achievable = /api/simulate after Allocate. Old-plan columns omitted."
           if achv else ""),
        start=1)
    r = _xlsx_plan_source_block(ws, r, cards)
    if Y:
        mats = Y.get("materials") or {}
        if achv:
            year_kpis = [
                ("Target", Y.get("target"), _XLSX_TGT, "Year tonnes"),
                ("Optimized predicted plan", Y.get("new_pred"), _XLSX_PRED, "Year tonnes"),
                ("Optimized achievable", Y.get("new_achv_raw") or Y.get("new_achv"),
                 _XLSX_ACHV, "Year tonnes"),
            ]
        else:
            year_kpis = [
                ("Target", Y.get("target"), _XLSX_TGT, "Year tonnes"),
                ("Old predicted plan", Y.get("old_pred"), _XLSX_MUTED, "Year tonnes"),
                ("Optimized predicted plan", Y.get("new_pred"), _XLSX_PRED, "Year tonnes"),
            ]
        r = _xlsx_kpi_strip(ws, r, year_kpis, start=1)
        pct_kpis = [
            ("Together · % of target", Y.get("cov_new_pred"),
             _xlsx_cov_tone(Y.get("cov_new_pred"))[0] or _XLSX_MUTED, "pct"),
            ("SAP · % of target", (mats.get("sap") or {}).get("cov_pred"),
             _xlsx_cov_tone((mats.get("sap") or {}).get("cov_pred"))[0] or _XLSX_MUTED, "pct"),
            ("LIM-TOS · % of target", (mats.get("tos") or {}).get("cov_pred"),
             _xlsx_cov_tone((mats.get("tos") or {}).get("cov_pred"))[0] or _XLSX_MUTED, "pct"),
            ("LIM-LD · % of target", (mats.get("ld") or {}).get("cov_pred"),
             _xlsx_cov_tone((mats.get("ld") or {}).get("cov_pred"))[0] or _XLSX_MUTED, "pct"),
        ]
        if achv:
            pct_kpis.append(
                ("Together · achievable %", Y.get("cov_new_achv_raw") or Y.get("cov_new_achv"),
                 _xlsx_cov_tone(Y.get("cov_new_achv_raw") or Y.get("cov_new_achv"))[0]
                 or _XLSX_MUTED, "pct"))
        r = _xlsx_kpi_strip(ws, r, pct_kpis, start=1)

        def pts(getter):
            out = []
            for c in cards:
                a = c.get("alloc") or {}
                out.append({"name": c.get("name"), **getter(a, c)})
            return out

        r = _xlsx_five_clock_block(
            ws, r, "Together · year",
            "Month on X · tonnes on Y. Target, old predicted plan, optimized predicted plan"
            + (" · old / optimized achievable." if achv else "."),
            pts(lambda a, c: {
                "target": a.get("target_month") if a else c.get("target_month"),
                "old_pred": a.get("old_pred_month") if a else c.get("pred_month"),
                "new_pred": a.get("new_pred_month") if a else None,
                "old_achv": _pick_achv(a, True, "month") if a else None,
                "new_achv": _pick_achv(a, False, "month") if a else None,
            }),
            start=1, chart_col="I", achv=achv)
        for key_m, title in (("sap", "SAP · year"), ("tos", "LIM-TOS · year"),
                             ("ld", "LIM-LD · year")):
            r = _xlsx_five_clock_block(
                ws, r, title,
                "Same clocks for this material only"
                + (" — predicted and achievable." if achv else "."),
                pts(lambda a, c, k=key_m: {
                    "target": ((a.get("materials") or {}).get(k) or {}).get("target_month"),
                    "old_pred": ((a.get("materials") or {}).get(k) or {}).get("pred_before_month"),
                    "new_pred": ((a.get("materials") or {}).get(k) or {}).get("pred_after_month"),
                    "old_achv": _pick_mat_achv((a.get("materials") or {}).get(k) or {}, True, "month"),
                    "new_achv": _pick_mat_achv((a.get("materials") or {}).get(k) or {}, False, "month"),
                }),
                start=1, chart_col="I", achv=achv)
        if achv:
            cov_heads = ["Month", "Target", "Optimized predicted plan",
                         "Optimized achievable"]
        else:
            cov_heads = ["Month", "Target", "Old predicted plan", "Optimized predicted plan"]
        cov_heads += ["Optimized %", "SAP %", "LIM-TOS %", "LIM-LD %", "Leaving"]
        if achv:
            cov_heads.append("Achievable %")
        r = _xlsx_section(
            ws, r, "Coverage table",
            "Optimized predicted plan ÷ target"
            + (" · achievable is /api/simulate (Your plan vs after Allocate), not predicted."
               if achv else "."))
        _xlsx_headers(ws, r, cov_heads, start=1)
        for c in cards:
            r += 1
            a = c.get("alloc") or {}
            _xlsx_text(ws.cell(row=r, column=1), c.get("name"))
            if a:
                _xlsx_num(ws.cell(row=r, column=2), a.get("target_month"))
                if achv:
                    _xlsx_num(ws.cell(row=r, column=3), a.get("new_pred_month"), True)
                    na = _pick_achv(a, False, "month")
                    ac = ws.cell(row=r, column=4)
                    _xlsx_num(ac, na, True)
                    col = 5
                else:
                    _xlsx_num(ws.cell(row=r, column=3), a.get("old_pred_month"))
                    _xlsx_num(ws.cell(row=r, column=4), a.get("new_pred_month"), True)
                    col = 5
                _xlsx_paint_cov(ws.cell(row=r, column=col), a.get("cov_new_pred"))
                _xlsx_paint_cov(ws.cell(row=r, column=col + 1),
                                ((a.get("materials") or {}).get("sap") or {}).get("cov_pred"))
                _xlsx_paint_cov(ws.cell(row=r, column=col + 2),
                                ((a.get("materials") or {}).get("tos") or {}).get("cov_pred"))
                _xlsx_paint_cov(ws.cell(row=r, column=col + 3),
                                ((a.get("materials") or {}).get("ld") or {}).get("cov_pred"))
                _xlsx_num(ws.cell(row=r, column=col + 4), a.get("left_new_pred_month"))
                if achv:
                    _xlsx_paint_cov(
                        ws.cell(row=r, column=col + 5),
                        _cov_pct(_pick_achv(a, False, "month"), a.get("target_month")))
            else:
                _xlsx_num(ws.cell(row=r, column=2), c.get("target_month"))
                if achv:
                    _xlsx_num(ws.cell(row=r, column=4), c.get("achv_month"))
                else:
                    _xlsx_num(ws.cell(row=r, column=3), c.get("pred_month"))
        r += 1
        tot_lab = ws.cell(row=r, column=1, value="TOTAL · %s months" % Y.get("n"))
        tot_lab.font = _xlsx_font(True, 11, _XLSX_NAVY)
        _xlsx_total_border(tot_lab)
        if achv:
            tot_row = [
                (2, Y.get("target"), None),
                (3, Y.get("new_pred"), None),
                (4, Y.get("new_achv_raw") or Y.get("new_achv"), None),
            ]
            col = 5
        else:
            tot_row = [
                (2, Y.get("target"), None),
                (3, Y.get("old_pred"), None),
                (4, Y.get("new_pred"), None),
            ]
            col = 5
        tot_row += [
            (col, None, Y.get("cov_new_pred")),
            (col + 1, None, (mats.get("sap") or {}).get("cov_pred")),
            (col + 2, None, (mats.get("tos") or {}).get("cov_pred")),
            (col + 3, None, (mats.get("ld") or {}).get("cov_pred")),
            (col + 4, Y.get("left_new_pred"), None),
        ]
        if achv:
            tot_row.append(
                (col + 5, None,
                 _cov_pct(Y.get("new_achv_raw") or Y.get("new_achv"), Y.get("target"))))
        for col, val, pctv in tot_row:
            cell = ws.cell(row=r, column=col)
            if pctv is not None:
                _xlsx_paint_cov(cell, pctv)
            else:
                _xlsx_num(cell, val, True)
            _xlsx_total_border(cell)
        r += 2
        note = ws.cell(
            row=r, column=1,
            value="Path table for every month (origin, destination, NB Days, Predicted / month) → Paths sheet.")
        note.font = _xlsx_font(False, 10, _XLSX_MUTED)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    else:
        tot_p = sum(c.get("pred_month") or 0 for c in cards)
        tot_t = sum(c.get("target_month") or 0 for c in cards)
        r = _xlsx_kpi_strip(ws, r, [
            ("Target", tot_t or None, _XLSX_TGT, "Year tonnes"),
            ("Old predicted plan", tot_p or None, _XLSX_MUTED, "Year tonnes"),
        ], start=1)
        if achv:
            tot_a = sum(c.get("achv_month") or 0 for c in cards) or None
            r = _xlsx_kpi_strip(ws, r, [
                ("Achievable", tot_a, _XLSX_ACHV, "Year tonnes"),
            ], start=1)
        r = _xlsx_five_clock_block(
            ws, r, "Year · monthly tonnes",
            "No Allocate snapshots yet — matrix predicted plan / target"
            + (" · achievable from /api/simulate." if achv else "."),
            [{"name": c.get("name"), "target": c.get("target_month"),
              "old_pred": c.get("pred_month"), "new_pred": None,
              "old_achv": c.get("achv_month") if achv else None,
              "new_achv": None} for c in cards],
            start=1, chart_col="I", achv=achv)

    r = _xlsx_road_corridor_block(ws, r + 2, cards)

    _xlsx_widths(ws, [16, 14, 14, 14, 12, 14, 14, 12, 14, 12, 10, 12, 12, 12])
    ws.freeze_panes = "A4"


def _xlsx_append_month_sheets(wb, year, cards, used, prefix="", achv=False):
    """One old-vs-new sheet per month card. Cards may carry alloc_raw for scenarios."""
    for c in cards:
        month = c["month"]
        st = _load_state(month) or {"month": month}
        st["month"] = month
        if c.get("alloc_raw"):
            raw, src = c["alloc_raw"], c.get("alloc_source")
        else:
            raw, src = _resolve_allocation(month, st, day=c.get("_alloc_day"))
        n = c.get("n_days") or len(_days_in(month))
        alloc = _alloc_view(raw, n, src, include_detail=True)
        name = _xlsx_unique_sheet_name(prefix + (c.get("name") or month), used)
        ws = wb.create_sheet(name)
        label = "%s %s" % (c.get("name") or "", year)
        if alloc:
            _xlsx_fill_month_alloc(
                ws, month,
                "%s — %s" % (label.strip(),
                             "plan · predicted · achievable" if achv else "old vs new"),
                alloc, st, achv=achv)
        elif st.get("prediction") or st.get("manual"):
            _xlsx_fill_month(
                ws, st, "%s — production, capacity & SAP" % label.strip(), achv=achv)
        else:
            ws["A1"] = label
            ws["A1"].font = _xlsx_font(True, 16, _XLSX_NAVY)
            ws["A2"] = "No saved Allocate snapshot and no month file yet."
            ws["A2"].font = _xlsx_font(False, 10, _XLSX_MUTED)


def append_year_book_sheets(wb, year, cards, used=None, prefix="", achv=False):
    """Add a year dashboard + month sheets to an existing workbook (multi-scenario export)."""
    if used is None:
        used = set(wb.sheetnames)
    yr = _xlsx_unique_sheet_name(prefix + "Year", used)
    ws = wb.create_sheet(yr)
    _xlsx_fill_year_dashboard(ws, year, cards, title_prefix=prefix.rstrip(" · "), achv=achv)
    _xlsx_append_paths_sheet(wb, year, cards, used, prefix=prefix, achv=achv,
                             after_sheet=yr)
    _xlsx_append_month_sheets(wb, year, cards, used, prefix=prefix, achv=achv)
    return used


def _xlsx_year_book(year, cards, achv=False):
    """Key = year dashboard, all-months path table, then one sheet per month."""
    from openpyxl import Workbook
    wb = Workbook()
    key = wb.active
    key.title = "Year"
    used = {"Year"}
    _xlsx_fill_year_dashboard(key, year, cards, achv=achv)
    _xlsx_append_paths_sheet(wb, year, cards, used, prefix="", achv=achv,
                             after_sheet="Year")
    _xlsx_append_month_sheets(wb, year, cards, used, prefix="", achv=achv)
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
    """Year workbook: Key + year chart + one production/capacity/SAP sheet per month.

    ONE WORKBOOK = ONE SCENARIO. `day` omitted resolves to
    DEFAULT_SCENARIO_DAY (S1 = day 01), never "latest save wins"; the resolved
    scenario, its day and the exact source file per month are printed on the
    Year sheet and echoed in the X-Plan-Scenario response headers.
    """
    year = (request.args.get("year") or str(date.today().year)).strip()
    if not re.fullmatch(r"\d{4}", year):
        return jsonify({"ok": False, "error": "year=YYYY"}), 400
    day = (request.args.get("day") or "").strip()
    day = int(day) if re.fullmatch(r"[0-9]{1,2}", day) and 1 <= int(day) <= 28 else None
    achv = (request.args.get("achv") or "").strip() in ("1", "true", "yes")
    resolved_day = DEFAULT_SCENARIO_DAY if day is None else day
    _yearly, cards = _year_cards(year, day=day)
    if not cards:
        return jsonify({
            "ok": False,
            "error": "no day-%02d (%s) plans stored for %s — load a matrix and "
                     "build the year first, or ask for another day"
                     % (resolved_day, _scenario_label_for_day(resolved_day), year),
        }), 404
    name = "monthly_plan_%s%s%s.xlsx" % (
        year, "" if not day else "_day%02d" % day, "_achievable" if achv else "")
    rv = _xlsx_send(_xlsx_year_book(year, cards, achv=achv), name)
    rv.headers["X-Plan-Scenario"] = _scenario_label_for_day(resolved_day)
    rv.headers["X-Plan-Scenario-Day"] = "%02d" % resolved_day
    rv.headers["X-Plan-Sources"] = ",".join(
        "%s=%s" % (c["month"], c.get("alloc_source_date") or "-") for c in cards)
    return rv



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


@bp.route("/api/monthly/targets")
def api_monthly_targets():
    """Year-matrix P1/P2/P3 rows for one month — Plan page stamps chips from this."""
    month = (request.args.get("month") or "").strip()
    date = (request.args.get("date") or "").strip()
    if not month and len(date) >= 7:
        month = date[:7]
    if not _month_path(month):
        return jsonify({"ok": False, "error": "supply month=YYYY-MM"}), 400
    yearly = _load_yearly()
    if not yearly:
        return jsonify({"ok": True, "month": month, "rows": [], "exists": False})
    mnum = str(int(month[5:7]))
    rows = []
    for e in yearly.get("entries") or []:
        wmt = (e.get("wmt") or {}).get(mnum) or 0
        dt = (e.get("dt") or {}).get(mnum) or 0
        if wmt <= 0 and dt <= 0:
            continue
        src = _ORIGIN_MAP.get((e.get("origin") or "").upper(), (e.get("origin") or "").upper())
        dst = _canon_dest(e.get("dest"))
        mat = (e.get("material") or "").upper()
        otype = (e.get("otype") or "").upper()
        prio = 1 if mat == "SAP" else (2 if mat == "LIM" and otype == "TOS" else 3)
        rows.append({
            "src": src, "dst": dst, "contractor": (e.get("contractor") or "").upper(),
            "mat": mat, "otype": otype, "prio": prio,
            "target": round(wmt) if wmt else 0, "dt": round(dt) if dt else 0,
        })
    return jsonify({"ok": True, "month": month, "exists": True, "rows": rows})


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


_CONG_TRIPS_CACHE = {}


def _congestion_trips_per_dt(route, contractor, n_comb):
    """Trips/DT/day from the ONE contractor-pricing owner: the calibrated
    congestion model, asked with the contractor.

    Until 2026-08-23 this module priced trips/DT as `dayRate × cf`, where cf
    was the contractor's fleet-wide Trips/DT ÷ the site-wide Trips/DT, clamped
    [0.5,1.5]. plan.js deleted exactly that factor the same day, because it is
    fleet-size-confounded (RIM ran ~140 trucks/day against SMA's ~58) and
    INVERTS on the TF corridor against matched-day history. Leaving it here
    would have made monthly_api the third owner of one concept — the shape
    that produced the 0.85 availability override (J55) and the capacity card
    (J71).

    congestion.predictor.predict() applies the contractor's own
    overhead_per_trip_min where calibration found a matched-day baseline, and
    answers POOLED where it did not — the exact transform
    trips_c = 1440 / (1440/trips_pooled − ovh_pooled + ovh_c) that plan.js and
    /api/congestion_model both use. Returns None for an uncalibrated route so
    the caller falls back to the measured ticket history, pooled.

    Basis note: priced on this route's OWN combined fleet, exactly like
    /api/congestion_model without `others`. Cross-route segment traffic is a
    known, disclosed gap here (the Plan tab supplies it via `others`); it is
    not silently approximated.
    """
    try:
        from congestion.config import route_params
        from congestion.predictor import predict
    except ImportError:
        return None
    n = max(1.0, float(n_comb or 0))
    key = (route, (contractor or "").upper(), round(n, 1))
    if key in _CONG_TRIPS_CACHE:
        return _CONG_TRIPS_CACHE[key]
    out = None
    try:
        if route_params(route).get("calibrated"):
            rec = predict(route, n, None, contractor=(contractor or None) and
                          str(contractor).strip().upper())
            v = rec.get("trips_per_DT_per_day")
            if v and float(v) > 0:
                out = float(v)
    except (ValueError, ArithmeticError, KeyError, TypeError, OSError):
        out = None
    if len(_CONG_TRIPS_CACHE) > 20000:
        _CONG_TRIPS_CACHE.clear()
    _CONG_TRIPS_CACHE[key] = out
    return out


def _path_row_wmt(src, dst, contractor, dt, n_comb, paths, fleet, contr_by):
    """One contractor-path through the Plan Step 1 path model (day grain, rain=0)."""
    k = "%s>%s" % (src, dst)
    m = paths.get(k) or {}
    dt = float(dt or 0)
    n_comb = float(n_comb or dt) or dt
    c = contr_by.get((contractor or "").upper()) or {}
    pay = c.get("tf") or m.get("tf")
    day_rate = m.get("dayRate") or m.get("avgTr")
    cap_trips = m.get("dayTripsCap")
    # Contractor pricing has exactly ONE owner (see _congestion_trips_per_dt).
    cong_tr = _congestion_trips_per_dt(k, contractor, n_comb)
    if not pay or dt <= 0 or (not day_rate and not cong_tr):
        return {"wmt": None, "trips": None,
                "flag": "no measured day history — using cycle × payload",
                "pay": pay, "cap_trips": cap_trips, "avg_dt": m.get("avgDt"),
                "contractor_basis": None}
    flag = None
    if cong_tr:
        # Calibrated route: the congestion model already carries saturation on
        # the combined fleet, so the legacy demonstrated-ceiling divide and the
        # 30% floor are NOT applied on top — same guard plan.js uses
        # (`if(!_hybridInfo && capEff>0 …)`). Two saturation models on one
        # number is the defect this repo has paid for three times.
        tr = cong_tr
        basis = "congestion model (contractor=%s)" % ((contractor or "-").upper())
        cap_trips = None
    else:
        tr = float(day_rate)  # POOLED — no contractor factor exists for this route
        basis = "measured day history, pooled (route not calibrated)"
        linear = tr * n_comb
        if cap_trips and cap_trips > 0 and linear > cap_trips:
            tr *= cap_trips / linear
            flag = "at demonstrated ceiling (%d trips/day)" % round(cap_trips)
        floor = 0.3 * float(day_rate)
        if tr < floor:
            tr = floor
    dt_max = m.get("dtMaxDayAll") or m.get("dtMaxAll") or m.get("dtMax")
    if dt_max and n_comb > dt_max:
        flag = "beyond measured fleet (max ever %d DT)" % round(dt_max)
    trips = dt * tr
    return {"wmt": trips * float(pay), "trips": trips, "flag": flag,
            "pay": pay, "cap_trips": cap_trips, "avg_dt": m.get("avgDt"),
            "trips_per_dt": tr, "contractor_basis": basis}


def _plan_predict_for_routes(route_list):
    """Plan tab Step 1 WMT for one typical day (rain=0, no WB / other-traffic knobs).

    Same ingredients the Plan tab uses: trips/DT from the calibrated congestion
    model priced for THIS contractor (the model's own saturation, no legacy
    ceiling divide on top), or the measured pooled day rate with the
    demonstrated ceiling where the route is not calibrated; tonnes = trips ×
    contractor t/trip.
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
    """Invert the path model for a day target. Same solver as planDtForWmt (rain=0).

    `cap_trips` (and therefore the "target above path ceiling" pre-check) only
    exists on routes the congestion model has no calibration for; on calibrated
    routes the model's own saturation is the ceiling and the solver walks it."""
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
    """Un-merged P1 SAP rows (kept for callers that still ask SAP-only)."""
    return [r for r in _priority_entries_for_month(yearly, mnum) if r.get("prio") == 1]


def _priority_entries_for_month(yearly, mnum):
    """Un-merged P1 SAP and P2 LIM-TOS rows. TOS vs LD is not collapsed."""
    mnum = str(int(mnum))
    rows = {}
    for e in (yearly or {}).get("entries") or []:
        mat = (e.get("material") or "").strip().upper()
        otype = (e.get("otype") or "").strip().upper()
        if mat == "SAP":
            prio = 1
        elif mat == "LIM" and otype == "TOS":
            prio = 2
        else:
            continue
        if not ((e.get("wmt") or {}).get(mnum) or 0) and not ((e.get("dt") or {}).get(mnum) or 0):
            continue
        src = _ORIGIN_MAP.get((e.get("origin") or "").upper(), (e.get("origin") or "").upper())
        dst = _canon_dest(e.get("dest"))
        contr = (e.get("contractor") or "").upper()
        key = (src, dst, contr, mat, otype)
        rec = rows.setdefault(key, {"src": src, "dst": dst, "contractor": contr,
                                    "mat": mat, "otype": otype, "prio": prio,
                                    "dt": 0.0, "wmt_day": 0.0})
        rec["dt"] += (e.get("dt") or {}).get(mnum) or 0
        rec["wmt_day"] += (e.get("wmt") or {}).get(mnum) or 0
    return [r for r in rows.values() if r["wmt_day"] > 0 or r["dt"] > 0]


def _sap_table_rows(st, paths, sim_rows):
    """Priority board for Excel: P1 SAP + P2 LIM-TOS. Achievable is this row's share of the route."""
    month = (st or {}).get("month")
    yearly = _load_yearly()
    sap_src = []
    if yearly and month:
        sap_src = _priority_entries_for_month(yearly, month[5:7])
    alloc_by = {}
    for row in ((st or {}).get("allocation") or {}).get("rows") or []:
        key = (row.get("route"), (row.get("contractor") or "").upper(),
               (row.get("mat") or "").upper(), (row.get("otype") or "").upper())
        alloc_by[key] = row
    if not sap_src:
        for p in paths or []:
            mat = (p.get("material") or "").upper()
            if "SAP" not in mat and "LIM" not in mat:
                continue
            key = p.get("key") or ""
            if ">" not in key:
                continue
            src, dst = key.split(">", 1)
            sap_src.append({"src": src, "dst": dst,
                            "contractor": (p.get("contractor") or "").upper(),
                            "mat": "SAP" if "SAP" in mat else "LIM",
                            "otype": "TOS", "prio": 1 if "SAP" in mat else 2,
                            "dt": float(p.get("dt") or 0),
                            "wmt_day": float(p.get("manual_wmt_day") or 0)})
    if not sap_src:
        return []
    ctx = _path_model_context()
    path_models, fleet, contr_by = ctx
    path_dt = {}
    route_achv = {}
    for i, p in enumerate(paths or []):
        k = p.get("key")
        path_dt[k] = path_dt.get(k, 0.0) + float(p.get("dt") or 0)
        if i < len(sim_rows or []) and sim_rows[i].get("achievable_production_t") is not None:
            route_achv[k] = route_achv.get(k, 0.0) + float(sim_rows[i]["achievable_production_t"]) * 2
        elif p.get("achv_wmt_day") is not None and k not in route_achv:
            route_achv[k] = float(p["achv_wmt_day"])
    out = []
    for s in sap_src:
        route = "%s>%s" % (s["src"], s["dst"])
        arow = alloc_by.get((route, s["contractor"], s.get("mat", ""), s.get("otype", "")))
        alloc = float((arow or {}).get("alloc_dt") or s["dt"] or 0)
        target = float(s["wmt_day"] or 0)
        n_comb = path_dt.get(route) or alloc
        others = max(0.0, n_comb - alloc)
        pred_row = _path_row_wmt(s["src"], s["dst"], s["contractor"], alloc,
                                 n_comb or alloc, path_models, fleet, contr_by)
        pred = pred_row.get("wmt")
        req, why = _required_dt_day(s["src"], s["dst"], s["contractor"], target,
                                    others, path_models, fleet, contr_by)
        route_a = route_achv.get(route)
        tot = path_dt.get(route) or alloc
        achv = (route_a * (alloc / tot)) if (route_a is not None and tot > 0) else None
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
            "mat": s.get("mat") or "",
            "otype": s.get("otype") or "",
            "prio": s.get("prio") or 1,
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
                 "at demonstrated day trips). Target is the matrix WMT/day. "
                 "Day = 2 × 12 h shifts."),
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


_ALLOC_MATS = (("sap", "SAP"), ("tos", "LIM-TOS"), ("ld", "LIM-LD"))


def _finite(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _hz_to_day(alloc):
    """Saved allocation numbers are already per selected horizon.

    Plan tab day grain multiplies by 2 (two 12 h shifts), so those figures
    are already t/day. Shift grain is one shift — scale ×2 to a day.
    """
    hz = (alloc or {}).get("horizon") or "day"
    if hz in ("shift", "12h", "night"):
        return 2
    return 1


def _find_saved_allocation(month, day=None):
    """Frozen Plan-tab allocation in data/saved_plans for YYYY-MM.

    day=None keeps the old rule (latest date wins). day=N restricts to that
    day of month - the scenario convention (owner, 2026-08-19): the 1st holds
    S1, the 2nd S2, the 3rd S3, so one month stores one plan per scenario."""
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month or ""):
        return None, None
    if not os.path.isdir(_SAVED_DIR):
        return None, None
    best, best_date = None, None
    prefix = month + "-" if day is None else "%s-%02d" % (month, int(day))
    try:
        names = os.listdir(_SAVED_DIR)
    except OSError:
        return None, None
    for fn in names:
        if not (fn.startswith(prefix) and fn.endswith(".json")):
            continue
        path = os.path.join(_SAVED_DIR, fn)
        try:
            with open(path, encoding="utf-8") as f:
                plan = json.load(f)
        except (OSError, ValueError):
            continue
        alloc = plan.get("allocation")
        if not isinstance(alloc, dict) or not alloc.get("frozen"):
            continue
        d = fn[:-5]
        if best_date is None or d > best_date:
            best_date, best = d, alloc
    return best, best_date


def _resolve_allocation(month, st=None, day=None):
    """Prefer the month file's copy; else the latest saved daily plan.

    With day=N the month-state copy is SKIPPED: that copy was frozen from
    whichever save last built the month, which may be another scenario's."""
    if st is None:
        st = _load_state(month)
    if day is not None:
        return _find_saved_allocation(month, day)
    pred = (st or {}).get("prediction") or {}
    for blob, src in (
        ((st or {}).get("saved_day_allocation"), pred.get("source_date")),
        (pred.get("allocation"), pred.get("source_date")),
    ):
        if isinstance(blob, dict) and blob.get("frozen"):
            return blob, src
    return _find_saved_allocation(month, day)


def _cov_pct(num, den):
    if num is None or not den:
        return None
    return round(100.0 * float(num) / float(den), 1)


def _plan_achv(pred, tgt):
    """Target-credited prediction for management presentation.

    This is deliberately not called achievable: achievable is reserved for
    raw /api/simulate output throughout the API and exports.
    """
    if pred is None:
        return None
    if tgt:
        return min(float(pred), float(tgt))
    return float(pred)


def _cap_at(val, cap):
    if val is None:
        return None
    if cap is None:
        return val
    return min(float(val), float(cap))


def _path_rates(row):
    """Trips/DT and WMT/DT from a saved allocation row. Old trips inferred from payload if missing."""
    dt_b, dt_a = _finite(row.get("dt_before")), _finite(row.get("dt_after"))
    pr_b, pr_a = _finite(row.get("pred_before")), _finite(row.get("pred_after"))
    tr_a = _finite(row.get("trips"))
    tr_b = _finite(row.get("trips_before"))
    if tr_b is None and tr_a and pr_a:
        pay = pr_a / tr_a
        if pay:
            tr_b = (pr_b / pay) if pr_b is not None else None
    achv_a = _finite(row.get("achv_after"))
    achv_b = _finite(row.get("achv_before"))
    sim_a = _finite(row.get("achv_sim"))
    if sim_a is None:
        sim_a = achv_a
    tgt = _finite(row.get("target"))

    def tpd(tr, dt):
        if tr is None or not dt:
            return None
        return round(tr / dt, 2)

    def wpd(pr, dt):
        if pr is None or not dt:
            return None
        return round(pr / dt, 1)

    def wpt(pr, tr):
        if pr is None or not tr:
            return None
        return round(pr / tr, 2)

    def rnd(v):
        return None if v is None else int(round(v))

    return {
        "trips_before": rnd(tr_b),
        "trips_after": rnd(tr_a),
        "trips_per_dt_before": tpd(tr_b, dt_b),
        "trips_per_dt_after": tpd(tr_a, dt_a),
        "wmt_per_dt_before": wpd(pr_b, dt_b),
        "wmt_per_dt_after": wpd(pr_a, dt_a),
        "wmt_per_trip_before": wpt(pr_b, tr_b),
        "wmt_per_trip_after": wpt(pr_a, tr_a),
        "achv_before_capped": rnd(_plan_achv(pr_b, tgt)),
        "achv_after_capped": rnd(_plan_achv(pr_a, tgt)),
        "achv_after_raw": rnd(sim_a),
        "over_cap": rnd(max(0, sim_a - (_plan_achv(pr_a, tgt) or 0))) if sim_a is not None else None,
    }


def _alloc_view(alloc, n_days, source_date=None, include_detail=False):
    """Day clocks × n_days → month totals. Never averages pred and achv."""
    if not isinstance(alloc, dict) or not alloc.get("frozen"):
        return None
    fac = _hz_to_day(alloc)
    n = int(n_days or 0)

    def day(v):
        x = _finite(v)
        return None if x is None else x * fac

    def rnd(v):
        return None if v is None else int(round(v))

    def month(v):
        d = day(v)
        return None if d is None else rnd(d * n)

    old = alloc.get("old") or {}
    new = alloc.get("new") or {}
    goals = alloc.get("goals") or {}
    buckets = alloc.get("buckets") or {}
    tgt_raw = new.get("target")
    if tgt_raw is None:
        tgt_raw = goals.get("total")
    materials = {}
    for key, label in _ALLOC_MATS:
        b = buckets.get(key) or {}
        tgt = day(b.get("target") if b.get("target") is not None else goals.get(key))
        pb, pa = day(b.get("pred_before")), day(b.get("pred_after"))
        ab_raw, aa_stored = day(b.get("achv_before")), day(b.get("achv_after"))
        aa_sim = day(b.get("achv_sim"))
        if aa_sim is None:
            aa_sim = aa_stored
        ab, aa = _plan_achv(pb, tgt), _plan_achv(pa, tgt)
        materials[key] = {
            "label": label,
            "n": int(b.get("n") or 0),
            "dt_before": b.get("dt_before"),
            "dt_after": b.get("dt_after"),
            "target_day": rnd(tgt),
            "pred_before_day": rnd(pb),
            "pred_after_day": rnd(pa),
            "credited_pred_before_day": rnd(ab),
            "credited_pred_after_day": rnd(aa),
            "achv_before_day": rnd(ab_raw),
            "achv_after_day": rnd(aa_sim),
            "achv_before_raw_day": rnd(ab_raw),
            "achv_after_raw_day": rnd(aa_sim),
            "over_achv_day": rnd(max(0, aa_sim - aa)) if aa_sim is not None and aa is not None else None,
            "target_month": rnd(tgt * n) if tgt is not None else None,
            "pred_before_month": rnd(pb * n) if pb is not None else None,
            "pred_after_month": rnd(pa * n) if pa is not None else None,
            "credited_pred_before_month": rnd(ab * n) if ab is not None else None,
            "credited_pred_after_month": rnd(aa * n) if aa is not None else None,
            "achv_before_month": rnd(ab_raw * n) if ab_raw is not None else None,
            "achv_after_month": rnd(aa_sim * n) if aa_sim is not None else None,
            "achv_before_raw_month": rnd(ab_raw * n) if ab_raw is not None else None,
            "achv_after_raw_month": rnd(aa_sim * n) if aa_sim is not None else None,
            "cov_pred": _cov_pct(pa, tgt),
            "cov_credited_pred": _cov_pct(aa, tgt),
            "cov_achv": _cov_pct(aa_sim, tgt),
            "cov_achv_raw": _cov_pct(aa_sim, tgt),
            "left_pred_month": rnd(max(0, tgt - pa) * n) if tgt is not None and pa is not None else None,
            "over_pred_month": rnd(max(0, pa - tgt) * n) if tgt is not None and pa is not None else None,
        }
    op, np_ = day(old.get("pred")), day(new.get("pred"))
    oa_raw, na_stored = day(old.get("achv")), day(new.get("achv"))
    na_sim = day(new.get("achv_sim"))
    if na_sim is None:
        na_sim = na_stored
    tgt = day(tgt_raw)
    rows = alloc.get("rows") or []
    prio_map = {1: "sap", 2: "tos", 3: "ld"}
    if rows:
        tot_aa = tot_ab = 0.0
        sums = {k: {"aa": 0.0, "ab": 0.0} for k, _ in _ALLOC_MATS}
        for row in rows:
            rt = day(row.get("target"))
            pa = day(row.get("pred_after"))
            pb = day(row.get("pred_before"))
            aa = _plan_achv(pa, rt)
            ab = _plan_achv(pb, rt)
            k = prio_map.get(row.get("prio"))
            if aa is not None:
                tot_aa += aa
                if k in sums:
                    sums[k]["aa"] += aa
            if ab is not None:
                tot_ab += ab
                if k in sums:
                    sums[k]["ab"] += ab
        credited_oa, credited_na = tot_ab, tot_aa
        for k, s in sums.items():
            mat = materials.get(k)
            if not mat:
                continue
            mat["credited_pred_after_day"] = rnd(s["aa"])
            mat["credited_pred_before_day"] = rnd(s["ab"])
            mat["credited_pred_after_month"] = rnd(s["aa"] * n) if n else None
            mat["credited_pred_before_month"] = rnd(s["ab"] * n) if n else None
            mat["cov_credited_pred"] = _cov_pct(s["aa"], mat.get("target_day"))
            if mat.get("achv_after_day") is not None and mat.get("credited_pred_after_day") is not None:
                mat["over_achv_day"] = rnd(max(0, mat["achv_after_day"] - mat["credited_pred_after_day"]))
    else:
        credited_oa, credited_na = _plan_achv(op, tgt), _plan_achv(np_, tgt)
    oa, na = oa_raw, na_sim
    fleet = alloc.get("fleet") or {}
    out = {
        "has": True,
        "source_date": source_date,
        "horizon": alloc.get("horizon") or "day",
        "dt_before": fleet.get("before") if fleet.get("before") is not None else old.get("dt"),
        "dt_after": fleet.get("after") if fleet.get("after") is not None else new.get("dt"),
        "old_pred_day": rnd(op), "new_pred_day": rnd(np_),
        "old_achv_day": rnd(oa), "new_achv_day": rnd(na),
        "old_credited_pred_day": rnd(credited_oa),
        "new_credited_pred_day": rnd(credited_na),
        "old_achv_raw_day": rnd(oa_raw), "new_achv_raw_day": rnd(na_sim),
        "over_new_achv_day": rnd(max(0, na_sim - na)) if na_sim is not None and na is not None else None,
        "target_day": rnd(tgt),
        "old_pred_month": rnd(op * n) if op is not None else None,
        "new_pred_month": rnd(np_ * n) if np_ is not None else None,
        "old_achv_month": rnd(oa * n) if oa is not None else None,
        "new_achv_month": rnd(na * n) if na is not None else None,
        "old_credited_pred_month": rnd(credited_oa * n) if credited_oa is not None else None,
        "new_credited_pred_month": rnd(credited_na * n) if credited_na is not None else None,
        "old_achv_raw_month": rnd(oa_raw * n) if oa_raw is not None else None,
        "new_achv_raw_month": rnd(na_sim * n) if na_sim is not None else None,
        "target_month": rnd(tgt * n) if tgt is not None else None,
        "cov_old_pred": _cov_pct(op, tgt),
        "cov_new_pred": _cov_pct(np_, tgt),
        "cov_old_achv": _cov_pct(oa, tgt),
        "cov_new_achv": _cov_pct(na, tgt),
        "cov_old_credited_pred": _cov_pct(credited_oa, tgt),
        "cov_new_credited_pred": _cov_pct(credited_na, tgt),
        "cov_new_achv_raw": _cov_pct(na_sim, tgt),
        "left_new_pred_month": rnd(max(0, tgt - np_) * n) if tgt is not None and np_ is not None else None,
        "over_new_pred_month": rnd(max(0, np_ - tgt) * n) if tgt is not None and np_ is not None else None,
        "over_new_achv_month": rnd(max(0, na_sim - na) * n) if na_sim is not None and na is not None else None,
        "moved_total": alloc.get("moved_total"),
        "materials": materials,
        # LIM-LD capacity (never clipped) vs credited production, and whether
        # the month's targets fit the pool at all. Both travel with the view so
        # the workbook and the API cannot report one without the other.
        "capacity": alloc.get("capacity"),
        "feasible": alloc.get("feasible", True),
    }
    if include_detail:
        out["rows"] = alloc.get("rows") or []
        out["moves"] = alloc.get("moves") or []
        out["notes"] = alloc.get("notes")
        out["fleet"] = fleet
        out["goals"] = goals
    return out


def _year_alloc_totals(cards):
    """Sum allocation months only. Two clocks stay separate."""
    keys = ("old_pred", "new_pred", "old_achv", "new_achv", "target")
    tot = {k: 0 for k in keys}
    tot["n"] = 0
    mats = {mk: {"target": 0, "pred_before": 0, "pred_after": 0,
                 "achv_before": 0, "achv_after": 0}
            for mk, _ in _ALLOC_MATS}
    for c in cards:
        a = c.get("alloc")
        if not a:
            continue
        tot["n"] += 1
        for k in keys:
            v = a.get(k + "_month")
            if v is not None:
                tot[k] += v
        for mk, mv in (a.get("materials") or {}).items():
            b = mats.setdefault(mk, {"target": 0, "pred_before": 0, "pred_after": 0,
                                     "achv_before": 0, "achv_after": 0})
            for fk, sk in (("target", "target_month"),
                           ("pred_before", "pred_before_month"),
                           ("pred_after", "pred_after_month"),
                           ("achv_before", "achv_before_month"),
                           ("achv_after", "achv_after_month")):
                v = mv.get(sk)
                if v is not None:
                    b[fk] += v
    if not tot["n"]:
        return None
    tot["cov_old_pred"] = _cov_pct(tot["old_pred"], tot["target"])
    tot["cov_new_pred"] = _cov_pct(tot["new_pred"], tot["target"])
    tot["cov_old_achv"] = _cov_pct(tot["old_achv"], tot["target"])
    tot["cov_new_achv"] = _cov_pct(tot["new_achv"], tot["target"])
    tot["left_new_pred"] = max(0, tot["target"] - tot["new_pred"])
    tot["over_new_pred"] = max(0, tot["new_pred"] - tot["target"])
    tot["old_achv_raw"] = 0
    tot["new_achv_raw"] = 0
    tot["over_new_achv"] = 0
    for c in cards:
        a = c.get("alloc")
        if not a:
            continue
        if a.get("old_achv_raw_month") is not None:
            tot["old_achv_raw"] += a["old_achv_raw_month"]
        if a.get("new_achv_raw_month") is not None:
            tot["new_achv_raw"] += a["new_achv_raw_month"]
        if a.get("over_new_achv_month") is not None:
            tot["over_new_achv"] += a["over_new_achv_month"]
    tot["cov_old_achv_raw"] = _cov_pct(tot["old_achv_raw"], tot["target"])
    tot["cov_new_achv_raw"] = _cov_pct(tot["new_achv_raw"], tot["target"])
    labels = dict(_ALLOC_MATS)
    for mk, b in mats.items():
        b["label"] = labels.get(mk, mk)
        b["cov_pred"] = _cov_pct(b["pred_after"], b["target"])
        b["cov_achv"] = _cov_pct(b["achv_after"], b["target"])
        b["left"] = max(0, b["target"] - b["pred_after"])
        b["over"] = max(0, b["pred_after"] - b["target"])
    tot["materials"] = mats
    return tot


# The day-of-month saved-plan convention (owner, 2026-08-19): day 01 holds
# Scenario 1, day 03 Scenario 3, day 04 Scenario 4. Day 02 is reserved (S2 was
# deleted from the app on 2026-08-21).
#
# ONE WORKBOOK = ONE SCENARIO. `day=None` used to mean "latest file wins" per
# month, and that silently mixed scenarios inside a single workbook: on
# 2026-08-23 the year book named monthly_plan_2026.xlsx resolved Aug from a
# legacy 2026-08-13 daily and Sep/Oct/Nov/Dec from the day-04 (S4) saves, so
# its Sep target read 2,410,410 t where the real S1 day-01 plan gives
# 2,840,190 t (-15%) and the Year TOTAL summed ACROSS scenarios with no
# disclosure. The default is now EXPLICIT: S1 = day 01.
DEFAULT_SCENARIO_DAY = 1
_SCENARIO_FOR_DAY = {1: "S1", 3: "S3", 4: "S4"}


def _scenario_label_for_day(day):
    """'S1' / 'S3' / 'S4' for the day-of-month convention, else 'day-NN plans'."""
    return _SCENARIO_FOR_DAY.get(int(day), "day-%02d plans" % int(day))


def _year_cards(year, day=None):
    """Month cards for the year board and the year Excel download.

    day=N picks that day-of-month's saved plan (the scenario convention).
    day=None resolves to DEFAULT_SCENARIO_DAY (=1, Scenario 1) rather than
    letting the latest file in each month win, so one workbook can only ever
    contain one scenario.

    A month with NO save on the requested day is dropped entirely - no target,
    no old predicted plan, and never another day's plan substituted (owner,
    2026-08-19: August belongs to Scenario 1 only). The dropped months are
    reported on every card as `_missing_months` so the Year sheet and the API
    can say so instead of leaving a silent hole. day=3 (S3) and day=4 (S4)
    therefore never include August."""
    resolved_day = DEFAULT_SCENARIO_DAY if day is None else int(day)
    yearly = _load_yearly()
    mnums = set(int(m) for m in (yearly or {}).get("months") or [])
    if os.path.isdir(_MONTH_DIR):
        for f in os.listdir(_MONTH_DIR):
            if re.fullmatch(r"%s-(0[1-9]|1[0-2])\.json" % year, f):
                mnums.add(int(f[5:7]))
    if os.path.isdir(_SAVED_DIR):
        try:
            for f in os.listdir(_SAVED_DIR):
                if re.fullmatch(r"%s-(0[1-9]|1[0-2])-\d{2}\.json" % year, f):
                    mnums.add(int(f[5:7]))
        except OSError:
            pass
    with_day = set()
    if os.path.isdir(_SAVED_DIR):
        try:
            for f in os.listdir(_SAVED_DIR):
                m = re.fullmatch(r"%s-(0[1-9]|1[0-2])-%02d\.json" % (year, resolved_day), f)
                if m:
                    with_day.add(int(m.group(1)))
        except OSError:
            pass
    asked = set(mnums)
    mnums &= with_day
    # August belongs to Scenario 1 only (owner 2026-08-19). Day 3 = S3,
    # day 4 = S4: start at September. A leftover 08-04 save is a legacy
    # daily plan, not S4 — do not treat it as a scenario month.
    if resolved_day != 1:
        mnums.discard(8)
        asked.discard(8)
    missing = sorted(asked - mnums)
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
        alloc, src = _resolve_allocation(month, st, day=resolved_day)
        view = _alloc_view(alloc, n, src, include_detail=False)
        card = {
            "month": month, "name": _MONTH_LABELS[mnum], "n_days": n,
            "dt": p.get("dt"),
            "pred_day": pred_day, "achv_day": achv_day, "target_day": tgt_day,
            "pred_month": round(pred_day * n) if pred_day is not None else None,
            "achv_month": round(achv_day * n) if achv_day is not None else None,
            "target_month": round(tgt_day * n) if tgt_day is not None else None,
            "built": bool(p and man),
            "has_alloc": bool(view),
            # Disclosure travels WITH the card, so the Year sheet, the month
            # sheets and the API cannot disagree about which plan was read.
            "_alloc_day": resolved_day,
            "_scenario": _scenario_label_for_day(resolved_day),
            "_missing_months": [_MONTH_LABELS.get(m, str(m)) for m in missing],
            "_source_note": (
                "%s — day-%02d saved plans only. Every month on this sheet comes "
                "from data/saved_plans/%s-MM-%02d.json; no other scenario's plan "
                "appears anywhere in this workbook."
                % (_scenario_label_for_day(resolved_day), resolved_day,
                   year, resolved_day)),
            "alloc_source_date": src,
        }
        if view:
            card["alloc"] = view
            if card.get("dt") is None:
                card["dt"] = view.get("dt_after")
        cards.append(card)
    return yearly, cards


@bp.route("/api/monthly/year-board")
def api_monthly_year_board():
    """Cards + year totals for the loaded matrix (and any stored months)."""
    year = (request.args.get("year") or str(date.today().year)).strip()
    if not re.fullmatch(r"\d{4}", year):
        return jsonify({"ok": False, "error": "year=YYYY"}), 400
    day = (request.args.get("day") or "").strip()
    day = int(day) if re.fullmatch(r"[0-9]{1,2}", day) and 1 <= int(day) <= 28 else None
    yearly, cards = _year_cards(year, day=day)
    resolved_day = DEFAULT_SCENARIO_DAY if day is None else day
    return jsonify({
        "ok": True, "year": year, "day": day,
        # Which plan this board is actually showing. `day` echoes what was
        # asked; `resolved_day`/`scenario` say what was read, and `sources`
        # names the exact saved file per month — one scenario, disclosed.
        "resolved_day": resolved_day,
        "scenario": _scenario_label_for_day(resolved_day),
        "default_day_applied": day is None,
        "sources": {c["month"]: c.get("alloc_source_date") for c in cards},
        "missing_months": (cards[0].get("_missing_months") if cards else []),
        "has_matrix": yearly is not None,
        "source": (yearly or {}).get("source"),
        "routes": len((yearly or {}).get("entries") or []),
        "matrix_months": (yearly or {}).get("months") or [],
        "cards": cards,
        "alloc_year": _year_alloc_totals(cards),
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
#   P1  SAP           — must-move. Filled first from the contractor fleet.
#   P2  LIM from TOS  — filled only with trucks left after SAP. May run short.
#   P3  LIM from LD   — first donor; leftover trucks stay here.
# If LD is not enough for SAP, LIM-TOS trucks move to SAP. Same contractor,
# same-origin donors first. Persisted beside the original month for Excel.

@bp.route("/api/monthly/allocate", methods=["POST"])
def api_monthly_allocate():
    body = request.get_json(silent=True) or {}
    month = (body.get("month") or "").strip()
    if not _month_path(month):
        return jsonify({"ok": False, "error": "supply month=YYYY-MM"}), 400
    yearly = _load_yearly()
    if not yearly:
        return jsonify({"ok": False, "error": "no yearly matrix loaded yet"}), 404
    mnum = str(int(month[5:7]))
    path_models, fleet_kpi, contr_by = _path_model_context()
    if not path_models:
        return jsonify({"ok": False, "error": "no measured day history (path-response empty)"}), 503

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
        prio = 1 if mat == "SAP" else (
            2 if (mat == "LIM" and otype == "TOS") else (3 if mat == "LIM" else 9))
        rows.append({"origin": e["origin"].upper(), "route": route, "src": src,
                     "dst": dst, "mat": mat, "otype": otype,
                     "contractor": e["contractor"].upper(),
                     "prio": prio, "target": wmt, "matrix_dt": dt})
    if not rows:
        return jsonify({"ok": False, "error": "no matrix rows for %s" % month}), 400

    from collections import defaultdict as _dd
    comb_matrix = _dd(float)
    for r in rows:
        comb_matrix[r["route"]] += r["matrix_dt"]

    for r in rows:
        others = max(0.0, comb_matrix[r["route"]] - r["matrix_dt"])
        if r["prio"] in (1, 2, 3) and r["target"] > 0:
            req, why = _required_dt_day(r["src"], r["dst"], r["contractor"],
                                        r["target"], others, path_models,
                                        fleet_kpi, contr_by)
            if req is None:
                seed = _path_row_wmt(r["src"], r["dst"], r["contractor"], 1,
                                     others + 1, path_models, fleet_kpi, contr_by)
                cap = seed.get("cap_trips")
                pay = seed.get("pay")
                max_wmt = (float(cap) * float(pay)) if cap and pay else None
                if max_wmt and max_wmt > 0:
                    req, why2 = _required_dt_day(
                        r["src"], r["dst"], r["contractor"], max_wmt * 0.995,
                        others, path_models, fleet_kpi, contr_by)
                    why = why or why2 or "target above path ceiling"
                r["capped"] = True
                r["req_dt"] = req if req is not None else r["matrix_dt"]
                r["cap_why"] = why
            else:
                r["req_dt"] = req
                r["capped"] = False
        else:
            r["req_dt"] = r["matrix_dt"]
            r["capped"] = False

    fleet = _dd(float)
    for r in rows:
        fleet[r["contractor"]] += r["matrix_dt"]
    moves, shortfalls = [], []
    unused_fleet = {}
    for cont in sorted(fleet):
        crows = [r for r in rows if r["contractor"] == cont]
        remaining = fleet[cont]
        # Supplied targets consume the fixed fleet strictly P1 -> P2 -> P3.
        # Unclassified work can use only what remains after all three targets.
        for prio in (1, 2, 3):
            for r in sorted([x for x in crows if x["prio"] == prio],
                            key=lambda x: -x["target"]):
                need = float(r["req_dt"] or 0)
                give = min(remaining, int(math.ceil(need))) if need else 0
                r["alloc_dt"] = round(give)
                remaining -= give
                if give + 0.5 < need:
                    if prio == 1:
                        shortfalls.append("%s SAP still short %d DT — %s fleet exhausted (LD + LIM-TOS used)"
                                          % (r["route"], round(need - give), cont))
                    else:
                        label = "LIM-TOS" if prio == 2 else "LIM-LD"
                        shortfalls.append("%s %s short %d DT after higher priorities used the fleet"
                                          % (r["route"], label, round(need - give)))
        for r in sorted([x for x in crows if x["prio"] == 9],
                        key=lambda x: -x["matrix_dt"]):
            give = min(remaining, round(r["matrix_dt"]))
            r["alloc_dt"] = max(0, give)
            remaining -= give
        unused_fleet[cont] = max(0.0, remaining)
        donors = [x for x in crows if x.get("alloc_dt", 0) < x["matrix_dt"]]
        receivers = [x for x in crows if x.get("alloc_dt", 0) > x["matrix_dt"]]
        for rec in sorted(receivers, key=lambda x: x["prio"]):
            need = rec["alloc_dt"] - rec["matrix_dt"]
            for prio_don in (3, 2, 9, 1):
                for same_origin in (True, False):
                    if need <= 0:
                        break
                    for don in donors:
                        if need <= 0:
                            break
                        if don["prio"] != prio_don:
                            continue
                        if (don["origin"] == rec["origin"]) != same_origin:
                            continue
                        avail = don["matrix_dt"] - don.get("alloc_dt", 0) - don.get("_given", 0)
                        if avail <= 0:
                            continue
                        take = min(need, avail)
                        don["_given"] = don.get("_given", 0) + take
                        need -= take
                        why = ("LD buffer" if don["prio"] == 3
                               else ("LIM-TOS → SAP" if rec["prio"] == 1 and don["prio"] == 2
                                     else "rebalance"))
                        moves.append({"contractor": cont,
                                      "from": "%s (%s %s)" % (don["route"], don["mat"], don["otype"]),
                                      "to": "%s (%s %s)" % (rec["route"], rec["mat"], rec["otype"]),
                                      "trucks": round(take),
                                      "same_origin": same_origin,
                                      "reason": why})

    comb = _dd(float)
    for r in rows:
        comb[r["route"]] += r.get("alloc_dt", 0)
    for r in rows:
        a = r.get("alloc_dt", 0)
        pr = _path_row_wmt(r["src"], r["dst"], r["contractor"], a,
                           comb[r["route"]] or a, path_models, fleet_kpi, contr_by)
        r["pred_wmt"] = round(pr["wmt"]) if pr.get("wmt") is not None else None
        r["met"] = r["pred_wmt"] is not None and r["target"] > 0 \
            and r["pred_wmt"] >= r["target"] * 0.995

    merged = {}
    for r in rows:
        key = (r["src"], r["dst"], r["contractor"])
        rec = merged.setdefault(key, {"src": r["src"], "dst": r["dst"],
                                      "contractor": r["contractor"],
                                      "dt": 0.0, "wmt_day": 0.0, "materials": set()})
        rec["dt"] += r.get("alloc_dt", 0)
        rec["wmt_day"] += r["target"]
        if r.get("mat"):
            rec["materials"].add(r["mat"])
    route_list = [v for v in merged.values() if v["dt"] > 0]
    plans = [{"route": "%s>%s" % (r["src"], r["dst"]), "source": r["src"],
              "destination": r["dst"], "n_trucks": int(round(r["dt"])),
              "contractor": r["contractor"]}
             for r in route_list]
    import plan_simulator
    sim = plan_simulator.simulate({"plans": plans})
    sim_rows = (sim or {}).get("results") or []
    pred_day, pred_rows = _plan_predict_for_routes(route_list)
    achv_day = 0.0
    for i, r in enumerate(route_list):
        sr = sim_rows[i] if i < len(sim_rows) else {}
        achv_shift = float(sr.get("achievable_production_t") or 0)
        achv_day += achv_shift * 2
        if i < len(pred_rows) and pred_rows[i].get("wmt") is not None:
            pass
    target_day = sum(r["target"] for r in rows)

    st = _load_state(month) or {"month": month}
    old_pred = (st.get("prediction") or {}).get("per_day_wmt")
    old_achv = (st.get("prediction") or {}).get("per_day_achv_wmt")
    if old_pred is None:
        orig_list = _routes_for_month(yearly, mnum)
        if orig_list:
            old_pred, _ = _plan_predict_for_routes(orig_list)
            old_pred = round(old_pred)
            orig_plans = [{"route": "%s>%s" % (r["src"], r["dst"]), "source": r["src"],
                           "destination": r["dst"], "n_trucks": int(round(r["dt"])),
                           "contractor": r["contractor"]} for r in orig_list]
            orig_sim = plan_simulator.simulate({"plans": orig_plans})
            old_achv = round(sum(float(x.get("achievable_production_t") or 0) * 2
                                 for x in (orig_sim.get("results") or [])))
    prio_sum = {str(p): {"target": round(sum(r["target"] for r in rows if r["prio"] == p)),
                         "pred": round(sum(r["pred_wmt"] or 0 for r in rows if r["prio"] == p))}
                for p in (1, 2, 3)}
    payload = {
        "applied_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "old": {"pred": old_pred, "achv": old_achv, "target": round(target_day),
                "dt": int(round(sum(r["matrix_dt"] for r in rows)))},
        "new": {"pred": round(pred_day), "achv": round(achv_day),
                "target": round(target_day),
                "dt": int(round(sum(r.get("alloc_dt", 0) for r in rows)))},
        "rows": [{k: r.get(k) for k in
                  ("origin", "route", "mat", "otype", "contractor", "prio", "target",
                   "matrix_dt", "alloc_dt", "pred_wmt", "met", "capped")}
                 for r in sorted(rows, key=lambda x: (x["prio"], x["contractor"]))],
        "moves": moves,
        "shortfalls": shortfalls,
        "prio_summary": prio_sum,
        "fleet": {c: round(v) for c, v in fleet.items()},
        "unused_fleet": {c: round(v, 1) for c, v in unused_fleet.items()},
    }
    st["allocation"] = payload
    _save_state(month, st)
    return jsonify({
        "ok": True, "month": month, "saved": True,
        "priorities": ["P1 SAP (fixed supply)", "P2 LIM from TOS", "P3 LIM from LD (target)"],
        "fleet": payload["fleet"],
        "unused_fleet": payload["unused_fleet"],
        "old": payload["old"], "new": payload["new"],
        "rows": payload["rows"], "moves": moves, "shortfalls": shortfalls,
        "prio_summary": prio_sum,
        "note": ("Supplied targets consume the fixed fleet in strict order: "
                 "SAP, then LIM-TOS, then LIM-LD. Any fleet beyond all targets "
                 "is reported as unused rather than credited as production. "
                 "Required DT inverts the Plan path model (hard ceiling). Original "
                 "month prediction is kept; this allocation is stored beside it."),
    })
