"""voice_api.py — Grok voice agent for the WBN haulage simulator.

Owner (2026-09-04): "can you make the voice agents ... use OAuth because I
have a subscription." The xAI Realtime API (wss://api.x.ai/v1/realtime,
grok-voice-latest) does speech-to-speech with client-side function tools.

AUTH — the SUBSCRIPTION, not the API key. The API key the owner pasted has
no credit ("team has used all available credits"), but the Grok CLI login
in ~/.grok/auth.json is an OIDC token from auth.x.ai whose scope includes
`api:access`, and it was PROVED (2026-09-04) to open /v1/realtime and
return spoken audio. That token expires every ~20 min; the refresh_token
next to it mints a new one at https://auth.x.ai/oauth2/token
(grant_types_supported includes refresh_token). This module never writes
auth.json — the Grok CLI owns that file — it keeps its refreshed access
token in memory only. Set XAI_API_KEY to force the key path instead.

BROWSER PATH — the OIDC token never reaches the page. /api/voice/session
mints an EPHEMERAL client secret (POST /v1/realtime/client_secrets) with
the owner's token and hands only that to the browser, which opens the
WebSocket itself (browsers cannot set Authorization headers; the secret
rides the WebSocket subprotocol per the docs). Audio therefore streams
browser <-> xAI directly with no relay hop through Flask.

TOOLS — READ-ONLY, answered from the simulator's own endpoints via the
Flask test client so the voice agent can never disagree with the Year
sheet. Nothing here mutates a plan.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.request
import urllib.error

from flask import Blueprint, jsonify, request, current_app, render_template

bp = Blueprint("voice_api", __name__)

_AUTH_FILE = os.path.expanduser("~/.grok/auth.json")
_TOKEN_URL = "https://auth.x.ai/oauth2/token"
_XAI = "https://api.x.ai/v1"
_LOCK = threading.Lock()
_CACHE = {"access": None, "exp": 0.0, "source": None}

# Day-of-month convention shared with monthly_api._SCENARIO_FOR_DAY.
_SCEN = {
    "4.1":   {"day": 7, "sid": "S7", "label": "4.1"},
    "4.2":   {"day": 8, "sid": "S8", "label": "4.2"},
    "4.2.1": {"day": 9, "sid": "S9", "label": "4.2.1"},
    "3.0.1": {"day": 3, "sid": "S3", "label": "3.0.1"},
    "3.0.2": {"day": 4, "sid": "S4", "label": "3.0.2"},
    "3.1.1": {"day": 5, "sid": "S5", "label": "3.1.1"},
    "3.1.2": {"day": 6, "sid": "S6", "label": "3.1.2"},
}
_ALIASES = {"s7": "4.1", "s8": "4.2", "s9": "4.2.1", "s3": "3.0.1", "s4": "3.0.2",
            "s5": "3.1.1", "s6": "3.1.2", "four point one": "4.1",
            "four point two": "4.2", "four point two point one": "4.2.1",
            "4.2 balance": "4.2.1", "balance": "4.2.1"}


# ── token ───────────────────────────────────────────────────────────────────

def _read_auth_file():
    with open(_AUTH_FILE, encoding="utf-8") as f:
        d = json.load(f)
    # one entry: "https://auth.x.ai::<client_id>"
    for k, v in d.items():
        if isinstance(v, dict) and v.get("key"):
            return v
    return None


def _jwt_exp(tok):
    try:
        import base64
        p = tok.split(".")[1]
        p += "=" * (-len(p) % 4)
        return float(json.loads(base64.urlsafe_b64decode(p)).get("exp") or 0)
    except Exception:
        return 0.0


def _refresh(entry):
    body = json.dumps({
        "grant_type": "refresh_token",
        "refresh_token": entry["refresh_token"],
        "client_id": entry.get("oidc_client_id"),
    }).encode()
    req = urllib.request.Request(_TOKEN_URL, data=body,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        # auth.x.ai may want form encoding; try once more that way.
        form = ("grant_type=refresh_token&refresh_token=%s&client_id=%s"
                % (entry["refresh_token"], entry.get("oidc_client_id") or "")).encode()
        req = urllib.request.Request(
            _TOKEN_URL, data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST")
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.load(r)
    tok = d.get("access_token")
    if not tok:
        raise RuntimeError("refresh returned no access_token")
    return tok


def xai_bearer():
    """Return (token, source). Prefers XAI_API_KEY when set; else the Grok
    subscription's OIDC token, refreshed in memory when within 2 min of
    expiry."""
    key = os.environ.get("XAI_API_KEY", "").strip()
    if key:
        return key, "api-key"
    with _LOCK:
        now = time.time()
        if _CACHE["access"] and _CACHE["exp"] - now > 120:
            return _CACHE["access"], _CACHE["source"]
        entry = _read_auth_file()
        if not entry:
            raise RuntimeError("no Grok login found in ~/.grok/auth.json "
                               "(run `grok login`) and XAI_API_KEY is not set")
        tok = entry["key"]
        exp = _jwt_exp(tok)
        src = "grok-subscription"
        if exp - now <= 120 and entry.get("refresh_token"):
            tok = _refresh(entry)
            exp = _jwt_exp(tok) or (now + 900)
            src = "grok-subscription (refreshed)"
        _CACHE.update(access=tok, exp=exp, source=src)
        return tok, src


# ── session (ephemeral client secret) ────────────────────────────────────────

_KEYTERMS = ["TOFU", "TF", "KRENE", "KR", "BLB", "POS 12", "POS 6", "POS 14",
             "Huafei", "BSE", "FeNi", "FeNi KM15", "FeNi KM0", "RIM", "SMA",
             "IWIP", "LIM", "LD", "SAP", "TOS", "limonite", "saprolite",
             "weighbridge", "T14", "T15", "T16", "T12", "T17", "Hugo",
             "Killian", "scenario 4.1", "scenario 4.2", "scenario 4.2.1",
             "trips per DT", "DT", "dump truck", "Year sheet", "park"]

_INSTRUCTIONS = """You are the haulage planning assistant for WBN's nickel-ore
mine on Halmahera. You speak to planners (Rahul, Hugo, Killian).

Domain: trucks are DT (dump trucks). Contractors RIM and SMA haul our ore;
IWIP trucks do POS transit reclaim and are not our fleet. Pits: TOFU (TF),
KRENE (KR), BLB. Materials: SAP (saprolite, to FeNi smelters) and LIM
(limonite: TOS is fresh from pit, LD is reclaimed from the TOFU stockpile).
Plants: FeNi KM0 and KM15, Huafei and BSE (the two HPAL plants). POS 12,
POS 6, POS 14 are transit stockpiles. Scenarios: 4.1 (all LD via POS 12,
19.0 Mt), 4.2 (client plant split 2/3 Huafei 1/3 BSE, LD 8.0 Mt, POS 6 from
November), 4.2.1 (same as 4.2 but 65% of Nov-Dec POS LD returns to POS 12
so the year lands 100% with the same fleet).

Rules:
- ALWAYS call a tool before quoting a number. Never guess a figure.
- Call the tool SILENTLY: do not say "let me fetch" or "I'll check" first.
  Speak only once you have the result.
- Answer in one to three short spoken sentences. Round tonnes to the nearest
  thousand and say "million tonnes" for large figures. Say percentages as
  "one hundred point three percent".
- If asked to change a plan, say you are read-only and the planner should do
  it in the Plan tab.
- If a scenario is not named, ask which one, or default to 4.2.1.
"""

_TOOLS = [
    {"type": "function", "name": "list_scenarios",
     "description": "List the haulage scenarios available and what each one is.",
     "parameters": {"type": "object", "properties": {}}},
    {"type": "function", "name": "scenario_result",
     "description": "Year result for one scenario: sales targets, predicted tonnes, % of target for SAP, LIM-TOS, LIM-LD and the total; the flat fleet level and trucks parked.",
     "parameters": {"type": "object",
                    "properties": {"scenario": {"type": "string", "description": "4.1, 4.2 or 4.2.1"}},
                    "required": ["scenario"]}},
    {"type": "function", "name": "month_detail",
     "description": "One month of a scenario: fleet DT, target and predicted tonnes for the month, and the biggest routes by trucks.",
     "parameters": {"type": "object",
                    "properties": {"scenario": {"type": "string"},
                                   "month": {"type": "string", "description": "September, October, November or December"}},
                    "required": ["scenario", "month"]}},
    {"type": "function", "name": "route_rate",
     "description": "Trips per truck per day and tonnes per truck per day the congestion model predicts for a route at a fleet size, with the cycle breakdown.",
     "parameters": {"type": "object",
                    "properties": {"route": {"type": "string", "description": "e.g. TF>POS 12, KR>FENI KM15, BLB>HUAFEI"},
                                   "contractor": {"type": "string", "description": "RIM or SMA"},
                                   "trucks": {"type": "number"}},
                    "required": ["route"]}},
    {"type": "function", "name": "weighbridges_for_route",
     "description": "Which weighbridges a route's trucks may use under the owner's matrix.",
     "parameters": {"type": "object",
                    "properties": {"route": {"type": "string"}},
                    "required": ["route"]}},
]


@bp.route("/voice")
def voice_page():
    return render_template("voice.html")


@bp.route("/api/voice/session", methods=["POST"])
def api_voice_session():
    """Mint an ephemeral client secret for the browser. The owner's token
    stays here."""
    try:
        tok, src = xai_bearer()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 503
    req = urllib.request.Request(
        _XAI + "/realtime/client_secrets",
        data=json.dumps({"expires_after": {"seconds": 600}}).encode(),
        headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        return jsonify({"ok": False, "error": "xai %s: %s" % (e.code, body),
                        "auth_source": src}), 502
    body = request.get_json(silent=True) or {}
    voice = str(body.get("voice") or "rigel")
    if not re.fullmatch(r"[a-z0-9]{2,16}", voice):
        voice = "rigel"
    return jsonify({
        "ok": True, "auth_source": src,
        "client_secret": d.get("value"), "expires_at": d.get("expires_at"),
        "url": "wss://api.x.ai/v1/realtime?model=grok-voice-latest",
        "session": {
            "voice": voice,
            "instructions": _INSTRUCTIONS,
            "turn_detection": {"type": "server_vad", "silence_duration_ms": 700},
            "tools": _TOOLS,
            "audio": {
                "input": {"format": {"type": "audio/pcm", "rate": 24000},
                          "transcription": {"language_hint": "en", "keyterms": _KEYTERMS}},
                "output": {"format": {"type": "audio/pcm", "rate": 24000}},
            },
            "replace": {"FeNi": "Fenny", "LIM": "lim", "SAP": "sap", "TOS": "toss",
                        "LD": "L D", "DT": "D T", "BSE": "B S E", "POS": "poss",
                        "IWIP": "eye whip", "RIM": "rim", "SMA": "S M A"},
        },
    })


# ── tools ────────────────────────────────────────────────────────────────────

def _get(path):
    rv = current_app.test_client().get(path)
    return rv.get_json() if rv.status_code == 200 else None


def _scen(name):
    s = str(name or "").strip().lower().replace("scenario", "").strip()
    s = _ALIASES.get(s, s)
    return _SCEN.get(s)


def _mt(t):
    try:
        t = float(t)
    except (TypeError, ValueError):
        return None
    return round(t / 1e6, 2)


def tool_list_scenarios(_a):
    ids = _get("/api/scenarios") or {}
    out = []
    for k, v in _SCEN.items():
        if k.startswith("4."):
            out.append({"scenario": k, "day_slot": v["day"]})
    return {"scenarios": out,
            "note": ("4.1: manager mine plan, all LD to POS 12, total 19.0 Mt. "
                     "4.2: client plant split 2/3 Huafei 1/3 BSE, LD 8.0 Mt, LIM to POS 6 from November. "
                     "4.2.1: 4.2 but 65% of Nov-Dec POS LD returns to POS 12 so the year lands 100% with the same fleet.")}


def tool_scenario_result(a):
    sc = _scen(a.get("scenario"))
    if not sc:
        return {"error": "unknown scenario; say 4.1, 4.2 or 4.2.1"}
    yb = _get("/api/monthly/year-board?year=2026&day=%d" % sc["day"])
    if not yb:
        return {"error": "year board unavailable"}
    ay = yb.get("alloc_year") or {}
    mats = ay.get("materials") or {}
    la = yb.get("ld_adjust") or {}
    res = {"scenario": sc["label"],
           "total": {"sales_target_mt": _mt(ay.get("sales_target")),
                     "predicted_mt": _mt(ay.get("new_pred")),
                     "percent_of_target": ay.get("cov_sales")}}
    for k, lab in (("sap", "SAP"), ("tos", "LIM-TOS"), ("ld", "LIM-LD")):
        m = mats.get(k) or {}
        res[lab] = {"target_mt": _mt(m.get("sales_target")),
                    "predicted_mt": _mt(m.get("pred_after")),
                    "percent_of_target": m.get("cov_sales")}
    if la.get("flat_level"):
        res["fleet"] = {"flat_level_dt": la.get("flat_level"),
                        "truck_months_parked": la.get("park"),
                        "ld_percent_before_parking": la.get("cov_before"),
                        "ld_percent_after_parking": la.get("cov_after")}
    else:
        res["fleet"] = {"note": "LIM-LD is under its line; nothing is parked",
                        "ld_percent": la.get("cov_before")}
    return res


_MONTHS = {"september": "09", "sep": "09", "october": "10", "oct": "10",
           "november": "11", "nov": "11", "december": "12", "dec": "12"}


def tool_month_detail(a):
    sc = _scen(a.get("scenario"))
    mm = _MONTHS.get(str(a.get("month") or "").strip().lower())
    if not sc or not mm:
        return {"error": "need a scenario (4.1/4.2/4.2.1) and a month (September to December)"}
    yb = _get("/api/monthly/year-board?year=2026&day=%d" % sc["day"])
    card = next((c for c in (yb or {}).get("cards", []) if str(c.get("month")) == "2026-" + mm), None)
    if not card:
        return {"error": "no saved plan for that month"}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "saved_plans",
                        "2026-%s-%02d.json" % (mm, sc["day"]))
    routes = []
    try:
        with open(path, encoding="utf-8") as f:
            plan = json.load(f)
        for k, v in (plan.get("paths") or {}).items():
            if not isinstance(v, dict) or k.startswith(("TENANT", "IWIP")):
                continue
            mat = v.get("material") or ""
            if mat == "LIM":
                mat = "LIM-" + (v.get("otype") or "TOS")
            routes.append({"route": v.get("key"), "contractor": v.get("contractor"),
                           "material": mat, "trucks": v.get("dt"),
                           "target_t_per_day": v.get("targetWmt")})
        routes.sort(key=lambda r: -(r["trucks"] or 0))
    except Exception:
        pass
    # Same clock as the Year sheet's month table: the ALLOCATED plan
    # (card.alloc.new_pred_month vs the sales-rescaled target_month). The
    # card's top-level pred_month is the pre-allocation holding plan.
    al = card.get("alloc") or {}
    return {"scenario": sc["label"], "month": card.get("name") or mm,
            "fleet_dt": card.get("dt"),
            "target_mt": _mt(al.get("target_month") or card.get("target_month")),
            "predicted_mt": _mt(al.get("new_pred_month") or card.get("pred_month")),
            "percent_of_target": al.get("cov_new_pred"),
            "top_routes": routes[:6]}


def _canon_route(s):
    s = str(s or "").upper().replace("→", ">").replace(" TO ", ">").replace("-", ">")
    s = re.sub(r"\s*>\s*", ">", s).strip()
    s = s.replace("TOFU", "TF").replace("KRENE", "KR").replace("POS12", "POS 12") \
         .replace("POS6", "POS 6").replace("FENI KM 15", "FENI KM15").replace("FENI KM 0", "FENI KM0") \
         .replace("FENI 15", "FENI KM15").replace("FENI 0", "FENI KM0").replace("KM15", "FENI KM15") \
         .replace("FENI FENI", "FENI")
    return s


def tool_route_rate(a):
    route = _canon_route(a.get("route"))
    c = str(a.get("contractor") or "RIM").upper()
    n = int(a.get("trucks") or 150)
    d = _get("/api/congestion_model?route=%s&n_trucks=%d&contractor=%s"
             % (urllib.parse.quote(route), n, c))
    if not d or not d.get("ok", True) or d.get("trips_per_DT_per_day") is None:
        return {"error": "no model for route %s" % route}
    comp = d.get("components") or {}
    trips = d.get("trips_per_DT_per_day")
    tot = d.get("total_tonnes_day")
    return {"route": route, "contractor": c, "trucks": n,
            "trips_per_truck_per_day": round(trips, 2),
            "tonnes_per_truck_per_day": round(tot / n) if tot and n else None,
            "route_tonnes_per_day": round(tot) if tot else None,
            "cycle_minutes": round(d.get("cycle_time_minutes") or 0),
            "driving_minutes": round(comp.get("t_free_road") or 0),
            "overhead_per_trip_minutes": round(comp.get("overhead_per_trip_minutes") or 0),
            "queue_wait_minutes": round(comp.get("queue_wait_minutes") or 0, 1),
            "congestion_status": d.get("congestion_status"),
            "calibrated": d.get("calibrated")}


def tool_weighbridges_for_route(a):
    route = _canon_route(a.get("route"))
    b = _get("/api/plan/wb-allocation-basis") or {}
    names = (b.get("matrix") or {}).get(route)
    if not names:
        hist = (b.get("history_pairs") or {}).get(route)
        if hist:
            return {"route": route, "bridges": ["T%d" % n for n in hist],
                    "basis": "measured history (no matrix row)"}
        return {"error": "no weighbridge rule for %s" % route}
    return {"route": route, "bridges": [n.replace("WB_IWIP_", "").replace("WB_RIM_", "RIM ") for n in names],
            "basis": "owner matrix"}


_TOOL_FN = {"list_scenarios": tool_list_scenarios,
            "scenario_result": tool_scenario_result,
            "month_detail": tool_month_detail,
            "route_rate": tool_route_rate,
            "weighbridges_for_route": tool_weighbridges_for_route}


@bp.route("/api/voice/tool", methods=["POST"])
def api_voice_tool():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name") or "")
    args = body.get("arguments") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {}
    fn = _TOOL_FN.get(name)
    if not fn:
        return jsonify({"ok": False, "error": "unknown tool %s" % name}), 404
    try:
        return jsonify({"ok": True, "result": fn(args)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


import urllib.parse  # noqa: E402  (used by tool_route_rate)
