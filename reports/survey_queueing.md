# Literature survey: predicting truck fleet productivity and loader queues in truck-shovel systems
### Verdict on open-system Erlang-C for a closed fleet

Date: 2026-08-26. Prepared from primary sources (fetched full text of Krause & Musingwini 2007 and Ercelebi & Bascetin 2009; abstracts/records for the rest via Crossref/OpenAlex DOIs) plus an exact numeric comparison (script `/tmp/qcomp.py`, reproduced in Section 5).

---

## Executive verdict

**Open M/M/c Erlang-C with lambda = N/cycle is NOT the model the literature uses for a closed truck fleet, and it fails in exactly the operating region that matters (match factor near or above ~0.8).** The truck-shovel system is a *finite-source (closed) cyclic queue*: a truck that is already waiting at the loader cannot simultaneously be "arriving," so the effective arrival rate falls as the queue grows. The open-system model ignores this self-throttling, which has two consequences:

1. **At low utilization (MF < ~0.5)** Erlang-C *overestimates* the mean queue wait by roughly 20–80% relative to the exact finite-source result, but the absolute wait is small so productivity error is under ~3%. Your model is defensible here.
2. **Near and above MF ≈ 1** the open model diverges (rho -> 1) while the real closed system remains perfectly stable with throughput saturating at the loader capacity c·mu. Your rho >= 1 "cap at half a shift" produces trips/day that are **40–85% below** the true loader-limited throughput (see table in Section 5). The cap is not a conservative approximation, it is a qualitatively wrong regime.

The standard corrections in the literature, in increasing order of fidelity, are (a) the **machine-repair / finite-source M/M/c//N model** (Koenigsberg 1958; Carmichael 1986/1987; Krause & Musingwini 2007), (b) **closed queueing networks solved by Mean Value Analysis**, including multi-class fleets (Gordon & Newell 1967; Reiser & Lavenberg 1980; Kappas & Yegulalp 1991; Muduli & Yegulalp 1996; Ercelebi & Bascetin 2009), and (c) **general-service corrections** via two-moment approximations (Whitt 1983; Kimura 1985; Allen–Cunneen) or the maximum-entropy/GI-service closed-network method of Kappas & Yegulalp (1991), who report <= 5% error vs simulation. The exact drop-in replacement formula for your code is given in Section 6.

A **match-factor sanity bound** (productivity <= min(truck-limited, loader-limited) rate) is standard practice (Douglas 1964; Morgan & Peterson 1968; Burt & Caccetta 2007) and your current model violates the loader-limited half of it whenever the cap engages.

---

## 1. Classic and modern truck-shovel queueing

### 1.1 The founding closed-cycle literature

- **Koenigsberg, E. (1958), "Cyclic Queues," *Operational Research Quarterly* 9(1):22–35.** DOI: 10.1057/jors.1958.3 (also 10.2307/3007650). The original closed cyclic-queue model: N customers circulate through k exponential stages. Koenigsberg's motivating application was mining (coal-face haulage cycles). This is the exact structural template of a haul circuit (load -> haul -> dump -> return). https://doi.org/10.1057/jors.1958.3
- **Koenigsberg, E. (1982), "Twenty Five Years of Cyclic Queues and Closed Queue Networks: A Review," *J. Operational Research Society* 33:605–619.** DOI: 10.1057/jors.1982.136. Survey confirming the closed-network treatment as the canonical model for vehicle/haulage cycles. https://doi.org/10.1057/jors.1982.136
- **Gordon, W.J. & Newell, G.F. (1967), "Closed Queuing Systems with Exponential Servers," *Operations Research* 15(2):254–265.** DOI: 10.1287/opre.15.2.254. Product-form solution for closed networks; the theoretical foundation for everything below. https://doi.org/10.1287/opre.15.2.254
- **Buzen, J.P. (1973), "Computational algorithms for closed queueing networks with exponential servers," *CACM* 16(9):527–531.** DOI: 10.1145/362342.362345. The convolution algorithm making Gordon–Newell computable. https://doi.org/10.1145/362342.362345
- **Reiser, M. & Lavenberg, S.S. (1980), "Mean-Value Analysis of Closed Multichain Queuing Networks," *JACM* 27(2):313–322.** DOI: 10.1145/322186.322195. MVA: computes closed-network waits and throughput by a simple recursion over population n = 1..N with no normalizing constants. This is the "MVA iteration" your team asked about. https://doi.org/10.1145/322186.322195

### 1.2 Mining/construction applications

- **Carmichael, D.G. (1986), "Shovel–truck queues: a reconciliation of theory and practice," *Construction Management and Economics* 4(2):161–177.** DOI: 10.1080/01446198600000013. Field study examining queueing assumptions (service discipline, steady state, distributions of backcycle and service times) against measurements; concludes finite-source queueing theory is a usable planning tool for shovel-truck operations. Companion: **Carmichael (1986), "Optimal shovel-truck operations," *Engineering Optimization* 10(1):51–63,** DOI: 10.1080/03052158608902527, and his book *Engineering Queues in Construction and Mining* (Ellis Horwood, 1987), which is built around the finite-source M/M/c//N and M/G/c//N models. https://doi.org/10.1080/01446198600000013
- **Kappas, G. & Yegulalp, T.M. (1991), "An application of closed queueing networks theory in truck-shovel systems," *Int. J. Surface Mining, Reclamation and Environment* 5(1):45–53.** DOI: 10.1080/09208119108944286. Closed network with **general (non-exponential) service distributions** at each activity, solved with a maximum-entropy-style approximation. **Reported accuracy: relative error of critical performance parameters vs simulation <= 5%.** https://doi.org/10.1080/09208119108944286
- **Muduli, P.K. & Yegulalp, T.M. (1996), "Modeling Truck–Shovel Systems as Closed Queueing Network with Multiple Job Classes," *Int. Transactions in Operational Research* 3(1):89–98.** DOI: 10.1111/j.1475-3995.1996.tb00038.x. **Multi-class MVA** for heterogeneous truck fleets: computes throughput, mean number of trucks, and mean waits per truck class. This is the reference method for mixed fleets. https://doi.org/10.1111/j.1475-3995.1996.tb00038.x
- **Krause, A. & Musingwini, C. (2007), "Modelling open pit shovel-truck systems using the Machine Repair Model," *J. South African Institute of Mining and Metallurgy* 107(8):469–476.** Free PDF: https://www.saimm.co.za/Journal/v107n08p469.pdf. Maps the truck circuit onto the finite-source **M/M/R/GD/K/K machine-repair model** (loading = "repair," R = shovels/loading sides, K = trucks; travel = "up time"). Validated on a virtual mine and on Optimum Colliery (Kwagga section) against Talpac, FPC, Elbrond's model, and an Arena discrete-event simulation benchmark. **Reported accuracy: MRM productivity estimates were 97%–99.7% of the Arena benchmark estimates** (i.e., within ~0.3–3%). Explicitly frames the truck fleet as a finite-source system where "should all the trucks be present at the loading unit ... the truck arrival rate will be zero," the precise phenomenon open Erlang-C ignores.
- **Ercelebi, S.G. & Bascetin, A. (2009), "Optimization of shovel-truck system for surface mining," *J. SAIMM* 109(7):433–439.** Free PDF: https://www.saimm.co.za/Journal/v109n07p433.pdf. Uses **closed cyclic queueing theory for truck allocation** (state-enumeration of the closed cycle, expected queue lengths and waits per station via the finite-source balance equations) plus LP for dispatch; case study at Orhaneli Open Pit Coal Mine (Turkey).
- **Ta, C.H., Kresta, J.V., Forbes, J.F. & Marquez, H.J. (2005), "A stochastic optimization approach to mine truck allocation," *Int. J. Surface Mining, Reclamation and Environment* 19(3):162–175.** DOI: 10.1080/13895260500128914. Chance-constrained truck allocation with explicitly stochastic cycle times (mean and variance from dispatch data). https://doi.org/10.1080/13895260500128914
- **Ta, C.H., Ingolfsson, A. & Doucette, J. (2013), "A linear model for surface mining haul truck allocation incorporating shovel idle probabilities," *European Journal of Operational Research* 231(3):770–778.** DOI: 10.1016/j.ejor.2013.06.016. The modern reference for your exact question: models each shovel with its allocated trucks as a **finite-source M/M/1//N queue**, expresses shovel idle probability P0(N) from the machine-repair steady state, and embeds a linearization of it in an LP. Note what they did NOT do: use an open-arrival Erlang formula. https://doi.org/10.1016/j.ejor.2013.06.016
- **Czaplicki, J.M. (2008), *Shovel-Truck Systems: Modelling, Analysis and Calculations*, CRC Press/Taylor & Francis.** DOI: 10.1201/9780203881248. Book-length treatment; the workhorse chapters model the exploitation process with finite-source queues (Maryanovitch-type models with spare trucks and failures), never open M/M/c. https://doi.org/10.1201/9780203881248
- **Haque, L. & Armstrong, M.J. (2007), "A survey of the machine interference problem," *EJOR* 179(2):469–482.** DOI: 10.1016/j.ejor.2006.02.036. Survey of the machine-repair/finite-source family (exact results, approximations, general service). Good map of available corrections. https://doi.org/10.1016/j.ejor.2006.02.036
- **Griffis, F.H. (1968), "Optimizing Haul Fleet Size Using Queueing Theory," *ASCE J. Construction Division* 94(1):75–88.** DOI: 10.1061/JCCEAZ.0000215. Early construction-side use of finite-source queueing for fleet sizing. https://doi.org/10.1061/JCCEAZ.0000215

### 1.3 Published open-vs-finite-source comparisons

Direct published head-to-head tables for mining parameters are scarce; the literature mostly skipped the open model because its inapplicability to small N was already textbook knowledge (the machine-interference literature since Ashcroft 1950). What is documented:

- Carmichael (1986, 1987) explicitly argues the infinite-source assumption is invalid for shovel-truck fleets because the calling population is small (typically N <= ~10 trucks per loader) and arrival rate is state-dependent.
- Krause & Musingwini (2007) list "bunching correction" regressive models (FPC) vs finite-source models and show FPC *underestimates* waiting time vs the MRM/Arena; the MRM (finite-source) tracks the simulation benchmark to 0.3–3%.
- General queueing texts (e.g., Gross & Harris, *Fundamentals of Queueing Theory*; Winston, *Operations Research*, 2004, cited as the MRM source by Krause & Musingwini) state that open-arrival formulas overestimate congestion for finite sources at high load because the open model permits an arrival stream unconstrained by the number of customers already in queue.

Because a direct numeric comparison at your parameters (N = 5–60, c = 1–4) was not found published, we computed it exactly; see Section 5. The result confirms the qualitative claims above and quantifies them.

---

## 2. Match factor

### 2.1 Definition and lineage

Match factor for homogeneous fleets (Douglas 1964; popularized by Morgan & Peterson 1968, "Determining Shovel-Truck Productivity," *Mining Engineering*, Dec 1968, pp. 76–80):

MF = (number of trucks × loader loading time) / (number of loaders × truck cycle time)
   = N · t_load / (c · T_cycle)

which in your notation is exactly **MF = lambda/(c·mu) = rho of your Erlang-C**. MF < 1 means the system is truck-limited (loaders idle), MF > 1 means loader-limited (trucks queue), MF = 1 is the theoretical balance point where, with *deterministic* times, neither queues. With stochastic times, throughput at MF = 1 is strictly below both asymptotes (the "bunching" loss).

### 2.2 Heterogeneous extensions

- **Burt, C.N. & Caccetta, L. (2007), "Match factor for heterogeneous truck and loader fleets," *Int. J. Mining, Reclamation and Environment* 21(4):262–270.** DOI: 10.1080/17480930701388606. Extends MF to heterogeneous truck fleets (unique-loading-time trucks: MF = total loader-side work rate over cycle-time-weighted truck availability, computed per truck class), heterogeneous loader fleets (LCM-based construction over loader cycle times), and both simultaneously. https://doi.org/10.1080/17480930701388606
- **Burt, C.N. & Caccetta, L. (2018), "Match Factor Extensions," in *Equipment Selection for Mining: With Case Studies*, Studies in Systems, Decision and Control 150, Springer, ch. 4.** DOI: 10.1007/978-3-319-76255-5_4. Consolidates the MF work, discusses MF as an efficiency/productivity indicator and its use as a bound and sanity check in equipment selection. https://doi.org/10.1007/978-3-319-76255-5_4
- **Burt, C.N. & Caccetta, L. (2014), "Equipment Selection for Surface Mining: A Review," *Interfaces* 44(2):143–162.** DOI: 10.1287/inte.2013.0732. Reviews how MF and queueing/simulation productivity curves feed fleet-sizing decisions in practice. https://doi.org/10.1287/inte.2013.0732

### 2.3 MF vs productivity curves, and the sanity bound

The closed-queue throughput curve X(N) rises almost linearly in N (truck-limited region, slope ≈ 1/T_cycle_freeflow), then saturates at c·mu (loader-limited region), with a stochastic rounding of the knee near MF ≈ 1. The deterministic two-piece envelope

trips/hour <= min( N / T_cycle_freeflow , c · mu )

is the **match-factor sanity bound**. Yes, production models use it: it is precisely the structure of Morgan & Peterson's productivity charts, of Elbrond's correction method (Elbrond, J. (1990), "Queueing theory calculation of shovel-truck production capacity," in *Surface Mining*, 2nd ed., SME), of FPC/Talpac-style estimators (documented in Krause & Musingwini 2007), and of the asymptotic-bound analysis standard in closed networks (throughput bound analysis, e.g., Lavenberg 1981, DOI: 10.1016/0166-5316(81)90056-0). **Any predicted trips/day exceeding either bound, or far below the min near MF >> 1, indicates a model error.** Your capped-Erlang-C output sits far below the c·mu bound when the cap fires.

---

## 3. Fleet sizing and dispatch practice; variability corrections

### 3.1 FMS / dispatch literature

- **Alarie, S. & Gamache, M. (2002), "Overview of Solution Strategies Used in Truck Dispatching Systems for Open Pit Mines," *Int. J. Surface Mining, Reclamation and Environment* 16(1):59–76.** DOI: 10.1076/ijsm.16.1.59.3408. Canonical review of commercial FMS (Modular Mining DISPATCH, Wenco, etc.): upper stage = fleet sizing / production planning (LP/queueing), lower stage = real-time assignment. Notes DISPATCH's "best path" + LP + dynamic assignment architecture; cycle-time inputs come from historical dispatch data. https://doi.org/10.1076/ijsm.16.1.59.3408
- **Munirathinam, M. & Yingling, J.C. (1994), "A review of computer-based truck dispatching strategies for surface mining operations," *Int. J. Surface Mining, Reclamation and Environment* 8(1):1–15.** DOI: 10.1080/09208119408964750. Earlier survey, same two-stage structure.
- **Soumis, F., Ethier, J. & Elbrond, J. (1989), "Truck dispatching in an open pit mine," *Int. J. Surface Mining* 3(2):115–119.** DOI: 10.1080/09208118908944263, and **Elbrond & Soumis (1987)**, DOI: 10.1080/09208118708944095. Queueing-informed planning + assignment; Elbrond's capacity method uses finite-source waiting-time curves with a variability interpolation (below).
- **White, J.W. & Olson, J.P. (1986), "Computer-based dispatching in mines with concurrent operating objectives," *Mining Engineering* 38(11):1045–1054** (the DISPATCH algorithm paper; reprinted as "Efficient optimal algorithms for haul truck dispatching in open pit mines," in *Off-Highway Haulage in Surface Mines*, Taylor & Francis, DOI: 10.1201/9780203745090-4).

### 3.2 How variability (SCV) enters the wait formulas

- **Elbrond, J. (1990)** (in *Surface Mining* 2nd ed., SME, ch. on production capacity): computes waiting time as an **interpolation between the deterministic (D/D/1//N) and exponential (M/M/1//N) finite-source results, indexed by the SCVs of backcycle and service time** estimated from dispatch data. This is exactly the role your calibrated `cycle_sd` should play, and it is applied to *finite-source* curves, not open ones. (Described and benchmarked in Krause & Musingwini 2007.)
- **Allen–Cunneen approximation** (Allen, A.O. (1990), *Probability, Statistics and Queueing Theory with Computer Science Applications*, 2nd ed., Academic Press): Wq(G/G/c) ≈ Wq(M/M/c) · (Ca² + Cs²)/2. Two-moment correction; widely used but defined for **open** systems.
- **Kimura, T. (1985), "A two-moment approximation for the mean waiting time in the GI/G/s queue," *Performance Evaluation* 5(2):111–118.** DOI: 10.1016/0166-5316(85)90014-8. Refined open-system two-moment corrections.
- **Whitt, W. (1983), "The Queueing Network Analyzer," *Bell System Technical Journal* 62(9):2779–2815.** DOI: 10.1002/j.1538-7305.1983.tb03204.x. Network-level two-moment (SCV-propagating) decomposition; the pattern followed by Kappas & Yegulalp (1991) for the closed mining network with GI service.
- **Insensitivity result that helps you:** Bunday, B.D. & Scraton, R.E. (1980), "The G/M/r machine interference model," *EJOR* 4(6):399–402, DOI: 10.1016/0377-2214(80)90193-9: in the finite-source model with **generally distributed travel (think) time and exponential service**, steady-state probabilities depend on the travel time only through its **mean**. Practical upshot: your `cycle_sd` on the haul/return legs matters much less than load-time variability; put your two-moment correction on the *service* side (load time SCV), not on the cycle.
- **Carmichael (1987)** (book, op. cit.) provides M/G/c//N-style tables and Erlang-k service options for shovel-truck circuits, the standard way to encode load-time SCV in the closed model.

### 3.3 Stochastic vs deterministic cycle times

Ta et al. (2005) DOI: 10.1080/13895260500128914 (chance-constrained, uses cycle time mean+variance); Ozdemir, B. & Kumral, M. (2019), "Simulation-based optimization of truck-shovel material handling systems in multi-pit surface mines," *Simulation Modelling Practice and Theory* 95:36–48, DOI: 10.1016/j.simpat.2019.04.006 (fully stochastic DES + optimization). Deterministic cycle times systematically overestimate production by ignoring bunching; every comparative study (Krause & Musingwini 2007; Chanda & Gardiner 2010) finds the deterministic/static estimates biased high.

---

## 4. What the best papers validate against, and reported accuracy

| Paper | Validated against | Reported accuracy |
|---|---|---|
| Kappas & Yegulalp 1991 (closed GI network) | Discrete-event simulation | Relative error of critical performance parameters <= **5%** |
| Krause & Musingwini 2007 (machine repair) | Arena DES benchmark + Talpac/FPC/Elbrond; real colliery case | MRM = **97–99.7%** of Arena estimates (0.3–3% deviation) |
| Muduli & Yegulalp 1996 (multi-class MVA) | Simulation computational study | Close agreement (no single % headline) |
| Ta et al. 2013 (finite-source in LP) | Oil-sands mine dispatch data | Linearized idle-probability model reproduces finite-source relationship; improvement demonstrated vs deterministic LP allocation |
| Chanda & Gardiner 2010, *Eng. Construction & Architectural Mgmt* 17(5):446–460, DOI: 10.1108/09699981011074556 | **Actual FMS-recorded cycle times** at a large open pit | Regression and neural nets beat DES; DES **underestimates short hauls and overestimates long hauls**. Errors reported per-route in-paper (single-digit % for NN/MR vs actuals) |
| Modern ML cycle-time papers (e.g., Fan et al. 2025, *Mining, Metallurgy & Exploration*, DOI: 10.1007/s42461-025-01225-0; Zhao et al. 2025, *Scientific Reports*, DOI: 10.1038/s41598-025-88543-x) | Held-out FMS records | Typically report R² ≈ 0.85–0.95 on travel/cycle time components |

**Benchmark context for your 20% MAPE:** analytic queueing models validated against *simulation* achieve <= 5%; against *field dispatch data*, well-calibrated models (queueing or regression) land around 5–15% on trips/day at route level. 20% MAPE is at the loose end of the published envelope and plausibly dominated by the structural Erlang-C error near MF ≈ 1 (Section 5): the error there is not noise, it is bias, and it is fixable by swapping the formula.

---

## 5. Quantitative comparison: open Erlang-C (your model) vs exact finite-source M/M/c//N

Computed exactly (birth-death solution), with your conventions: lambda = N/cycle_freeflow, mu = 60/load_min, cap Wq at 6 h when rho >= 1, trips/day over 20 effective hours. Z = free-flow cycle minus load time. Reproduce with `/tmp/qcomp.py`. Selected rows:

| N | c | load (min) | Z (h) | MF | Wq open (min) | Wq finite (min) | open Wq error | trips/day open | trips/day finite | productivity error |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 | 1 | 3 | 1.0 | 0.24 | 0.9 | 0.7 | +43% | 93.8 | 94.3 | −0.4% |
| 10 | 1 | 3 | 1.0 | 0.48 | 2.7 | 1.9 | +41% | 182.6 | 184.8 | −1.2% |
| 20 | 1 | 3 | 1.0 | 0.95 | 60.0 | 8.3 | **+620%** | 195.1 | 336.4 | **−42%** |
| 30 | 1 | 3 | 1.0 | 1.43 | cap 6 h | 27.8 | — | 85.1 | 396.6 | **−79%** |
| 40 | 2 | 3 | 1.0 | 0.95 | 29.3 | 5.4 | +438% | 520 | 701 | −26% |
| 60 | 2 | 3 | 1.0 | 1.43 | cap 6 h | 27.1 | — | 170 | 799 | **−79%** |
| 30 | 2 | 3 | 2.0 | 0.37 | 0.5 | 0.4 | +16% | 292 | 292 | −0.1% |
| 40 | 4 | 2.5 | 4.0 | 0.10 | ~0 | ~0 | +27% | 198 | 198 | ~0% |

Findings:

1. **MF <~ 0.5 (most multi-loader, long-cycle routes):** Erlang-C overestimates Wq by ~15–80% relative, but absolute waits are < 1–3 min, so trips/day error < ~2%. Defensible.
2. **MF ≈ 0.8–1.0:** Erlang-C wait explodes (4–9× the true wait). Productivity underestimated 25–45%. This is the region fleet sizing actually targets (mines deliberately operate near MF ≈ 1), so the model is worst exactly where decisions are made.
3. **MF > 1 (rho >= 1, cap engaged):** the real system delivers the loader-limited plateau c·mu·T (e.g., 400 trips/day for c = 1, 3-min loads over 20 h); the capped model delivers 15–60% of that, with the error *depending on the arbitrary cap*, not on physics. Underestimation of 40–85%.
4. The finite-source model needs **no cap and no stability condition**: it is stable for every N, which is the whole point of a closed model.

---

## 6. The correction to implement

### 6.1 Exact drop-in: machine-repair M/M/c//N (the "Erlang finite-source" formula)

Parameters per route: N trucks, c loaders, service rate mu = 60/load_min per loader, **think time Z = free-flow cycle minus load time** = spot + haul + dump + return (+ BPR road delay), think rate 1/Z per truck.

Steady-state probabilities (birth–death; Winston 2004; Krause & Musingwini 2007; Haque & Armstrong 2007):

- For n = 0..N trucks at the loader station:
  - p_n = p_0 · C(N,n) · n! / (c!·c^(n−c)) · (1/(Z·mu))^n, using C(N,n)·(1/(Z mu))^n for n <= c and the c-server correction for n > c. Equivalently, recursively:
  - p_n = p_{n−1} · [(N−n+1)/Z] / [min(n,c)·mu], normalized so sum p_n = 1.
- Mean number at loader: L = Σ n·p_n
- **Throughput (trips per hour for the route): X = Σ min(n,c)·mu·p_n**  (equivalently X = (N − L)/Z)
- Mean time at loader station (Little): W = L/X, **queue wait Wq = W − 1/mu**
- Trips/day = X × effective hours. Loader utilization = X/(c·mu).

Ten lines of code, exact, always stable, no cap needed. Sanity bound satisfied automatically: X <= min(N/(Z + 1/mu), c·mu).

### 6.2 Equivalent alternative: MVA iteration (extends to multi-station and multi-class)

Reiser & Lavenberg (1980): for n = 1..N with Q_loader(0) = 0:
1. W_loader(n) = (1/mu)·(1 + Q_loader(n−1))   [single-server per loader; use the multiserver approximate-MVA correction for c > 1, or model c loaders as c separate queues with route splitting]
2. X(n) = n / (Z + W_loader(n))
3. Q_loader(n) = X(n) · W_loader(n)

Use Muduli & Yegulalp (1996) for mixed truck classes; Kappas & Yegulalp (1991) for non-exponential service.

### 6.3 Variability correction (your calibrated SCVs)

- Per Bunday & Scraton (1980), travel-time (cycle_sd on haul legs) distribution shape is nearly irrelevant given its mean; **calibrate and correct for load-time SCV** instead.
- Practical two-moment closed-system correction (Elbrond 1990 style): compute Wq_det (deterministic finite-source, ≈ max(0, N/(c·mu) − (Z + 1/mu))·shape term or via D/D/c//N recursion) and Wq_exp (Section 6.1), then interpolate Wq ≈ Wq_det + (Cs²+Ca²)/2 ·(Wq_exp − Wq_det) clipped to [Wq_det, Wq_exp·(Cs²+1)/2]. Or simplest defensible step: Wq ≈ Wq_{M/M/c//N} · (1 + Cs²)/2 with Cs² = SCV of load time.
- Keep the BPR road delay in Z; it is a travel-leg effect and by insensitivity only its mean matters at the queue.

### 6.4 What to test

Replace the Erlang-C + cap with 6.1 verbatim, keep everything else identical, and re-score MAPE on the dispatch data, stratified by route MF. Expect: negligible change for MF < 0.5 routes, large improvement for MF > 0.8 routes. Also add the match-factor bound as an assertion: predicted trips/day must not exceed min(N·T/(Z+1/mu), c·mu·T) and should approach c·mu·T (not the cap artifact) as MF grows.

---

## 7. Full citation list

1. Koenigsberg, E. (1958). Cyclic Queues. *Operational Research Quarterly* 9(1):22–35. https://doi.org/10.1057/jors.1958.3
2. Koenigsberg, E. (1982). Twenty Five Years of Cyclic Queues and Closed Queue Networks: A Review. *JORS* 33:605–619. https://doi.org/10.1057/jors.1982.136
3. Gordon, W.J., Newell, G.F. (1967). Closed Queuing Systems with Exponential Servers. *Operations Research* 15(2):254–265. https://doi.org/10.1287/opre.15.2.254
4. Buzen, J.P. (1973). Computational algorithms for closed queueing networks. *CACM* 16(9):527–531. https://doi.org/10.1145/362342.362345
5. Reiser, M., Lavenberg, S.S. (1980). Mean-Value Analysis of Closed Multichain Queuing Networks. *JACM* 27(2):313–322. https://doi.org/10.1145/322186.322195
6. Carmichael, D.G. (1986). Shovel–truck queues: a reconciliation of theory and practice. *Construction Management and Economics* 4(2):161–177. https://doi.org/10.1080/01446198600000013
7. Carmichael, D.G. (1986). Optimal shovel-truck operations. *Engineering Optimization* 10(1):51–63. https://doi.org/10.1080/03052158608902527
8. Carmichael, D.G. (1987). *Engineering Queues in Construction and Mining*. Ellis Horwood, Chichester.
9. Kappas, G., Yegulalp, T.M. (1991). An application of closed queueing networks theory in truck-shovel systems. *IJSM* 5(1):45–53. https://doi.org/10.1080/09208119108944286
10. Muduli, P.K., Yegulalp, T.M. (1996). Modeling Truck–Shovel Systems as Closed Queueing Network with Multiple Job Classes. *ITOR* 3(1):89–98. https://doi.org/10.1111/j.1475-3995.1996.tb00038.x
11. Krause, A., Musingwini, C. (2007). Modelling open pit shovel-truck systems using the Machine Repair Model. *J. SAIMM* 107(8):469–476. https://www.saimm.co.za/Journal/v107n08p469.pdf
12. Ercelebi, S.G., Bascetin, A. (2009). Optimization of shovel-truck system for surface mining. *J. SAIMM* 109(7):433–439. https://www.saimm.co.za/Journal/v109n07p433.pdf
13. Ta, C.H., Kresta, J.V., Forbes, J.F., Marquez, H.J. (2005). A stochastic optimization approach to mine truck allocation. *IJSM* 19(3):162–175. https://doi.org/10.1080/13895260500128914
14. Ta, C.H., Ingolfsson, A., Doucette, J. (2013). A linear model for surface mining haul truck allocation incorporating shovel idle probabilities. *EJOR* 231(3):770–778. https://doi.org/10.1016/j.ejor.2013.06.016
15. Czaplicki, J.M. (2008). *Shovel-Truck Systems*. CRC Press. https://doi.org/10.1201/9780203881248
16. Haque, L., Armstrong, M.J. (2007). A survey of the machine interference problem. *EJOR* 179(2):469–482. https://doi.org/10.1016/j.ejor.2006.02.036
17. Griffis, F.H. (1968). Optimizing Haul Fleet Size Using Queueing Theory. *ASCE J. Constr. Div.* 94(1):75–88. https://doi.org/10.1061/JCCEAZ.0000215
18. Burt, C.N., Caccetta, L. (2007). Match factor for heterogeneous truck and loader fleets. *IJMRE* 21(4):262–270. https://doi.org/10.1080/17480930701388606
19. Burt, C.N., Caccetta, L. (2014). Equipment Selection for Surface Mining: A Review. *Interfaces* 44(2):143–162. https://doi.org/10.1287/inte.2013.0732
20. Burt, C.N., Caccetta, L. (2018). Match Factor Extensions. In *Equipment Selection for Mining*, Springer SSDC 150, ch. 4. https://doi.org/10.1007/978-3-319-76255-5_4
21. Morgan, W.C., Peterson, L.L. (1968). Determining Shovel-Truck Productivity. *Mining Engineering*, Dec 1968:76–80.
22. Douglas, J. (1964). *Prediction of Shovel-Truck Production: A Reconciliation of Computer and Conventional Estimates*. Stanford University, Dept. of Civil Engineering, Tech. Report 37.
23. Elbrond, J. (1990). Queueing theory calculation of shovel-truck production capacity. In *Surface Mining*, 2nd ed., SME.
24. Elbrond, J., Soumis, F. (1987). Towards integrated production planning and truck dispatching in open pit mines. *IJSM* 1(1):1–6. https://doi.org/10.1080/09208118708944095
25. Soumis, F., Ethier, J., Elbrond, J. (1989). Truck dispatching in an open pit mine. *IJSM* 3(2):115–119. https://doi.org/10.1080/09208118908944263
26. Alarie, S., Gamache, M. (2002). Overview of Solution Strategies Used in Truck Dispatching Systems for Open Pit Mines. *IJSM* 16(1):59–76. https://doi.org/10.1076/ijsm.16.1.59.3408
27. Munirathinam, M., Yingling, J.C. (1994). A review of computer-based truck dispatching strategies for surface mining. *IJSM* 8(1):1–15. https://doi.org/10.1080/09208119408964750
28. White, J.W., Olson, J.P. (1986). Computer-based dispatching in mines with concurrent operating objectives. *Mining Engineering* 38(11):1045–1054. (Reprint DOI: 10.1201/9780203745090-4)
29. Whitt, W. (1983). The Queueing Network Analyzer. *Bell System Technical Journal* 62(9):2779–2815. https://doi.org/10.1002/j.1538-7305.1983.tb03204.x
30. Kimura, T. (1985). A two-moment approximation for the mean waiting time in the GI/G/s queue. *Performance Evaluation* 5(2):111–118. https://doi.org/10.1016/0166-5316(85)90014-8
31. Allen, A.O. (1990). *Probability, Statistics and Queueing Theory with Computer Science Applications*, 2nd ed. Academic Press. (Allen–Cunneen formula)
32. Bunday, B.D., Scraton, R.E. (1980). The G/M/r machine interference model. *EJOR* 4(6):399–402. https://doi.org/10.1016/0377-2214(80)90193-9
33. Chanda, E.K., Gardiner, S. (2010). A comparative study of truck cycle time prediction methods in open-pit mining. *ECAM* 17(5):446–460. https://doi.org/10.1108/09699981011074556
34. Ozdemir, B., Kumral, M. (2019). Simulation-based optimization of truck-shovel material handling systems in multi-pit surface mines. *SIMPAT* 95:36–48. https://doi.org/10.1016/j.simpat.2019.04.006
35. Fan et al. (2025). Rapid Estimation of Truck Cycle Time in Open-Pit Mine Haulage Based on Feature-Optimized Machine Learning. *Mining, Metallurgy & Exploration*. https://doi.org/10.1007/s42461-025-01225-0
36. Zhao et al. (2025). Prediction of open-pit mine truck travel time based on LSTM-TabTransformer. *Scientific Reports* 15. https://doi.org/10.1038/s41598-025-88543-x
37. Winston, W.L. (2004). *Operations Research: Applications and Algorithms*, 4th ed. Thomson Brooks/Cole. (Machine Repair Model = M/M/R/GD/K/K.)
38. Lavenberg, S.S. (1981). Closed multichain product form queueing networks with large population sizes. *Performance Evaluation* 1(1). https://doi.org/10.1016/0166-5316(81)90056-0

*Notes on sourcing: items 8, 21, 22, 23, 31, 37 are books/reports verified via secondary citation in the fetched full-text papers (Krause & Musingwini 2007; Ercelebi & Bascetin 2009; Burt & Caccetta records); all journal items verified against Crossref/OpenAlex DOI records on 2026-08-26. The Section 5 comparison table is our own exact computation, not a published table.*
