#!/usr/bin/env bash
# Phase 2 prediction pipeline — PASS/FAIL verification harness.
#
#   bash scripts/verify_phase2.sh
#
# Prints one line per check and a final SCORE n/24. Exit 0 only at 24/24.
# Written before the implementation so the first run is an honest baseline.
cd "$(dirname "$0")/.." || exit 2
PY=.venv/bin/python
BASE=http://127.0.0.1:5055
PASS=0; FAIL=0
# TOTAL is derived, not hardcoded: a literal drifts the moment a check is added
# and turns the score into decoration (it read 33 while 39 checks ran). The
# Phase 3.5 block is conditional, so count what actually executed.
TOTAL=0
ok(){ printf '  \033[32mPASS\033[0m %s\n' "$1"; PASS=$((PASS+1)); }
no(){ printf '  \033[31mFAIL\033[0m %s — %s\n' "$1" "$2"; FAIL=$((FAIL+1)); }
chk(){ TOTAL=$((TOTAL+1)); if [ "$1" = "0" ]; then ok "$2"; else no "$2" "$3"; fi; }

echo "── A · data extraction ───────────────────────────────────────────"
[ -f data/training_data.csv ]; chk $? "A1  training_data.csv exists" "missing"
$PY - <<'EOF' >/dev/null 2>&1
import csv,sys
need={'contractor','source','destination','distance_km','payload_t','rainfall_mm','shift',
      'day_of_week','weighbridges_open','trucks_dt','trips_per_dt_per_shift','wmt_per_shift','date'}
h=set(next(csv.reader(open('data/training_data.csv'))))
sys.exit(0 if need<=h else 1)
EOF
chk $? "A2  all 13 required columns present" "schema mismatch"
$PY -c "import csv;r=sum(1 for _ in open('data/training_data.csv'))-1;exit(0 if r>500 else 1)" 2>/dev/null
chk $? "A3  >500 training rows" "too few rows"
$PY - <<'EOF' >/dev/null 2>&1
import json,sys
m=json.load(open('data/training_metadata.json'))
sys.exit(0 if {'extracted_at','row_count','date_range','features'}<=set(m) else 1)
EOF
chk $? "A4  training_metadata.json complete" "missing keys"
$PY - <<'EOF' >/dev/null 2>&1
import csv,sys
rows=[r for r in csv.DictReader(open('data/training_data.csv'))
      if r['source']=='TF' and r['destination'].startswith('FENI KM0')]
sys.exit(0 if rows and abs(float(rows[0]['distance_km'])-67.8)<0.01 else 1)
EOF
chk $? "A5  TF→FENI KM0 distance = 67.8 km" "distance lookup wrong"

echo "── B · feature store ─────────────────────────────────────────────"
$PY -c "import joblib;joblib.load('data/encoders.pkl')" >/dev/null 2>&1
chk $? "B6  encoders.pkl loads" "not saved"
$PY -c "import joblib;joblib.load('data/scaler.pkl')" >/dev/null 2>&1
chk $? "B7  scaler.pkl loads" "not saved"
$PY - <<'EOF' >/dev/null 2>&1
import json,sys,prediction_pipeline as pp
X=pp.transform_one(dict(contractor='RIM',source='TF',destination='FENI KM0',distance_km=67.8,
    payload_t=48.6,rainfall_mm=0.0,shift='day',day_of_week=2,weighbridges_open=8,trucks_dt=19))
n=len(json.load(open('data/model_metadata.json'))['features'])
sys.exit(0 if X.shape[1]==n else 1)
EOF
chk $? "B8  transform width matches trained features" "width mismatch"

echo "── C · training ──────────────────────────────────────────────────"
OUT=$($PY train_model.py 2>&1)
echo "$OUT" | grep -qiE 'ols.*r2.*mae.*rmse|r2.*mae.*rmse.*ols'; chk $? "C9   OLS metrics reported" "no OLS line"
echo "$OUT" | grep -qiE 'random_forest.*r2.*mae.*rmse|forest'; chk $? "C10  RandomForest metrics reported" "no RF line"
[ -f data/model.pkl ]; chk $? "C11  model.pkl written" "missing"
$PY -c "
import json;m=json.load(open('data/model_metadata.json'))
exit(0 if m.get('model_type') in ('ols','random_forest') else 1)" 2>/dev/null
chk $? "C12  model_metadata.model_type valid" "bad metadata"
A=$($PY -c "import json;m=json.load(open('data/model_metadata.json'));print(round(m['r2'],6),round(m['mae'],6))" 2>/dev/null)
$PY train_model.py >/dev/null 2>&1
B=$($PY -c "import json;m=json.load(open('data/model_metadata.json'));print(round(m['r2'],6),round(m['mae'],6))" 2>/dev/null)
[ -n "$A" ] && [ "$A" = "$B" ]; chk $? "C13  retraining is idempotent" "metrics drifted: '$A' vs '$B'"

# Wait for the model to be SERVING before measuring it. F23 fires /api/retrain,
# and a retrain still reloading — from this run or from a previous one minutes
# earlier — makes /api/predict answer slowly and can serve a transitional
# model. That is what failed D16 (p95) and D18b (canonicalisation) repeatedly on
# 2026-08-23/24 while both passed every direct probe against an idle server
# (p95 2.0 ms against a 100 ms gate — a 50x margin). Measuring a warming model
# and calling it a latency or naming defect is how a suite teaches people to
# ignore it. Poll until answers are fast and stable, then measure.
$PY - <<'EOF' >/dev/null 2>&1
import json,sys,time,urllib.request
req=json.dumps({"contractor":"RIM","source":"TF","destination":"FENI KM0","trucks":19,
 "shift_hours":12,"rainfall":0,"shift":"day","weighbridges_open":8,"mode":"dt_to_wmt"}).encode()
def one():
    t=time.perf_counter()
    urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:5055/api/predict",req,
        {'Content-Type':'application/json'}),timeout=120).read()
    return (time.perf_counter()-t)*1000
deadline=time.time()+300
while time.time()<deadline:
    try:
        if max(one() for _ in range(5))<50: sys.exit(0)
    except Exception: pass
    time.sleep(5)
sys.exit(0)   # never block the suite; the gates below report the truth
EOF

echo "── D · prediction API ────────────────────────────────────────────"
REQ='{"contractor":"RIM","source":"TF","destination":"FENI KM0","trucks":19,"shift_hours":12,"rainfall":0,"shift":"day","weighbridges_open":8,"mode":"dt_to_wmt"}'
curl -s -X POST -H 'Content-Type: application/json' -d "$REQ" $BASE/api/predict > /tmp/p2_pred.json 2>/dev/null
$PY - <<'EOF' >/dev/null 2>&1
import json,sys
d=json.load(open('/tmp/p2_pred.json')); p=d.get('prediction',{})
sys.exit(0 if {'trips_per_dt','total_trips','payload_per_trip','total_wmt','confidence'}<=set(p)
         and {'model_used','model_trained_at','model_r2','fallback'}<=set(d) else 1)
EOF
chk $? "D14  dt_to_wmt response shape correct" "shape mismatch"
curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"contractor":"RIM","source":"TF","destination":"FENI KM0","target_wmt":5000,"shift_hours":12,"rainfall":0,"shift":"day","weighbridges_open":8,"mode":"wmt_to_dt"}' \
  $BASE/api/predict > /tmp/p2_rev.json 2>/dev/null
$PY - <<'EOF' >/dev/null 2>&1
import json,sys
d=json.load(open('/tmp/p2_rev.json'));p=d.get('prediction',{})
n=p.get('trucks_needed')
sys.exit(0 if isinstance(n,int) and n>0 and n*p['trips_per_dt']*p['payload_per_trip']>=5000*0.999 else 1)
EOF
chk $? "D15  wmt_to_dt returns ceil'd integer fleet" "reverse mode wrong"
$PY - <<'EOF' >/dev/null 2>&1
import json,sys,time,urllib.request
req=json.dumps({"contractor":"RIM","source":"TF","destination":"FENI KM0","trucks":19,
 "shift_hours":12,"rainfall":0,"shift":"day","weighbridges_open":8,"mode":"dt_to_wmt"}).encode()
ts=[]
for _ in range(20):
    t=time.perf_counter()
    urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:5055/api/predict",req,
        {'Content-Type':'application/json'}),timeout=5).read()
    ts.append((time.perf_counter()-t)*1000)
ts.sort(); p95=ts[18]
print('p95=%.1fms'%p95)
sys.exit(0 if p95<100 else 1)
EOF
chk $? "D16  p95 latency < 100 ms (20 calls)" "too slow"
$PY - <<'EOF' >/dev/null 2>&1
import json,sys,urllib.request
req=json.dumps({"contractor":"RIM","source":"TF","destination":"FENI KM0","trucks":19,
 "shift_hours":12,"rainfall":0,"shift":"day","weighbridges_open":8,"mode":"dt_to_wmt"}).encode()
g=lambda:json.loads(urllib.request.urlopen(urllib.request.Request(
    "http://127.0.0.1:5055/api/predict",req,{'Content-Type':'application/json'})).read()).get('model_instance')
a,b=g(),g()
sys.exit(0 if a and a==b else 1)
EOF
chk $? "D17  model loaded once (stable instance id)" "reloading per request"
CODE=$(curl -s -o /tmp/p2_fb.json -w '%{http_code}' "$BASE/api/predict?contractor=RIM&source=TF&destination=NOWHERE&trucks=19&mode=dt_to_wmt")
[ "$CODE" = "200" ]; chk $? "D18  unknown route still returns 200" "http $CODE"
$PY - <<'EOF' >/dev/null 2>&1
import json,sys,time,urllib.parse,urllib.request
base='http://127.0.0.1:5055/api/predict?contractor=RIM&shift=day&trucks=30&'
def get(src,dst):
    # This gate asserts CANONICALISATION, not latency (D16 owns latency). It
    # runs right after F23's retrain, and a reloading model answers slower than
    # the old timeout=5 allowed — so it flaked three times on 2026-08-23/24 and
    # passed every direct probe. A flaky gate is worse than no gate: it trains
    # people to wave failures through. Generous timeout + bounded retry.
    q=urllib.parse.urlencode({'source':src,'destination':dst})
    last=None
    for attempt in range(3):
        try:
            return json.load(urllib.request.urlopen(base+q,timeout=60))
        except Exception as exc:      # noqa: BLE001 — retry, then re-raise
            last=exc
            time.sleep(2*(attempt+1))
    raise last
def same(a,b):
    return (a.get('canonical_route')==b.get('canonical_route') and
            a.get('prediction',{}).get('trips_per_dt')==b.get('prediction',{}).get('trips_per_dt'))
tf, tofu = get('TF','HUAFEI'), get('TOFU','HUAFEI')
p14, p14x = get('BLB','POS 14'), get('BLB','POS14')
ok=(same(tf,tofu) and same(p14,p14x) and
    tf.get('inputs',{}).get('distance_km')==63.7 and
    p14.get('inputs',{}).get('distance_km')==6.7 and
    tf.get('model_match_level')!='global' and p14.get('model_match_level')!='global')
sys.exit(0 if ok else 1)
EOF
chk $? "D18b route aliases and focus distances are canonical" "TF/TOFU or POS14 split/fallback"

echo "── E/F · integration & regressions ───────────────────────────────"
grep -q "api/predict" static/js/plan.js 2>/dev/null
chk $? "E19  Plan tab calls /api/predict" "not wired"
grep -qE "model_used|est-model" static/js/plan.js 2>/dev/null
chk $? "E20  Plan tab renders model attribution" "no attribution"
grep -qE "catch|fallback" static/js/plan.js 2>/dev/null
chk $? "E21  Plan tab keeps local fallback" "no fallback path"
BAD=0
for u in /simulator /api/simulator/capability /api/simulator/path-response /api/simulator/trucks \
         /api/simulator/constraints /api/weighbridge-summary /api/simulator/weighbridge \
         /api/simulator/congestion-model /api/simulator/weighbridge-positions \
         /api/simulator/shift-context /static/js/plan.js; do
  [ "$(curl -s -o /dev/null -w '%{http_code}' $BASE$u)" = "200" ] || BAD=$((BAD+1))
done
[ "$BAD" = "0" ]; chk $? "F22  all 11 pre-existing endpoints 200" "$BAD endpoint(s) broken"
# ONE retrain, not two. There was a redundant warm-up POST here, harmless while
# a retrain was quick; once retrain also rebuilt the cycle model (~5 min against
# the live DB) it doubled to >10 min and looked like a hang.
#
# cycle=0 because this check asks "does the endpoint work", not "rebuild every
# model". The cycle model is verified separately by I34-I40 against artifacts
# that cycle_model.py writes. --max-time stops a genuinely stuck endpoint from
# stalling the harness instead of failing it.
[ "$(curl -s -o /dev/null --max-time 900 -w '%{http_code}' -X POST "$BASE/api/retrain?cycle=0")" = "200" ]
chk $? "F23  /api/retrain returns 200" "retrain endpoint down or >900s"
# G24: BOTH remotes must match local HEAD. The hold on origin (rdinkelmann)
# was lifted by the owner on 2026-08-07 ("push everything to git, me and
# Rudolf"), so the gate is re-widened to its original two-remote form. The
# 2026-07-30..2026-08-07 narrowing (mirror-only assert, origin reported) is in
# this file's git history if the hold ever returns.
LOCAL=$(git rev-parse HEAD 2>/dev/null)
M=$(git ls-remote --heads mirror main 2>/dev/null | cut -f1)
O=$(git ls-remote --heads origin main 2>/dev/null | cut -f1)
[ -n "$LOCAL" ] && [ "$LOCAL" = "$M" ] && [ "$LOCAL" = "$O" ]
chk $? "G24  mirror AND origin match local HEAD" "mirror=${M:0:7} origin=${O:0:7} local=${LOCAL:0:7}"

echo "── H · Phase 3 · OLS, validation, leakage ────────────────────────"
[ -f data/model_ols.pkl ]; chk $? "H25  model_ols.pkl written" "missing"
[ -f data/validation_results.json ]; chk $? "H26  validation_results.json written" "missing"
[ -f data/model_comparison.json ]; chk $? "H27  model_comparison.json written" "missing"
[ -f data/feature_significance.json ]; chk $? "H28  feature_significance.json written" "missing"
$PY - <<'EOF' >/dev/null 2>&1
import json, sys
v = json.load(open('data/validation_results.json'))
folds = (v.get('ols') or {}).get('folds', [])
sys.exit(0 if len(folds) >= 4 else 1)
EOF
chk $? "H29  rolling-origin CV has >= 4 folds" "too few folds"
$PY - <<'EOF' >/dev/null 2>&1
import json, sys
c = json.load(open('data/model_comparison.json')).get('per_model', {})
need = {'ols', 'random_forest', 'group_mean_baseline'}
sys.exit(0 if need <= set(c) else 1)
EOF
chk $? "H30  comparison covers OLS + RF + baseline" "missing a model"
# Hard fail: a VIF above 10 means coefficients are not separately identified,
# so the p-values and signs cannot be reported as findings.
#
# Scoped to the INTERPRETABLE features. A high-cardinality one-hot (74 routes,
# 8 contractors) always shows VIF > 10 on its larger levels because the dummies
# are mutually exclusive by construction — TF>POS 12 sits at 12.7 precisely
# because it is the biggest route in the data, 3,926 of 52,818 rows. Those
# coefficients are reported as counts and never interpreted individually, which
# is exactly the thing this gate exists to protect. Physical and operational
# features are still held to VIF < 10 with no exemption.
$PY - <<'EOF' >/dev/null 2>&1
import json, sys
s = json.load(open('data/feature_significance.json'))
interp = [f for f in (s.get('vif_over_10') or [])
          if not f.startswith(('route_', 'contractor_', 'source_',
                               'destination_', 'shift_', 'rt_'))]
sys.exit(1 if interp else 0)
EOF
chk $? "H31  no interpretable feature has VIF > 10" "multicollinearity"
# Hard fail: these columns are exact algebraic restatements of the target
# (wmt = target*payload*trucks, trips = target*trucks), so their presence would
# make the model score ~1.0 while being unable to predict anything.
$PY - <<'EOF' >/dev/null 2>&1
import json, sys
bad = {'trips', 'wmt_per_shift', 'cycle_time_min', 'trips_per_dt_per_shift'}
feats = set(json.load(open('data/feature_significance.json')).get('coefficients', {}))
sys.exit(1 if (bad & feats) else 0)
EOF
chk $? "H32  no target-leakage feature in the OLS" "LEAKAGE"
$PY - <<'EOF' >/dev/null 2>&1
import json, sys
m = json.load(open('data/model_metadata.json'))
sys.exit(0 if m.get('selected_model') and m.get('ols_training_timestamp') else 1)
EOF
chk $? "H33  metadata has selected_model + ols timestamp" "missing fields"

# ── Phase 3.5: cycle-time model ────────────────────────────────────────────
# These skip cleanly when no cycle model has been trained (no VPN, fresh clone)
# so the public demo still scores full marks without the database.
if [ -f data/cycle_model_report.json ]; then
$PY - <<'EOF' >/dev/null 2>&1
import json, sys
r = json.load(open('data/cycle_model_report.json'))
sys.exit(0 if r.get('rows', 0) >= 2000 and r.get('months_ok', True) else 1)
EOF
chk $? "I34  cycle dataset >= 2,000 rows" "too little data to model"
# Hard fail: load+haul+dump IS the target. Any of them as a feature would score
# ~1.0 while being unknowable when planning a future shift.
$PY - <<'EOF' >/dev/null 2>&1
import json, sys
bad = {'load_min', 'haul_min', 'dump_min', 'return_min', 'cycle_time_min',
       'avg_cycle_time_min', 'wmt_per_shift', 'trips', 'trips_per_dt_per_shift'}
feats = set(json.load(open('data/cycle_model_report.json')).get('coefficients', {}))
sys.exit(1 if (bad & feats) else 0)
EOF
chk $? "I35  no cycle-component leakage in the cycle OLS" "LEAKAGE"
$PY - <<'EOF' >/dev/null 2>&1
import json, sys
v = (json.load(open('data/cycle_model_report.json')).get('in_sample') or {}).get('max_vif_interpretable')
sys.exit(0 if (v is not None and v < 10) else 1)
EOF
chk $? "I36  cycle model interpretable VIF < 10" "multicollinearity"
$PY - <<'EOF' >/dev/null 2>&1
import json, sys
r = json.load(open('data/cycle_model_report.json'))
sys.exit(0 if len((r.get('sign_checks') or {}).get('violations', [])) == 0 else 1)
EOF
chk $? "I37  no unexplained coefficient sign violations" "physics violated"
# The served scale must match the fitted scale, or the API exponentiates raw
# minutes and returns e^68. This is the bug that shipped once; it stays gated.
$PY - <<'EOF' >/dev/null 2>&1
import pickle, sys
b = pickle.load(open('data/cycle_model.pkl', 'rb'))
c = float(b['params']['const'])
ok = (2.0 < c < 8.0) if b.get('param_scale') == 'log_minutes' else (10 < c < 600)
sys.exit(0 if ok else 1)
EOF
chk $? "I38  served param scale matches recorded scale" "would serve exp(raw minutes)"
$PY - <<'EOF' >/dev/null 2>&1
import sys
sys.path.insert(0, '.')
import cycle_serving as cs
day = cs.predict_cycle_time('TF', 'FENI KM0', 'day', trucks=30, rainfall_mm=0)
night = cs.predict_cycle_time('TF', 'FENI KM0', 'night', trucks=30, rainfall_mm=0)
wet = cs.predict_cycle_time('TF', 'FENI KM0', 'day', trucks=30, rainfall_mm=40)
unknown = cs.predict_cycle_time('NOWHERE', 'NOPLACE', 'day', trucks=30)
ok = (day and night and wet and unknown
      and 5 < day['cycle_time_min'] < 900                 # physically sane
      and wet['cycle_time_min'] > day['cycle_time_min']   # rain slows trucks
      and unknown['basis'] in ('route_mean', 'global_mean'))
sys.exit(0 if ok else 1)
EOF
chk $? "I39  cycle serving is sane and falls back" "serving misbehaves"
# Cycle time only becomes tonnage through a utilisation factor. A guessed 0.85
# made the two models report 5,046 t and 10,667 t for the SAME fleet, so this
# gates that the factor is FITTED and still reconciles them.
$PY - <<'EOF' >/dev/null 2>&1
import json, sys
u = (json.load(open('data/cycle_model_report.json')).get('utilisation') or {})
v, err = u.get('utilisation'), u.get('reconcile_median_abs_pct')
sys.exit(0 if (v and 0.1 < v < 0.9 and u.get('routes', 0) >= 5
               and err is not None and err < 35) else 1)
EOF
chk $? "I40  utilisation is fitted and reconciles both models" "cycle/weighbridge tonnage disagree"
fi
# Unit tests for the maths BETWEEN the model and the user. That layer is where
# this phase's real bugs lived (a scale mismatch that would have served
# exp(67.9) minutes; a guessed utilisation that reported two tonnages for one
# fleet) and neither showed up in a model metric. Runs with or without a trained
# model: the prediction tests skip themselves, the arithmetic tests do not.
$PY tests/test_cycle.py >/dev/null 2>&1
chk $? "I41  cycle unit tests pass" "see: python tests/test_cycle.py"
# The trip extract is KEPT (it is the simulator's data layer), so its integrity
# guard is kept too. A truncated or partially regenerated extract silently
# invalidates every figure derived from it.
if [ -f data/trip_metadata.json ] && [ -f data/trip_level_base.csv ]; then
$PY - <<'EOF' >/dev/null 2>&1
import json, sys
m = json.load(open('data/trip_metadata.json'))
with open('data/trip_level_base.csv', newline='') as fh:
    n = sum(1 for _ in fh) - 1
ok = (m.get('rows') == n and n > 100000
      and 0 < (m.get('variance_decomposition') or {}).get(
          'aggregate_model_r2_ceiling', 0) < 1)
sys.exit(0 if ok else 1)
EOF
chk $? "I42  trip metadata matches the extract" "row count or ceiling drifted"
fi


# ---------------------------------------------------------------------------
# J43-J52: the production-simulator suites.
#
# These existed as standalone files and the harness did not run them, so
# verify_phase2.sh reported 42/42 while eight suites - including the gate that
# catches a 5x production overprediction - were never exercised by CI. A gate
# nobody runs is decoration, so they are wired in here.
#
# Each is skipped rather than failed when its artifacts are absent, because the
# GPS ones need data/day_x_*.csv which only exists after a deep-dive extraction,
# and a missing optional artifact must not fail the whole harness.
# ---------------------------------------------------------------------------
if [ -f data/route_lookup.csv ]; then
$PY test_trips_per_shift.py >/dev/null 2>&1
chk $? "J43  trips/shift reproduces observed trips" "see: python test_trips_per_shift.py"

$PY test_trips_mutation.py >/dev/null 2>&1
chk $? "J44  trips gate catches the weigh-to-weigh bug" "mutation test failed to discriminate"

$PY test_plan_simulator.py >/dev/null 2>&1
chk $? "J45  plan simulator invariants hold" "see: python test_plan_simulator.py"
fi

if [ -f data/trip_features.csv ]; then
$PY test_holdout_tonnage.py >/dev/null 2>&1
chk $? "J46  cycle fix beats the old formula out of sample" "held-out tonnage regressed"

$PY test_holdout_robustness.py >/dev/null 2>&1
chk $? "J47  holds across 4 splits + unseen-route fallback" "see: python test_holdout_robustness.py"

$PY test_congestion_audit_mutation.py >/dev/null 2>&1
chk $? "J48  congestion sign audit discriminates" "mutation test failed"
fi

if [ -f data/route_lookup.csv ]; then
$PY test_retrain_preserves_fix.py >/dev/null 2>&1
chk $? "J49  a retrain preserves the cycle fix" "see: python test_retrain_preserves_fix.py"
fi

# Needs the availability extract, which requires the DB. Skipped in a clean checkout.
if [ -f data/availability_per_truck.csv ] && [ -f data/route_lookup.csv ]; then
$PY test_availability_usage.py >/dev/null 2>&1
chk $? "J52  availability sizes the fleet and never scales tonnage" "see: python test_availability_usage.py"
fi

# Needs the congestion-segment extract, which requires the DB.
if [ -f data/congestion_seg_hourly.csv ] && [ -f reports/speed_density_fit.json ]; then
$PY test_speed_density.py >/dev/null 2>&1
chk $? "J53  congestion measured, negligible, and kept out of the model" "see: python test_speed_density.py"
fi

# Road crowding by hour. Runs on plan_corridor_hours._FIXTURE, so no DB/VPN.
# It was NOT wired to any gate until 2026-08-23 — the hourly DES shipped three
# times while its only test ran by hand. Asserts the invariances that were
# actually broken: row ORDER must not change the answer (a peak moved 43% on a
# swap), v/c must not move with the display bin (2.5x on identical traffic),
# executed trips must track the priced cadence (-41%..+35%), and a fleet above
# the sample size must be WEIGHTED, not silently truncated.
$PY test_plan_shared_flow.py >/dev/null 2>&1
chk $? "J75  road crowding: order- and bin-invariant, trips match the cadence" "see: python test_plan_shared_flow.py"

# The frozen reference curves are SERVED (tagged servedFrom:"reference") on any
# machine without a live calibration — a fresh clone, or the deployed Mac. They
# rotted silently once: TF>HUAFEI shipped up to 40.7% low for two days because
# "regenerate after recalibration" lived only in a docstring. --check compares
# the artifact's recorded provenance (calibration timestamp, network constants
# AND congestion/ model-code digest) against the current build, and prints what
# moved. Needs no DB or VPN.
$PY scripts/export_saturation_curves.py --check >/dev/null 2>&1
chk $? "J76  frozen saturation curves match the current model" "stale: python scripts/export_saturation_curves.py --check"

# Other tenants (owner register 2026-08-24): 1,340 DT that take our road and
# give us no tonnage. The register is the owner's; what this gate pins is the
# WIRING, and each assertion below is one that broke on the way in:
# direction (the empty-carriageway leg must cost no loaded-lane capacity),
# UNIT (tenants arrive as flow, not trucks, or a 5-trip/day fleet is priced
# as if it turned 2), MONOTONICITY (adding traffic can never raise trips/DT —
# the first Excel column read 6.6% HIGH), and the off-mainline BLB spur, which
# must be blank rather than repeating its clear-road rate under a "with other
# tenants" heading. Mutation-tested three ways before being wired here.
# Needs no DB or VPN.
$PY test_tenant_traffic.py >/dev/null 2>&1
chk $? "J77  other tenants take road, never tonnage" "see: python test_tenant_traffic.py"

# The workbook's road grid and the Plan tab's road grid must be the SAME
# numbers. Owner, 2026-08-25: "my excel should show exactly what is written in
# this table." They already share plan_shared_flow, but through two different
# callers, and a caller can diverge six ways that all move the cells (plans,
# shift_hours, rain_mm, start_hour, whole_day, tenants). This compares them
# CELL BY CELL over every saved scenario, so moving one side without the other
# fails here instead of in a screenshot. Needs the server on :5055.
$PY test_corridor_parity.py >/dev/null 2>&1
chk $? "J79  Excel road grid == app road grid" "see: python test_corridor_parity.py"

# HUAFEI is a junction at km 5.5 with a ~0.9 km branch, NOT a coastal dump at
# km 0 (owner, 2026-08-25). physics.py had been carrying the contradiction in
# ONE file — NODE_KM said 0.0 while MEASURED_HAUL_KM said TF>HUAFEI = 63.7 km,
# which is impossible from TF at 67.8 — and the two halves fed pricing and
# placement respectively, so it priced right and drew 5.5 km wrong. The gate
# pins the constant in all three NODE_KM copies, the branch, the S4 occupancy
# consequence, and re-derives the junction from the committed survey. Mutation
# -tested three ways incl. a full revert to the original bug. No DB needed.
$PY test_huafei_geometry.py >/dev/null 2>&1
chk $? "J80  HUAFEI is a junction at km 5.5, not the coast" "see: python test_huafei_geometry.py"

# J81-J86 — the 2026-08-25 three-agent QA audit fixes, one gate script:
# J81 flow readout divides by OFFICIAL geometry (600/600/600/400), never the
#     ~54 tph Jul GPS demonstrated peak ("most we ever did" != "most we can");
# J82 tenant DT never reach the readout's production math, their road flow IS
#     charged at their own tempo; J83 (browser) frozen loads open with the
#     alloc panel, no stale required-DT board, and REBUILT pricing state
#     (totals round-trip <0.5%); J84 priority board sums ONE fleet basis and
#     an unknown achievable renders as a dash, never 0; J85 Excel TOTAL DT is
#     our fleet with IWIP named beside it; J86 every offered scenario exports
#     (S4 has no file by design) with no phantom scenarios from legacy saves.
# Mutation-tested 7 ways 2026-08-25 (incl. two gate weaknesses the mutants
# exposed and fixed: a two-call-site substring and an unbounded browser wait).
# Needs the server on :5055; the J83 sub-check skips without playwright.
$PY scripts/check_qa_2026_08_25.py >/dev/null 2>&1
chk $? "J81-J86  2026-08-25 QA audit fixes hold (6 gates in one script)" "see: python scripts/check_qa_2026_08_25.py"

# J78 — the tenants are VISIBLE in the plan (owner: "I didn't see all these new
# DT in my plan"), drawn the same way the POS-transit IWIP rows are. A tenant
# fleet has two representations and only ONE may reach pricing: the ROW the
# owner reads, and the FLOW the model prices. If the rows also entered the
# segment background the fleet would be charged twice, at OUR tempo, and
# nothing on screen would look wrong — trips/DT would just be quietly low.
# Asserts presence AND absence for that reason. Mutation-tested three ways
# (rows leaking into the background, rows reaching the engine, pricing no
# longer asking for the flow), each failing exactly its own assertion.
if $PY -c "import playwright" >/dev/null 2>&1 \
   && [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 $BASE/health)" = "200" ]; then
$PY scripts/check_tenant_plan_rows.py >/dev/null 2>&1
chk $? "J78  other tenants show in the plan, charged once" "see: python scripts/check_tenant_plan_rows.py"
fi

# Pure local test with a stubbed connection, so it needs no VPN.
$PY test_accumulator.py >/dev/null 2>&1
chk $? "J54  the GPS accumulator is idempotent and loses no history" "see: python test_accumulator.py"

# Needs the Day X GPS extract. Absent in a clean checkout, so skipped there.
if [ -f data/day_x_segment_speeds.csv ] && [ -f data/day_x_gps_snapped.csv ]; then
$PY test_segment_cross_validation.py >/dev/null 2>&1
chk $? "J50  GPS snapping agrees with FMS_CONGESTION_SEG" "see: python test_segment_cross_validation.py"
fi

# The deliverables must match the requested shape, not just contain correct
# numbers. Caught a real gap: segment speeds and dwell were in separate files
# and route_path did not exist.
if [ -f data/day_x_trip_gps_features.csv ]; then
$PY test_deliverable_schema.py >/dev/null 2>&1
chk $? "J51  deliverables match the requested schema" "see: python test_deliverable_schema.py"
fi

# J55 — the OTHER availability path. J52 passed for the entire time the shipped
# UI was under-quoting tonnage by 15%, because it builds its own payload with no
# `availability` key and so only ever exercised the default. The real caller was
# the one supplying it. This gate tests a caller-supplied override AND asserts
# the front end does not send one, because the defect needed both halves.
if [ -f data/route_lookup.csv ]; then
$PY test_availability_override.py >/dev/null 2>&1
chk $? "J55  a supplied availability never scales tonnage" "see: python test_availability_override.py"
fi

# J56 — the assessment view actually draws. Counts rendered canvases and asserts
# the honesty labels, after repeated renders: a chart cached against a detached
# DOM node blanks only from the SECOND render on, which is how every gauge shipped
# empty while a element-counting check passed. Needs playwright and a live server;
# skipped rather than failed where either is absent, like the other optional gates.
if $PY -c "import playwright" >/dev/null 2>&1 \
   && [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 $BASE/health)" = "200" ]; then
$PY scripts/check_assessment_view.py >/dev/null 2>&1
chk $? "J56  plan assessment view renders sections 2-8" "see: python scripts/check_assessment_view.py"
fi

# J57 — the weather input. The suspicion was that a wet cycle uplift feeds through
# to fewer tonnes; measured, it does not, and never did. The REAL defect was that
# the cycle carried only the LOADING point's wet penalty while implied travel is
# the residual cycle-load-dump, so the dumping penalty was subtracted from travel
# and never added back: rain appeared to make trucks travel FASTER on 11 of 14
# routes. Asserts invariance AND that weather still does something, because an
# invariance-only gate is passed perfectly by deleting the feature.
if [ -f data/route_lookup.csv ]; then
$PY test_weather_path.py >/dev/null 2>&1
chk $? "J57  weather moves dwell, never tonnage or travel" "see: python test_weather_path.py"
fi

# J58 — the THIRD dual-mode state. "No DB" and "DB reachable" were both tested;
# "DB configured but unreachable" was not, and it is the normal state here because
# the VPN drops every few minutes. Five endpoints caught their own exception and
# returned ok:false with HTTP 200, which _register reads as success, so the
# fixture fallback never fired. Drives the real app against an unroutable host.
$PY test_dualmode_unreachable.py >/dev/null 2>&1
chk $? "J58  unreachable DB still serves a tagged fixture" "see: python test_dualmode_unreachable.py"

# J59 — regenerating identical results must not churn the tree. Once git status is
# always dirty it stops being a signal and a real accidental change hides in it.
$PY test_stamp_stability.py >/dev/null 2>&1
chk $? "J59  identical results keep their generated_at" "see: python test_stamp_stability.py"

# J60 — shift_minutes, the last caller-supplied field that scales tonnage. No
# UI/engine disagreement here (both use 720), but the effective cycle it divides
# was MEASURED at 720, and 98.5% of truck-shifts are exactly 12.0 h so the fixed
# vs per-trip split cannot be estimated. Any other shift length is therefore an
# extrapolation, and this asserts it is labelled as one -- and silent at 720.
if [ -f data/route_lookup.csv ]; then
$PY test_shift_minutes.py >/dev/null 2>&1
chk $? "J60  shift_minutes labels its extrapolation" "see: python test_shift_minutes.py"
fi

# J61 — segment speeds split by direction. The plumbing is easy; the MAPPING is
# what needed proving, since 'down' is a chainage direction and reading it as
# 'loaded' is an inference (verified: 100% of loaded corridor hauls run
# down-chainage). The majority-and-sign check is what catches a silent inversion,
# which would look entirely normal on screen.
$PY test_direction_split.py >/dev/null 2>&1
chk $? "J61  segment speeds split loaded vs empty" "see: python test_direction_split.py"

# J62 — the HRM correlation, and specifically its METHOD. The first pass found
# r=-0.46 at p~1e-21 with an obvious causal story, and it was route length:
# hrm_hours is summed along a route, and long routes also do fewer trips/truck.
# This asserts the confound stays measured, the within-route test stays the one
# that decides, and the spurious statistic stays labelled rather than deleted.
if [ -f reports/hrm_impact.json ]; then
$PY test_hrm_impact.py >/dev/null 2>&1
chk $? "J62  HRM analysis controls the route-length confound" "see: python test_hrm_impact.py"
fi

# J63 — the committed road centreline. A deliberate, ONE-FILE exception to "no
# site geometry on the public mirror": a road centreline (road, km, lat, lng and
# nothing else) that OpenStreetMap already renders, committed so the section-9
# map works on a fresh clone. The schema assertion is the load-bearing one: a
# re-export that quietly added a `zone` column would leak zone data through a
# path that already has permission, and nothing else would notice.
$PY test_map_geometry.py >/dev/null 2>&1
chk $? "J63  committed road centreline, and only that" "see: python test_map_geometry.py"

# J64 — capability filters are real AND fast. Until 2026-07-31 this endpoint was
# answered with the committed fixture and request.args were discarded, so every
# KPI on the Capability tab was frozen at 2026-07-22 capture values. It now
# queries DISPATCH RESULTS LITE 2 (via a whole-view snapshot) and honours all
# six filter parameters. The speed assertion is load-bearing: the view costs
# ~17 s to materialise, so a per-request SQL path would pass every correctness
# check while making the tab unusable again. Skips cleanly in no-DB mode.
# Requires a live server on :5055 (same convention as J56 / browser gates).
if curl -fsS --max-time 5 http://127.0.0.1:5055/health >/dev/null 2>&1; then
$PY test_capability_filters.py >/dev/null 2>&1
chk $? "J64  capability filters real + under 3s" "see: python test_capability_filters.py"
else
  echo "  SKIP J64  (no server on :5055 — start serve.py to exercise)"
fi

# J65 — TARGET TRIP is a RATE (planned trips/DT). Storing the raw rate and
# dividing SUM(rate)/SUM(DT PLAN) produced planTripsPerDT≈0.15 and Trip-eff
# KPIs of 1700–2600% on Tab 1 (QC 2026-07-31). _ptr must hold trip-COUNTS
# (rate × DT PLAN) so the weighted average lands near ~4.4 and effTrip ~0.9.
# Offline unit checks always run; live HTTP asserts run when :5055 is up.
$PY test_plan_trip_rate.py >/dev/null 2>&1
chk $? "J65  planTripsPerDT is weighted TARGET TRIP rate" "see: python test_plan_trip_rate.py"

# J66 — path-response snapshot (rain panel). Was 15–18 s per call and ignored
# Apply. Same whole-view snapshot as capability; date from/to filter in Python.
if curl -fsS --max-time 5 http://127.0.0.1:5055/health >/dev/null 2>&1; then
$PY test_path_response_perf.py >/dev/null 2>&1
chk $? "J66  path-response snapshotted + under 3s" "see: python test_path_response_perf.py"
else
  echo "  SKIP J66  (no server on :5055 — start serve.py to exercise)"
fi

# J67 — weighbridge-summary must not look live when HAULAGE_IWIP_CLEAN is weeks
# old. Tags source + ageDays + stale.
if curl -fsS --max-time 5 http://127.0.0.1:5055/health >/dev/null 2>&1; then
$PY test_weighbridge_honesty.py >/dev/null 2>&1
chk $? "J67  weighbridge-summary discloses age/stale" "see: python test_weighbridge_honesty.py"
else
  echo "  SKIP J67  (no server on :5055 — start serve.py to exercise)"
fi

# J68 — disk-backed snapshots (P3). After restart, empty memory used to force a
# 14–20 s SQL hit. data/cap_snapshot.json + pr_snapshot.json warm the process;
# stale disk serves immediately and refreshes in the background.
# Offline unit always runs; live file asserts when :5055 is in database mode.
$PY test_disk_snapshot.py >/dev/null 2>&1
chk $? "J68  disk snapshots write/load/stale-refresh" "see: python test_disk_snapshot.py"

# J69 — Tab 1 flow motion from measured GPS; posted Excel limits as overlay.
$PY test_flow_gps_speeds.py >/dev/null 2>&1
chk $? "J69  GPS-first flow + posted-limit ribbon" "see: python test_flow_gps_speeds.py"

# J70 — Tab 1 leftovers: GPS map, constraints persist, live trucks, measured V/C,
# refreshed GPS window.
$PY test_tab1_leftovers.py >/dev/null 2>&1
chk $? "J70  Tab1 map/constraints/trucks/V/C/GPS-window" "see: python test_tab1_leftovers.py"

# J71 — the A · Capacity card must quote the ENGINE's shortfall. It used to divide
# by predict.wmt (the Step 1 path model), so a fleet past the loader ceiling read
# "Shortfall 0 t · vs planned 120%" while /api/simulate was clipping 16,012 t and
# raising two capacity_warnings — the availability override (J55) in another card.
# Driven through the browser with a real predict.wmt for the J52 reason: a gate that
# builds its own input cannot catch a bug in what the real caller sends. Asserts BOTH
# directions (0 t inside the envelope, the engine's clip past it), because a
# one-sided check is passed by hardcoding a constant. Mutation-tested 2026-08-12:
# restoring predict.wmt as the denominator fails 5 of its assertions.
# Needs playwright and a live server; skipped rather than failed where either is
# absent, like J56.
if $PY -c "import playwright" >/dev/null 2>&1 \
   && [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 $BASE/health)" = "200" ]; then
$PY scripts/check_capacity_card.py >/dev/null 2>&1
chk $? "J71  capacity card quotes the engine, not the path model" "see: python scripts/check_capacity_card.py"
fi

# J72 — mine-plan scenarios (S1/S2/S3): the priority waterfall conserves the
# fleet per contractor (P1 SAP + P2 LIM-TOS + P3 free == the matrix pool),
# never puts a non-RIM truck at BLB, and honours the 8 Mt LIM-LD cap in BOTH
# directions (capped months say so; impossible targets starve P3 to zero and
# report deficits instead of inventing trucks). S1 is derived live from the
# yearly matrix and may never exist as a file.
$PY scripts/check_scenarios.py >/dev/null 2>&1
chk $? "J72  scenario waterfall conserves fleet, BLB=RIM, 8 Mt cap" "see: python scripts/check_scenarios.py"


echo
# J73 — hybrid congestion model (owner spec 2026-08-20): physics + Erlang-C +
# BPR calibrated per route from HAULAGE_CLEAN trip gaps, anchored to the
# dispatch day-rate basis. Backtest on ~3,900 real dispatch days must hold
# R2 > 0.7 / MAPE < 15% at the route x fleet-bucket level; more loaders must
# raise trips/DT; the decline past the knee must be nonlinear (not 1/N);
# hybrid must differ from the legacy divide; no NaN/Inf on 1-1000 trucks.
# Skips (not fails) when the calibration data is absent (fresh clone).
if [ -f data/congestion_params.json ] && [ -f data/congestion_dayshift.json ]; then
$PY scripts/verify_congestion.py >/dev/null 2>&1
chk $? "J73  hybrid congestion model: backtest R2>0.7, loaders raise ceiling" "see: python scripts/verify_congestion.py"
else
echo "  SKIP J73  (no congestion calibration data — run scripts/calibrate_congestion.py --refresh)"
fi

printf 'SCORE %d/%d   (failures: %d)\n' "$PASS" "$TOTAL" "$FAIL"
[ "$FAIL" = "0" ]
