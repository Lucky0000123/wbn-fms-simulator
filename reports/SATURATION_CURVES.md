# Reference saturation curves — trips/DT/day vs fleet

> Generated 2026-08-21T04:54:43Z by scripts/export_saturation_curves.py — regenerate after any
> recalibration. Formula: `trips = 1440/(road_congested + ops + queue +
> bunching + overhead_per_trip)`; BPR on road time only, capped at 3x.
> `calibrated faces` is what the Congestion-tab chart shows;
> `proportional` is what the plan builder prices with (rules §10.9).

## TF>HUAFEI

road_free 209 min · ops 8 min · overhead/trip 384 min · anchor day-rate 2.374 @ 70 DT · knee ~130.0 DT · 23.3 trucks/loader

| DT | trips/DT (calibrated faces) | trips/DT (proportional loaders) | cycle min | p10–p90 |
|---:|---:|---:|---:|---|
| 50 | 2.39 | 2.37 | 219 | 2.15–2.62 |
| 100 | 2.34 | 2.37 | 232 | 2.10–2.57 |
| 150 | 2.20 | 2.35 | 270 | 1.98–2.42 |
| 200 | 1.98 | 2.31 | 345 | 1.66–2.29 |
| 250 | 1.78 | 2.25 | 426 | 1.33–2.22 |
| 300 | 1.61 | 2.19 | 509 | 1.06–2.16 |
| 350 | 1.48 | 2.13 | 592 | 0.89–2.06 |
| 400 | 1.43 | 2.06 | 625 | 0.86–2.00 |
| 450 | 1.40 | 2.00 | 643 | 0.84–1.96 |
| 500 | 1.37 | 1.95 | 663 | 0.82–1.92 |
| 550 | 1.34 | 1.89 | 686 | 0.81–1.88 |
| 600 | 1.32 | 1.84 | 710 | 0.79–1.84 |
| 650 | 1.29 | 1.80 | 735 | 0.77–1.80 |
| 700 | 1.26 | 1.75 | 761 | 0.75–1.76 |
| 750 | 1.23 | 1.71 | 787 | 0.74–1.72 |
| 800 | 1.20 | 1.67 | 814 | 0.72–1.68 |

## BLB>POS 14

road_free 97 min · ops 8 min · overhead/trip 97 min · anchor day-rate 7.070 @ 19 DT · knee ~60.0 DT · 6.3 trucks/loader

| DT | trips/DT (calibrated faces) | trips/DT (proportional loaders) | cycle min | p10–p90 |
|---:|---:|---:|---:|---|
| 50 | 6.76 | 7.01 | 116 | 6.08–7.43 |
| 100 | 5.29 | 7.00 | 175 | 4.34–6.24 |
| 150 | 4.07 | 6.99 | 257 | 2.57–5.58 |
| 200 | 3.30 | 6.98 | 339 | 1.98–4.62 |
| 250 | 2.77 | 6.94 | 422 | 1.66–3.88 |
| 300 | 2.47 | 6.89 | 486 | 1.48–3.46 |
| 350 | 2.42 | 6.81 | 497 | 1.45–3.39 |
| 400 | 2.37 | 6.72 | 512 | 1.42–3.31 |
| 450 | 2.30 | 6.61 | 529 | 1.38–3.22 |
| 500 | 2.23 | 6.49 | 548 | 1.34–3.12 |
| 550 | 2.16 | 6.36 | 569 | 1.30–3.03 |
| 600 | 2.09 | 6.23 | 591 | 1.26–2.93 |
| 650 | 2.03 | 6.10 | 614 | 1.22–2.84 |
| 700 | 1.96 | 5.98 | 637 | 1.18–2.75 |
| 750 | 1.90 | 5.85 | 660 | 1.14–2.66 |
| 800 | 1.90 | 5.74 | 663 | 1.14–2.65 |

## Physical floor check

The corrected formula can never predict below one trip per day:

- TF>HUAFEI minimum over 10–800 DT: **1.20** trips/DT/day
- BLB>POS 14 minimum over 10–800 DT: **1.90** trips/DT/day
