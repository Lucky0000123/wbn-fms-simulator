#!/usr/bin/env python3
"""Fold phase-5 join-test results into reports/FUEL_DATA_RECON.md as section 10.

Interpretation is decided here, up front, so the answer does not depend on
whoever happens to read the numbers later. Idempotent: rewrites section 10
rather than appending a second copy.
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "fuel_recon" / "phase5_join_test.json"
REPORT = ROOT / "reports" / "FUEL_DATA_RECON.md"
MARK = "\n---\n\n## 10. Join test results"


def tbl(cols, rows, maxw=60):
    if not rows:
        return "_(no rows)_\n"
    def c(v):
        s = "" if v is None else str(v).replace("|", "\\|").replace("\n", " ")
        return s[:maxw] + ("…" if len(s) > maxw else "")
    out = ["| " + " | ".join(cols) + " |",
           "|" + "|".join("---" for _ in cols) + "|"]
    out += ["| " + " | ".join(c(v) for v in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def val(d, key, col, default=None):
    """Pull one scalar out of a result block by column name."""
    b = d.get(key)
    if not b or not b["rows"] or col not in b["columns"]:
        return default
    return b["rows"][0][b["columns"].index(col)]


def main():
    if not SRC.exists():
        raise SystemExit(f"missing {SRC} — run scripts/fuel_recon5.py first")
    d = json.loads(SRC.read_text())

    L = [MARK, ""]
    w = L.append
    w("Run of `scripts/fuel_recon5.py` against the live database. These counts "
      "settle the open questions from section 9.3.\n")

    # --- verdict, computed not asserted
    direct = val(d, "A_direct_fuel_to_hours", "matched")
    fuel_u = val(d, "A_direct_fuel_to_hours", "fuel_units")
    dw = val(d, "B_bridge_day_works", "fuel_units_seen_in_day_works")
    eq_id = val(d, "B_bridge_equipments_master", "via_ID_EQ")
    eq_new = val(d, "B_bridge_equipments_master", "via_NEW_ID_EQ")
    eq_ser = val(d, "B_bridge_equipments_master", "via_SERIAL_NO")
    hx = val(d, "B_bridge_haulage_ext", "fuel_units_in_haulage_ext")
    hm_recent = val(d, "C_day_works_hourmeter_recent", "start_hm")
    tot_ud = val(d, "D_training_set_direct", "fuel_unit_days")
    join_ud = val(d, "D_training_set_direct", "joined_unit_days")
    haul_ud = val(d, "D_training_set_via_haulage", "joined_unit_days")

    w("### 10.1 Verdict\n")
    lines = []
    if direct is not None and fuel_u:
        pct = 100.0 * direct / fuel_u
        lines.append(
            f"- **Direct fuel→hours join: {direct} of {fuel_u} units "
            f"({pct:.1f}%).** " +
            ("Confirms the namespace split — a direct join is not viable."
             if pct < 5 else
             "Unexpectedly viable; the namespace split is narrower than the "
             "sampled shapes implied."))
    cands = [(dw, "DAY_WORKS.UNIT_ID"), (eq_id, "EQUIPMENTS.ID_EQ"),
             (eq_new, "EQUIPMENTS.NEW_ID_EQ"), (eq_ser, "EQUIPMENTS.SERIAL_NO"),
             (hx, "HAULAGE_IWIP_EXT.TRUCK_ID")]
    known = [(n, nm) for n, nm in cands if n is not None]
    detail = (f"(DAY_WORKS {dw}, EQUIPMENTS ID_EQ/NEW_ID_EQ/SERIAL "
              f"{eq_id}/{eq_new}/{eq_ser}, HAULAGE_IWIP_EXT {hx})")
    if not known:
        lines.append(f"- **Bridge: not measured** — no candidate returned a "
                     f"result, so the query failed or was skipped. {detail}")
    elif max(known)[0] == 0:
        lines.append(f"- **No bridge found: every candidate matched 0 fuel "
                     f"units.** {detail} An external ID mapping is required.")
    else:
        best = max(known)
        lines.append(f"- **Best bridge: `{best[1]}` matching {best[0]} fuel "
                     f"units** {detail}")
    if hm_recent is not None:
        lines.append(
            f"- **DAY_WORKS hour meters since 2026-02: {hm_recent} populated.** " +
            ("Unusable as a denominator." if not hm_recent else
             "Usable — prefer these over derived OPERATING_HOURS."))
    if tot_ud:
        lines.append(
            f"- **Training set: {join_ud} of {tot_ud} fuel unit-days join to "
            f"hours ({100.0*(join_ud or 0)/tot_ud:.1f}%); "
            f"{haul_ud} join to the weighbridge "
            f"({100.0*(haul_ud or 0)/tot_ud:.1f}%).**")
        if (haul_ud or 0) > (join_ud or 0):
            lines.append("- **=> Use litres-per-tonne-km via the weighbridge "
                         "as the primary target**, per section 9.4 fallback (2).")
        elif (join_ud or 0) > 0:
            lines.append("- **=> Litres-per-operating-hour is viable**, "
                         "per section 9.4 path (1).")
        else:
            lines.append("- **=> Neither path joins. Fuel litres cannot be "
                         "normalised; a per-unit intensity model is not "
                         "possible without an external ID mapping.**")

    # E/F: is a tonne-km target actually constructible?
    pay_tot = val(d, "E_payload_join", "fuel_unit_days")
    pay_hit = val(d, "E_payload_join", "with_payload")
    gps_tot = val(d, "F_gps_km_bridge", "fuel_units")
    gps_hit = val(d, "F_gps_km_bridge", "with_imei")
    if pay_tot:
        lines.append(
            f"- **Payload denominator: {pay_hit} of {pay_tot} fuel unit-days "
            f"have weighbridge tonnes ({100.0*(pay_hit or 0)/pay_tot:.1f}%).** "
            "The ticket carries no distance column, so this alone gives "
            "litres-per-tonne, not litres-per-tonne-km.")
    if gps_tot:
        lines.append(
            f"- **GPS-km bridge (`FMS_EQUIPMENTS.plateNumber`→`imei`): "
            f"{gps_hit} of {gps_tot} fuel units carry an imei "
            f"({100.0*(gps_hit or 0)/gps_tot:.1f}%).** " +
            ("Distance is obtainable, so a true tonne-km target is "
             "constructible." if (gps_hit or 0) > 0.5 * gps_tot else
             "Coverage is too thin to price distance for most fuelled units; "
             "prefer litres-per-tonne or fall back to route lookup."))
    w("\n".join(lines) + "\n")

    TITLES = {
        "A_direct_fuel_to_hours": "A. Direct fuel → operating-hours join",
        "B_bridge_day_works": "B. Bridge candidate: DAY_WORKS.UNIT_ID",
        "B_bridge_equipments_master": "B. Bridge candidate: EQUIPMENTS master",
        "B_bridge_haulage_ext": "B. Bridge candidate: HAULAGE_IWIP_EXT.TRUCK_ID",
        "B_equipments_namespace_map": "B. EQUIPMENTS rows for trucks/excavators",
        "C_day_works_hourmeter_coverage": "C. DAY_WORKS hour-meter coverage (all time)",
        "C_day_works_hourmeter_recent": "C. DAY_WORKS hour-meter coverage (since 2026-02)",
        "D_training_set_direct": "D. Training-set size via operating hours",
        "D_training_set_via_haulage": "D. Training-set size via weighbridge",
        "D_sample_joined_rows": "D. Sample aggregated fuel unit-days",
        "E_payload_join": "E. Payload denominator via weighbridge (direct join)",
        "F_gps_km_bridge": "F. GPS-km bridge via FMS_EQUIPMENTS plateNumber→imei",
    }
    w("\n### 10.2 Raw results\n")
    for k, title in TITLES.items():
        b = d.get(k)
        if not b:
            continue
        w(f"\n**{title}**\n")
        w(tbl(b["columns"], b["rows"]))

    block = "\n".join(L)
    # View definitions in section 5 contain CRLF. Reading with the default
    # newline handling then writing back silently strips every CR, rewriting
    # 812 lines of SQL. Preserve bytes exactly by disabling translation.
    with open(REPORT, "r", encoding="utf-8", newline="") as fh:
        txt = fh.read()
    if MARK in txt:
        txt = txt[:txt.index(MARK)]
    with open(REPORT, "w", encoding="utf-8", newline="") as fh:
        fh.write(txt.rstrip() + "\n" + block)
    print(f"section 10 written to {REPORT}")


if __name__ == "__main__":
    main()
