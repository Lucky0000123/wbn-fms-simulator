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
LOCAL=$(git rev-parse HEAD 2>/dev/null)
O=$(git ls-remote --heads origin main 2>/dev/null | cut -f1)
M=$(git ls-remote --heads mirror main 2>/dev/null | cut -f1)
[ -n "$LOCAL" ] && [ "$LOCAL" = "$O" ] && [ "$LOCAL" = "$M" ]
chk $? "G24  origin + mirror match local HEAD" "not pushed to both"

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


echo
printf 'SCORE %d/%d   (failures: %d)\n' "$PASS" "$TOTAL" "$FAIL"
[ "$FAIL" = "0" ]
