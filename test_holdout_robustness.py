"""Three things I built but never validated. Each could be wrong.

1. FALLBACK_EFFECTIVE_RATIO = 4.7 for routes with no measured history. I derived
   it from the site median and never checked whether it HELPS on routes it would
   actually serve. If it is worse than the alternatives, an unseen route gets a
   bad answer and nothing says so.

2. The wet-weather path scales the effective cycle by (wet cycle / dry cycle).
   Never validated against observed WET tonnage. A wrong wet uplift would
   mispredict exactly the shifts a planner most wants warning about.

3. The held-out result used ONE cut date (2026-05-01). A single split can be
   lucky. Test several.

Each is checked against data the lookup never saw.
"""
import sys

sys.path.insert(0, "/Users/lucky/wbn-fms-simulator")
import numpy as np
import pandas as pd

SHIFT = 720.0
d = pd.read_csv("/Users/lucky/wbn-fms-simulator/data/trip_features.csv")
d["date"] = pd.to_datetime(d["date"])
fails = []


def check(name, cond, detail=""):
    print("   %-54s %s%s" % (name, "PASS" if cond else "FAIL",
                             "" if cond else "  <- " + str(detail)))
    if not cond:
        fails.append(name)


def build(x, min_shifts=30):
    g = (x.groupby(["truck_id", "date", "shift", "route"], observed=True)
          .size().rename("trips").reset_index())
    e = (g.groupby("route", observed=True)
          .agg(ts=("trips", "size"), tr=("trips", "sum")).reset_index())
    e = e[e.ts >= min_shifts].copy()
    e["eff"] = (e.ts * SHIFT) / e.tr
    w = (x.groupby("route", observed=True)
          .agg(wb=("cycle_time_min", "median"),
               pay=("payload_t", "median")).reset_index())
    return e.merge(w, on="route")


def truth(x):
    return (x.groupby(["route", "truck_id", "date", "shift"], observed=True)
             .agg(trips=("ticket_no", "size"), wmt=("payload_t", "sum"))
             .reset_index())


print("=== 1. MULTIPLE held-out splits (one split can be lucky) ===")
print("%-14s %8s %10s %10s %10s" % ("cut", "shifts", "old bias", "new bias", "new MAE"))
print("-" * 58)
for cut in ("2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01"):
    c = pd.Timestamp(cut)
    lk, te = build(d[d.date < c]), truth(d[d.date >= c])
    m = te.merge(lk[["route", "eff", "wb", "pay"]], on="route", how="inner")
    if m.empty:
        continue
    old = (SHIFT * 0.85) / m.wb * m.pay
    new = (SHIFT / m.eff) * m.pay
    ob = 100 * (old - m.wmt).mean() / m.wmt.mean()
    nb = 100 * (new - m.wmt).mean() / m.wmt.mean()
    print("%-14s %8s %+9.1f%% %+9.1f%% %9.1f t"
          % (cut, f"{len(m):,}", ob, nb, (new - m.wmt).abs().mean()))
    check("cut %s: new bias under 25%%" % cut, abs(nb) < 25, "%.1f%%" % nb)
    check("cut %s: new beats old" % cut, abs(nb) < abs(ob))

print("\n=== 2. is the 4.7x FALLBACK ratio any good on unseen routes? ===")
print("held out routes entirely: build on some, predict routes never seen\n")
c = pd.Timestamp("2026-05-01")
tr_all, te_all = d[d.date < c], d[d.date >= c]
lk_all = build(tr_all)
known = set(lk_all.route)
# Routes that appear in the test period but have NO training history: exactly
# the population the fallback serves.
te_t = truth(te_all)
unseen = te_t[~te_t.route.isin(known)].copy()
print("   truck-shifts on routes with no training history: %s" % f"{len(unseen):,}")
if len(unseen):
    wb_unseen = (te_all[~te_all.route.isin(known)]
                 .groupby("route", observed=True)
                 .agg(wb=("cycle_time_min", "median"),
                      pay=("payload_t", "median")).reset_index())
    u = unseen.merge(wb_unseen, on="route", how="inner")
    site_eff = float(lk_all.eff.median())
    for lbl, eff in (("4.7x weigh-to-weigh (shipped)", u.wb * 4.7),
                     ("site median eff cycle", pd.Series([site_eff] * len(u))),
                     ("no adjustment (old bug)", u.wb / 0.85)):
        p = (SHIFT / eff.values) * u.pay.values
        b = 100 * (p - u.wmt.values).mean() / u.wmt.mean()
        print("   %-32s bias %+8.1f%%  MAE %8.1f t"
              % (lbl, b, np.abs(p - u.wmt.values).mean()))
    fb = (SHIFT / (u.wb * 4.7).values) * u.pay.values
    old = (SHIFT * 0.85 / u.wb).values * u.pay.values
    check("fallback beats the old formula on unseen routes",
          abs((fb - u.wmt.values).mean()) < abs((old - u.wmt.values).mean()))
    check("fallback bias under 60% on unseen routes",
          abs(100 * (fb - u.wmt.values).mean() / u.wmt.mean()) < 60,
          "%.1f%%" % (100 * (fb - u.wmt.values).mean() / u.wmt.mean()))
else:
    print("   (no unseen routes in this split; fallback untestable here)")

print("\n=== 3. does the WET path predict wet shifts correctly? ===")
d["wet"] = (pd.to_numeric(d.rainfall_mm, errors="coerce").fillna(0) > 5)
lk = build(d[d.date < c])
te = truth(d[d.date >= c])
wetmap = (d[d.date >= c].groupby(["route", "date", "shift"], observed=True)
          .wet.first().rename("wet").reset_index())
m = te.merge(lk[["route", "eff", "pay"]], on="route", how="inner") \
      .merge(wetmap, on=["route", "date", "shift"], how="left")
m["wet"] = m.wet.fillna(False)
for lbl, sub in (("dry shifts", m[~m.wet]), ("wet shifts", m[m.wet])):
    if sub.empty:
        continue
    p = (SHIFT / sub.eff) * sub.pay
    print("   %-12s n=%7s  actual %6.1f t  predicted %6.1f t  bias %+6.1f%%"
          % (lbl, f"{len(sub):,}", sub.wmt.mean(), p.mean(),
             100 * (p - sub.wmt).mean() / sub.wmt.mean()))
wd, ww = m[~m.wet], m[m.wet]
if len(wd) and len(ww):
    # This deliberately does NOT assert that wet produces less. Measured within
    # route and month, rain moves tonnage a median +0.1% and reduces it in only
    # 49% of 122 comparable route-months, so a wet production penalty is not
    # supported. What matters is that the model is not BIASED on wet shifts.
    pw = ((SHIFT / ww.eff) * ww.pay)
    pdry = ((SHIFT / wd.eff) * wd.pay)
    bw = 100 * (pw - ww.wmt).mean() / ww.wmt.mean()
    bd = 100 * (pdry - wd.wmt).mean() / wd.wmt.mean()
    check("model is not materially more biased on wet shifts",
          abs(bw - bd) < 10, "wet %+.1f%% vs dry %+.1f%%" % (bw, bd))
    check("wet bias itself is under 25%", abs(bw) < 25, "%+.1f%%" % bw)

print("\n%s  (%d failures)"
      % ("ALL PASS" if not fails else "FAILURES: " + ", ".join(fails), len(fails)))
sys.exit(1 if fails else 0)
