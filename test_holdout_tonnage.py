"""Close the loop: is the fixed simulator measurably better on data it has never
been fitted to?

WHY THIS IS NEEDED
Every check so far compared the simulator against the SAME aggregate it was built
from. The effective cycle is defined as shift-minutes/trips per route, so of
course dividing the shift by it reproduces trips per shift. That is arithmetic
identity, not validation, and reporting it as evidence would be circular.

The honest test is HELD-OUT and forward in time: build the lookup from earlier
data only, then predict a later period the model never saw. If the fix is real,
it beats the old formula out of sample too. If it only wins in-sample, the win is
an artefact of the definition.

Predicts TONNAGE, not trips, because tonnage is what a planner acts on and it
compounds the trip error with payload.
"""
import sys

sys.path.insert(0, "/Users/lucky/wbn-fms-simulator")
import numpy as np
import pandas as pd

d = pd.read_csv("/Users/lucky/wbn-fms-simulator/data/trip_features.csv")
d["date"] = pd.to_datetime(d["date"])
SHIFT = 720.0
CUT = pd.Timestamp("2026-05-01")          # train before, test after
tr, te = d[d.date < CUT], d[d.date >= CUT]
print("train %s trips (%s..%s) | test %s trips (%s..%s)"
      % (f"{len(tr):,}", str(tr.date.min())[:10], str(tr.date.max())[:10],
         f"{len(te):,}", str(te.date.min())[:10], str(te.date.max())[:10]))


def build_lookup(x):
    """Both cycle definitions, measured on the training period only."""
    g = (x.groupby(["truck_id", "date", "shift", "route"], observed=True)
          .size().rename("trips").reset_index())
    eff = (g.groupby("route", observed=True)
            .agg(truck_shifts=("trips", "size"), trips=("trips", "sum"))
            .reset_index())
    eff["eff_cycle"] = (eff.truck_shifts * SHIFT) / eff.trips
    wb = (x.groupby("route", observed=True)
           .agg(wb_cycle=("cycle_time_min", "median"),
                payload=("payload_t", "median")).reset_index())
    return eff.merge(wb, on="route")


lk = build_lookup(tr)
lk = lk[lk.truck_shifts >= 30]
print("routes in the training lookup: %d" % len(lk))

# Ground truth on the HELD-OUT period: what each route+truck-shift actually did.
obs = (te.groupby(["route", "truck_id", "date", "shift"], observed=True)
        .agg(trips=("ticket_no", "size"), wmt=("payload_t", "sum"))
        .reset_index())
obs = obs.merge(lk[["route", "eff_cycle", "wb_cycle", "payload"]], on="route",
                how="inner")
print("held-out truck-shifts on known routes: %s" % f"{len(obs):,}")

# The two competing predictions, per truck-shift.
obs["pred_old"] = (SHIFT * 0.85) / obs.wb_cycle * obs.payload
obs["pred_new"] = (SHIFT / obs.eff_cycle) * obs.payload
obs["actual"] = obs.wmt

print("\n=== HELD-OUT tonnage per truck-shift ===")
print("%-22s %10s %10s %10s" % ("", "actual", "old", "new"))
print("-" * 56)
print("%-22s %10.1f %10.1f %10.1f"
      % ("mean t", obs.actual.mean(), obs.pred_old.mean(), obs.pred_new.mean()))
print("%-22s %10.1f %10.1f %10.1f"
      % ("median t", obs.actual.median(), obs.pred_old.median(),
         obs.pred_new.median()))
for lbl, col in (("old formula", "pred_old"), ("new formula", "pred_new")):
    err = obs[col] - obs.actual
    bias = 100 * err.mean() / obs.actual.mean()
    mae = err.abs().mean()
    print("\n%s:" % lbl)
    print("   bias %+8.1f%%   MAE %8.1f t   median abs err %8.1f t"
          % (bias, mae, err.abs().median()))

old_bias = abs(100 * (obs.pred_old - obs.actual).mean() / obs.actual.mean())
new_bias = abs(100 * (obs.pred_new - obs.actual).mean() / obs.actual.mean())
old_mae = (obs.pred_old - obs.actual).abs().mean()
new_mae = (obs.pred_new - obs.actual).abs().mean()

print("\n=== VERDICT on held-out data ===")
print("   bias: %.1f%% -> %.1f%%  (%.1fx better)"
      % (old_bias, new_bias, old_bias / max(new_bias, 1e-9)))
print("   MAE : %.0f t -> %.0f t   (%.1fx better)"
      % (old_mae, new_mae, old_mae / max(new_mae, 1e-9)))

print("\n=== per-route, held out, biggest routes ===")
g = (obs.groupby("route")
      .agg(shifts=("actual", "size"), actual=("actual", "mean"),
           old=("pred_old", "mean"), new=("pred_new", "mean")).reset_index())
g["old_err%"] = (100 * (g.old - g.actual) / g.actual).round(0)
g["new_err%"] = (100 * (g.new - g.actual) / g.actual).round(0)
print(g[g.shifts >= 200].sort_values("shifts", ascending=False)
       .head(12).round(1).to_string(index=False))
sub = g[g.shifts >= 200]
print("\nroutes where the new formula is closer: %d of %d"
      % (int((sub["new_err%"].abs() < sub["old_err%"].abs()).sum()), len(sub)))
better = new_bias < old_bias and new_mae < old_mae
print("\nRESULT: %s" % ("the fix is better OUT OF SAMPLE, not just in-sample"
                        if better else "NO out-of-sample improvement"))
sys.exit(0 if better else 1)
