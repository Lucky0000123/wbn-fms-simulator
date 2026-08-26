# Reference saturation curves — trips/DT/day vs fleet

> Generated 2026-08-26T07:19:28Z by scripts/export_saturation_curves.py — regenerate after any
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

road_free 378 min · ops 8 min · overhead/trip 218 min · anchor day-rate 2.374 @ 70 DT · knee ~260.0 DT · 23.3 trucks/loader

| DT | trips/DT (calibrated faces) | trips/DT (proportional loaders) | cycle min | p10–p90 |
|---:|---:|---:|---:|---|
| 50 | 2.38 | 2.38 | 388 | 2.14–2.61 |
| 100 | 2.37 | 2.37 | 389 | 2.13–2.61 |
| 150 | 2.36 | 2.36 | 392 | 2.12–2.59 |
| 200 | 2.34 | 2.36 | 398 | 1.96–2.71 |
| 250 | 2.27 | 2.36 | 415 | 1.71–2.84 |
| 300 | 2.15 | 2.36 | 450 | 1.42–2.88 |
| 350 | 2.03 | 2.36 | 491 | 1.22–2.84 |
| 400 | 1.92 | 2.36 | 533 | 1.15–2.68 |
| 450 | 1.82 | 2.36 | 574 | 1.09–2.54 |
| 500 | 1.73 | 2.36 | 616 | 1.03–2.42 |
| 550 | 1.64 | 2.36 | 658 | 0.99–2.30 |
| 600 | 1.57 | 2.36 | 699 | 0.94–2.20 |
| 650 | 1.50 | 2.36 | 741 | 0.90–2.10 |
| 700 | 1.44 | 2.36 | 783 | 0.86–2.01 |
| 750 | 1.38 | 2.36 | 824 | 0.83–1.93 |
| 800 | 1.33 | 2.36 | 866 | 0.80–1.86 |

## BLB>POS 14

road_free 102 min · ops 8 min · overhead/trip 92 min · anchor day-rate 7.069 @ 19 DT · knee ~70.0 DT · 6.3 trucks/loader

| DT | trips/DT (calibrated faces) | trips/DT (proportional loaders) | cycle min | p10–p90 |
|---:|---:|---:|---:|---|
| 50 | 6.92 | 6.99 | 116 | 6.22–7.61 |
| 100 | 6.12 | 6.97 | 143 | 5.02–7.22 |
| 150 | 5.21 | 6.97 | 184 | 3.28–7.13 |
| 200 | 4.53 | 6.97 | 226 | 2.72–6.34 |
| 250 | 4.00 | 6.97 | 267 | 2.40–5.60 |
| 300 | 3.59 | 6.97 | 309 | 2.15–5.02 |
| 350 | 3.25 | 6.96 | 351 | 1.95–4.55 |
| 400 | 2.97 | 6.94 | 392 | 1.78–4.16 |
| 450 | 2.73 | 6.91 | 434 | 1.64–3.83 |
| 500 | 2.54 | 6.88 | 476 | 1.52–3.55 |
| 550 | 2.36 | 6.84 | 517 | 1.42–3.31 |
| 600 | 2.21 | 6.80 | 559 | 1.33–3.10 |
| 650 | 2.08 | 6.74 | 601 | 1.25–2.91 |
| 700 | 1.96 | 6.68 | 642 | 1.18–2.74 |
| 750 | 1.84 | 6.62 | 690 | 1.10–2.58 |
| 800 | 1.66 | 6.55 | 773 | 1.00–2.33 |

## Physical floor check

The corrected formula can never predict below one trip per day:

- TF>HUAFEI minimum over 10–800 DT: **1.33** trips/DT/day
- BLB>POS 14 minimum over 10–800 DT: **1.66** trips/DT/day
