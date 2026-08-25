# Reference saturation curves — trips/DT/day vs fleet

> Generated 2026-08-25T10:28:51Z by scripts/export_saturation_curves.py — regenerate after any
> recalibration. Formula: `trips = 1440/(road_congested + ops + queue +
> bunching + overhead_per_trip)`; BPR on road time only, capped at 3x.
> `calibrated faces` is what the Congestion-tab chart shows;
> `proportional` is what the plan builder prices with (rules §10.9).

Built from **data/congestion_params.json** generated 2026-08-23T23:41:19Z (`sha256:a57ce03e3021c983`, `sha256:f8efaf136d339a6a`).

Verify this file is still current — exits non-zero when it is not:

```bash
.venv/bin/python scripts/export_saturation_curves.py --check
```

## TF>HUAFEI

road_free 378 min · ops 8 min · overhead/trip 218 min · anchor day-rate 2.374 @ 70 DT · knee ~240.0 DT · 23.3 trucks/loader

| DT | trips/DT (calibrated faces) | trips/DT (proportional loaders) | cycle min | p10–p90 |
|---:|---:|---:|---:|---|
| 50 | 2.38 | 2.38 | 388 | 2.14–2.61 |
| 100 | 2.37 | 2.37 | 389 | 2.13–2.61 |
| 150 | 2.36 | 2.36 | 392 | 2.12–2.59 |
| 200 | 2.33 | 2.36 | 400 | 1.96–2.70 |
| 250 | 2.19 | 2.36 | 438 | 1.65–2.74 |
| 300 | 1.97 | 2.36 | 513 | 1.30–2.63 |
| 350 | 1.77 | 2.36 | 595 | 1.06–2.48 |
| 400 | 1.61 | 2.36 | 677 | 0.96–2.25 |
| 450 | 1.48 | 2.36 | 752 | 0.89–2.08 |
| 500 | 1.48 | 2.36 | 752 | 0.89–2.08 |
| 550 | 1.48 | 2.36 | 752 | 0.89–2.08 |
| 600 | 1.48 | 2.36 | 752 | 0.89–2.08 |
| 650 | 1.48 | 2.36 | 752 | 0.89–2.08 |
| 700 | 1.48 | 2.36 | 752 | 0.89–2.08 |
| 750 | 1.48 | 2.36 | 752 | 0.89–2.08 |
| 800 | 1.48 | 2.36 | 752 | 0.89–2.08 |

## BLB>POS 14

road_free 102 min · ops 8 min · overhead/trip 92 min · anchor day-rate 7.069 @ 19 DT · knee ~60.0 DT · 6.3 trucks/loader

| DT | trips/DT (calibrated faces) | trips/DT (proportional loaders) | cycle min | p10–p90 |
|---:|---:|---:|---:|---|
| 50 | 6.88 | 6.99 | 117 | 6.20–7.57 |
| 100 | 5.38 | 6.97 | 175 | 4.41–6.35 |
| 150 | 4.12 | 6.97 | 257 | 2.60–5.64 |
| 200 | 3.33 | 6.97 | 340 | 2.00–4.66 |
| 250 | 2.79 | 6.97 | 423 | 1.68–3.91 |
| 300 | 2.54 | 6.97 | 474 | 1.53–3.56 |
| 350 | 2.54 | 6.96 | 474 | 1.53–3.56 |
| 400 | 2.54 | 6.94 | 474 | 1.53–3.56 |
| 450 | 2.54 | 6.91 | 474 | 1.53–3.56 |
| 500 | 2.54 | 6.88 | 474 | 1.53–3.56 |
| 550 | 2.54 | 6.84 | 474 | 1.53–3.56 |
| 600 | 2.54 | 6.80 | 474 | 1.53–3.56 |
| 650 | 2.54 | 6.74 | 474 | 1.53–3.56 |
| 700 | 2.54 | 6.68 | 474 | 1.53–3.56 |
| 750 | 2.54 | 6.62 | 474 | 1.53–3.56 |
| 800 | 2.54 | 6.55 | 474 | 1.53–3.56 |

## Physical floor check

The corrected formula can never predict below one trip per day:

- TF>HUAFEI minimum over 10–800 DT: **1.48** trips/DT/day
- BLB>POS 14 minimum over 10–800 DT: **2.54** trips/DT/day
