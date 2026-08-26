# Congestion & Fleet Prediction — Deep Analysis vs the Literature

**Date:** 2026-08-26 · **Prepared by:** 3 research survey agents (115 cited works) + numeric experiments on WBN production data
**Full surveys:** `/tmp/survey_congestion.md` (31 refs) · `/tmp/survey_queueing.md` (38 refs) · `/tmp/survey_simulation.md` (46 refs)

---

## 1. What our model does today

`trips/DT/day = f( physics free-flow cycle + Erlang-C loader queue + BPR road penalty + bunching term )`

| Layer | Method | Literature verdict |
|---|---|---|
| Free speed | v(RR) rolling-resistance regression | ✅ Matches practice (vehicle-dynamics basis is standard) — but the Meneses & Sepúlveda 2023 citation could not be verified online; confirm its fit range |
| Loader queue | **Open** M/M/c Erlang-C, λ=N/cycle, capped at half-shift when ρ≥1 | ⚠️ Wrong model class for a closed fleet — but see §3: harmless at our actual operating point |
| Road congestion | BPR (α=0.15, β=4), c = slowest-bin-speed/50 m, one loaded lane | ⚠️ Fine below v/c≈0.9; indefensible above 1.0 — but see §4: our plans never get there |
| Bunching | Small additive penalty | ⚠️ Literature says this is the **dominant** mechanism on no-overtaking mine roads; ours is underweight |
| Validation | Walk-forward vs dispatch, ~20% MAPE, R²>0.7 | ✅ At parity with published state of the art (best hybrid ML+DES: R²=0.68; link-level ML: 12–15%; DES "validations" are usually weaker in-sample checks) |

## 2. Verdict in one line

**The architecture is right, the benchmark is competitive, and the two theoretically-wrong pieces are currently operating inside their validity zones — but each has a cliff nearby, and one input-handling bug-class (defaulted loaders) is producing real −23…−39% errors today.**

## 3. Loader queue: open Erlang-C vs the correct closed-fleet model

The queueing literature (Koenigsberg 1958 → Carmichael 1986 → Kappas & Yegulalp 1991 → Ta et al. 2013 EJOR) is unanimous: a fixed fleet of N trucks is a **finite-source** system (M/M/c//N "machine repair"), not an open queue. I implemented the exact model and compared on our routes:

| Regime (match factor) | Open-vs-closed error | Where our plans sit |
|---|---|---|
| MF < 0.5 | < 2 % — negligible | **All frozen-plan rows: MF ≤ 0.24** with their real loader counts |
| MF 0.8–1.0 | waits over-estimated 4–9×, trips −25…−45 % | Only reached when loaders are wrong |
| ρ ≥ 1 (half-shift cap) | trips −57…−82 % vs true loader-limited plateau | Never with real loaders |

**The real bug found:** when a caller omits `n_loaders`, the default (c≈2) drives ρ→1.0 and the half-shift cap fires. Measured on Dec rows: TF>HUAFEI −33 %, BLB>FENI KM0 −39 %, BLB>HUAFEI −23 % vs the same row with its saved loader count. The model class is not hurting us; **defaulted loaders are.** (Tenant rows are flow-only and never touch the queue — verified.)

**Recommendation R1 (cheap, ~10 lines):** replace `erlang_c` with the exact birth–death machine-repair recursion (drop the cap entirely — a closed system has no instability), and add the match-factor throughput bound `trips/hr ≤ min(N/T_cycle, c·μ)` as an assertion. Same runtime, removes the cliff.
**Recommendation R2 (safety):** loud warning (or refusal) when loaders default on rows with N ≥ 50 — today this silently costs tens of percent.

## 4. Road congestion: BPR audit

Transport literature consensus (Akçelik 1991; Small & Chu 2003; Hadi et al. 2013 FDOT; Pan et al. 2023 ASCE): static BPR's over-capacity branch is a mathematical extrapolation with no physics — real oversaturation delay grows with *how long* demand exceeds capacity, which a static curve cannot express. FDOT's explicit rule: BPR below capacity, Akçelik's time-dependent form above.

**Our measured operating point:** across all 93 rows of six frozen plans, **max road v/c = 0.12** and every BPR penalty = 0.0 min. The engine's binding constraint everywhere is the loader/cycle side, not the road. So the "v/c 3–5" regime the old BPR2 exploded on comes from *hypothetical* what-ifs, not saved plans.

My numeric comparison (BLB>HUAFEI, c=400/hr, T=12 h): BPR and Akçelik agree within 12 % up to v/c≈1.1, then diverge structurally (at v/c=3: BPR says 1,841 min, Akçelik 860 min — and only Akçelik's number means anything, because it scales with the oversaturation duration).

**Recommendation R3 (one function):** piecewise — keep BPR for v/c<1, Akçelik `t = t_free + 0.25T[(x−1)+√((x−1)²+8Jx/(cT))]` above. Only affects what-if extremes today, but makes the corridor readout honest when someone plans past capacity.
**Recommendation R4 (data, no code):** our c = slowest-bin/50 m is a *safety-rule ceiling*, not measured saturation flow (Tannant & Regensburg 2001). Fit observed max sustained trucks/hr per section from our GPS history (Kucharski & Drabicki 2017 method) and compare. If measured < rule-based, capacity is optimistic everywhere.

## 5. Bunching: the literature's #1 mine-road mechanism

Field evidence (Krzyzanowska 2007, Venetia mixed-fleet; Zeng et al. 2019 no-overtaking DES; Soofastaei 2016 payload-variance) says platooning behind the slowest truck — not v/c — dominates congestion on shared single-lane mine roads with heterogeneous fleets. Our bunching term exists but is small (4.5 min on a 140-min haul).

**Recommendation R5:** moving-bottleneck upgrade — per section, pace = min(model speed, slowest-active-truck speed sampled from contractor speed distributions). Directly usable: we already track per-contractor speed distributions per segment. This is where the multi-contractor + tenant mix actually bites, and it is unpublished territory (our data could support a paper).

## 6. Accuracy runway

Published benchmarks put us at parity (≈20 % MAPE walk-forward). The literature's best next step for accuracy-per-effort (horse's survey): **GBM residual model** on top of the analytical prediction (features: rain, shift, contractor mix, loaders, route) — published deltas suggest 20 % → ~14–17 %. We already have the residual-diagnostics scaffolding (`data/residual_diagnostics.json`).

Note: I tested the closed-fleet swap against 2,124 measured route-days — at our MF≤0.24 operating point it changes nothing (as theory predicts), confirming the 20 % MAPE residual lives in *variability* (rain, availability, dispatch) not queue-model bias. That is exactly what a residual ML layer targets.

## 7. Priority list

| # | Change | Effort | Impact |
|---|---|---|---|
| R2 | Warn/refuse on defaulted loaders (N≥50) | trivial | kills live −23…−39 % errors |
| R1 | Machine-repair queue swap + MF bound | small | removes ρ≥1 cliff, correct model class |
| R4 | Measured-saturation capacity check from GPS | analysis only | validates every v/c we print |
| R3 | Akçelik tail above v/c=1 | small | honest oversaturation what-ifs |
| R5 | Moving-bottleneck bunching | medium | the real mechanism per field studies |
| R6 | GBM residual layer | medium | 20 %→~15 % MAPE per published deltas |

---

## Post-audit implementation log (2026-08-26, same day)

**R1+R2 shipped** (`18e8347`): machine-repair M/M/c//N queue + loader-default guard. Production rows within 0.2%, cliff removed, MAPE flat-to-better on 2,124 measured days. A follow-up (`e521aa7`) memoises the O(N) recursion on exact argument keys after the 500-DT tenant row proved 457× slower inside the 120-sweep pricing fixed point (and a first, rounded-key cache broke J79 parity by one truck — exact keys fixed it).

**R3 shipped** (this commit): `bpr_travel_min` is now piecewise — BPR below v/c=1, Akçelik time-dependent above, `period_h` = the plan's shift. Verified continuous and monotone across the seam (sweep x=0.5…5.0); at x=3 the honest answer is 881 min vs the polynomial's 1,841. J = 2α so per-route BPR calibration carries over.

**R4 answered with data** (this commit): observed max sustained flow per road, from 109k segment-hour GPS records (`congestion_seg_hourly.csv`, TRUCK_N per segment-hour-direction):

| Road | hours | p95 | p99 | max obs trucks/hr | rule capacity |
|---|---|---|---|---|---|
| KR | 20,185 | 46 | 60 | **83** | 400–600 |
| TF | 16,002 | 35 | 45 | 67 | 400–600 |
| CBB | 6,296 | 30–34 | 41–49 | 70 | 400–600 |
| BLB | 5,962 | 20 | 27 | 49 | 400–600 |

**Conclusion: the corridor has never been loaded past ~14% of the rule capacity.** Two consequences: (1) the 50 m headway capacity is *unvalidatable* from history — no observed hour comes close, so neither confirmation nor refutation is possible; (2) every v/c the app prints is demand against a never-tested ceiling, which is fine for ranking plans but means the oversaturation regime (where R3 matters) is purely hypothetical today. The engine's existing `vc_vs_observed_peak` metric is the honest companion number. If capacity validation ever matters, it needs a deliberately dense operating period, not more history.

**Still open (need owner sign-off, larger design):**
- **R5** moving-bottleneck bunching — the literature's dominant mechanism; medium effort; our per-contractor speed distributions make it feasible.
- **R6** GBM residual layer — published deltas suggest 20%→~15% MAPE; scaffolding exists in `data/residual_diagnostics.json`.
