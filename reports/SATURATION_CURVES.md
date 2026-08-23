# Reference saturation curves — trips/DT/day vs fleet

> Generated 2026-08-23T15:47:11Z by scripts/export_saturation_curves.py — regenerate after any
> recalibration. Formula: `trips = 1440/(road_congested + ops + queue +
> bunching + overhead_per_trip)`; BPR on road time only, capped at 3x.
> `calibrated faces` is what the Congestion-tab chart shows;
> `proportional` is what the plan builder prices with (rules §10.9).

Built from **data/congestion_params.json** generated 2026-08-22T04:07:23Z (`sha256:9545ee6d357f17cd`, `sha256:bc48f67671f41c45`).

Verify this file is still current — exits non-zero when it is not:

```bash
.venv/bin/python scripts/export_saturation_curves.py --check
```

## TF>HUAFEI

road_free 209 min · ops 8 min · overhead/trip 387 min · anchor day-rate 2.374 @ 70 DT · knee ~140.0 DT · 23.3 trucks/loader

| DT | trips/DT (calibrated faces) | trips/DT (proportional loaders) | cycle min | p10–p90 |
|---:|---:|---:|---:|---|
| 50 | 2.38 | 2.37 | 218 | 2.14–2.62 |
| 100 | 2.36 | 2.37 | 223 | 2.12–2.60 |
| 150 | 2.21 | 2.37 | 264 | 1.99–2.44 |
| 200 | 1.97 | 2.36 | 343 | 1.66–2.29 |
| 250 | 1.77 | 2.36 | 426 | 1.33–2.21 |
| 300 | 1.61 | 2.36 | 509 | 1.06–2.15 |
| 350 | 1.49 | 2.36 | 583 | 0.89–2.08 |
| 400 | 1.49 | 2.36 | 583 | 0.89–2.08 |
| 450 | 1.49 | 2.36 | 583 | 0.89–2.08 |
| 500 | 1.49 | 2.36 | 583 | 0.89–2.08 |
| 550 | 1.49 | 2.36 | 583 | 0.89–2.08 |
| 600 | 1.49 | 2.36 | 583 | 0.89–2.08 |
| 650 | 1.49 | 2.36 | 583 | 0.89–2.08 |
| 700 | 1.49 | 2.36 | 583 | 0.89–2.08 |
| 750 | 1.49 | 2.36 | 583 | 0.89–2.08 |
| 800 | 1.49 | 2.36 | 583 | 0.89–2.08 |

## BLB>POS 14

road_free 97 min · ops 8 min · overhead/trip 97 min · anchor day-rate 7.070 @ 19 DT · knee ~60.0 DT · 6.3 trucks/loader

| DT | trips/DT (calibrated faces) | trips/DT (proportional loaders) | cycle min | p10–p90 |
|---:|---:|---:|---:|---|
| 50 | 6.88 | 7.01 | 112 | 6.19–7.57 |
| 100 | 5.31 | 7.00 | 174 | 4.35–6.26 |
| 150 | 4.08 | 7.00 | 256 | 2.57–5.58 |
| 200 | 3.30 | 7.00 | 339 | 1.98–4.62 |
| 250 | 2.77 | 6.99 | 422 | 1.66–3.88 |
| 300 | 2.55 | 6.98 | 469 | 1.53–3.56 |
| 350 | 2.55 | 6.97 | 469 | 1.53–3.56 |
| 400 | 2.55 | 6.95 | 469 | 1.53–3.56 |
| 450 | 2.55 | 6.92 | 469 | 1.53–3.56 |
| 500 | 2.55 | 6.89 | 469 | 1.53–3.56 |
| 550 | 2.54 | 6.85 | 469 | 1.53–3.56 |
| 600 | 2.54 | 6.79 | 469 | 1.53–3.56 |
| 650 | 2.54 | 6.74 | 469 | 1.53–3.56 |
| 700 | 2.54 | 6.67 | 469 | 1.53–3.56 |
| 750 | 2.54 | 6.61 | 469 | 1.53–3.56 |
| 800 | 2.54 | 6.54 | 469 | 1.53–3.56 |

## Physical floor check

The corrected formula can never predict below one trip per day:

- TF>HUAFEI minimum over 10–800 DT: **1.49** trips/DT/day
- BLB>POS 14 minimum over 10–800 DT: **2.54** trips/DT/day
