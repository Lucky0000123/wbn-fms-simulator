"""FMS_DB plan-memory tables: nodes, edges, day KPI corpus, analogue cache.

Create/read/write helpers. Safe when DB is unavailable — callers fall back to
capability fixture / snapshot.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime

DDL = [
    """
    IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'SIM_PLAN_DAY_KPI')
    CREATE TABLE dbo.SIM_PLAN_DAY_KPI (
        id BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        d DATE NOT NULL,
        origin NVARCHAR(64) NOT NULL,
        dest NVARCHAR(64) NOT NULL,
        contractor NVARCHAR(64) NULL,
        dt FLOAT NOT NULL,
        trips FLOAT NOT NULL,
        wmt FLOAT NOT NULL,
        trips_per_dt FLOAT NULL,
        payload_t FLOAT NULL,
        rain_mm FLOAT NULL,
        season NVARCHAR(16) NULL,
        has_gps BIT NOT NULL DEFAULT 0,
        avg_speed_kmh FLOAT NULL,
        wb_trucks FLOAT NULL,
        sections_json NVARCHAR(MAX) NULL,
        source NVARCHAR(32) NULL,
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    )
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_SIM_PLAN_DAY_KPI_route_d'
                   AND object_id = OBJECT_ID('dbo.SIM_PLAN_DAY_KPI'))
    CREATE INDEX IX_SIM_PLAN_DAY_KPI_route_d
      ON dbo.SIM_PLAN_DAY_KPI (origin, dest, d)
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'SIM_PLAN_NODE')
    CREATE TABLE dbo.SIM_PLAN_NODE (
        node_id NVARCHAR(64) NOT NULL PRIMARY KEY,
        route NVARCHAR(128) NOT NULL,
        contractor NVARCHAR(64) NULL,
        dt_bucket INT NOT NULL,
        weather NVARCHAR(8) NOT NULL,
        hit_count INT NOT NULL DEFAULT 0,
        last_seen DATETIME2 NULL,
        meta_json NVARCHAR(MAX) NULL
    )
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'SIM_PLAN_EDGE')
    CREATE TABLE dbo.SIM_PLAN_EDGE (
        edge_id NVARCHAR(128) NOT NULL PRIMARY KEY,
        from_node NVARCHAR(64) NOT NULL,
        to_node NVARCHAR(64) NOT NULL,
        shared_section NVARCHAR(64) NULL,
        weight FLOAT NOT NULL DEFAULT 1,
        outcome_delta FLOAT NULL,
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    )
    """,
    """
    IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = 'SIM_PLAN_ANALOGUE_CACHE')
    CREATE TABLE dbo.SIM_PLAN_ANALOGUE_CACHE (
        fingerprint NVARCHAR(32) NOT NULL PRIMARY KEY,
        query_json NVARCHAR(MAX) NOT NULL,
        result_json NVARCHAR(MAX) NOT NULL,
        hit_count INT NOT NULL DEFAULT 1,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    )
    """,
]


def ensure_tables(conn):
    cur = conn.cursor()
    for stmt in DDL:
        cur.execute(stmt)
    conn.commit()


def _dt_bucket(n_trucks):
    n = int(round(float(n_trucks or 0)))
    # 10-truck buckets
    return max(0, (n // 10) * 10)


def node_id(route, contractor, n_trucks, wet):
    c = (contractor or "ANY").upper()
    w = "wet" if wet else "dry"
    return "%s|%s|%d|%s" % (route, c, _dt_bucket(n_trucks), w)


def upsert_nodes_edges(conn, result):
    """Strengthen graph memory from a successful analogues response."""
    if not result or not result.get("ok"):
        return
    cur = conn.cursor()
    plans = result.get("plans") or []
    wet = bool(result.get("wet"))
    node_ids = []
    for p in plans:
        nid = node_id(p["route"], p.get("contractor"), p.get("n_trucks"), wet)
        node_ids.append(nid)
        meta = json.dumps({"sections": p.get("sections") or []})
        cur.execute(
            "MERGE dbo.SIM_PLAN_NODE AS t "
            "USING (SELECT %s AS node_id) AS s ON t.node_id = s.node_id "
            "WHEN MATCHED THEN UPDATE SET hit_count = t.hit_count + 1, "
            "  last_seen = SYSUTCDATETIME(), meta_json = %s "
            "WHEN NOT MATCHED THEN INSERT "
            "  (node_id, route, contractor, dt_bucket, weather, hit_count, last_seen, meta_json) "
            "  VALUES (%s, %s, %s, %s, %s, 1, SYSUTCDATETIME(), %s);",
            (nid, meta, nid, p["route"], p.get("contractor"),
             _dt_bucket(p.get("n_trucks")), "wet" if wet else "dry", meta),
        )
    shared = (result.get("shared_road") or {}).get("shared_sections") or []
    collapse = (result.get("shared_road") or {}).get("trips_per_dt_collapse_pct")
    for i, a in enumerate(node_ids):
        for b in node_ids[i + 1:]:
            for sec in (shared or ["overlap"]):
                eid = "%s→%s|%s" % (a, b, sec)
                cur.execute(
                    "MERGE dbo.SIM_PLAN_EDGE AS t "
                    "USING (SELECT %s AS edge_id) AS s ON t.edge_id = s.edge_id "
                    "WHEN MATCHED THEN UPDATE SET weight = t.weight + 1, "
                    "  outcome_delta = %s, updated_at = SYSUTCDATETIME() "
                    "WHEN NOT MATCHED THEN INSERT "
                    "  (edge_id, from_node, to_node, shared_section, weight, outcome_delta) "
                    "  VALUES (%s, %s, %s, %s, 1, %s);",
                    (eid, collapse, eid, a, b, sec, collapse),
                )
    conn.commit()


def cache_get(conn, fingerprint):
    cur = conn.cursor()
    cur.execute(
        "SELECT result_json FROM dbo.SIM_PLAN_ANALOGUE_CACHE WHERE fingerprint=%s",
        (fingerprint,))
    row = cur.fetchone()
    if not row:
        return None
    try:
        data = json.loads(row[0])
    except Exception:  # noqa: BLE001
        return None
    cur.execute(
        "UPDATE dbo.SIM_PLAN_ANALOGUE_CACHE SET hit_count = hit_count + 1, "
        "updated_at = SYSUTCDATETIME() WHERE fingerprint=%s",
        (fingerprint,))
    conn.commit()
    return data


def cache_put(conn, fingerprint, query, result):
    cur = conn.cursor()
    qj = json.dumps(query)
    rj = json.dumps(result)
    cur.execute(
        "MERGE dbo.SIM_PLAN_ANALOGUE_CACHE AS t "
        "USING (SELECT %s AS fingerprint) AS s ON t.fingerprint = s.fingerprint "
        "WHEN MATCHED THEN UPDATE SET result_json=%s, query_json=%s, "
        "  hit_count = t.hit_count + 1, updated_at = SYSUTCDATETIME() "
        "WHEN NOT MATCHED THEN INSERT (fingerprint, query_json, result_json) "
        "  VALUES (%s, %s, %s);",
        (fingerprint, rj, qj, fingerprint, qj, rj),
    )
    conn.commit()


def read_day_kpi_rows(conn, limit=200000):
    """Return rows shaped like dailyByPath (+ contractor/rain/speed)."""
    cur = conn.cursor()
    cur.execute(
        "SELECT TOP (%d) CONVERT(char(10), d, 23), origin, dest, contractor, "
        "dt, trips, wmt, rain_mm, avg_speed_kmh, wb_trucks, source "
        "FROM dbo.SIM_PLAN_DAY_KPI ORDER BY d DESC" % int(limit))
    out = []
    for (d, o, dd, contr, dt, trips, wmt, rain, spd, wb, src) in cur.fetchall():
        out.append({
            "d": d, "o": o, "dd": dd, "contractor": contr,
            "snb": float(dt or 0), "srit": float(trips or 0), "sw": float(wmt or 0),
            "nb": float(dt or 0), "rit": float(trips or 0), "w": float(wmt or 0),
            "rain_mm": float(rain) if rain is not None else None,
            "avg_speed_kmh": float(spd) if spd is not None else None,
            "wb_trucks": float(wb) if wb is not None else None,
            "source": src or "fms_memory",
        })
    return out


_LOCAL_KPI = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "plan_day_kpi.json")


def write_local_day_kpi(corpus_rows):
    """Disk fallback when FMS_DB writes time out over VPN."""
    os.makedirs(os.path.dirname(_LOCAL_KPI), exist_ok=True)
    payload = {
        "at": time.time(),
        "n": len(corpus_rows),
        "rows": [{
            "d": c["date"], "o": c["origin"], "dd": c["dest"],
            "contractor": c.get("contractor"),
            "snb": c["dt"], "srit": c["trips"], "sw": c["wmt"],
            "nb": c["dt"], "rit": c["trips"], "w": c["wmt"],
            "rain_mm": c.get("rain_mm"),
            "avg_speed_kmh": c.get("avg_speed_kmh"),
            "wb_trucks": c.get("wb_trucks"),
            "source": c.get("source") or "local_memory",
        } for c in corpus_rows],
    }
    tmp = _LOCAL_KPI + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    os.replace(tmp, _LOCAL_KPI)
    return len(corpus_rows)


def read_local_day_kpi():
    if not os.path.isfile(_LOCAL_KPI):
        return None
    try:
        with open(_LOCAL_KPI, encoding="utf-8") as f:
            data = json.load(f)
        rows = data.get("rows") or []
        return rows if rows else None
    except Exception:  # noqa: BLE001
        return None


def _kpi_json_row(c):
    return {
        "d": c["date"], "o": c["origin"], "dd": c["dest"],
        "contractor": c.get("contractor"),
        "dt": c["dt"], "trips": c["trips"], "wmt": c["wmt"],
        "trips_per_dt": c.get("trips_per_dt"), "payload_t": c.get("payload_t"),
        "rain_mm": c.get("rain_mm"), "season": c.get("season"),
        "has_gps": 1 if c.get("has_gps") else 0,
        "avg_speed_kmh": c.get("avg_speed_kmh"), "wb_trucks": c.get("wb_trucks"),
        "sections_json": json.dumps(c.get("sections") or []),
        "source": c.get("source") or "build",
    }


def replace_day_kpi(conn, corpus_rows, batch_size=1500):
    """Full refresh via OPENJSON batches (VPN-friendly vs row-by-row executemany)."""
    cur = conn.cursor()
    cur.execute("IF OBJECT_ID('dbo.SIM_PLAN_DAY_KPI','U') IS NOT NULL TRUNCATE TABLE dbo.SIM_PLAN_DAY_KPI")
    conn.commit()
    sql = (
        "INSERT INTO dbo.SIM_PLAN_DAY_KPI "
        "(d, origin, dest, contractor, dt, trips, wmt, trips_per_dt, payload_t, "
        " rain_mm, season, has_gps, avg_speed_kmh, wb_trucks, sections_json, source) "
        "SELECT CONVERT(date, d), o, dd, contractor, dt, trips, wmt, trips_per_dt, payload_t, "
        "       rain_mm, season, has_gps, avg_speed_kmh, wb_trucks, sections_json, source "
        "FROM OPENJSON(%s) WITH ("
        "  d nvarchar(10) '$.d', o nvarchar(64) '$.o', dd nvarchar(64) '$.dd', "
        "  contractor nvarchar(64) '$.contractor', "
        "  dt float '$.dt', trips float '$.trips', wmt float '$.wmt', "
        "  trips_per_dt float '$.trips_per_dt', payload_t float '$.payload_t', "
        "  rain_mm float '$.rain_mm', season nvarchar(16) '$.season', "
        "  has_gps bit '$.has_gps', avg_speed_kmh float '$.avg_speed_kmh', "
        "  wb_trucks float '$.wb_trucks', sections_json nvarchar(max) '$.sections_json', "
        "  source nvarchar(32) '$.source'"
        ")"
    )
    n = 0
    for i in range(0, len(corpus_rows), batch_size):
        chunk = [_kpi_json_row(c) for c in corpus_rows[i:i + batch_size]]
        cur.execute(sql, (json.dumps(chunk),))
        conn.commit()
        n += len(chunk)
        print("  SIM_PLAN_DAY_KPI inserted %d / %d" % (n, len(corpus_rows)))
    return n


def fetch_gps_speed_by_date(conn_fms, dates):
    """Avg segment speed (km/h) per day from FMS_CONGESTION_SEG when present.

    HOUR_TS is epoch-ms bigint. Speed = SUM_SPD / FIX_N. Only returns keys for
    dates that actually have rows — never fabricates peak-season speeds.
    """
    if not dates:
        return {}
    from plan_analogues import has_haul_gps
    want = sorted({str(d)[:10] for d in dates if has_haul_gps(d)})
    if not want:
        return {}
    cur = conn_fms.cursor()
    out = {}
    # Convert epoch-ms → date; average of per-row mean speeds weighted by FIX_N.
    # Pull a date window covering requested days rather than huge IN lists.
    d0, d1 = want[0], want[-1]
    sql = (
        "SELECT CONVERT(char(10), DATEADD(SECOND, HOUR_TS/1000, '1970-01-01'), 23) AS d, "
        "       SUM(SUM_SPD) / NULLIF(SUM(FIX_N), 0) AS avg_spd "
        "FROM dbo.FMS_CONGESTION_SEG "
        "WHERE FIX_N > 0 "
        "  AND DATEADD(SECOND, HOUR_TS/1000, '1970-01-01') >= %s "
        "  AND DATEADD(SECOND, HOUR_TS/1000, '1970-01-01') < DATEADD(DAY, 1, %s) "
        "GROUP BY CONVERT(char(10), DATEADD(SECOND, HOUR_TS/1000, '1970-01-01'), 23)"
    )
    try:
        cur.execute(sql, (d0, d1))
        want_set = set(want)
        for d, spd in cur.fetchall():
            ds = str(d)[:10]
            if ds in want_set and spd is not None:
                out[ds] = float(spd)
    except Exception as e:  # noqa: BLE001
        print("[plan_memory] gps speed query failed: %s" % e)
    return out
