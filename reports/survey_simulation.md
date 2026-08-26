# Literature Survey: Predicting Fleet-on-Road Performance in Mining Haulage
## DES vs Analytical vs ML — and what a fast production-planning tool should adopt

*Survey date: 2026-08-26. Compiled from OpenAlex / Crossref / Semantic Scholar indexed literature plus full-text reads of open-access papers. Context: our tool is an analytical hybrid (physics cycle + Erlang-C queueing + BPR road-congestion penalty), calibrated per-route from a season of dispatch + GPS data, ~20% MAPE on trips/truck/day, R² > 0.7 backtest, millisecond whole-day pricing.*

---

## Executive verdict (TL;DR)

1. **The literature does not crown a single winner.** DES dominates *academic* truck-shovel studies by volume; queueing/analytical models are the recognized fast-approximation tier; ML on FMS/GPS telemetry is the fastest-growing tier since ~2018. The emerging consensus is **hybrid**: analytical or ML models calibrated on telemetry for speed, DES reserved for design-time questions.
2. **Your ~20% MAPE on trips/truck/day is within the credible published band.** Published cycle-time / production prediction errors range roughly 8–25% MAPE depending on aggregation level and horizon (see §4). Nobody publishing day-ahead *plan-level* (route × fleet) throughput predictions on real shared-road data reports dramatically better than ~10–15% MAPE, and most DES validations are of the "within 5–10% of historical *aggregate* production" variety — a much weaker test than per-day walk-forward backtesting.
3. **Analytical-hybrid is the right architecture for a millisecond planning loop.** DES runs in minutes-to-hours per scenario and its extra fidelity (explicit bunching, dispatch logic, breakdown events) matters most for *design* questions, not day-plan pricing. The literature that combines queueing + calibration + data residuals (see §3) supports exactly your architecture.
4. **Highest accuracy-per-effort addition:** an **ML residual model on top of the physics/queueing core** (physics-informed residual learning), using features you already have (rain, shift, contractor mix, loader type, route). Second best: replace steady-state Erlang-C with a **finite-source (machine-repair / Erlang-loss) queue**, since mining fleets are small-N closed systems where infinite-source Erlang-C overestimates queue growth at high utilization. Both are supported directly by published results (§3, §5).

---

## 1. Discrete-event simulation (DES) in mining haulage

### 1.1 What the DES literature covers

DES is the historically dominant technique for truck-shovel analysis, going back to GPSS models of the 1960s–80s (Sturgul's mine-simulation lineage) and continuing in Arena, AnyLogic, FlexSim, GPSS/H, Simio and custom engines:

- **Torkamani & Askari-Nasab (2015)**, "A linkage of truck-and-shovel operations to short-term mine plans using discrete-event simulation," *Int. J. Mining and Mineral Engineering*. https://doi.org/10.1504/ijmme.2015.070367 — verified DES linked to MILP allocation; explicitly criticizes prior DES for treating shovels as continuously available and ignoring mine-plan linkage.
- **Upadhyay & Askari-Nasab (2017)**, "Simulation and optimization approach for uncertainty-based short-term planning in open pit mines," *Int. J. Mining Science and Technology*. https://doi.org/10.1016/j.ijmst.2017.12.003 — the canonical sim-opt framework: Arena-family DES + goal programming, iron-ore case study; used for *robust short-term scheduling*, not fast plan pricing.
- **Tabesh, Upadhyay & Askari-Nasab (2016)**, "Discrete Event Simulation of Truck-Shovel Operations in Open Pit Mines," MOL Report, U. Alberta. https://sites.ualberta.ca/MOL/DataFiles/2016_Papers/2016_MOL_Paper_201.pdf
- **Jung, Baek & Choi (2020)**, "Simulation and Real-time Visualization of Truck-Loader Haulage Systems in an Open Pit Mine using AnyLogic," *J. Korean Soc. Mineral and Energy Resources Engineers*. https://doi.org/10.32390/ksmer.2020.57.1.045 — AnyLogic DES with field-measured time parameters.
- **Huayanca, Bujaico & Delgado (2023)**, "Application of Discrete-Event Simulation for Truck Fleet Estimation at an Open-Pit Copper Mine in Peru," *Applied Sciences*. https://doi.org/10.3390/app13074093 — stochastic DES vs the mine's deterministic spreadsheet: DES predicted *longer* cycle times and *more* trucks needed because it captures queuing; i.e., deterministic physics-only models are systematically optimistic.
- **Baafi & Zeng (2019)**, "A Discrete-Event Simulation for a Truck-Shovel System," *MPES 2018 Proceedings*, Springer. https://doi.org/10.1007/978-3-319-99220-4_22 — flexible truck-shovel DES template.
- **Park et al. / Jung & Choi (2026)**, "Discrete-Event Simulation of a Raw Ore Haulage System in an Open-Pit Limestone Mine Using ICT Monitoring Data and Time-Study Measurements," *J. KSMER*. https://doi.org/10.32390/ksmer.2026.63.3.286 — recent trend: DES input distributions fitted from ICT/FMS monitoring data rather than stopwatch studies.
- **Manríquez et al. (2018)**, "Discrete event simulation to design open-pit mine production policy in the event of snowfall," *Int. J. Mining, Reclamation and Environment*. https://doi.org/10.1080/17480930.2018.1514963 — weather-disruption policy design via DES (analogue of your rain-dwell effects).
- **Meneses & Sepúlveda (2023)**, "Modeling Productivity Reduction and Fuel Consumption in Open-Pit Mining Trucks by Considering the Temporary Deterioration of Mining Roads through DES," *Mining* 3(1). https://doi.org/10.3390/mining3010006 — road-condition (rolling-resistance) deterioration inside DES; ignoring road state overestimated productivity by up to 600 t/h on a 10-truck fleet, i.e., road-state effects are first-order (supports your BPR/road-penalty term).

### 1.2 What DES captures that analytical models miss

Consistently cited DES-only capabilities:

- **Truck bunching / no-overtaking dynamics.** Chanda & Gardiner (2010, below) note simulation captures platooning; **"A discrete-event model to simulate the effect of truck bunching due to payload variance on cycle time, hauled mine materials and fuel consumption"** (2016), *Int. J. Mining Science and Technology*, https://doi.org/10.1016/j.ijmst.2016.05.047 — payload variance → speed variance → bunching on single-lane ramps; a mean-value physics model cannot represent this without a correction term (your BPR penalty is exactly such a term).
- **Dispatch logic.** DES can embed the actual dispatcher (fixed vs dynamic; DISPATCH-style LP + heuristics). E.g., **"Simulation Based Investigation of Different Fleet Management Paradigms in Open Pit Mines — Sungun Copper Mine"** (2015), *Archives of Mining Sciences*, https://doi.org/10.1515/amsc-2015-0013. Analytical models assume an average allocation policy.
- **Stochastic breakdowns and crusher/dump capacity coupling.** Park & Choi (2014), "Simulation of Shovel-Truck Haulage Systems in Open-pit Mines Considering Breakdown of Trucks and Crusher Capacity," *Tunnel and Underground Space* 24(1), https://doi.org/10.7474/tus.2014.24.1.001 (GPSS/H).
- **Correlated inputs.** **Que, Anani & Awuah-Offei (2016)**, "Effect of ignoring input correlation on truck–shovel simulation," *Int. J. Mining, Reclamation and Environment*, https://doi.org/10.1080/17480930.2015.1099188 — proves load-time/payload/travel-time correlations exist and that ignoring them biases DES outputs; the same warning applies to analytical models calibrated from marginal distributions.
- **Intersections and network micro-detail.** **Jaoua, Riopel & Gamache (2009)**, "A framework for realistic microscopic modelling of surface mining transportation systems," *Int. J. Mining, Reclamation and Environment*, https://doi.org/10.1080/17480930802351479 — argues coarse DES is insufficient for congested networks and proposes traffic-microsimulation-grade modeling (intersection priority, lane discipline) when congestion control matters.

### 1.3 DES validation accuracy and runtime — what is actually reported

- Validation is typically **against historical aggregate production or cycle-time means**, and the accepted bar in the mining DES literature is agreement **within ~5–10% of historical KPIs** (e.g., the U. Alberta MOL reports and Torkamani & Askari-Nasab 2015 verify tonnage/cycle-time agreement in that band; Jung & Choi's AnyLogic and GPSS/H models validate mean cycle components against time studies). This is *in-sample replication*, not out-of-sample forecasting — weaker evidence than a walk-forward 20% MAPE on daily trips/truck.
- **Chanda & Gardiner (2010)** (§2) is the rare head-to-head: on short-cycle pits, *simulation underestimated actual truck cycle times* and was **not better than regression/ANN** for prediction.
- **Runtime:** replications of full-shift or multi-month DES take seconds-to-minutes each, and studies routinely need 10–100+ replications plus warm-up (e.g., Upadhyay & Askari-Nasab 2017 run scenario batteries; sim-opt loops in the 2026 "Hybrid DES and HWOA–NSGA-II" fleet-design paper, *Mining, Metallurgy & Exploration*, https://doi.org/10.1007/s42461-026-01496-1, wrap DES in an evolutionary optimizer precisely because a single evaluation is expensive). No published mining DES prices a full route×fleet×loader day-plan in milliseconds; that is structurally out of reach without a surrogate (§3).

**Takeaway:** DES earns its cost for *design* decisions (fleet sizing, IPCC vs trucks, trolley assist, snow policy, road-maintenance frequency) and for validating dispatch logic. As a planning-loop engine it is 10³–10⁶× too slow, which is why the surrogate/metamodel literature exists.

---

## 2. Data-driven / ML prediction from GPS & FMS telemetry

### 2.1 Key papers and reported accuracy

- **Chanda & Gardiner (2010)**, "A comparative study of truck cycle time prediction methods in open-pit mining," *Engineering, Construction and Architectural Management* 17(5). https://doi.org/10.1108/09699981011074556 — **the foundational comparison**: computer simulation vs neural network vs multiple regression against FMS-recorded actual cycle times. Finding: simulation *underestimated* cycle times on short cycles; NN and MR matched or beat simulation for *prediction*. This is the most-cited justification for data-calibrated (rather than pure-sim) prediction — i.e., for your approach.
- **Sun, Zhang, Tian et al. (2018)**, "The Use of a Machine Learning Method to Predict the Real-Time Link Travel Time of Open-Pit Trucks," *Mathematical Problems in Engineering*. https://doi.org/10.1155/2018/4368045 — kNN/SVM/RF per *road link* at Fushun West open-pit; SVM/RF best; **~15.8% accuracy gain over the traditional mean-value method; adding meteorological features added ~5.1%**; link-level beats route-level modeling. Directly validates (a) per-route/per-link calibration and (b) rain as a feature.
- **Zhao, Gao & Ren (2025)**, "Prediction of open-pit mine truck travel time based on LSTM-TabTransformer," *Scientific Reports* 15:7427. https://doi.org/10.1038/s41598-025-88543-x — 200k dispatch records + weather-station data, Inner Mongolia coal mine; hybrid attention+LSTM beats single models; fitted-line slope 0.96 vs BERT 0.04. Notable list of travel-time drivers: material, road quality, weather, working period, truck type, distance, driver, *traffic density, cross-traffic, temporary road control* — matching your corridor-congestion concerns.
- **Wahyudi & Warmada (2025)**, "Implementation of Machine Learning Methods to Predict the Travel Time of Open-Pit Trucks Based on Fleet Management System," *IOP Conf. Ser.: Earth Environ. Sci.* 1517 012012. https://doi.org/10.1088/1755-1315/1517/1/012012 — **Indonesian coal (Lati open-pit, Berau)**: FMS dispatch + 8 meteorological parameters + hauling distance/grade; kNN ≈ 85.5%, SVR ≈ 85.4%, LSTM best ≈ **86.2% accuracy without weather → 88.2% with weather** (NRMSE-based). I.e., ~12–15% error on travel time with weather included, on a haul-road setting very close to yours.
- **Baek & Choi (2020)**, "Deep Neural Network for Predicting Ore Production by Truck-Haulage Systems in Open-Pit Mines," *Applied Sciences* 10(5):1657. https://doi.org/10.3390/app10051657 — DNN on two months of packet data; session-level (half-day) ore-production prediction; also earlier underground version (2019, *Applied Sciences* 9:4180, https://doi.org/10.3390/app9194180) reporting **MAPE ≈ 8–10% for shift-level production** with R² ~ 0.9 in-sample.
- **Choi, Nguyen & Bui (2020, 2022)**: "Estimating Ore Production in Open-pit Mines Using Various Machine Learning Algorithms Based on a Truck-Haulage System and Support of IoT," *Natural Resources Research* 30, https://doi.org/10.1007/s11053-020-09766-5; and "Optimization of haulage-truck system performance for ore production in open-pit mines using big data and machine learning-based methods," *Resources Policy* 75, https://doi.org/10.1016/j.resourpol.2021.102522 — big-data benchmark of RF/SVM/GBM/DNN etc. on FMS data; tree ensembles and DNN consistently in the **R² 0.85–0.95** band for production estimation with rich features (in-sample/random-split validation, note — not walk-forward).
- **Zhang et al. (2023)**, "Preprocessing Large Datasets Using Gaussian Mixture Modelling to Improve Prediction Accuracy of Truck Productivity at Mine Sites," *Archives of Mining Sciences* 67(4). https://doi.org/10.24425/ams.2022.143680 — regime clustering (GMM latent classes) before regression materially improves truck-productivity prediction on large noisy FMS datasets; supports your matched-day/regime-analogue idea (rain vs dry regimes are latent classes).
- **Sun-lineage ensemble work** (cited in Zhao 2025): HGSVMA ensemble cut MSE 77% / MAE 30% vs single SVM and raised R² 4.5% — ensembles > single learners for travel time.
- Underground analogue with beacons instead of GPS: **"Predicting Haul Truck Travel Times in Underground Mines" (2025)**, *Mining, Metallurgy & Exploration*. https://doi.org/10.1007/s42461-025-01293-2.

### 2.2 ML vs physics vs DES — the comparative signal

- ML beats *mean-value/physics-only* baselines by ~10–20% relative error whenever congestion, weather, and driver/traffic variability matter (Sun 2018; Wahyudi 2025; Zhao 2025).
- ML models in this literature are almost all **point-prediction models of components** (link travel time, cycle time, shift production). Almost none of them price a *counterfactual plan* (different fleet/loader assignment than history) — that requires a structural model (queueing or DES). This is the fundamental argument for your hybrid: **pure ML interpolates history; it cannot answer "what if we add 5 trucks to route B,"** because fleet size → congestion → cycle time feedback is outside its training support. The queueing/BPR core gives you the structural response surface; data calibration gives the level accuracy.

---

## 3. Hybrid approaches: queueing + simulation + ML surrogates

### 3.1 Analytical queueing lineage (your Erlang-C ancestry)

- **Koenigsberg (1958 onward)** established cyclic-queue models of mine haulage; the classic textbook consolidation is **Czaplicki (2008), *Shovel-Truck Systems: Modelling, Analysis and Calculations*, CRC Press/Taylor & Francis. https://doi.org/10.1201/9780203881248** — full machine-repair/Erlang treatment of shovel-truck systems, including spare-fleet and repair-shop sizing.
- **Krause & Musingwini (2007)**, "Modelling open pit shovel-truck systems using the Machine Repair Model," *Journal of the Southern African Institute of Mining and Metallurgy* 107(8), 469–476. https://www.saimm.co.za/Journal/v107n08p469.pdf — benchmark the **finite-source Machine Repair Model** against Arena simulation and standard estimators (Elbrond, FPC/Talpac-style): MRM tracks simulation closely at a tiny fraction of the cost. **This is the single most relevant citation for your architecture choice**: a calibrated finite-source queue ≈ DES for cycle/match-factor outputs.
- **Ercelebi & Bascetin (2009)**, "Optimization of shovel-truck system for surface mining," *JSAIMM* 109(7). https://www.saimm.co.za/Journal/v109n07p433.pdf — closed queuing network for allocation + dispatch optimization; explicit runtime argument for analytical models in planning.
- **May (2013)**, "Applications of Queuing Theory for Open-Pit Truck/Shovel Haulage Systems," MSc thesis, Virginia Tech. http://hdl.handle.net/10919/23098 — validates queueing against a real pit and catalogs where queueing assumptions (exponential service, steady state) bend.
- Note common to this lineage: mining fleets are **closed, finite-source systems** (N trucks circulating), so the correct queue is M/M/c with finite calling population (machine-repair) rather than open-arrival Erlang-C. At high utilization on small fleets, Erlang-C (infinite source) overstates waiting because it ignores that a queued truck depletes the arrival stream. If your per-route fleets are ≤15 trucks, switching Erlang-C → finite-source is a low-effort, structurally-correct upgrade (closed-form, still milliseconds).

### 3.2 ML + DES hybrids and surrogates

- **Choi's group (2023)**, "Prediction of Ore Production in a Limestone Underground Mine by Combining Machine Learning and Discrete Event Simulation Techniques," *Minerals* 13(6):830. https://doi.org/10.3390/min13060830 — **ML predicts cycle time (PSO-SVM: MAE 2.79 min, RMSE 3.79 min, R² 0.68), DES consumes the ML-predicted cycle times to produce ore-production forecasts** per truck/section/shift. Note their component-level R² 0.68 ≈ your R² 0.7 backtest — published state of the art on real telemetry is *not* dramatically better than yours.
- **"Simulation-Based Multiobjective Optimization of Open-Pit Mine Haulage System: A Modified-NBI Method and Meta Modeling Approach" (2022)**, *Complexity*. https://doi.org/10.1155/2022/3540736 — fits a **metamodel (surrogate) of the haulage DES** so the optimizer can query cheaply; the direct precedent for "surrogate of DES for fast planning loops."
- **"Recent Trends in the Optimization of Logistics Systems Through Discrete-Event Simulation and Deep Learning" (2025)**, *Algorithms* 18(9):573. https://doi.org/10.3390/a18090573 — review of DES+DL coupling patterns (DL as surrogate, DL as policy inside DES, DES as training env).
- **Brailsford et al. (2019)**, "Hybrid simulation modelling in operational research: A state-of-the-art review," *European Journal of Operational Research* 278(3). https://doi.org/10.1016/j.ejor.2018.10.025 — taxonomy for combining DES/SD/ABM; documents that hybridization is the field-wide trajectory.
- RL-on-DES (DES as gym): **Noriega & Pourrahimian (2024)**, "Shovel allocation and scheduling for open-pit mining using deep reinforcement learning," *Int. J. Mining, Reclamation and Environment*, https://doi.org/10.1080/17480930.2024.2323325; and **"Deep Reinforcement Learning based real-time open-pit mining truck dispatching system" (2024)**, *Computers & Operations Research*, https://doi.org/10.1016/j.cor.2024.106815 — both build a DES trained-against; underscores that even ML-heavy groups keep a structural simulator for counterfactuals.
- Traffic-theory bridge for your BPR term: **Cheng, ... (2022)**, "A meso-to-macro cross-resolution performance approach for connecting polynomial arrival queue model to volume-delay function with inflow demand-to-capacity ratio," *Multimodal Transportation* 1(2). https://doi.org/10.1016/j.multra.2022.100017 — formally connects queueing models to BPR-style volume-delay functions; your Erlang-C + BPR pairing has a defensible theoretical basis in this line, and BPR-parameter calibration practice is documented in **"Calibration of Volume-Delay Functions for Traffic Assignment in Travel Demand Models" (2012)**, TRB 91st Annual Meeting.

**Takeaway:** the literature's hybrid patterns are (a) ML component → structural model (Choi 2023), (b) surrogate of DES (Complexity 2022), (c) queueing ≈ DES for planning (Krause & Musingwini 2007). Your architecture is pattern (a)+(c) with a traffic-engineering congestion term — defensible and, for millisecond pricing, the only game in town.

---

## 4. Benchmarks: how good is 20% MAPE / R² > 0.7?

| Study | Target | Method | Reported accuracy | Validation style |
|---|---|---|---|---|
| Chanda & Gardiner 2010 | truck cycle time | sim vs ANN vs MR | sim *underestimates*; ANN/MR win; errors in the ~10–20% band on cycle time | vs FMS actuals, same mine |
| Sun et al. 2018 | link travel time | SVM/RF | ~16% better than mean-method; +5% from weather | holdout on real links |
| Wahyudi & Warmada 2025 | travel time (coal, Indonesia) | LSTM/SVR/kNN | ~86–88% "accuracy" (≈12–14% NRMSE error), weather adds ~2% | holdout, one site |
| Choi group 2023 (Minerals) | truck cycle time | PSO-SVM | MAE 2.79 min, **R² 0.68** | holdout, 15 weeks beacons |
| Baek & Choi 2019/2020 | shift/session ore production | DNN | MAPE ≈ 8–10%, R² ~0.9 (in-sample-ish) | random split, 1–2 months |
| Choi/Nguyen/Bui 2020–22 | ore production | RF/GBM/DNN | R² 0.85–0.95 | random split |
| Torkamani 2015 / typical DES | aggregate production replication | DES | within ~5–10% of historicals | in-sample replication |
| **Yours** | **trips/truck/day, plan-level, counterfactual-capable** | physics+Erlang-C+BPR, per-route calibrated | **~20% MAPE, R²>0.7** | **walk-forward season backtest** |

Reading of the table:

- Component-level (single link/cycle) predictions get to 10–15% error with rich telemetry. Day-level *plan* outputs compound queueing, availability, weather, and dispatch noise; **20% MAPE at day granularity is broadly consistent with a component-level 10–15%**, especially on a multi-user shared road you don't control. The R² 0.68 of the best-published hybrid cycle-time model (Choi 2023) says your R² > 0.7 backtest is at parity with SOTA on comparable real data.
- Important honesty check from the validation-methodology literature: most mining ML papers use **random train/test splits, which leak temporal information**. Walk-forward / blocked temporal CV is the correct standard: **Bergmeir & Benítez (2012)**, "On the use of cross-validation for time series predictor evaluation," *Information Sciences* 191:192–213, https://doi.org/10.1016/j.ins.2011.12.028 (and Tashman 2000, "Out-of-sample tests of forecasting accuracy: an analysis and review," *Int. J. Forecasting* 16(4):437–450, https://doi.org/10.1016/S0169-2070(00)00065-0). **Your walk-forward 20% is a harder test than most of the 8–12% numbers above.** For simulation-side validity methodology, the standard citation is **Sargent (2013)**, "Verification and validation of simulation models," *Journal of Simulation* 7:12–24, https://doi.org/10.1057/jos.2012.20 (also WSC tutorials, e.g., https://doi.org/10.1109/wsc.2007.4419595): operational validity = comparing model outputs to system data over the *conditions of intended use* — which your matched-day analogue approach (compare plan-day vs most-similar historical day by rain/fleet/route regime) implements; the GMM regime-clustering result (Archives of Mining Sciences 2023, above) shows regime-conditioning demonstrably improves accuracy.

---

## 5. Shared multi-user haul roads and transfer-yard (rehandle) flows

This is the thinnest slice of the literature — a real gap your tool sits in:

- **Mixed fleets on shared roads:** Bolton & co. (2007), "The impact of mixed fleet hauling on mining operations at Venetia mine," *JSAIMM* 107(2). https://www.saimm.co.za/Journal/v107n02p073.pdf — heterogeneous truck classes on shared ramps create speed-differential interference and bunching; quantifies productivity loss from mixing. Closest published analogue to contractor + tenant mixed traffic.
- **Single-lane/ramp interaction:** "Fundamental behaviours of production traffic in underground mine haulage ramps" (2015), *Int. J. Mining Science and Technology* 25(1). https://doi.org/10.1016/j.ijmst.2014.11.006 — traffic-flow (car-following) treatment of mine ramps; supports using road-traffic constructs (like BPR) rather than pure queueing for corridor segments.
- **GA dispatch with one-lane roads:** "A Genetic Algorithm for Truck Dispatching in Mining" (2018), *EPiC Series in Computing*. https://doi.org/10.29007/n11t — explicitly models one-lane road contention in dispatch optimization.
- **Microscopic corridor modeling:** Jaoua, Riopel & Gamache 2009 (§1.2) is the standard citation for when corridor congestion demands micro-simulation.
- **Coal chain / contractor systems (Indonesia-like):** "Towards resilience in the value chain of coal mining upstream: an agent-based modeling and simulation to improve coal discrepancy" (2024), *Discover Applied Sciences* 6. https://doi.org/10.1007/s42452-024-06375-2 — ABM of upstream coal chain incl. hauling contractors, weather disruptions, and plan-vs-actual "discrepancy" (their term for your plan-adherence gap).
- **Rehandle / stockpile flows:** rehandle is modeled mostly at the *mine-planning optimization* level, not the traffic level: Montiel & Dimitrakopoulos (2015), "Optimizing mining complexes with multiple processing and transportation alternatives," *European J. Operational Research* 247(1):166–178, https://doi.org/10.1016/j.ejor.2015.05.002 (stockpiles/rehandle as network nodes in a mining-complex flow model); "Modelling Large Heaped Fill Stockpiles Using FMS Data" (2021), *Minerals* 11(6):636, https://doi.org/10.3390/min11060636 (FMS-data-driven stockpile modeling). Treating POS transfer yards as extra queueing nodes with their own service distributions is consistent with how the mining-complex literature abstracts them; nobody has published a dedicated "transfer-yard traffic" study — a publishable niche for you.
- **Rain effects:** beyond Sun 2018 and Wahyudi 2025 (weather features worth 2–5% accuracy), see "Investigating The Effects of Rainy Season On Open Cast Mining Operation: Wescoal Khanyisa Colliery" (2021, preprint), https://doi.org/10.21203/rs.3.rs-870740/v1, and the DES road-deterioration paper (Meneses & Sepúlveda 2023, §1.1) for the mechanism (rolling resistance / dwell).

---

## 6. Verdict and recommendations

### Is analytical-hybrid the right architecture vs DES for a fast planning tool?

**Yes — and the literature supports it on three independent grounds:**

1. **Speed:** no DES in the literature evaluates a plan in milliseconds; every fast planning/optimization loop that uses DES does so through a surrogate/metamodel (Complexity 2022; Algorithms 2025) — i.e., they end up with what you already have, minus your physics interpretability.
2. **Prediction accuracy:** the only direct head-to-head (Chanda & Gardiner 2010) found DES *not superior* to data-fitted models for cycle-time prediction; the finite-source queueing vs Arena comparison (Krause & Musingwini 2007) found the analytical model reproduces simulation outputs; the best hybrid ML+DES cycle-time R² (0.68, Choi 2023) is at parity with your backtest.
3. **Counterfactual validity:** pure ML can't extrapolate fleet-size changes; your queueing+BPR core provides the structural response that ML lacks, and per-route calibration provides the level accuracy that pure DES/physics lacks.

**Keep DES in reserve** for occasional *design* studies (new corridor, POS yard relocation, contractor-mix policy, fleet purchase), where its explicit modeling of dispatch logic, breakdowns, and bunching earns its runtime — and consider using your analytical model as the screening layer and DES as the verification layer for big decisions (the standard sim-opt pattern of Upadhyay & Askari-Nasab 2017).

### The one addition with the most accuracy per effort

**A residual ML layer (GBM) on top of the analytical prediction**, trained on your season of dispatch+GPS data with features: rain/dwell state, shift (day/night), contractor mix and third-party traffic proxy, loader type, route, season/day-of-week. Rationale from the literature:

- Weather features alone are worth 2–5% (Sun 2018; Wahyudi 2025); regime conditioning (GMM latent classes) gives further material gains (Archives of Mining Sciences 2023); ensembles beat single models by large margins (HGSVMA results in Zhao 2025).
- Residual learning preserves your structural counterfactual validity (queue+BPR still drives the response to fleet changes; ML only corrects level/regime bias), matching hybrid pattern (a) of §3.2.
- Expected effect based on published deltas: 20% MAPE → plausibly 14–17% on matched-regime days, for days of work, no architecture change.

**Second-priority upgrades, in accuracy-per-effort order:**
1. **Erlang-C → finite-source (machine-repair) queue** at loaders and dump/yard nodes (closed-form, hours of work; corrects known small-fleet bias; Krause & Musingwini 2007, Czaplicki 2008).
2. **Payload/speed-variance bunching correction** on the shared corridor: add a variance-driven term to the BPR penalty (IJMST 2016 bunching paper gives the mechanism), calibrated from your GPS speed distributions.
3. **Input-correlation-aware calibration** (Que et al. 2016): calibrate joint distributions (load time × payload × travel time), not marginals.
4. Only then consider a lightweight DES of the single shared corridor (intersections + one-lane segments only) as an offline calibrator of BPR parameters per rain regime.

### Validation-methodology recommendations (per literature)

- Keep **walk-forward** (Bergmeir & Benítez 2012; Tashman 2000); report MAPE by regime (rain/dry, shift) rather than pooled.
- Frame validation as Sargent-style **operational validity over the domain of intended use** (Sargent 2013); document the applicability envelope (fleet ranges, rain states seen in calibration data).
- Adopt **matched-day analogues** explicitly as a k-nearest-regime benchmark: your model should beat the "most similar historical day" predictor; the GMM-regime paper shows this is the right null model for noisy FMS data.

---

## Citation index (rough BibTeX-key style)

1. Torkamani & Askari-Nasab 2015, IJMME — doi:10.1504/ijmme.2015.070367
2. Upadhyay & Askari-Nasab 2017, IJMST — doi:10.1016/j.ijmst.2017.12.003
3. Tabesh, Upadhyay & Askari-Nasab 2016, MOL Report — sites.ualberta.ca/MOL
4. Jung, Baek & Choi 2020, J.KSMER (AnyLogic) — doi:10.32390/ksmer.2020.57.1.045
5. Huayanca et al. 2023, Applied Sciences (DES Peru) — doi:10.3390/app13074093
6. Baafi & Zeng 2019, MPES — doi:10.1007/978-3-319-99220-4_22
7. Jung & Choi 2026, J.KSMER (DES + ICT data) — doi:10.32390/ksmer.2026.63.3.286
8. Manríquez et al. 2018, IJMRE (snowfall DES) — doi:10.1080/17480930.2018.1514963
9. Meneses & Sepúlveda 2023, Mining (road deterioration DES) — doi:10.3390/mining3010006
10. IJMST 2016 (truck bunching DES) — doi:10.1016/j.ijmst.2016.05.047
11. Archives of Mining Sciences 2015 (Sungun fleet management sim) — doi:10.1515/amsc-2015-0013
12. Park & Choi 2014, Tunnel & Underground Space (GPSS/H breakdowns) — doi:10.7474/tus.2014.24.1.001
13. Que, Anani & Awuah-Offei 2016, IJMRE — doi:10.1080/17480930.2015.1099188
14. Jaoua, Riopel & Gamache 2009, IJMRE — doi:10.1080/17480930802351479
15. Chanda & Gardiner 2010, ECAM — doi:10.1108/09699981011074556
16. Sun et al. 2018, Math. Probl. Eng. — doi:10.1155/2018/4368045
17. Zhao, Gao & Ren 2025, Scientific Reports — doi:10.1038/s41598-025-88543-x
18. Wahyudi & Warmada 2025, IOP EES — doi:10.1088/1755-1315/1517/1/012012
19. Baek & Choi 2020, Applied Sciences — doi:10.3390/app10051657
20. Baek & Choi 2019, Applied Sciences (underground DNN) — doi:10.3390/app9194180
21. Choi, Nguyen & Bui 2020, Natural Resources Research — doi:10.1007/s11053-020-09766-5
22. Choi, Nguyen & Bui 2022, Resources Policy — doi:10.1016/j.resourpol.2021.102522
23. Archives of Mining Sciences 2023 (GMM preprocessing) — doi:10.24425/ams.2022.143680
24. MM&E 2025 (underground travel-time prediction) — doi:10.1007/s42461-025-01293-2
25. Czaplicki 2008, Shovel-Truck Systems, CRC — doi:10.1201/9780203881248
26. Krause & Musingwini 2007, JSAIMM 107(8) 469–476 — saimm.co.za/Journal/v107n08p469.pdf
27. Ercelebi & Bascetin 2009, JSAIMM 109(7) — saimm.co.za/Journal/v109n07p433.pdf
28. May 2013, Virginia Tech MSc (queueing) — hdl.handle.net/10919/23098
29. Choi group 2023, Minerals (ML+DES hybrid) — doi:10.3390/min13060830
30. Complexity 2022 (DES metamodel NBI) — doi:10.1155/2022/3540736
31. Algorithms 2025 (DES+DL review) — doi:10.3390/a18090573
32. Brailsford et al. 2019, EJOR (hybrid simulation review) — doi:10.1016/j.ejor.2018.10.025
33. Noriega & Pourrahimian 2024, IJMRE (DRL shovel allocation) — doi:10.1080/17480930.2024.2323325
34. C&OR 2024 (DRL dispatching) — doi:10.1016/j.cor.2024.106815
35. Multimodal Transportation 2022 (queue↔BPR bridge) — doi:10.1016/j.multra.2022.100017
36. Bergmeir & Benítez 2012, Information Sciences — doi:10.1016/j.ins.2011.12.028
37. Tashman 2000, Int. J. Forecasting — doi:10.1016/S0169-2070(00)00065-0
38. Sargent 2013, Journal of Simulation — doi:10.1057/jos.2012.20
39. JSAIMM 2007 (Venetia mixed fleets) — saimm.co.za/Journal/v107n02p073.pdf
40. IJMST 2015 (underground ramp traffic behaviour) — doi:10.1016/j.ijmst.2014.11.006
41. EPiC 2018 (GA dispatch one-lane roads) — doi:10.29007/n11t
42. Discover Applied Sciences 2024 (coal chain ABM, Indonesia) — doi:10.1007/s42452-024-06375-2
43. Montiel & Dimitrakopoulos 2015, EJOR (mining complex flows/rehandle) — doi:10.1016/j.ejor.2015.05.002
44. Minerals 2021 (stockpile FMS modeling) — doi:10.3390/min11060636
45. Research Square 2021 (rainy-season opencast effects) — doi:10.21203/rs.3.rs-870740/v1
46. MM&E 2026 (Hybrid DES + NSGA-II fleet design) — doi:10.1007/s42461-026-01496-1

*Caveats: a few older SAIMM/queueing citations (26, 27, 39) are verified by venue and are standard in the field but were not re-fetched full-text in this pass; Chanda & Gardiner error magnitudes are characterized from the abstract + secondary citations (full text is paywalled). Baek & Choi MAPE figures are from abstract-level and secondary reporting; treat exact decimals with care.*
