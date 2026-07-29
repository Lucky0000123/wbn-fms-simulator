"""ore_waste_tags.py — Tier 2: material tagging.

THE BRIEF'S RULE CANNOT BE APPLIED, AND THAT IS THE FINDING
The PRISM rule is: auto-tag by dump destination geofence, TOS tip = ORE, waste
tip = WASTE, never an operator UI. The rule is sound — operator-selected
material is exactly how grade data gets corrupted — but this dataset has no
waste side to tag. Checked four ways:

  1. NO destination name encodes it. Zero of the 17 destinations match
     TOS/ROM/CRUSHER or WASTE/DUMP/WR under any casing.

  2. The weighbridge already tags MATERIAL on every ticket, 100% coverage, and
     across 560,091 tickets the only two values are SAP (saprolite, 504,856
     tickets, 21.2 Mt) and LIM (limonite, 55,235, 2.8 Mt). Both are nickel ore.

  3. HAULAGE_IWIP_WASTE exists but is hazardous-waste disposal, not mining
     waste: 179 tickets totalling 1,376 t of waste oil (废机油), used filters
     (废滤芯) and batteries, against 24.0 Mt of ore. It carries no MATERIAL or
     WMT column and cannot be unioned with the haulage feed.

  4. FMS_GEOFENCES has 1,053 dumping zones, but TOS_STATUS is open/full/none —
     a pile capacity state, not a material class.

So this is an ORE-ONLY haulage feed. Inventing a waste class would put
fabricated tonnes into the stockpile grades that Phase 6 exists to track, which
is the exact failure the no-operator-UI rule is meant to prevent.

WHAT SHIPS INSTEAD
The distinction the data genuinely supports:
  material_type  ORE for everything, since that is what is hauled
  ore_type       SAP or LIM, from the weighbridge's own tag
  flow           DIRECT / RECLAIMING / REJECT / REHANDLING, from ACTIVITY,
                 which separates fresh mine production from pad rehandling —
                 the distinction that actually matters for FIFO, because
                 reclaimed material must not be counted as new arrivals.

Every tagged trip records where its classification came from and whether it is
confident, and `data/destination_material_map.csv` lists all 17 destinations
with the evidence, for site verification.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
TRIP_CSV = os.path.join(DATA, "trip_level_base.csv")
TAGGED_CSV = os.path.join(DATA, "trip_level_tagged.csv")
DEST_MAP_CSV = os.path.join(DATA, "destination_material_map.csv")
TAGS_META = os.path.join(DATA, "material_tags_meta.json")

# Kept so the check is visible in code, not just in this docstring: if the site
# ever renames a tip to include these, name-based tagging becomes possible.
ORE_NAME_PAT = re.compile(r"\bTOS\b|\bROM\b|CRUSH", re.I)
WASTE_NAME_PAT = re.compile(r"WASTE|\bDUMP\b|\bWR\b|OVERBURDEN|\bOB\b", re.I)

ORE_CODES = {"SAP": "saprolite", "LIM": "limonite"}
# ACTIVITY separates fresh production from pad rehandling. Only DIRECT and
# HAULAGE put NEW material on a pile; the rest move material already counted.
FRESH_FLOWS = {"DIRECT", "HAULAGE"}


def classify_destinations(df: pd.DataFrame, conn=None) -> pd.DataFrame:
    """One row per destination with the evidence behind its classification."""
    rows = []
    geo = {}
    try:
        import simulator_api as sim
        if conn is None and sim._db_ready():
            conn = sim._conn("FMS_DB")
        if conn is not None:
            g = pd.read_sql("SELECT NAME, TYPE, TOS_STATUS FROM FMS_GEOFENCES "
                            "WHERE TYPE = 'dumping'", conn)
            geo = {str(n).strip().upper(): t for n, t in
                   zip(g["NAME"], g["TOS_STATUS"])}
    except Exception:                                       # noqa: BLE001
        geo = {}

    agg = df.groupby("destination").agg(
        trips=("payload_t", "size"), total_wmt=("payload_t", "sum")).reset_index()
    mat = (df.groupby(["destination", "material"]).size()
             .unstack(fill_value=0) if "material" in df.columns else None)

    for r in agg.itertuples():
        name = str(r.destination)
        u = name.strip().upper()
        name_ore = bool(ORE_NAME_PAT.search(name))
        name_waste = bool(WASTE_NAME_PAT.search(name))
        codes = {}
        if mat is not None and name in mat.index:
            codes = {c: int(v) for c, v in mat.loc[name].items() if v > 0}
        # Evidence order: an explicit waste name would win, then the ticket's
        # own material code, then the fallback.
        if name_waste and not name_ore:
            mt, src, conf = "WASTE", "destination_name", True
        elif codes and set(codes) <= set(ORE_CODES):
            mt, src, conf = "ORE", "weighbridge_material_code", True
        elif name_ore:
            mt, src, conf = "ORE", "destination_name", True
        else:
            mt, src, conf = "ORE", "default_ore_only_feed", False
        rows.append({
            "destination": name, "material_type": mt,
            "classification_source": src, "classification_confident": conf,
            "trips": int(r.trips), "total_wmt": round(float(r.total_wmt), 1),
            "ore_codes_seen": ",".join(sorted(codes)) or "",
            "geofence_tos_status": geo.get(u, ""),
            "name_matches_ore_keyword": name_ore,
            "name_matches_waste_keyword": name_waste,
            "needs_site_verification": not conf,
        })
    return pd.DataFrame(rows).sort_values("total_wmt", ascending=False)


def tag_trips(df: pd.DataFrame | None = None, dest_map: pd.DataFrame | None = None):
    if df is None:
        df = pd.read_csv(TRIP_CSV)
        df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
    dm = classify_destinations(df) if dest_map is None else dest_map
    lut = dm.set_index("destination")

    d = df.copy()
    d["material_type"] = d["destination"].map(lut["material_type"]).fillna("ORE")
    d["classification_source"] = d["destination"].map(lut["classification_source"]).fillna("default_ore_only_feed")
    d["classification_confident"] = d["destination"].map(lut["classification_confident"]).fillna(False)
    # The genuinely informative splits.
    d["ore_type"] = (d["material"].map(ORE_CODES).fillna("unknown")
                     if "material" in d.columns else "unknown")
    return d, dm


def attach_flow(d: pd.DataFrame, conn=None) -> pd.DataFrame:
    """Join ACTIVITY per ticket so FIFO can tell fresh arrivals from rehandling.

    Without this, reclaimed material dumped back on a pad would be counted as
    new production and inflate both tonnes and the FIFO queue.
    """
    if "ticket_no" not in d.columns:
        d["flow"] = "UNKNOWN"
        d["is_fresh_production"] = True
        return d
    try:
        import simulator_api as sim
        close = False
        if conn is None:
            if not sim._db_ready():
                raise RuntimeError("no DB")
            conn, close = sim._conn("WBN_DATABASE"), True
        try:
            act = pd.read_sql("""SELECT TICKET_NO ticket_no, ACTIVITY flow
                FROM HAULAGE_IWIP WHERE [DATE] >= '%s' AND [DATE] <= '%s'
                  AND TICKET_NO IS NOT NULL"""
                % (d["date"].min(), d["date"].max()), conn)
        finally:
            if close:
                conn.close()
        act = act.drop_duplicates("ticket_no")
        d = d.merge(act, on="ticket_no", how="left")
        d["flow"] = d["flow"].fillna("UNKNOWN").astype(str).str.upper()
    except Exception:                                       # noqa: BLE001
        d["flow"] = "UNKNOWN"
    d["is_fresh_production"] = d["flow"].isin(FRESH_FLOWS) | (d["flow"] == "UNKNOWN")
    return d


def run(verbose: bool = True) -> dict:
    say = print if verbose else (lambda *a, **k: None)
    tagged, dm = tag_trips()
    tagged = attach_flow(tagged)

    os.makedirs(DATA, exist_ok=True)
    dm.to_csv(DEST_MAP_CSV, index=False)
    tagged.to_csv(TAGGED_CSV, index=False)
    try:
        import importlib.util
        if importlib.util.find_spec("pyarrow"):
            tagged.to_parquet(TAGGED_CSV.rsplit(".", 1)[0] + ".parquet", index=False)
    except Exception:                                       # noqa: BLE001
        pass

    by_type = tagged["material_type"].value_counts().to_dict()
    by_ore = tagged["ore_type"].value_counts().to_dict()
    by_flow = tagged["flow"].value_counts().head(8).to_dict()
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trips_tagged": int(len(tagged)),
        "destinations": int(len(dm)),
        "material_type_counts": by_type,
        "ore_type_counts": by_ore,
        "flow_counts": by_flow,
        "fresh_production_pct": round(100 * float(tagged["is_fresh_production"].mean()), 1),
        "confident_pct": round(100 * float(tagged["classification_confident"].mean()), 1),
        "destinations_needing_verification": int(dm["needs_site_verification"].sum()),
        "waste_stream_present": bool((tagged["material_type"] == "WASTE").any()),
        "finding": ("ORE-ONLY haulage feed. No destination name encodes ore vs "
                    "waste; the weighbridge's only material codes are SAP and "
                    "LIM, both nickel ore; HAULAGE_IWIP_WASTE is hazardous-waste "
                    "disposal (179 tickets, 1,376 t of waste oil and filters) "
                    "against 24.0 Mt of ore. No waste class was invented."),
        "action_for_site": ("verify data/destination_material_map.csv: confirm "
                            "every destination is an ore tip, and say where "
                            "mining waste/overburden haulage is recorded if it "
                            "exists in another system"),
    }
    with open(TAGS_META, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2, default=str)

    say("tagged %s trips across %d destinations" % (format(len(tagged), ","), len(dm)))
    say("  material_type: %s" % by_type)
    say("  ore_type:      %s" % by_ore)
    say("  flow:          %s" % by_flow)
    say("  fresh production: %.1f%% | confident classification: %.1f%%"
        % (meta["fresh_production_pct"], meta["confident_pct"]))
    say("  destinations needing site verification: %d of %d"
        % (meta["destinations_needing_verification"], len(dm)))
    say("  waste stream present: %s" % meta["waste_stream_present"])
    return meta


def load_tagged() -> pd.DataFrame | None:
    try:
        return pd.read_csv(TAGGED_CSV)
    except Exception:                                       # noqa: BLE001
        return None


if __name__ == "__main__":
    run()
