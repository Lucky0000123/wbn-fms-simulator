# Database Schema Analysis

*Complete read-only inventory of `WBN_DATABASE` and `FMS_DB`. Generated 2026-07-30 03:16 UTC by `scripts/scan_all_tables.py` + `scripts/write_full_schema_report.py`. Every base table with rows was sampled. No object was created, altered or dropped.*

**Scope:** 215 base tables and 454 views across both databases.

Jump to: [WBN_DATABASE](#wbn_database) · [FMS_DB](#fms_db) · [Cross-Database Analysis](#cross-database-analysis) · [What data exists for the simulator](#summary-what-data-exists-for-the-simulator)

---

## WBN_DATABASE

579 objects: **161 base tables**, 418 views. Every base table with rows was sampled; views are catalogued for columns (each is defined over base tables already covered).

### WBN_DATABASE — index

| Table | Rows | Cols | Date range |
|---|---|---|---|
| [`EQUIPMENTS_HOURLY_STATUS`](#wbn-database-equipments-hourly-status) | 16,558,379 | 20 | 1899-12-30 → 2026-07-29 |
| [`EQUIPMENTS_HOURLY_ACTIVITIES`](#wbn-database-equipments-hourly-activities) | 4,682,656 | 21 | 1899-12-30 → 2026-07-29 |
| [`BLOCK_INDESIGN`](#wbn-database-block-indesign) | 4,288,722 | 13 | 2025-06-12 → 2026-05-10 |
| [`EQUIPMENTS_STATUS`](#wbn-database-equipments-status) | 3,680,170 | 22 | 2024-10-01 → 2026-07-29 |
| [`HAULAGE`](#wbn-database-haulage) | 3,509,230 | 24 | 2021-09-24 → 2026-07-28 |
| [`S123_STOCK_SHAPE_OLD`](#wbn-database-s123-stock-shape-old) | 1,732,432 | 12 | 2026-03-17 → 2026-06-27 |
| [`HAULAGE_IWIP_EXT`](#wbn-database-haulage-iwip-ext) | 1,508,871 | 28 | 2026-05-30 → 2026-07-11 |
| [`RSF_HAULING_DATA`](#wbn-database-rsf-hauling-data) | 1,143,509 | 18 | 2023-12-23 → 2026-01-22 |
| [`WAITING_TIME`](#wbn-database-waiting-time) | 878,240 | 24 | 2025-01-01 → 2026-07-22 |
| [`HAULAGE_IWIP`](#wbn-database-haulage-iwip) | 572,742 | 35 | 2025-12-27 → 2026-07-08 |
| [`TOS_STATUS`](#wbn-database-tos-status) | 548,621 | 6 | 2024-09-30 → 2026-07-28 |
| [`DAY_WORKS`](#wbn-database-day-works) | 495,592 | 27 | 2024-10-15 → 2026-07-25 |
| [`PRODUCTION_ACTIVITY_PIT`](#wbn-database-production-activity-pit) | 450,848 | 34 | 2024-07-01 → 2026-07-29 |
| [`PRODUCTION_PIT_OLD`](#wbn-database-production-pit-old) | 407,593 | 23 | 2024-07-01 → 2026-06-07 |
| [`ASSAYS`](#wbn-database-assays) | 396,428 | 36 | 1900-01-01 → 2026-07-30 |
| [`PP_MINED_NEW_RECONCIL_MENG`](#wbn-database-pp-mined-new-reconcil-meng) | 308,918 | 11 | — |
| [`SAMPLE`](#wbn-database-sample) | 249,620 | 26 | 1900-01-02 → 2026-07-20 |
| [`auto_edge_HAULAGE`](#wbn-database-auto-edge-haulage) | 246,971 | 11 | 2021-09-24 → 2026-07-28 |
| [`DISPATCH WBN ACTUAL`](#wbn-database-dispatch-wbn-actual) | 212,890 | 14 | 2024-10-01 → 2026-07-22 |
| [`auto_node_STOCK_ID`](#wbn-database-auto-node-stock-id) | 186,833 | 29 | 2021-02-20 → 2026-07-28 |
| [`POS FOLLOW UP`](#wbn-database-pos-follow-up) | 177,744 | 9 | 2024-10-01 → 2026-07-31 |
| [`autoQC_CF_BM_TOS_HISTORY_OLD`](#wbn-database-autoqc-cf-bm-tos-history-old) | 175,475 | 17 | — |
| [`CRUSHER_STOCKPILE_OUTPUT_DATA`](#wbn-database-crusher-stockpile-output-data) | 156,726 | 13 | 2024-10-01 → 2026-06-04 |
| [`QC PIT-TOS OMR`](#wbn-database-qc-pit-tos-omr) | 149,360 | 19 | 2024-10-01 → 2026-07-17 |
| [`autoBLOCK_PROD_QC_BM_TOS_CORR`](#wbn-database-autoblock-prod-qc-bm-tos-corr) | 132,306 | 18 | 2025-12-29 → 2026-07-28 |
| [`CONTRACTOR FOLLOW UP`](#wbn-database-contractor-follow-up) | 130,873 | 25 | 2024-10-01 → 2026-07-28 |
| [`FeNi Reclaiming Plan`](#wbn-database-feni-reclaiming-plan) | 128,118 | 10 | 2024-10-01 → 2026-07-30 |
| [`MINING_PLAN_WEEKLY`](#wbn-database-mining-plan-weekly) | 124,358 | 34 | 2025-02-08 → 2026-05-01 |
| [`SAMPLING_CONTRACTOR`](#wbn-database-sampling-contractor) | 123,130 | 15 | 2024-10-01 → 2026-07-25 |
| [`TOS_PILE_INFO`](#wbn-database-tos-pile-info) | 97,738 | 6 | — |
| [`autoQC_STOCK_ALL_VIA_ALL`](#wbn-database-autoqc-stock-all-via-all) | 93,116 | 93 | 2021-10-17 → 2026-07-21 |
| [`TOS FOLLOW`](#wbn-database-tos-follow) | 87,045 | 13 | 2024-10-01 → 2026-07-22 |
| [`OMR_QC`](#wbn-database-omr-qc) | 85,995 | 15 | 2024-10-01 → 2026-07-22 |
| [`DISPATCH FeNi PLAN & ACTUAL`](#wbn-database-dispatch-feni-plan---actual) | 84,384 | 11 | 2024-10-01 → 2026-07-29 |
| [`DISTANCE_MINING`](#wbn-database-distance-mining) | 83,462 | 14 | 2024-02-25 → 2025-09-27 |
| [`DAILY_QUALITY_DISPATCH`](#wbn-database-daily-quality-dispatch) | 66,774 | 19 | 2025-02-27 → 2026-07-22 |
| [`PILES_SHARED_FENI`](#wbn-database-piles-shared-feni) | 66,571 | 7 | 2024-11-19 → 2026-05-29 |
| [`EXC_TRIMMING`](#wbn-database-exc-trimming) | 59,362 | 9 | 2024-11-13 → 2026-07-11 |
| [`RAINFALL`](#wbn-database-rainfall) | 55,934 | 9 | 2002-01-01 → 2026-04-11 |
| [`SURVEY POS`](#wbn-database-survey-pos) | 50,385 | 19 | 2024-10-05 → 2026-07-25 |
| [`HAULAGE_M_DOME_2026_IWIP_PLAN`](#wbn-database-haulage-m-dome-2026-iwip-plan) | 44,289 | 15 | 2026-03-05 → 2026-04-06 |
| [`autoTOS_SURVEY_ESTIMATION`](#wbn-database-autotos-survey-estimation) | 43,187 | 19 | 2026-05-02 → 2026-07-30 |
| [`QC_TOS_DATA_ML`](#wbn-database-qc-tos-data-ml) | 38,001 | 33 | — |
| [`PP_REMAIN_INPIT_MINEOUT`](#wbn-database-pp-remain-inpit-mineout) | 36,206 | 13 | — |
| [`PP_MINED_YTD_OK`](#wbn-database-pp-mined-ytd-ok) | 35,922 | 12 | — |
| [`TSS`](#wbn-database-tss) | 35,218 | 19 | 2024-10-01 → 2026-04-11 |
| [`HRM_INSPECTION`](#wbn-database-hrm-inspection) | 30,610 | 14 | 2024-10-01 → 2025-12-11 |
| [`DISTANCE_HAULING`](#wbn-database-distance-hauling) | 30,587 | 12 | 2025-04-28 → 2025-09-27 |
| [`CRUSHER LOIPOLOY`](#wbn-database-crusher-loipoloy) | 27,353 | 17 | 2024-10-01 → 2026-07-27 |
| [`DISPATCH WBN PLAN SHIFT`](#wbn-database-dispatch-wbn-plan-shift) | 27,058 | 15 | 2024-10-01 → 2026-07-22 |
| [`QC SAMPLE DATA`](#wbn-database-qc-sample-data) | 25,425 | 15 | 2024-01-12 → 2025-02-17 |
| [`VERY VERY SHORT TERM PIT SERVICE`](#wbn-database-very-very-short-term-pit-service) | 21,064 | 16 | 2024-10-01 → 2026-07-27 |
| [`ASSAYS_NITON_GGSHEET`](#wbn-database-assays-niton-ggsheet) | 19,700 | 25 | 2026-01-28 → 2026-07-30 |
| [`PRODUCTION_PIT_PRELIM_auto`](#wbn-database-production-pit-prelim-auto) | 15,887 | 19 | 2025-11-17 → 2026-03-23 |
| [`STOCK_STATUS`](#wbn-database-stock-status) | 14,720 | 12 | 1900-01-01 → 2026-07-15 |
| [`blasting_drilling`](#wbn-database-blasting-drilling) | 14,648 | 22 | 2024-11-25 → 2026-03-19 |
| [`WBN_DATABASE_ST_LOG_ON`](#wbn-database-wbn-database-st-log-on) | 13,681 | 3 | 2026-06-18 → 2026-07-30 |
| [`OLD_VERY_SHORT_TERM`](#wbn-database-old-very-short-term) | 13,470 | 16 | 2024-10-05 → 2025-11-27 |
| [`HAULAGE_REPORT`](#wbn-database-haulage-report) | 13,459 | 16 | 2024-10-05 → 2025-11-26 |
| [`QUARRY PRODUCTION`](#wbn-database-quarry-production) | 12,646 | 14 | 2024-10-01 → 2025-09-10 |
| [`PROD VERY VERY SHORT TERM`](#wbn-database-prod-very-very-short-term) | 11,180 | 29 | 2024-10-01 → 2026-07-29 |
| [`RSF_SURVEY`](#wbn-database-rsf-survey) | 9,103 | 20 | 2024-10-04 → 2025-06-20 |
| [`autoQC_CF_BM_TOS`](#wbn-database-autoqc-cf-bm-tos) | 8,249 | 20 | 2026-07-06 → 2026-07-30 |
| [`RECLASSIFICATION`](#wbn-database-reclassification) | 7,789 | 5 | — |
| [`EQUIPMENTS`](#wbn-database-equipments) | 7,221 | 15 | — |
| [`FENI_REQUESTS`](#wbn-database-feni-requests) | 7,196 | 7 | 2025-07-01 → 2026-05-29 |
| [`QS_LIMS_RIM_CK`](#wbn-database-qs-lims-rim-ck) | 6,131 | 19 | 2026-06-10 → 2026-07-30 |
| [`DARONNE_Htemp`](#wbn-database-daronne-htemp) | 5,812 | 19 | 2026-05-01 → 2026-06-30 |
| [`EQUIPMENTS_OLD`](#wbn-database-equipments-old) | 5,658 | 14 | — |
| [`WMT_FOR_3RD_PARTY`](#wbn-database-wmt-for-3rd-party) | 5,529 | 12 | 2023-12-13 → 2026-07-20 |
| [`BATCH`](#wbn-database-batch) | 4,931 | 3 | — |
| [`DRAFTS`](#wbn-database-drafts) | 4,848 | 30 | 2023-10-03 → 2026-07-07 |
| [`TOS_SURVEY`](#wbn-database-tos-survey) | 4,804 | 18 | 2026-03-28 → 2026-07-10 |
| [`S123_STOCK_SHAPE`](#wbn-database-s123-stock-shape) | 4,785 | 11 | 2026-07-30 → 2026-07-30 |
| [`STOCK_STATUS_HAULAGE_GGSHEET`](#wbn-database-stock-status-haulage-ggsheet) | 4,750 | 17 | 2026-07-18 → 2026-07-18 |
| [`STOCK_REQUESTS`](#wbn-database-stock-requests) | 4,735 | 9 | 2025-06-20 → 2025-08-03 |
| [`3RD_PARTY_ACTIVITIES_RECLAIM`](#wbn-database-3rd-party-activities-reclaim) | 4,162 | 16 | 2024-12-22 → 2026-07-29 |
| [`REQUEST`](#wbn-database-request) | 3,920 | 6 | 2021-01-01 → 2026-07-01 |
| [`ORE STOCK SALES`](#wbn-database-ore-stock-sales) | 3,800 | 21 | 2021-02-20 → 2025-06-20 |
| [`S123_TOS_STATUS`](#wbn-database-s123-tos-status) | 3,589 | 11 | 2026-07-30 → 2026-07-30 |
| [`CRUSHER_BLENDING_DATA`](#wbn-database-crusher-blending-data) | 3,332 | 11 | 2024-10-01 → 2025-05-25 |
| [`3RD_PARTY_ACTIVITIES`](#wbn-database-3rd-party-activities) | 3,318 | 15 | 2024-10-01 → 2026-07-29 |
| [`HAUL_ROAD_STA`](#wbn-database-haul-road-sta) | 3,122 | 11 | — |
| [`Calendar_For_Exploitation`](#wbn-database-calendar-for-exploitation) | 2,665 | 7 | 2019-09-12 → 2026-12-28 |
| [`S123_ENVIRO_TSS`](#wbn-database-s123-enviro-tss) | 2,366 | 33 | 2026-06-08 → 2026-06-25 |
| [`MINING_PLAN_3MRMP`](#wbn-database-mining-plan-3mrmp) | 2,295 | 45 | 2026-03-29 → 2026-05-14 |
| [`blasting_parameters`](#wbn-database-blasting-parameters) | 2,081 | 20 | 2023-02-01 → 2025-05-04 |
| [`EQUIPMENTS_PLAN`](#wbn-database-equipments-plan) | 2,071 | 12 | 2025-12-29 → 2026-05-14 |
| [`Calendar_Svy_topo_by_deposit`](#wbn-database-calendar-svy-topo-by-deposit) | 1,839 | 5 | 2024-12-28 → 2026-07-28 |
| [`DAY_WORKS_PLAN_DAILY`](#wbn-database-day-works-plan-daily) | 1,773 | 17 | 2026-06-28 → 2026-07-30 |
| [`ORE_STOCK_SALES_MOISSONNEUSE_BATTEUSE`](#wbn-database-ore-stock-sales-moissonneuse-batteuse) | 1,585 | 7 | 2021-01-01 → 2025-06-01 |
| [`RSF_PER_LOCATION`](#wbn-database-rsf-per-location) | 1,489 | 15 | 2024-10-01 → 2024-12-16 |
| [`CLASS2025`](#wbn-database-class2025) | 1,438 | 7 | 2024-12-29 → 2025-07-12 |
| [`CONSOLIDATED SURVEY`](#wbn-database-consolidated-survey) | 1,188 | 15 | — |
| [`WATER_MANAGEMENT`](#wbn-database-water-management) | 1,074 | 12 | 2025-06-24 → 2025-10-07 |
| [`QUARRY_PLAN`](#wbn-database-quarry-plan) | 1,060 | 11 | 2026-06-01 → 2026-08-02 |
| [`OLD_prod_correction_factor_ACCESS`](#wbn-database-old-prod-correction-factor-access) | 957 | 6 | — |
| [`ROLLING_MINE_PLAN`](#wbn-database-rolling-mine-plan) | 834 | 20 | 2023-11-13 → 2024-07-26 |
| [`IWIP_REQUESTS_DATE`](#wbn-database-iwip-requests-date) | 772 | 3 | 2025-06-01 → 2026-05-02 |
| [`TRANSHIPMENT_WBN_ORE`](#wbn-database-transhipment-wbn-ore) | 573 | 7 | 2023-04-11 → 2026-07-19 |
| [`ID_DT_HUAFEI`](#wbn-database-id-dt-huafei) | 485 | 1 | — |
| [`SUMMARY_SURVEY`](#wbn-database-summary-survey) | 460 | 12 | — |
| [`BLASTING_PROD`](#wbn-database-blasting-prod) | 433 | 12 | 2026-01-02 → 2026-05-27 |
| [`DISPATCH_PLAN_WB`](#wbn-database-dispatch-plan-wb) | 432 | 15 | 2026-01-07 → 2026-07-22 |
| [`COLOR_CHEMICAL`](#wbn-database-color-chemical) | 404 | 4 | — |
| [`WBN_DATABASE_ESSENTIALS`](#wbn-database-wbn-database-essentials) | 334 | 3 | — |
| [`autoQC_PLAN_NI_CF_OLD`](#wbn-database-autoqc-plan-ni-cf-old) | 264 | 21 | — |
| [`DISPATCH HAULAGE TF`](#wbn-database-dispatch-haulage-tf) | 264 | 5 | — |
| [`DISPATCH ROADS OLD`](#wbn-database-dispatch-roads-old) | 254 | 36 | — |
| [`autoHAULAGE_VS_PROD_MONTHLY_CF`](#wbn-database-autohaulage-vs-prod-monthly-cf) | 223 | 6 | 2026-07-29 → 2026-07-29 |
| [`DISPATCH ROADS`](#wbn-database-dispatch-roads) | 222 | 33 | — |
| [`HRM_CONTRACT_EQUIPMENT`](#wbn-database-hrm-contract-equipment) | 198 | 8 | — |
| [`PROJECTS_SUPERVISION`](#wbn-database-projects-supervision) | 198 | 23 | 2025-08-21 → 2025-11-24 |
| [`MBAR`](#wbn-database-mbar) | 173 | 12 | — |
| [`HRM_MAJOR_ROADWORK`](#wbn-database-hrm-major-roadwork) | 149 | 11 | 2024-10-15 → 2024-11-03 |
| [`LME`](#wbn-database-lme) | 145 | 4 | 2026-01-02 → 2026-07-29 |
| [`LME_GOLD`](#wbn-database-lme-gold) | 143 | 2 | 2026-01-02 → 2026-07-29 |
| [`TSS_POINT`](#wbn-database-tss-point) | 121 | 36 | — |
| [`TOS_DUMP_COORDINATES`](#wbn-database-tos-dump-coordinates) | 118 | 7 | — |
| [`TSS_CROSSTABLE`](#wbn-database-tss-crosstable) | 109 | 5 | — |
| [`MINING_FLASH_REPORT_FLEET_PROD`](#wbn-database-mining-flash-report-fleet-prod) | 108 | 8 | 2025-11-28 → 2025-11-30 |
| [`MINING_FLASH_REPORT_EQUIPMENT`](#wbn-database-mining-flash-report-equipment) | 102 | 9 | 2025-11-28 → 2025-11-30 |
| [`BLASTING_REMAINING`](#wbn-database-blasting-remaining) | 98 | 7 | 2026-05-27 → 2026-05-27 |
| [`CONTRACTOR_DEPOSIT`](#wbn-database-contractor-deposit) | 84 | 4 | — |
| [`EQUIPMENTS_WORKS`](#wbn-database-equipments-works) | 82 | 14 | 2024-09-06 → 2024-10-14 |
| [`WBN_DATABASE_PROCEDURE_QUEUE`](#wbn-database-wbn-database-procedure-queue) | 79 | 3 | — |
| [`TEAM_PLAN`](#wbn-database-team-plan) | 78 | 8 | 2024-12-29 → 2025-02-14 |
| [`COMPANIES`](#wbn-database-companies) | 73 | 7 | — |
| [`DARONNEtemp`](#wbn-database-daronnetemp) | 61 | 3 | 2026-05-01 → 2026-06-30 |
| [`Ni_COLOR`](#wbn-database-ni-color) | 45 | 3 | — |
| [`MINING_FLASH_REPORT_PRODUCTION`](#wbn-database-mining-flash-report-production) | 42 | 8 | 2025-11-28 → 2025-11-30 |
| [`ACTIVITIES_MAT`](#wbn-database-activities-mat) | 39 | 4 | — |
| [`LOCATION_WB_SH`](#wbn-database-location-wb-sh) | 39 | 6 | — |
| [`DT_DENSITY_HR_MODEL$`](#wbn-database-dt-density-hr-model-) | 37 | 15 | 2025-09-13 → 2025-09-13 |
| [`TEAM`](#wbn-database-team) | 34 | 5 | — |
| [`MINING_EQ_TARGET_3MRMP`](#wbn-database-mining-eq-target-3mrmp) | 30 | 5 | — |
| [`ALL_HR_KM_SECTIONS`](#wbn-database-all-hr-km-sections) | 27 | 8 | — |
| [`ASSAY_CLASS`](#wbn-database-assay-class) | 27 | 8 | 2020-01-01 → 2025-01-01 |
| [`SHAPE_STOCK_AREA`](#wbn-database-shape-stock-area) | 26 | 5 | — |
| [`HRM_REQUEST_MATERIAL`](#wbn-database-hrm-request-material) | 25 | 10 | 2024-11-08 → 2024-11-09 |
| [`TEAM_FB`](#wbn-database-team-fb) | 25 | 6 | 2025-08-07 → 2026-05-01 |
| [`POS POSSIBILITY For HAULAGE`](#wbn-database-pos-possibility-for-haulage) | 23 | 3 | — |
| [`REQUEST_SALES_LATE_2025`](#wbn-database-request-sales-late-2025) | 18 | 3 | 2025-11-01 → 2025-11-01 |
| [`BLOCK_ID_XYPARAM`](#wbn-database-block-id-xyparam) | 16 | 8 | — |
| [`CRUSHER_SURVEY_LOYPOLOY`](#wbn-database-crusher-survey-loypoloy) | 16 | 13 | 2024-10-13 → 2024-10-13 |
| [`ACTIVITIES`](#wbn-database-activities) | 13 | 3 | — |
| [`HAULAGE CONTRACTORS`](#wbn-database-haulage-contractors) | 11 | 2 | — |
| [`SUPERVISION_SAFETY_ACTIONS`](#wbn-database-supervision-safety-actions) | 6 | 23 | 2025-09-10 → 2025-09-30 |
| [`CRUSHER_CF`](#wbn-database-crusher-cf) | 3 | 3 | — |
| [`HAULAGE_ADJ`](#wbn-database-haulage-adj) | 3 | 8 | 2025-02-01 → 2025-02-01 |
| [`autoQC_CF_BM_PROP`](#wbn-database-autoqc-cf-bm-prop) | 0 | 17 | — |
| [`blasting_production`](#wbn-database-blasting-production) | 0 | 19 | — |
| [`CORRECTIVE_ACTIONS`](#wbn-database-corrective-actions) | 0 | 12 | — |
| [`DAYWORK_REQUEST`](#wbn-database-daywork-request) | 0 | 11 | — |
| [`FMS_TOS_STATUS`](#wbn-database-fms-tos-status) | 0 | 11 | — |
| [`PRODUCTION_PIT_MINING_DISTANCE`](#wbn-database-production-pit-mining-distance) | 0 | 14 | — |
| [`START LIM STOCK`](#wbn-database-start-lim-stock) | 0 | 16 | — |
| [`TEAM_PROFILE`](#wbn-database-team-profile) | 0 | 12 | — |
| [`tempHAULAGE_IWIP`](#wbn-database-temphaulage-iwip) | 0 | 1 | — |
| [`TOS`](#wbn-database-tos) | 0 | 11 | — |
| [`WBN_DATABASE_ERROR_PROCEDURE`](#wbn-database-wbn-database-error-procedure) | 0 | 8 | — |

### WBN_DATABASE — table detail

<a id="wbn-database-equipments-hourly-status"></a>

#### `EQUIPMENTS_HOURLY_STATUS`

**Rows:** 16,558,379  |  **Columns:** 20  |  **DATE:** 1899-12-30 00:00:00 → 2026-07-29 00:00:00

**Columns:** `ID` int, `CONTRACTOR` nvarchar(50), `DATE` datetime, `SHIFT` float, `START_HOUR` float, `END_HOUR` float, `ID_EQ` nvarchar(50), `ACTIVITY` nvarchar(50), `LOCATION` nvarchar(50), `WORKING_HOURS` float, `STBY_HOURS` float, `STBY_CODE` nvarchar(50), `BD_HOURS` float, `BD_CODE` nvarchar(50), `PM_HOURS` float, `PM_CODE` nvarchar(50), `OPERATING_HOURS` float, `REMARK` nvarchar(50), `STATUS` nvarchar(50), `LOCATION_DETAILS` nvarchar(50)

**Identifier vocabularies:**

- `STBY_CODE` — 40 distinct. e.g. `S5`, `S20`, `S15`, `S8`, `S14`, `S10`, `S6`, `S11`, `S13`, `S22`, ``, `S17`
- `BD_CODE` — 67 distinct. e.g. `ES`, `TR`, `CH`, `EN`, `OTH`, `TY`, `BR`, `BU`, `SP`, ``, `UC`, `DB`
- `PM_CODE` — 24 distinct. e.g. ``, `0`, `0,00`, `0.0`, `0.00`, `AC`, `BR`, `BU`, `CH`, `DB`, `DF`, `EN`

**Sample rows** (first 14 of 20 columns):

| ID | CONTRACTOR | DATE | SHIFT | START_HOUR | END_HOUR | ID_EQ | ACTIVITY | LOCATION | WORKING_HOURS | STBY_HOURS | STBY_CODE | BD_HOURS | BD_CODE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | HJS | 2024-10-01T00:00:00.000 | 1.0 | 7.0 | 8.0 | ATCT0450027 | MINING | CBB | 0.0 | 0.17 | S6 | 0.0 |  |
| 2 | HJS | 2024-10-01T00:00:00.000 | 1.0 | 7.0 | 8.0 | ATCT0450027 | MINING | CBB | 0.58 | 0.0 |  | 0.0 |  |
| 3 | HJS | 2024-10-01T00:00:00.000 | 1.0 | 7.0 | 8.0 | ATCT0450027 | MINING | CBB | 0.25 | 0.0 |  | 0.0 |  |
| 4 | HJS | 2024-10-01T00:00:00.000 | 1.0 | 8.0 | 9.0 | ATCT0450027 | MINING | CBB | 1.0 | 0.0 |  | 0.0 |  |
| 5 | HJS | 2024-10-01T00:00:00.000 | 1.0 | 9.0 | 10.0 | ATCT0450027 | MINING | CBB | 1.0 | 0.0 |  | 0.0 |  |

<a id="wbn-database-equipments-hourly-activities"></a>

#### `EQUIPMENTS_HOURLY_ACTIVITIES`

**Rows:** 4,682,656  |  **Columns:** 21  |  **DATE:** 1899-12-30 → 2026-07-29

**Columns:** `ID` int, `CONTRACTOR` nvarchar(50), `DATE` date, `SHIFT` int, `START_HOUR` int, `END_HOUR` int, `ACTIVITY` nvarchar(255), `MATERIAL` nvarchar(255), `MATERIAL_CLASS` nvarchar(255), `ORIGIN_AREA` nvarchar(255), `ORIGIN_ID` nvarchar(255), `SUB_PIT` nvarchar(255), `PROD_ID` nvarchar(255), `DESTINATION_AREA` nvarchar(255), `DESTINATION_ID` nvarchar(255), `DISTANCE` float, `TRUCK_ID` nvarchar(255), `TRUCK_FACTOR` float, `EXCAVATOR_ID` nvarchar(255), `RIT` float, `REMARK` nvarchar(255)

**Identifier vocabularies:**

- `ORIGIN_ID` — 118,417 distinct. e.g. `P367-88-4-Z367`, `Z321-BOULDER BANCH`, `Z321-SPOIL BANCH`, `P377-070-4-Z349`, `P376-072-4-Z349`, `Z349-SPOIL BANCH`, `Z375-BIOMAS`, `P360-87-5-Z375`, `Z375-SPOIL BANCH`, `P381-64-1-Z342`, `P357-83-5-Z372`, `P357-083-5-Z372`
- `PROD_ID` — 117,470 distinct. e.g. `P367-88-4-Z367`, `Z321-BOULDER BANCH`, `Z321-SPOIL BANCH`, `P377-070-4-Z349`, `P376-072-4-Z349`, `Z349-SPOIL BANCH`, `Z375-BIOMAS`, `P360-87-5-Z375`, `P381-64-1-Z342`, `P357-83-5-Z372`, `P357-083-5-Z372`, `Z371-SPOIL BANCH`
- `DESTINATION_ID` — 40,512 distinct. e.g. `RIM.E.02`, `RIM.104`, `RIM.080`, `RIM.105`, `RIM.106`, `RIM.E.05`, `RIM.107`, `RIM.109`, `RIM.110`, `RIM.108`, `RIM.111`, `RIM.02`
- `TRUCK_ID` — 1,382 distinct. e.g. `ADT153`, `ADT168`, `ADT169`, `ADT141`, `ADT135`, `ADT133`, `ADT167/165`, `ADT143/168`, `ADT139/147`, `ADT142`, `ADT148`, `ADT138`
- `EXCAVATOR_ID` — 436 distinct. e.g. `E846`, `E835`, `E841`, `E845`, `E838`, `E844`, `E782`, `E781`, `E777`, `E834`, `E840/849`, `E840`

**Sample rows** (first 14 of 21 columns):

| ID | CONTRACTOR | DATE | SHIFT | START_HOUR | END_HOUR | ACTIVITY | MATERIAL | MATERIAL_CLASS | ORIGIN_AREA | ORIGIN_ID | SUB_PIT | PROD_ID | DESTINATION_AREA |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6634 | RIM | 2024-11-26T00:00:00.000 | 1 | 8 | 9 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD |
| 6635 | RIM | 2024-11-26T00:00:00.000 | 1 | 9 | 10 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD |
| 6636 | RIM | 2024-11-26T00:00:00.000 | 1 | 10 | 11 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD |
| 6637 | RIM | 2024-11-26T00:00:00.000 | 1 | 11 | 12 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD |
| 6638 | RIM | 2024-11-26T00:00:00.000 | 1 | 13 | 14 | MINING | LIM |  | PS | P367-88-4-Z367 | PS1 | P367-88-4-Z367 | LD |

<a id="wbn-database-block-indesign"></a>

#### `BLOCK_INDESIGN`

**Rows:** 4,288,722  |  **Columns:** 13  |  **DATE:** 2025-06-12 00:00:00 → 2026-05-10 00:00:00

**Columns:** `ID` int, `DATE` datetime, `PIT` nvarchar(255), `X` float, `Y` float, `Z` float, `BLOCK_ID` nvarchar(255), `PP_INPIT` float, `size (X)` float, ` size(Y)` float, ` size(Z)` float, `SUBPIT` nvarchar(255), `SUBPIT_REMARKS` nvarchar(255)

**Identifier vocabularies:**

- `BLOCK_ID` — 4,274,624 distinct. e.g. `401_B23_S198`, `401_B23_S199`, `401_B23_S200`, `401_B23_S201`, `401_B23_S202`, `401_B23_S203`, `401_B23_S204`, `401_B23_S205`, `401_B24_S180`, `401_B24_S181`, `401_B24_S182`, `401_B24_S183`

**Coordinate extent:** `X` 380337.5 → 393731.25; `Y` 55412.5 → 92081.25

**Sample rows**:

| ID | DATE | PIT | X | Y | Z | BLOCK_ID | PP_INPIT | size (X) |  size(Y) |  size(Z) | SUBPIT | SUBPIT_REMARKS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2025-06-12T00:00:00.000 | CBB | 380600.0 | 57750.0 | 402.0 | 401_B23_S198 | 0.0898 | 12.5 | 12.5 | 2.0 | CBBB3 | Old_25x25x2 |
| 2 | 2025-06-12T00:00:00.000 | CBB | 380600.0 | 57737.5 | 402.0 | 401_B23_S199 | 0.5566 | 12.5 | 12.5 | 2.0 | CBBB3 | Old_25x25x2 |
| 3 | 2025-06-12T00:00:00.000 | CBB | 380600.0 | 57725.0 | 402.0 | 401_B23_S200 | 0.8691 | 12.5 | 12.5 | 2.0 | CBBB3 | Old_25x25x2 |
| 4 | 2025-06-12T00:00:00.000 | CBB | 380600.0 | 57712.5 | 402.0 | 401_B23_S201 | 1.0 | 12.5 | 12.5 | 2.0 | CBBB3 | Old_25x25x2 |
| 5 | 2025-06-12T00:00:00.000 | CBB | 380600.0 | 57700.0 | 402.0 | 401_B23_S202 | 0.998 | 12.5 | 12.5 | 2.0 | CBBB3 | Old_25x25x2 |

<a id="wbn-database-equipments-status"></a>

#### `EQUIPMENTS_STATUS`

**Rows:** 3,680,170  |  **Columns:** 22  |  **DATE:** 2024-10-01 → 2026-07-29

**Columns:** `ID` int, `CONTRACTOR` nvarchar(50), `DATE` date, `SHIFT` int, `ID_EQ` nvarchar(50), `STATUS` nvarchar(50), `ACTIVITY` nvarchar(50), `LOCATION` nvarchar(50), `LOCATION_DETAILS` nvarchar(50), `HOUR_METER_START` float, `HOUR_METER_END` float, `USAGE_KM_METER` float, `WORKING_HOURS` float, `STBY_HOURS` float, `STBY_CODE` nvarchar(50), `BD_HOURS` float, `BD_CODE` nvarchar(50), `BD_START` date, `BD_EST_RFU` date, `BD_COMPARTMENT` nvarchar(50), `BD_STATUS` nvarchar(50), `REMARK` nvarchar(50)

**Sample rows** (first 14 of 22 columns):

| ID | CONTRACTOR | DATE | SHIFT | ID_EQ | STATUS | ACTIVITY | LOCATION | LOCATION_DETAILS | HOUR_METER_START | HOUR_METER_END | USAGE_KM_METER | WORKING_HOURS | STBY_HOURS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 26533 | SMA | 2024-10-01T00:00:00.000 |  | EX407 | BREAKDOWN | PIT MAINTENANCE | WORKSHOP | Workshop |  | 16154.4 |  |  |  |
| 26534 | SMA | 2024-10-01T00:00:00.000 |  | EX408 | RFU | PIT MAINTENANCE | TF | Pit TF |  | 19621.9 |  |  |  |
| 26535 | SMA | 2024-10-01T00:00:00.000 |  | EX409 | BREAKDOWN | PIT MAINTENANCE | WORKSHOP | Workshop |  | 19905.0 |  |  |  |
| 26536 | SMA | 2024-10-01T00:00:00.000 |  | EX410 | BREAKDOWN | PIT MAINTENANCE | WORKSHOP | Workshop |  | 17538.2 |  |  |  |
| 26537 | SMA | 2024-10-01T00:00:00.000 |  | EX411 | BREAKDOWN | PIT MAINTENANCE | WORKSHOP | Workshop |  | 18204.1 |  |  |  |

<a id="wbn-database-haulage"></a>

#### `HAULAGE`

**Rows:** 3,509,230  |  **Columns:** 24  |  **DATE:** 2021-09-24 → 2026-07-28

**Columns:** `ID` int, `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `TRUCK_ID` nvarchar(50), `TIME_LOADED` time, `TIME_EMPTY` time, `RIT` int, `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(50), `DESTINATION_AREA` nvarchar(50), `DESTINATION_ID` nvarchar(50), `KG_LOADED` float, `KG_EMPTY` float, `KG_NET` float, `WMT` float, `BCM` float, `WB_ID` nvarchar(50), `REMARK` nvarchar(50), `TICKET_NO` nvarchar(30), `UPDATE_DATE` datetime2, `UPDATE_BY` nvarchar(50)

**Identifier vocabularies:**

- `TRUCK_ID` — 7,167 distinct. e.g. `DT-5702`, `DT-5725`, `DT-5737`, `DT-5525`, `DT-5729`, `DT-5171`, `DT-5723`, `DT-5715`, `DT-5126`, `DT-5172`, `DT-5726`, `DT-5102`
- `ORIGIN_ID` — 65,874 distinct. e.g. `A.14`, `A.15`, `A.16`, `A.17`, `A.18`, `A.19`, `A.2573`, `A.2801`, `A.2806`, `A.2838`, `A.2894`, `A.2907`
- `DESTINATION_ID` — 9,127 distinct. e.g. `AA.268`, `AA.355`, `AA.419.A`, `AA.420`, `AA.421`, `AA.422`, `AA.423`, `AA.424`, `AA.425`, `AA.426`, `AA.427`, `AA.428`
- `WB_ID` — 87 distinct. e.g. `WB_RIM`, `WB_SMA_KM33`, `WB_STM_KM32`, `TIDAK TIMBANG`, `WB 1`, `WB_HJS`, `WB 4 CBB`, `TIMBANGAN ERROR`, `WB_MTM`, `WB_IWIP_T11`, `WB_WBN`, `WB_IWIP_T5`

**Sample rows** (first 14 of 24 columns):

| ID | DATE | SHIFT | CONTRACTOR | ACTIVITY | MATERIAL | TRUCK_ID | TIME_LOADED | TIME_EMPTY | RIT | ORIGIN_AREA | ORIGIN_ID | DESTINATION_AREA | DESTINATION_ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3127402 | 2025-01-20T00:00:00.000 | 1 | GMG | HAULAGE | SAP | DT-5702 | 12:48:53 | 13:30:06 | 1 | TOS_KR_STM_08 | KR.I.1280 | POS 6 | AA.525 |
| 3127403 | 2025-01-20T00:00:00.000 | 1 | GMG | HAULAGE | SAP | DT-5725 | 12:49:21 | 13:27:54 | 1 | TOS_KR_STM_05 | KR.I.1277 | POS 6 | AAM.314 |
| 3127404 | 2025-01-20T00:00:00.000 | 1 | GMG | HAULAGE | SAP | DT-5737 | 12:52:01 | 13:42:24 | 1 | TOS_KR_STM_08 | KR.I.1280 | POS 6 | AA.525 |
| 3127405 | 2025-01-20T00:00:00.000 | 1 | GMG | HAULAGE | SAP | DT-5525 | 12:54:51 | 13:53:01 | 1 | TOS_KR_STM_08 | KR.I.1280 | POS 6 | AA.525 |
| 3127406 | 2025-01-20T00:00:00.000 | 1 | GMG | HAULAGE | SAP | DT-5729 | 13:07:13 | 14:09:31 | 1 | TOS_KR_STM_05 | KR.I.1277 | POS 6 | AAM.314 |

<a id="wbn-database-s123-stock-shape-old"></a>

#### `S123_STOCK_SHAPE_OLD`

**Rows:** 1,732,432  |  **Columns:** 12  |  **UPDATE_DATE:** 2026-03-17 08:41:50 → 2026-06-27 09:47:07

**Columns:** `UPDATE_DATE` datetime, `id` int, `FID` int, `name` nvarchar(255), `CreationDa` datetime, `Creator` nvarchar(255), `EditDate` datetime, `geom` geography(-1), `new_dome_i` nvarchar(255), `old_dome_i` nvarchar(255), `menggantik` nvarchar(255), `OBJECTID` int

*Sample unavailable: could not serialise*

<a id="wbn-database-haulage-iwip-ext"></a>

#### `HAULAGE_IWIP_EXT`

**Rows:** 1,508,871  |  **Columns:** 28  |  **FETCH_DATE:** 2026-05-30 11:32:40 → 2026-07-11 05:10:04

**Columns:** `FETCH_DATE` datetime2, `SERIAL_NO` nvarchar(255), `WB_TIME` int, `DATE` date, `WB_ID` nvarchar(255), `TICKET_NO` nvarchar(50), `TRUCK_ID` nvarchar(255), `CARGO_NAME` nvarchar(255), `ORIGIN_ID` nvarchar(255), `SELLER` nvarchar(255), `BUYER` nvarchar(255), `CONTRACTOR` nvarchar(255), `ORIGIN_AREA` nvarchar(255), `DESTINATION_AREA` nvarchar(255), `WEIGHING_STATUS` nvarchar(255), `BUSINESS_TYPE` nvarchar(255), `GROSS_WEIGHT` bigint, `TARE_WEIGHT` bigint, `NET_WEIGHT` bigint, `FIRST_WB_TIME` datetime, `SECOND_WB_TIME` datetime, `GROSS_WEIGHT_TIME` datetime, `TARE_WEIGHT_TIME` datetime, `GROSS_WEIGHT_POINT` nvarchar(255), `TARE_WEIGHT_POINT` nvarchar(255), `IS_COMPLETED` nvarchar(255), `SHIFT` nvarchar(255), `REMARKS` nvarchar(255)

**Identifier vocabularies:**

- `WB_ID` — 18 distinct. e.g. `T1`, `T10`, `T11`, `T12`, `T13`, `T14`, `T15`, `T16`, `T17`, `T18`, `T19`, `T2`
- `TRUCK_ID` — 4,021 distinct. e.g. `R587`, `K043`, `B792`, `R591`, `L643`, `L647`, `L547`, `B795`, `L697`, `L691`, `L633`, `B357`
- `ORIGIN_ID` — 10,193 distinct. e.g. `CN857`, `HN635`, `KN773`, `L2N341`, `LCMI-ZL-25080`, `QN341`, `IWHD006`, `F1N247`, `KN769`, `SWSS.01`, `SN388`, `CN868`

**Sample rows** (first 14 of 28 columns):

| FETCH_DATE | SERIAL_NO | WB_TIME | DATE | WB_ID | TICKET_NO | TRUCK_ID | CARGO_NAME | ORIGIN_ID | SELLER | BUYER | CONTRACTOR | ORIGIN_AREA | DESTINATION_AREA |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-05-30T11:33:15.000 | 16538 | 20251231 | 2025-12-31T00:00:00.000 | T10 | 10A20251231025052 | R587 | ?? | CN857 | YNI????? | YNI????? | EOS?????? | 15#??C??-YNI????? | POS14-YNI????? |
| 2026-05-30T11:33:15.000 | 16280 | 20251231 | 2025-12-31T00:00:00.000 | T10 | 10A20251231025830 | K043 | ?? | CN857 | YNI????? | YNI????? | ????F?? | 15#??C??-YNI????? | POS14-YNI????? |
| 2026-05-30T11:33:15.000 | 14403 | 20251231 | 2025-12-31T00:00:00.000 | T10 | 10A20251231030555 | B792 | ?? | HN635 | HKNI????? | HKNI????? | ????H?? | 15#??G??-HKNI????? | EOS-HKNI????? |
| 2026-05-30T11:33:15.000 | 13291 | 20251231 | 2025-12-31T00:00:00.000 | T10 | 10A20251231031308 | R591 | ?? | CN857 | YNI????? | YNI????? | EOS?????? | 15#??C??-YNI????? | POS14-YNI????? |
| 2026-05-30T11:33:15.000 | 15865 | 20251231 | 2025-12-31T00:00:00.000 | T10 | 10A20251231031429 | L643 | ?? | HN635 | HKNI????? | HKNI????? | EOS?????? | 15#??G??-HKNI????? | EOS-HKNI????? |

<a id="wbn-database-rsf-hauling-data"></a>

#### `RSF_HAULING_DATA`

**Rows:** 1,143,509  |  **Columns:** 18  |  **DATE:** 2023-12-23 00:00:00 → 2026-01-22 00:00:00

**Columns:** `ID` int, `DATE` datetime, `SHIFT` int, `COMPANY` nvarchar(50), `DEPARTEMENT` nvarchar(50), `UNIT_TYPE` nvarchar(50), `UNIT_BRAND` nvarchar(50), `NB_UNIT` nvarchar(50), `TRIP` float, `LOADING_TIME` time, `UNLOADING_TIME` time, `ORIGIN_KM` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION_KM` nvarchar(50), `DESTINATION` nvarchar(50), `LOCATION` nvarchar(50), `ELEVATION` float, `TF` float

**Identifier vocabularies:**

- `UNIT_TYPE` — 644 distinct. e.g. ``, `10  BALL  DT`, `10 BALL  DT`, `10 WHEELS`, `10WHEELS`, `12  BALL  DT`, `12 BALL  DT`, `12 BALL DT`, `12 WHEELS`, `12WHEELS`, `B236`, `B301`
- `UNIT_BRAND` — 2 distinct. e.g. `HOWO`, `K`
- `NB_UNIT` — 4,331 distinct. e.g. `L240`, `K365`, `L216`, `L565`, `L236`, `K493`, `B911`, `L248`, `L257`, `L516`, `L204`, `L188`

**Sample rows** (first 14 of 18 columns):

| ID | DATE | SHIFT | COMPANY | DEPARTEMENT | UNIT_TYPE | UNIT_BRAND | NB_UNIT | TRIP | LOADING_TIME | UNLOADING_TIME | ORIGIN_KM | ORIGIN | DESTINATION_KM |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 321550 | 2024-10-01T00:00:00.000 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L240 | 1.0 |  |  | KM8 | HUAFEI | KM26 |
| 321551 | 2024-10-01T00:00:00.000 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | K365 | 1.0 |  |  | KM8 | HUAFEI | KM26 |
| 321552 | 2024-10-01T00:00:00.000 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L216 | 1.0 |  |  | KM8 | HUAFEI | KM26 |
| 321553 | 2024-10-01T00:00:00.000 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L565 | 1.0 |  |  | KM8 | HUAFEI | KM26 |
| 321554 | 2024-10-01T00:00:00.000 | 1 | RIM | HUAFEI TAILING | 10 WHEELS | HOWO | L236 | 1.0 |  |  | KM8 | HUAFEI | KM26 |

<a id="wbn-database-waiting-time"></a>

#### `WAITING_TIME`

**Rows:** 878,240  |  **Columns:** 24  |  **DATE:** 2025-01-01 → 2026-07-22

> Measured loading and dumping dwell in minutes (LOADING_DIFFERENCE_TIME, DUMPING_DIFFERENCE_TIME). Already used; covers 24.8% of trips on a truck+date+shift join.

**Columns:** `ID` int, `TEAM` nvarchar(10), `DATE` date, `EQUIPMENT_ID` nvarchar(50), `SHIFT` int, `ORIGIN_ID` nvarchar(50), `ORIGIN_AREA` nvarchar(50), `DESTINATION` nvarchar(100), `BLOCK_ID` nvarchar(50), `RIT` int, `WB_ID` nvarchar(50), `LOADING_WAITING_TIME` time, `LOADING_TIME` time, `LOADING_DIFFERENCE_TIME` int, `DUMPING_WAITING_TIME` time, `DUMPING_TIME` time, `DUMPING_DIFFERENCE_TIME` int, `DRIVER_ID` nvarchar(50), `PIT` nvarchar(50), `FUEL_FILLING_TIME` time, `REMARK` nvarchar(255), `FUEL_FILLING_TIME 2` time, `TOTAL_FUEL` nvarchar(50), `TOTAL_FUEL 2` nvarchar(50)

**Identifier vocabularies:**

- `EQUIPMENT_ID` — 1,288 distinct. e.g. `L961`, `K811`, `N035`, `L958`, `L054`, `L056`, `K724`, `N726`, `K620`, `N657`, `N498`, `N693`
- `ORIGIN_ID` — 1,523 distinct. e.g. `BATU KAPUR`, `M1_POS12_01`, `SAMPLE`, `LD_POS12_001/D`, `ADM.678`, `LD.POS 12.001`, `L2NW038`, `BLB-A.131`, `M1_POS12_001`, `BLB.LIM/B-BSE`, `BLB.LIM.1125`, `BLB-Q.16`
- `BLOCK_ID` — 14,221 distinct. e.g. `BATU KAPUR`, `KRENE.I.708`, `SAMPLE`, `E/KRENE.I.090`, `TF.B.3935`, `LD.KR.003`, `TOS1-RIM-1174`, `E/KRENE.I.091`, `BLB.G.5759`, `TF.B.3009`, `E/BLB.D.925`, `E/BLB.G.2775`
- `WB_ID` — 53 distinct. e.g. `NOT WEIGHED`, `14`, `8`, `6A`, `7L`, `15L`, `NOT WEIGTH`, `TIMBANGAN 14`, `12`, `13`, `11`, `NO WEIGHED`
- `DRIVER_ID` — 5,105 distinct. e.g. `8240209005`, `8241011100`, `8231207168`, `8240303036`, `8240812099`, `8240114149`, `8231204004`, `8241119101`, `8240122006`, `8240219029`, `8240701079`, `8240531063`

**Sample rows** (first 14 of 24 columns):

| ID | TEAM | DATE | EQUIPMENT_ID | SHIFT | ORIGIN_ID | ORIGIN_AREA | DESTINATION | BLOCK_ID | RIT | WB_ID | LOADING_WAITING_TIME | LOADING_TIME | LOADING_DIFFERENCE_TIME |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 71844 | E | 2025-10-30T00:00:00.000 | L961 | 2 | BATU KAPUR | 15KM | 13KM | BATU KAPUR | 1 | NOT WEIGHED | 02:47:00 | 05:55:00 | 188 |
| 71845 | B | 2025-10-30T00:00:00.000 | K811 | 1 | M1_POS12_01 | TOS_KRENE_01 | POS12 | KRENE.I.708 | 1 | 14 | 09:47:00 | 12:07:00 | 140 |
| 71846 | E | 2025-10-30T00:00:00.000 | N035 | 1 | BATU KAPUR | 15KM | 13KM | BATU KAPUR | 1 | NOT WEIGHED | 11:00:00 | 13:18:00 | 138 |
| 71847 | D | 2025-10-30T00:00:00.000 | L958 | 1 | SAMPLE | CSW | BIRI | SAMPLE | 1 | NOT WEIGHED | 16:41:00 | 18:57:00 | 136 |
| 71848 | B | 2025-10-30T00:00:00.000 | L054 | 1 | M1_POS12_01 | TOS_KRENE_01 | POS12 | KRENE.I.708 | 1 | 14 | 14:55:00 | 17:09:00 | 134 |

<a id="wbn-database-haulage-iwip"></a>

#### `HAULAGE_IWIP`

**Rows:** 572,742  |  **Columns:** 35  |  **DATE:** 2025-12-27 → 2026-07-08

**Columns:** `SERIAL_NO` nvarchar(50), `WB_TIME` float, `DATE` date, `WB_ID` nvarchar(50), `TICKET_NO` nvarchar(50), `TRUCK_ID` nvarchar(50), `CARGO_NAME` nvarchar(50), `SELLER` nvarchar(50), `BUYER` nvarchar(50), `CONTRACTOR` nvarchar(50), `ORIGIN_AREA` nvarchar(50), `ORIGIN_AREA_CLEAN` nvarchar(50), `ORIGIN_ID` nvarchar(50), `ORIGIN_ID_CLEAN` nvarchar(50), `DESTINATION_AREA` nvarchar(50), `DESTINATION_AREA_CLEAN` nvarchar(50), `DESTINATION_ID` nvarchar(50), `DESTINATION_ID_CLEAN` nvarchar(50), `WEIGHING_STATUS` float, `BUSINESS_TYPE` nvarchar(50), `ACTIVITY` nvarchar(50), `GROSS_WEIGHT` float, `TARE_WEIGHT` float, `NET_WEIGHT` float, `FIRST_WB_TIME` datetime, `SECOND_WB_TIME` datetime, `GROSS_WEIGHT_TIME` datetime, `TARE_WEIGHT_TIME` datetime, `GROSS_WEIGHT_POINT` nvarchar(50), `TARE_WEIGHT_POINT` nvarchar(50), `IS_COMPLETED` nvarchar(50), `SHIFT` nvarchar(50), `REMARKS` nvarchar(50), `FETCH_DATE` datetime, `IS_CLEAN` int

**Identifier vocabularies:**

- `WB_ID` — 19 distinct. e.g. ``, `1`, `10`, `11`, `12`, `13`, `14`, `15`, `16`, `17`, `18`, `19`
- `TRUCK_ID` — 3,270 distinct. e.g. ``, `B345`, `N539`, `R123`, `L088`, `B011`, `K927`, `K955`, `K946`, `K552`, `K542`, `K551`
- `ORIGIN_ID` — 3,398 distinct. e.g. ``, `E/TF.B.238`, `LD_TF_002`, `HMT-M-26035`, `HMT-M-26032`, `HMT-M-26031`, `HMT-M-26034`, `TF.B.4810`, `TF.A.7014`, `TF.A.7019`, `TF.B.4823`, `TF.B.4822`
- `DESTINATION_ID` — 1,990 distinct. e.g. ``, `SWSS.01`, `L2N-ADM.433`, `MN-M1_POS12_002`, `L2N-ADM.484`, `ACM.652`, `SSH-LY-004`, `F2NF019`, `SN497`, `GNF035`, `BNF051`, `CNF029`

**Sample rows** (first 14 of 35 columns):

| SERIAL_NO | WB_TIME | DATE | WB_ID | TICKET_NO | TRUCK_ID | CARGO_NAME | SELLER | BUYER | CONTRACTOR | ORIGIN_AREA | ORIGIN_AREA_CLEAN | ORIGIN_ID | ORIGIN_ID_CLEAN |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 0.0 |  |  |  |  |  |  |  |  |  |  |  |  |
| 3943 | 20260102.0 | 2026-01-02T00:00:00.000 | 10 | 10A20260102123411 | B345 |  |  |  | ????F?? | CAS????-WBN????? | CRUSHER CAS |  |  |
| 3741 | 20260102.0 | 2026-01-02T00:00:00.000 | 10 | 10A20260102132414 | B345 |  |  |  | ????F?? | CAS????-WBN????? | CRUSHER CAS |  |  |
| 318 | 20260102.0 | 2026-01-02T00:00:00.000 | 10 | 10A20260102144822 | B345 |  |  |  | ????F?? | CAS????-WBN????? | CRUSHER CAS |  |  |
| 3327 | 20260104.0 | 2026-01-04T00:00:00.000 | 10 | 10A20260104102217 | N539 |  |  |  | INLE??C?? | POS12 EXT-IFMI????? | POS 12 |  |  |

<a id="wbn-database-tos-status"></a>

#### `TOS_STATUS`

**Rows:** 548,621  |  **Columns:** 6  |  **DATE:** 2024-09-30 00:00:00 → 2026-07-28 00:00:00

**Columns:** `ID` int, `CONTRACTOR` nvarchar(50), `DATE` datetime, `SHIFT` float, `STOCK_ID` nvarchar(50), `STOCK_STATUS` nvarchar(50)

**Identifier vocabularies:**

- `STOCK_ID` — 42,992 distinct. e.g. `TF.A.2441`, `TF.A.2446`, `TF.A.2452`, `TF.A.2457`, `TF.A.2469`, `TF.A.249`, `TF.A.250`, `TF.A.2503`, `TF.A.2521`, `TF.A.2524`, `TF.B.587`, `TF.B.598`

**Sample rows**:

| ID | CONTRACTOR | DATE | SHIFT | STOCK_ID | STOCK_STATUS |
|---|---|---|---|---|---|
| 1 |  | 2025-03-12T00:00:00.000 | 1.0 | TF.A.2441 | COMPLETE |
| 2 |  | 2025-03-12T00:00:00.000 | 2.0 | TF.A.2441 | COMPLETE |
| 3 |  | 2025-03-13T00:00:00.000 | 1.0 | TF.A.2441 | COMPLETE |
| 4 |  | 2025-03-13T00:00:00.000 | 2.0 | TF.A.2441 | COMPLETE |
| 5 |  | 2025-03-14T00:00:00.000 | 1.0 | TF.A.2441 | COMPLETE |

<a id="wbn-database-day-works"></a>

#### `DAY_WORKS`

**Rows:** 495,592  |  **Columns:** 27  |  **DATE:** 2024-10-15 → 2026-07-25

**Columns:** `ID` int, `UUID` nvarchar(255), `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY_CAT` nvarchar(50), `ACTIVITY_DESC` nvarchar(255), `ACTIVITY_PLANNED` nvarchar(50), `ACTIVITY_TIME_START` time, `ACTIVITY_TIME_END` time, `OPERATOR_ID` nvarchar(50), `UNIT_TYPE` nvarchar(50), `UNIT_CLASS` nvarchar(50), `UNIT_ID` nvarchar(50), `UNIT_START_HOUR_METER` float, `UNIT_END_HOUR_METER` float, `LOCATION` nvarchar(255), `ROAD_NAME` nvarchar(50), `ROAD_STA_KM` float, `ROAD_END_KM` float, `ROAD_LANE` nvarchar(50), `LOADING_POINT` nvarchar(50), `LOADING_RIT` float, `DISTANCE_KM` float, `REMARK` nvarchar(255), `UPDATE_DATE` datetime, `UPDATE_BY` nvarchar(50)

**Identifier vocabularies:**

- `OPERATOR_ID` — 18,559 distinct. e.g. `Matius Irfan`, `Budi Sulistiyo`, `Spare/To Be Named`, `Muhammad Indra Sangadji`, `Murdiyanto`, `La Ode Muju Taro`, `Billy Meyfandi Nangin`, `Johan Fery Napitupulu`, `Irwanto Kandolla`, `Mudfar D R Malan`, `Hendra Yanto Seleky`, `Faisal Panigoro`
- `UNIT_TYPE` — 64 distinct. e.g. `Compactor`, `Motor Grader`, `Water Truck`, `Hauler`, `Exca`, `GRADER`, `DT`, `BULLDOZER`, `EXCAVATOR`, `WT`, `DOZER`, `WL`
- `UNIT_CLASS` — 135 distinct. e.g. `110 NE`, `535`, `20 Ton`, `150`, `CAT 160K`, `Bomag 20t`, `Volvo 20t`, `Hino 500`, `Hitachi 20`, `Hitachi 6.5`, `SANY-SY215H`, `Komatsu GD 535`
- `UNIT_ID` — 1,951 distinct. e.g. `VRVV11011`, `MGKM53007`, `WTHN0200018`, `VRBM0100002`, `MGKM0150010`, `WTHN28009`, `VRVV11010`, `MGCT16003`, `WTHN26002`, `DTIZ0200330`, `DTIZ0200380`, `DTIZ34121`

**Sample rows** (first 14 of 27 columns):

| ID | UUID | DATE | SHIFT | CONTRACTOR | ACTIVITY_CAT | ACTIVITY_DESC | ACTIVITY_PLANNED | ACTIVITY_TIME_START | ACTIVITY_TIME_END | OPERATOR_ID | UNIT_TYPE | UNIT_CLASS | UNIT_ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 59482 |  | 2024-10-15T00:00:00.000 | 1 | HJS | ROAD MAINTENANCE | Compacting | PLANNED | 07:00:00 | 18:00:00 | Matius Irfan | Compactor | 110 NE | VRVV11011 |
| 59483 |  | 2024-10-15T00:00:00.000 | 1 | HJS | ROAD MAINTENANCE | Spreading Material - Scraping Mud - Gr… | PLANNED | 07:00:00 | 18:00:00 | Budi Sulistiyo | Motor Grader | 535 | MGKM53007 |
| 59484 |  | 2024-10-15T00:00:00.000 | 1 | HJS | ROAD MAINTENANCE | Spraying - Watering | PLANNED | 07:00:00 | 18:00:00 | Spare/To Be Named | Water Truck | 20 Ton | WTHN0200018 |
| 59485 |  | 2024-10-15T00:00:00.000 | 1 | HJS | ROAD MAINTENANCE | Compacting | PLANNED | 07:00:00 | 18:00:00 | Muhammad Indra Sangadji | Compactor | 110 NE | VRBM0100002 |
| 59486 |  | 2024-10-15T00:00:00.000 | 1 | HJS | ROAD MAINTENANCE | Spreading Material - Scraping Mud - Gr… | PLANNED | 07:00:00 | 18:00:00 | Murdiyanto | Motor Grader | 150 | MGKM0150010 |

<a id="wbn-database-production-activity-pit"></a>

#### `PRODUCTION_ACTIVITY_PIT`

**Rows:** 450,848  |  **Columns:** 34  |  **DATE:** 2024-07-01 00:00:00 → 2026-07-29 00:00:00

**Columns:** `ID` int, `DATE` datetime, `CONTRACTOR` nvarchar(255), `SHIFT` float, `AREA` nvarchar(255), `SUB_AREA` nvarchar(255), `ACTIVITY` nvarchar(255), `ENTITY` nvarchar(255), `MATERIAL` nvarchar(255), `MATERIAL_CLASS` nvarchar(255), `ORIGIN_ID_BLOCK_ID` nvarchar(255), `PROD_ID` nvarchar(255), `BLAST_ID` nvarchar(255), `DESTINATION_AREA` nvarchar(255), `DESTINATION_ID` nvarchar(255), `TF_BCM` float, `TF_WMT` float, `RIT` float, `BCM` float, `WMT` float, `EXCA_ID` nvarchar(255), `GRAP_ID` nvarchar(255), `WL_ID` nvarchar(255), `ADT_ID` nvarchar(255), `DT_ID` nvarchar(255), `DOZER_ID` nvarchar(255), `GRADER_ID` nvarchar(255), `COMPACT_ID` nvarchar(255), `WT_ID` nvarchar(255), `RIG_ID` nvarchar(255), `STATUS` nvarchar(255), `REMARK` nvarchar(255), `UPDATE_DATE` datetime, `UPDATE_BY` nvarchar(255)

**Identifier vocabularies:**

- `ORIGIN_ID_BLOCK_ID` — 126,056 distinct. e.g. `TOS_BLB_RIM_05`, `CBB4`, `BLB5`, `CBB_JALAN_A_KM18`, `CRUSHER_BLB`, `T438_B104 _S377`, `T465_B88 _S341`, `T465_B88 _S342`, `BKS_LAM_LD_TF_001`, `TOPSOIL_TEMP_SD_TF_01`, `BOULDER_LD_TF_001`, `T462_B89_S344`
- `PROD_ID` — 162,772 distinct. e.g. `T438_B104 _S377`, `T465_B88 _S341`, `T465_B88 _S342`, `BKS_LAM_LD_TF_001`, `TOPSOIL_TEMP_SD_TF_01`, `BOULDER_LD_TF_001`, `T462_B89_S344`, `T462_B90_S344`, `REHANDLING_SD_TF4`, `T465_B90 _S396`, `T465_B89 _S345`, `T465_B90_S345`
- `BLAST_ID` — 1,303 distinct. e.g. `20260509_BLB 3 TOS 5 IWIP-RIM ID-02`, `20260117_CBB 4 PP ID 21 QUARY`, `20260430_BLB 5 IWIP-RIM ID STP`, `20260523_BLB 5 IWIP-RIM ID 66`, ``, `-`, `STM-BL-TF-95-20260518`, `STM-BL-TF-96-20260527`, `STM-BL-TF-94-20260402`, `SMA_BL_32_12/01/2025`, `STM-BL-TF-28-20250111`, `STM-BL-TF-85-20251211`
- `DESTINATION_ID` — 48,172 distinct. e.g. `KM9`, `BLB.G.6991`, `BLB.G.6992`, ``, `-`, `BLB.G.6986`, `BLB.G.6993`, `BLB.G.6990`, `E/T742_B205_S343`, `G/TF.A.004`, `TF.A.8354`, `TF.A.8355`
- `EXCA_ID` — 142 distinct. e.g. `E681`, `E470/E677`, `E781`, `E014`, `E465`, `E470`, `E677/470`, `E946`, `E122`, `E471`, `W643`, `E014/E622`
- `GRAP_ID` — 1 distinct. e.g. ``

**Sample rows** (first 14 of 34 columns):

| ID | DATE | CONTRACTOR | SHIFT | AREA | SUB_AREA | ACTIVITY | ENTITY | MATERIAL | MATERIAL_CLASS | ORIGIN_ID_BLOCK_ID | PROD_ID | BLAST_ID | DESTINATION_AREA |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-05-26T00:00:00.000 | RIM | 1.0 | BLB | BLB3 | BLASTINGS | QUARRY | QRY |  | TOS_BLB_RIM_05 |  | 20260509_BLB 3 TOS 5 IWIP-RIM ID-02 | BSE_KM9 |
| 2 | 2026-05-27T00:00:00.000 | RIM | 1.0 | CBB | CBB4 | BLASTINGS | QUARRY | QRY |  | CBB4 |  | 20260117_CBB 4 PP ID 21 QUARY | BSE_KM9 |
| 3 | 2026-05-27T00:00:00.000 | RIM | 1.0 | CBB | CBB4 | BLASTINGS | QUARRY | QRY |  | CBB4 |  | 20260117_CBB 4 PP ID 21 QUARY | BSE_KM9 |
| 4 | 2026-05-27T00:00:00.000 | RIM | 1.0 | CBB | CBB4 | BLASTINGS | QUARRY | QRY |  | CBB4 |  | 20260117_CBB 4 PP ID 21 QUARY | BSE_KM9 |
| 5 | 2026-05-27T00:00:00.000 | RIM | 1.0 | CBB | CBB4 | BLASTINGS | QUARRY | QRY |  | CBB4 |  | 20260117_CBB 4 PP ID 21 QUARY | BSE_KM9 |

<a id="wbn-database-production-pit-old"></a>

#### `PRODUCTION_PIT_OLD`

**Rows:** 407,593  |  **Columns:** 23  |  **DATE:** 2024-07-01 00:00:00 → 2026-06-07 00:00:00

**Columns:** `ID` int, `CONTRACTOR` nvarchar(255), `DATE` datetime, `SHIFT` float, `ACTIVITY` nvarchar(255), `PIT` nvarchar(255), `SUBPIT` nvarchar(255), `BLOCK_TYPE` nvarchar(255), `BLOCK_STATUS` nvarchar(255), `BLOCK_ID` nvarchar(255), `PROD_ID` nvarchar(255), `MATERIAL` nvarchar(255), `MATERIAL_CLASS` nvarchar(255), `RIT` float, `TF` float, `WMT` float, `DESTINATION` nvarchar(255), `TOS_PILE` nvarchar(255), `BLAST_STATUS` nvarchar(255), `BLAST_ID` nvarchar(255), `UPDATE_DATE` datetime, `UPDATE_BY` nvarchar(50), `REMARK` nvarchar(50)

**Identifier vocabularies:**

- `BLOCK_ID` — 124,195 distinct. e.g. `T429_B164_S46`, `T429_B164_S47`, `T423_B180_S32`, `T423_B180_S33`, `T420_B180_S33`, `T444_B148_S40`, `T423_B165_S53`, `T453_B145_S45`, `T429_B129_S30`, `T453_B146_S44`, `T444_B147_S40`, `T441_B147_S35`
- `PROD_ID` — 160,813 distinct. e.g. `T429_B164_S46`, `T429_B164_S47`, `T423_B180_S32`, `T423_B180_S33`, `T420_B180_S33`, `T444_B148_S40`, `T423_B165_S53`, `T453_B145_S45`, `T429_B129_S30`, `T453_B146_S44`, `T444_B147_S40`, `T441_B147_S35`
- `BLAST_ID` — 1,293 distinct. e.g. `STM-BL-TF-94-20260402`, `SMA_BL_32_12/01/2025`, `STM-BL-TF-28-20250111`, `STM-BL-TF-85-20251211`, `STM-BL-TF-27-20250110`, `PPP_BL_151_250109`, `PPP_BL_158_250115`, `PPP_BL_146_250104`, `PPP_BL_137_241225`, `PPP_BL_142_241230`, `PPP_BL_155_250113`, `PPP_BL_157_250114`

**Sample rows** (first 14 of 23 columns):

| ID | CONTRACTOR | DATE | SHIFT | ACTIVITY | PIT | SUBPIT | BLOCK_TYPE | BLOCK_STATUS | BLOCK_ID | PROD_ID | MATERIAL | MATERIAL_CLASS | RIT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 684434 | STM | 2026-04-17T00:00:00.000 | 1.0 | MINING | TF | TF9 | BLOCK | CLOSE | T429_B164_S46 | T429_B164_S46 | SAP | HGS | 25.0 |
| 684435 | STM | 2026-04-17T00:00:00.000 | 1.0 | MINING | TF | TF9 | BLOCK | CLOSE | T429_B164_S47 | T429_B164_S47 | SAP | HGS | 21.0 |
| 684436 | STM | 2026-04-17T00:00:00.000 | 1.0 | MINING | TF | TF9 | BLOCK | CLOSE | T423_B180_S32 | T423_B180_S32 | SAP | HGS | 26.0 |
| 684437 | STM | 2026-04-17T00:00:00.000 | 1.0 | MINING | TF | TF9 | BLOCK | CLOSE | T423_B180_S33 | T423_B180_S33 | SAP | HGS | 14.0 |
| 684438 | STM | 2026-04-17T00:00:00.000 | 1.0 | MINING | TF | TF9 | BLOCK | CLOSE | T420_B180_S33 | T420_B180_S33 | SAP | HGS | 20.0 |

<a id="wbn-database-assays"></a>

#### `ASSAYS`

**Rows:** 396,428  |  **Columns:** 36  |  **DATE_RECEIVED:** 1900-01-01 → 2026-07-30

**Columns:** `ID` int, `CONTRACTOR` nvarchar(50), `DATE_RECEIVED` date, `DATE_ANALYSIS` date, `ASSAY_TYPE` nvarchar(50), `ASSAY_STATUS` nvarchar(50), `ACTIVITY` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `SAMPLE_ID` nvarchar(50), `SAMPLE_JOB` nvarchar(50), `STOCK_TYPE` nvarchar(50), `STOCK_ID` nvarchar(50), `STOCK_SUBLOT` int, `RIT` float, `WMT` float, `Ni` float, `Fe` float, `Co` float, `Al2O3` float, `CaO` float, `Cr2O3` float, `Fe2O3` float, `MnO` float, `P2O5` float, `SiO2` float, `MgO` float, `C` float, `P` float, `S` float, `K2O` float, `Na2O` float, `TiO2` float, `LOI` float, `MC` float, `REMARK` nvarchar(255)

**Identifier vocabularies:**

- `SAMPLE_ID` — 290,610 distinct. e.g. `CBB-7387`, `CBB-7388`, `CBB-7389`, `CBB-7390`, `CBB-7391`, `CBB-7392`, `CBB-7393`, `CBB-7394`, `CBB-7395`, `CBB-7396`, `CBB-7397`, `CBB-7398`
- `STOCK_ID` — 161,363 distinct. e.g. `0`, `0_AP_16`, `0_AP_18`, `0_AP_19`, `0_AP_20`, `0_AP_21`, `0_AQ_16`, `0_AQ_19`, `0_AQ_20`, `0_AQ_21`, `0_AQ_22`, `0_AR_16`

**Sample rows** (first 14 of 36 columns):

| ID | CONTRACTOR | DATE_RECEIVED | DATE_ANALYSIS | ASSAY_TYPE | ASSAY_STATUS | ACTIVITY | ORIGIN | DESTINATION | SAMPLE_ID | SAMPLE_JOB | STOCK_TYPE | STOCK_ID | STOCK_SUBLOT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 505151 | WBN | 2025-01-16T00:00:00.000 |  | PRELIM |  | TOS SAMPLING |  |  | CBB-7387 | WBN.BB-611 | TOS | BB.D.4679 |  |
| 505152 | WBN | 2025-01-17T00:00:00.000 |  | PRELIM |  | TOS SAMPLING |  |  | CBB-7388 | WBN.BB-612 | TOS | BB.D.4680 |  |
| 505153 | WBN | 2025-01-17T00:00:00.000 |  | PRELIM |  | TOS SAMPLING |  |  | CBB-7389 | WBN.BB-612 | TOS | AR/BB.D.4680 |  |
| 505154 | WBN | 2025-01-17T00:00:00.000 |  | PRELIM |  | TOS SAMPLING |  |  | CBB-7390 | WBN.BB-612 | TOS | BB.D.4681 |  |
| 505155 | WBN | 2025-01-17T00:00:00.000 |  | PRELIM |  | TOS SAMPLING |  |  | CBB-7391 | WBN.BB-612 | TOS | BB.D.4682 |  |

<a id="wbn-database-pp-mined-new-reconcil-meng"></a>

#### `PP_MINED_NEW_RECONCIL_MENG`

**Rows:** 308,918  |  **Columns:** 11

**Columns:** `ID` int, `YEAR` float, `MONTH` float, `WEEK` float, `PIT` nvarchar(255), `X` float, `Y` float, `Z` float, `classification_no` float, `block_id` nvarchar(255), `pp_mined_progress` float

**Identifier vocabularies:**

- `block_id` — 150,982 distinct. e.g. `711_B15_S119`, `715_B15_S119`, `711_B16_S119`, `711_B17_S119`, `715_B16_S119`, `719_B16_S119`, `715_B17_S119`, `719_B17_S119`, `775_B50_S133`, `775_B51_S133`, `779_B49_S131`, `779_B50_S133`

**Coordinate extent:** `X` 380937.5 → 393668.75; `Y` 56425.0 → 92018.75

**Sample rows**:

| ID | YEAR | MONTH | WEEK | PIT | X | Y | Z | classification_no | block_id | pp_mined_progress |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2025.0 | 1.0 | 4.0 | BLB | 384231.25 | 59381.25 | 713.0 | 1.0 | 711_B15_S119 | 0.46 |
| 2 | 2025.0 | 1.0 | 4.0 | BLB | 384231.25 | 59381.25 | 717.0 | 1.0 | 715_B15_S119 | 0.09 |
| 3 | 2025.0 | 1.0 | 4.0 | BLB | 384256.25 | 59381.25 | 713.0 | 1.0 | 711_B16_S119 | 0.47 |
| 4 | 2025.0 | 1.0 | 4.0 | BLB | 384281.25 | 59381.25 | 713.0 | 1.0 | 711_B17_S119 | 0.32 |
| 5 | 2025.0 | 1.0 | 4.0 | BLB | 384256.25 | 59381.25 | 717.0 | 1.0 | 715_B16_S119 | 0.45 |

<a id="wbn-database-sample"></a>

#### `SAMPLE`

**Rows:** 249,620  |  **Columns:** 26  |  **DATE:** 1900-01-02 00:00:00 → 2026-07-20 00:00:00

**Columns:** `CONTRACTOR` nvarchar(50), `DATE` datetime, `SHIFT` float, `SAMPLE_JOB` nvarchar(50), `SAMPLE_ID` nvarchar(50), `SAMPLE_ID_ORI` nvarchar(50), `BLOCK_ID` nvarchar(50), `SAMPLE_COMPOSITE` nvarchar(50), `SAMPLE_TYPE` nvarchar(50), `SAMPLE_CONTRACTOR` nvarchar(50), `ANALYSIS_TYPE` nvarchar(50), `STOCK_AREA` nvarchar(50), `STOCK_ID` nvarchar(50), `PREP_AREA` nvarchar(50), `PREP_SPV` nvarchar(50), `REPORTER` nvarchar(50), `DATE_OUT` datetime, `MATERIAL` nvarchar(50), `RIT` float, `TOTAL_KG` float, `ROCKY_KG` float, `EARTHY_KG` float, `GA_KG` float, `ORIGIN_BLOCK` nvarchar(50), `SAMPLE_STATUS` nvarchar(50), `REMARK` nvarchar(255)

**Identifier vocabularies:**

- `SAMPLE_ID` — 249,620 distinct. e.g. `A`, `AA.129.A`, `AA.4`, `AA.5`, `AA.6`, `AA.H.2302.A`, `AB.2`, `AB.233.A`, `AB.6`, `AB.7`, `AB.8`, `AB.9`
- `BLOCK_ID` — 8,636 distinct. e.g. `775_B54_S118`, `783_B59_S119`, `779_B57_S117`, `783_B55_S125`, `783_B55_S124`, `779_B56_S118`, `783_B55_S123`, `779_B56_S119`, `771_B53_S110`, `779_B55_S124`, `779_B56_S120`, `779_B55_S125`
- `STOCK_ID` — 195,421 distinct. e.g. `A`, `AA.129.A`, `AA.4`, `AA.5`, `AA.6`, `AA.H.2302.A`, `AB.2`, `AB.233.A`, `AB.6`, `AB.7`, `AB.8`, `AB.9`

**Sample rows** (first 14 of 26 columns):

| CONTRACTOR | DATE | SHIFT | SAMPLE_JOB | SAMPLE_ID | SAMPLE_ID_ORI | BLOCK_ID | SAMPLE_COMPOSITE | SAMPLE_TYPE | SAMPLE_CONTRACTOR | ANALYSIS_TYPE | STOCK_AREA | STOCK_ID | PREP_AREA |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|  | 2021-02-13T00:00:00.000 |  |  | A | A |  |  | ORIGINAL |  |  |  | A |  |
|  | 2023-02-26T00:00:00.000 |  |  | AA.129.A | AA.129.A |  |  | ORIGINAL |  |  |  | AA.129.A |  |
|  | 2021-02-13T00:00:00.000 |  |  | AA.4 | AA.4 |  |  | ORIGINAL |  |  |  | AA.4 |  |
|  | 2021-02-13T00:00:00.000 |  |  | AA.5 | AA.5 |  |  | ORIGINAL |  |  |  | AA.5 |  |
|  | 2021-02-13T00:00:00.000 |  |  | AA.6 | AA.6 |  |  | ORIGINAL |  |  |  | AA.6 |  |

<a id="wbn-database-auto-edge-haulage"></a>

#### `auto_edge_HAULAGE`

**Rows:** 246,971  |  **Columns:** 11  |  **DATE:** 2021-09-24 → 2026-07-28

**Columns:** `graph_id_C7E0D1F64E9842258DB9B840FB41A4A5` bigint, `$edge_id_66E9FA405A3E4BBB85210E85D05D1FB5` nvarchar(1000), `from_obj_id_CB360B2B9C494D959EB055C1A3A8C172` int, `from_id_F62207485BA5405F970312413F9A2960` bigint, `$from_id_6B4478C15D4A4DF3869F135421AEDD1E` nvarchar(1000), `to_obj_id_C8DAED3DF52E4B5EBECB026E7E32933B` int, `to_id_47F941D1B2CA46508D36C8AA495043C9` bigint, `$to_id_4FBF9C508A514BB78FE8C09B6EEDA1D2` nvarchar(1000), `HAULAGE_ID` int, `DATE` date, `WMT` float

*Sample unavailable: could not serialise*

<a id="wbn-database-dispatch-wbn-actual"></a>

#### `DISPATCH WBN ACTUAL`

**Rows:** 212,890  |  **Columns:** 14  |  **DATE:** 2024-10-01 → 2026-07-22

**Columns:** `ID` int, `DATE` date, `CONTRACTOR` nvarchar(50), `SHIFT` int, `TYPE DATA` nvarchar(50), `TYPE HAULAGE` nvarchar(50), `MATERIAL` nvarchar(50), `COMPANY` nvarchar(50), `DISPATCH ZONE` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `BUYER` nvarchar(50), `NB DT` float, `WMT` float

**Sample rows**:

| ID | DATE | CONTRACTOR | SHIFT | TYPE DATA | TYPE HAULAGE | MATERIAL | COMPANY | DISPATCH ZONE | ORIGIN | DESTINATION | BUYER | NB DT | WMT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 82931 | 2024-10-01T00:00:00.000 | STM | 1 | ACTUAL | DIRECT CRUSHER | CS | WBN | KR to FeNi | KR | FENI |  |  |  |
| 82932 | 2024-10-01T00:00:00.000 | STM | 1 | ACTUAL | DIRECT | SAP | WBN | KR to FeNi | KR | FENI |  |  |  |
| 82933 | 2024-10-01T00:00:00.000 | STM | 1 | ACTUAL | HAULAGE | SAP | WBN | KR to CSTL | KR | EOS |  |  |  |
| 82934 | 2024-10-01T00:00:00.000 | STM | 1 | ACTUAL | HAULAGE | SAP | WBN | KR to CSTL | KR | POS GOMDI |  |  |  |
| 82935 | 2024-10-01T00:00:00.000 | STM | 1 | ACTUAL | HAULAGE | SAP | WBN | KR to KM 11 | KR | POS 6 |  |  |  |

<a id="wbn-database-auto-node-stock-id"></a>

#### `auto_node_STOCK_ID`

**Rows:** 186,833  |  **Columns:** 29  |  **ASSAY_DATE:** 2021-02-20 → 2026-07-28

**Columns:** `graph_id_83A179A0BB35432D89748AEC92C6DB3E` bigint, `$node_id_B3C06F53460D452C8C24D2C646C0E52F` nvarchar(1000), `STOCK_ID` nvarchar(100), `STOCK_TYPE` nvarchar(50), `STOCK_AREA` nvarchar(50), `WMT_IN` float, `WMT_OUT` float, `ASSAY_TYPE` nvarchar(50), `ASSAY_DATE` date, `ASSAY_STATUS` nvarchar(50), `ASSAY_STATUS_%` float, `ASSAY_CONTRACTOR` nvarchar(50), `WMT_CERT` float, `Al2O3` float, `CaO` float, `Co` float, `Cr2O3` float, `Fe_ORI` float, `Fe` float, `Fe2O3` float, `MC` float, `MgO_ORI` float, `MgO` float, `MnO` float, `Ni_ORI` float, `Ni` float, `P2O5` float, `SiO2_ORI` float, `SiO2` float

**Identifier vocabularies:**

- `STOCK_ID` — 186,833 distinct. e.g. `A`, `A.2912`, `A.3023`, `A.3338`, `A.3368`, `A.3483`, `A.3529`, `A.3762`, `A.3870`, `A.3914`, `A.3936`, `A.3944`

*Sample unavailable: could not serialise*

<a id="wbn-database-pos-follow-up"></a>

#### `POS FOLLOW UP`

**Rows:** 177,744  |  **Columns:** 9  |  **DATE:** 2024-10-01 → 2026-07-31

**Columns:** `ID` int, `DATE` date, `AREA` nvarchar(50), `POS` nvarchar(50), `PADS` nvarchar(50), `NUMBER` int, `AVG` float, `EDD` date, `PRECISION` nvarchar(50)

**Sample rows**:

| ID | DATE | AREA | POS | PADS | NUMBER | AVG | EDD | PRECISION |
|---|---|---|---|---|---|---|---|---|
| 31062 | 2024-10-01T00:00:00.000 | KR | POS 6 | EXISTING | 38 | 20000.0 |  |  |
| 31063 | 2024-10-01T00:00:00.000 | KR | POS 6 | FREE | 17 | 20000.0 |  |  |
| 31064 | 2024-10-01T00:00:00.000 | KR | POS 6 | ON PRGS MTN | 0 | 20000.0 |  |  |
| 31065 | 2024-10-01T00:00:00.000 | KR | POS 6 | NEED MTN | 3 | 20000.0 |  |  |
| 31066 | 2024-10-01T00:00:00.000 | KR | POS 6 | CONTRUCTION PAD | 0 | 20000.0 |  |  |

<a id="wbn-database-autoqc-cf-bm-tos-history-old"></a>

#### `autoQC_CF_BM_TOS_HISTORY_OLD`

**Rows:** 175,475  |  **Columns:** 17

**Columns:** `DATETIME` nvarchar(50), `YEAR` int, `MONTH` int, `ORIGIN_PIT` nvarchar(50), `CONTRACTOR_PILE` nvarchar(50), `MATERIAL` nvarchar(50), `DIL_BM_MC` float, `DIL_BM_Ni` float, `DIL_BM_Fe` float, `DIL_BM_SiO2` float, `DIL_BM_MgO` float, `DIL_TOS_MC` float, `DIL_TOS_Ni` float, `DIL_TOS_Fe` float, `DIL_TOS_SiO2` float, `DIL_TOS_MgO` float, `DIL_PROP_BM_Ni` float

**Sample rows** (first 14 of 17 columns):

| DATETIME | YEAR | MONTH | ORIGIN_PIT | CONTRACTOR_PILE | MATERIAL | DIL_BM_MC | DIL_BM_Ni | DIL_BM_Fe | DIL_BM_SiO2 | DIL_BM_MgO | DIL_TOS_MC | DIL_TOS_Ni | DIL_TOS_Fe |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-05-23 10:30:40 | 2024 | 6 | BLB | RIM | LIM | 0.9983768394 | 0.9251471825 | 1.3830479081 | 11.0131477185 | 21.1194029851 | 1.0082512898 | 0.9827810349 | 0.8273280452 |
| 2026-05-23 10:30:40 | 2024 | 7 | BLB | HJS | LIM | 0.9354435609 | 0.8687153018 | 0.9571238192 | 1.0424508309 | 1.3608734216 | 0.9672758054 | 0.8678844263 | 0.8374354888 |
| 2026-05-23 10:30:40 | 2024 | 7 | BLB | HJS | SAP | 0.9677435522 | 0.8621670129 | 1.0624823834 | 0.9606798457 | 1.0157900997 | 0.9186474545 | 0.8332376717 | 0.9996507994 |
| 2026-05-23 10:30:40 | 2024 | 7 | BLB | RIM | LIM | 0.9234836138 | 0.883581161 | 0.9098123139 | 1.2966134513 | 2.0834818094 | 0.9598611807 | 0.882624609 | 0.8370530615 |
| 2026-05-23 10:30:40 | 2024 | 7 | CBB | RIM | LIM | 0.9114671346 | 0.8896435893 | 0.8879047407 | 1.4266462084 | 2.8993479852 | 0.9506832308 | 0.8934815105 | 0.8400958366 |

<a id="wbn-database-crusher-stockpile-output-data"></a>

#### `CRUSHER_STOCKPILE_OUTPUT_DATA`

**Rows:** 156,726  |  **Columns:** 13  |  **DATE:** 2024-10-01 00:00:00 → 2026-06-04 00:00:00

**Columns:** `ID` int, `DATE` datetime, `SHIFT` nvarchar(50), `CONTRACTOR_HAULING` nvarchar(50), `UNIT_ID_HAULER` nvarchar(50), `STOCK_ID` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `DESTINATION 2` nvarchar(50), `RIT` float, `TF` float, `BCM` float, `WMT` float

**Identifier vocabularies:**

- `UNIT_ID_HAULER` — 1,690 distinct. e.g. `421`, `424`, `427`, `428`, `429`, `430`, `433`, `435`, `439`, `440`, `N482`, `N413`
- `STOCK_ID` — 717 distinct. e.g. `BASE COURSE`, `LAMINATING`, `LPA`, `LPB`, `BATU`, `BOULDER`, `MUD`, `BC 5-7`, `BC 2-3`, `SW-SS.680`, `SW-SS.679`, `SW-CS.680`

**Sample rows**:

| ID | DATE | SHIFT | CONTRACTOR_HAULING | UNIT_ID_HAULER | STOCK_ID | ORIGIN | DESTINATION | DESTINATION 2 | RIT | TF | BCM | WMT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 189541 | 2026-04-29T00:00:00.000 | 1 | PPP | 421 | BASE COURSE | STOCKPILE KM38 | POS 12 | POS 12 | 1.0 | 15.0 | 15.0 |  |
| 189542 | 2026-04-29T00:00:00.000 | 1 | PPP | 424 | BASE COURSE | STOCKPILE KM38 | POS 12 | POS 12 | 1.0 | 15.0 | 15.0 |  |
| 189543 | 2026-04-29T00:00:00.000 | 1 | PPP | 427 | BASE COURSE | STOCKPILE KM38 | POS 12 | POS 12 | 1.0 | 15.0 | 15.0 |  |
| 189544 | 2026-04-29T00:00:00.000 | 1 | PPP | 428 | BASE COURSE | STOCKPILE KM38 | POS 12 | POS 12 | 1.0 | 15.0 | 15.0 |  |
| 189545 | 2026-04-29T00:00:00.000 | 1 | PPP | 429 | BASE COURSE | STOCKPILE KM38 | POS 12 | POS 12 | 1.0 | 15.0 | 15.0 |  |

<a id="wbn-database-qc-pit-tos-omr"></a>

#### `QC PIT-TOS OMR`

**Rows:** 149,360  |  **Columns:** 19  |  **DATE:** 2024-10-01 00:00:00 → 2026-07-17 00:00:00

**Columns:** `ID` int, `DATE` datetime, `SHIFT` float, `CONTRACTOR` nvarchar(255), `MATERIAL` nvarchar(255), `PIT` nvarchar(255), `SUBPIT` nvarchar(255), `BLOCK_ID` nvarchar(255), `BLOCK_STATUS` nvarchar(255), `TOS_LOCATION` nvarchar(255), `PILE_ID` nvarchar(255), `PILE_STATUS` nvarchar(255), `TF` float, `RIT` float, `WMT` float, `BATCH` nvarchar(255), `TYPE` nvarchar(255), `BLAST` nvarchar(255), `REMARK` nvarchar(255)

**Identifier vocabularies:**

- `BLOCK_ID` — 96,234 distinct. e.g. `433_B93_S175`, `439_B99_S176`, `337_B62_S279`, `439_B100_S175`, `443_B101_S176`, `439_B99_S178`, `433_B101_S190`, `433_B94_S176`, `337_B61_S279`, `439_B99_S175`, `439_B98_S175`, `337_B62_S278`
- `PILE_ID` — 42,693 distinct. e.g. `BB.D.1841`, `BB.D.1846`, `BB.D.1847`, `BB.D.1848`, `BB.D.1849`, `BB.D.1850`, `BB.D.1851`, `BB.D.1852`, `BB.D.1853`, `BB.D.1854`, `BB.D.1855`, `BB.D.1856`

**Sample rows** (first 14 of 19 columns):

| ID | DATE | SHIFT | CONTRACTOR | MATERIAL | PIT | SUBPIT | BLOCK_ID | BLOCK_STATUS | TOS_LOCATION | PILE_ID | PILE_STATUS | TF | RIT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 109692 | 2024-10-01T00:00:00.000 | 1.0 | HJS | SAP | CBB | CBBT1 | 433_B93_S175 | CONTINUE | TOS_CBB_18 | BB.D.1841 | CONTINUE | 47.0 | 15.0 |
| 109693 | 2024-10-01T00:00:00.000 | 1.0 | HJS | SAP | CBB | CBBB1 | 439_B99_S176 | CLOSE | TOS_CBB_RIM_13 | BB.D.1846 | CONTINUE | 47.0 | 10.0 |
| 109694 | 2024-10-01T00:00:00.000 | 1.0 | HJS | SAP | CBB | CBBB1 | 337_B62_S279 | CONTINUE | TOS_CBB_RIM_13 | BB.D.1847 | CONTINUE | 30.0 | 17.0 |
| 109695 | 2024-10-01T00:00:00.000 | 1.0 | HJS | SAP | CBB | CBBBT1 | 439_B100_S175 | CONTINUE | TOS_CBB_RIM_01 | BB.D.1848 | CONTINUE | 47.0 | 21.0 |
| 109696 | 2024-10-01T00:00:00.000 | 1.0 | HJS | SAP | CBB | CBBBT1 | 443_B101_S176 | CONTINUE | TOS_CBB_RIM_01 | BB.D.1848 | CONTINUE | 47.0 | 10.0 |

<a id="wbn-database-autoblock-prod-qc-bm-tos-corr"></a>

#### `autoBLOCK_PROD_QC_BM_TOS_CORR`

**Rows:** 132,306  |  **Columns:** 18  |  **DATE:** 2025-12-29 00:00:00 → 2026-07-28 00:00:00

**Columns:** `OBJECT_NAME` varchar(17), `DATE` datetime, `SURVEY_CLASS` nvarchar(255), `CONTRACTOR` nvarchar(255), `ACTIVITY` nvarchar(255), `MATERIAL` nvarchar(255), `STOCK_POINT` varchar(11), `STOCK_TYPE` nvarchar(50), `STOCK_AREA` nvarchar(255), `STOCK_ID` nvarchar(510), `ORIGIN_AREA` nvarchar(255), `ORIGIN_ID` nvarchar(-1), `DESTINATION_ID` nvarchar(510), `RIT` float, `WMT` float, `WMT_METHOD` varchar(2), `SURVEY_TYPE` int, `SURVEY_WEEK` int

**Identifier vocabularies:**

- `STOCK_ID` — 7,975 distinct. e.g. `ROCKWALL_TF7_UTARA`, `AKSES_BACKFILL_TF9`, `BACKFILL_TF9`, `WD_BLB_10`, `WD_KRENE_09`, `INPIT_LOADING_POINT_TF9`, `ROCKWALL_BACKFILL_TF9`, `E/KRENE.I.234`, `E/KRENE.I.241`, `REKLAMASI_AREA7`, `WD_BLB_05`, `ROCKWALL_WD_BLB_JL13`
- `ORIGIN_ID` — 6,784 distinct. e.g. `BLB-BLB5; BLB-CRUSHER_BLB; CBB-CBB4; CBB`, `TF-CRUSHER_TF; TF-STOCK_TF_KM49; TF-STOC`, `BLB-E/T742_B205_S343`, `BLB-BLB5; BLB-CRUSHER_BLB; CBB-CBB_KM15;`, `BLB-CRUSHER_BLB`, `BLB-BLB5; BLB-CRUSHER_BLB; CBB-STOCK_CBB`, `BLB-BLB5; BLB-TOS_BLB_RIM_05; BLB-TOS8; `, `TF-N318_B177_S103; TF-N394_B106_S185`, `TF-N318_B177_S102; TF-N394_B107_S182`, `TF-N318_B177_S103; TF-N334_B164_S111`, `TF-N330_B163_S112; TF-N390_B105_S186`, `TF-N314_B173_S106; TF-N322_B177_S103; TF`
- `DESTINATION_ID` — 7,975 distinct. e.g. `ROCKWALL_TF7_UTARA`, `AKSES_BACKFILL_TF9`, `BACKFILL_TF9`, `WD_BLB_10`, `WD_KRENE_09`, `INPIT_LOADING_POINT_TF9`, `ROCKWALL_BACKFILL_TF9`, `E/KRENE.I.234`, `E/KRENE.I.241`, `REKLAMASI_AREA7`, `WD_BLB_05`, `ROCKWALL_WD_BLB_JL13`

**Sample rows** (first 14 of 18 columns):

| OBJECT_NAME | DATE | SURVEY_CLASS | CONTRACTOR | ACTIVITY | MATERIAL | STOCK_POINT | STOCK_TYPE | STOCK_AREA | STOCK_ID | ORIGIN_AREA | ORIGIN_ID | DESTINATION_ID | RIT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MINING EXTRACTION | 2026-03-31T00:00:00.000 | WST | STM | MINING | WST | DESTINATION | WD | ROCKWALL_TF7_UTARA | ROCKWALL_TF7_UTARA | TF |  | ROCKWALL_TF7_UTARA | 1.0 |
| MINING EXTRACTION | 2026-04-22T00:00:00.000 | WST | STM | MINING | WST | DESTINATION | WD | AKSES_BACKFILL_TF9 | AKSES_BACKFILL_TF9 | TF |  | AKSES_BACKFILL_TF9 | 10.0 |
| MINING EXTRACTION | 2026-03-10T00:00:00.000 | WST | STM | LAMINATING | WST | DESTINATION | WD | BACKFILL_TF9 | BACKFILL_TF9 | TF |  | BACKFILL_TF9 | 9.0 |
| MINING EXTRACTION | 2026-03-21T00:00:00.000 | WST | RIM | MINING | WST | DESTINATION | WD | WD_BLB_10 | WD_BLB_10 | BLB |  | WD_BLB_10 | 4.0 |
| MINING EXTRACTION | 2026-03-02T00:00:00.000 | WST | RIM | LAMINATING | WST | DESTINATION | WD | WD_BLB_10 | WD_BLB_10 | BLB |  | WD_BLB_10 | 4.0 |

<a id="wbn-database-contractor-follow-up"></a>

#### `CONTRACTOR FOLLOW UP`

**Rows:** 130,873  |  **Columns:** 25  |  **Date:** 2024-10-01 → 2026-07-28

**Columns:** `ID` int, `Date` date, `Contractor` nvarchar(255), `Activity` nvarchar(255), `Equipment` nvarchar(255), `Brand` nvarchar(255), `Model` nvarchar(255), `Capacity` nvarchar(255), `Quantity` float, `PA` float, `Target Fleet` float, `RFU` float, `Breakdown` float, `Act PA` float, `Running Average` float, `Stand by` float, `Actual Utilization` float, `Manpower Factor` float, `Manpower Budget` float, `Manpower` float, `Manpower On Site` float, `Hiring` float, `Eq class` nvarchar(255), `DT Reclaiming` float, `DT OTHER` float

**Identifier vocabularies:**

- `Equipment` — 121 distinct. e.g. `DT Sachman`, `Exca 30 Ton`, `Exca 20 Ton`, `DT Hino 25T`, `DT Volvo 30T`, `DT Sachman 30T`, `DT HONGYAN 50T`, `EX SANY 50T`, `EX20`, `EX30`, `Bulldozer`, `ADT VOLVO 60T`

**Sample rows** (first 14 of 25 columns):

| ID | Date | Contractor | Activity | Equipment | Brand | Model | Capacity | Quantity | PA | Target Fleet | RFU | Breakdown | Act PA |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 82044 | 2024-10-01T00:00:00.000 | CKB | HAULING | DT Sachman | Shacman | X3000 | 43 | 30.0 | 0.85 | 26.0 | 19.0 | 11.0 | 0.6333333333 |
| 82045 | 2024-10-01T00:00:00.000 | CKB | HAULING | Exca 30 Ton | Cat | CAT 330 | 30 | 1.0 | 0.9 | 1.0 | 1.0 | 0.0 | 1.0 |
| 82046 | 2024-10-01T00:00:00.000 | CKB | HAULING | Exca 20 Ton | Sany | SY215C | 20 | 1.0 | 0.9 | 1.0 | 1.0 | 0.0 | 1.0 |
| 82047 | 2024-10-01T00:00:00.000 | GMG  | HAULING | DT Hino 25T | HINO | FM 280JD | 25 | 35.0 | 0.89 | 32.0 | 18.0 | 17.0 | 0.5142857143 |
| 82048 | 2024-10-01T00:00:00.000 | GMG  | HAULING | DT Volvo 30T | VOLVO | VOLVO 6 X 4 | 30 | 67.0 | 0.9 | 61.0 | 49.0 | 18.0 | 0.7313432836 |

<a id="wbn-database-feni-reclaiming-plan"></a>

#### `FeNi Reclaiming Plan`

**Rows:** 128,118  |  **Columns:** 10  |  **DATE:** 2024-10-01 → 2026-07-30

**Columns:** `ID` int, `DATE` date, `SHIFT` int, `ORE LOCATION` nvarchar(50), `DOME ID FENI` nvarchar(50), `PLAN VEHICULE` int, `PLANNED WEIGHBRIDGE` nvarchar(50), `PLANNED WMT` float, `DESTINATION` nvarchar(50), `DOME` nvarchar(50)

**Sample rows**:

| ID | DATE | SHIFT | ORE LOCATION | DOME ID FENI | PLAN VEHICULE | PLANNED WEIGHBRIDGE | PLANNED WMT | DESTINATION | DOME |
|---|---|---|---|---|---|---|---|---|---|
| 49759 | 2024-10-01T00:00:00.000 | 1 | POS 14 | ADM.227 | 8 | 11#? | 1500.0 |  |  |
| 49760 | 2024-10-01T00:00:00.000 | 1 | POS10 | AA.477 | 8 | 11#? | 1500.0 |  |  |
| 49761 | 2024-10-01T00:00:00.000 | 1 | 5??????? | RN063 | 6 | 1#? | 0.0 |  |  |
| 49762 | 2024-10-01T00:00:00.000 | 1 | POS12 | AD.202 | 8 | 11#? | 1300.0 |  |  |
| 49763 | 2024-10-01T00:00:00.000 | 1 | POS 14 | ADM.227 | 8 | 11#? | 1500.0 |  |  |

<a id="wbn-database-mining-plan-weekly"></a>

#### `MINING_PLAN_WEEKLY`

**Rows:** 124,358  |  **Columns:** 34  |  **DATE:** 2025-02-08 00:00:00 → 2026-05-01 00:00:00

**Columns:** `YEAR` float, `MONTH` float, `WEEK` float, `DATE` datetime, `CONTRACTOR` nvarchar(255), `PIT` nvarchar(255), `SUBPIT` nvarchar(255), `MATERIAL` nvarchar(255), `FSAP_RSAP` nvarchar(255), `CATEGORY` nvarchar(255), `BLOCK_ID` nvarchar(255), `BCM` float, `WMT` float, `DMT` float, `Ni` float, `Fe` float, `SM` float, `SiO2` float, `MgO` float, `H2O` float, `MINE_RECOVERY` float, `WMT_REC` float, `BCM_ROM` float, `WMT_ROM` float, `DMT_ROM` float, `Ni_DILUTION` float, `Fe_DILUTION` float, `MgO_DILUTION` float, `H2O_DILUTION` float, `Ni_ROM` float, `Fe_ROM` float, `MgO_ROM` float, `H2O_ROM` float, `ID` int

**Identifier vocabularies:**

- `BLOCK_ID` — 51,370 distinct. e.g. `N943_B341_S213`, `N943_B341_S212`, `N943_B341_S211`, `N943_B341_S209`, `N943_B341_S208`, `N943_B340_S208`, `N943_B340_S207`, `N943_B340_S206`, `N943_B339_S206`, `N939_B341_S211`, `N939_B341_S210`, `N939_B341_S209`

**Sample rows** (first 14 of 34 columns):

| YEAR | MONTH | WEEK | DATE | CONTRACTOR | PIT | SUBPIT | MATERIAL | FSAP_RSAP | CATEGORY | BLOCK_ID | BCM | WMT | DMT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026.0 | 2.0 | 5.0 | 2026-02-02T00:00:00.000 | RIM | BLB | 10 | LIM | WST | LIM ORE | N943_B341_S213 | 611.572 | 886.78 | 642.1506 |
| 2026.0 | 2.0 | 5.0 | 2026-02-02T00:00:00.000 | RIM | BLB | 10 | LIM | WST | LIM ORE | N943_B341_S212 | 324.707 | 470.825 | 340.94235 |
| 2026.0 | 2.0 | 5.0 | 2026-02-02T00:00:00.000 | RIM | BLB | 10 | WST | WST | WST LIM | N943_B341_S211 | 13.428 | 19.739 | 14.0994 |
| 2026.0 | 2.0 | 5.0 | 2026-02-02T00:00:00.000 | RIM | BLB | 10 | WST | WST | WST LIM | N943_B341_S209 | 197.754 | 288.721 | 207.6417 |
| 2026.0 | 2.0 | 5.0 | 2026-02-02T00:00:00.000 | RIM | BLB | 10 | WST | WST | WST SAP | N943_B341_S208 | 345.459 | 490.552 | 362.73195 |

<a id="wbn-database-sampling-contractor"></a>

#### `SAMPLING_CONTRACTOR`

**Rows:** 123,130  |  **Columns:** 15  |  **DATE:** 2024-10-01 00:00:00 → 2026-07-25 00:00:00

**Columns:** `ID` int, `CONTRACTOR` nvarchar(50), `DATE` datetime, `SHIFT` nvarchar(50), `ACTIVITY` nvarchar(50), `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(50), `DESTINATION_AREA` nvarchar(50), `DESTINATION_ID` nvarchar(50), `CONTRACTOR_HAULING` nvarchar(50), `RIT` float, `SPV_CONTRACTOR` nvarchar(50), `SPV_WBN` nvarchar(50), `SAMPLING_POINT` nvarchar(50), `REMARK` nvarchar(50)

**Identifier vocabularies:**

- `ORIGIN_ID` — 43,219 distinct. e.g. `LGS.BLB45`, `ABM.258`, `ABM.255`, `LGS.CBB152`, `ADM.253.A`, `ACM.347`, `LGS.CBB203.A`, `LGS.BLB33`, `LGS.BLB.33`, `ADM.260`, `ACM.313`, `ACM.304`
- `DESTINATION_ID` — 4,756 distinct. e.g. `ABM.242`, `LGS.CBB192`, `LGS.CBB193`, `ADM.228`, `AB.373`, `LGS.CBB194`, `LGS.CBB197`, `ABM.241`, `LGS.CBB196`, `ADM.232`, `LGS.CBB195`, `AB.371`

**Sample rows** (first 14 of 15 columns):

| ID | CONTRACTOR | DATE | SHIFT | ACTIVITY | ORIGIN_AREA | ORIGIN_ID | DESTINATION_AREA | DESTINATION_ID | CONTRACTOR_HAULING | RIT | SPV_CONTRACTOR | SPV_WBN | SAMPLING_POINT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | TBI | 2024-12-26T00:00:00.000 | 1 | RECLAIMING | POS CSW | LGS.BLB45 | POS CSW |  | FENI | 50.0 | SOLY EKA PUTRA |  | SHR.POS14 |
| 2 | TBI | 2024-12-26T00:00:00.000 | 1 | RECLAIMING | POS CSW | ABM.258 | POS CSW |  | FENI | 40.0 | SOLY EKA PUTRA |  | SHR.POS14 |
| 3 | TBI | 2024-12-26T00:00:00.000 | 1 | RECLAIMING | POS CSW | ABM.255 | POS CSW |  | FENI | 13.0 | SOLY EKA PUTRA |  | SHR.POS14 |
| 4 | TBI | 2024-12-26T00:00:00.000 | 2 | RECLAIMING | POS CSW | ABM.258 | FENI K |  | FENI | 24.0 | SOLY EKA PUTRA |  | SHR.POS14 |
| 5 | TBI | 2024-12-26T00:00:00.000 | 2 | RECLAIMING | POS CSW | ABM.255 | FENI R |  | FENI | 8.0 | SOLY EKA PUTRA |  | SHR.POS14 |

<a id="wbn-database-tos-pile-info"></a>

#### `TOS_PILE_INFO`

**Rows:** 97,738  |  **Columns:** 6

**Columns:** `ID` int, `TOS_PILE` nvarchar(50), `TOS` nvarchar(50), `PIT` nvarchar(50), `CONTRACTOR_PROD` nvarchar(50), `MATERIAL_TYPE` nvarchar(50)

**Sample rows**:

| ID | TOS_PILE | TOS | PIT | CONTRACTOR_PROD | MATERIAL_TYPE |
|---|---|---|---|---|---|
| 1 | A.1 | Grizzly 332 | KR | STM | GRIZZLY |
| 2 | A.2 | Grizzly 332 | KR | STM | GRIZZLY |
| 3 | A.3 | Grizzly 332 | KR | STM | GRIZZLY |
| 4 | A.4 | Grizzly 332 | KR | STM | GRIZZLY |
| 5 | A.5 | Grizzly 332 | KR | STM | GRIZZLY |

<a id="wbn-database-autoqc-stock-all-via-all"></a>

#### `autoQC_STOCK_ALL_VIA_ALL`

**Rows:** 93,116  |  **Columns:** 93  |  **TOS_ASSAY_DATE:** 2021-10-17 → 2026-07-21

**Columns:** `LAST_UPDATE` nvarchar(50), `STOCK_TYPE` nvarchar(50), `STOCK_ID` nvarchar(260), `Ni_` float, `PLAN_MC` float, `PLAN_Ni` float, `PLAN_Fe` float, `PLAN_SiO2` float, `PLAN_MgO` float, `PLAN_Co` float, `PLAN_Cr2O3` float, `CF_PLAN_Ni` float, `DEF_ASSAY_TYPE` nvarchar(101), `DEF_MC` float, `DEF_Ni` float, `DEF_Fe` float, `DEF_SiO2` float, `DEF_MgO` float, `DEF_Al2O3` float, `DEF_Co` float, `DEF_Cr2O3` float, `DEF_MnO` float, `DEF_P2O5` float, `BM_ASSAY_TYPE` nvarchar(101), `BM_MC` float, `BM_Ni` float, `BM_Fe` float, `BM_SiO2` float, `BM_MgO` float, `BM_Al2O3` float, `BM_Co` float, `BM_Cr2O3` float, `BM_MnO` float, `BM_P2O5` float, `BM_Ni_CORR` float, `BM_Fe_CORR` float, `BM_SiO2_CORR` float, `BM_MgO_CORR` float, `TOS_ASSAY_TYPE` nvarchar(101), `TOS_ASSAY_DATE` date, `TOS_MC` float, `TOS_Ni` float, `TOS_Fe` float, `TOS_SiO2` float, `TOS_MgO` float, `TOS_Al2O3` float, `TOS_Co` float, `TOS_Cr2O3` float, `TOS_MnO` float, `TOS_P2O5` float, `POS_ASSAY_TYPE` nvarchar(101), `POS_ASSAY_STATUS` varchar(8), `POS_ASSAY_STATUS_%` float, `POS_ASSAY_CONTRACTOR` nvarchar(50), `POS_ASSAY_DATE` date, `POS_WMT_CERT` float, `POS_MC` float, `POS_Ni` float, `POS_Fe` float, `POS_SiO2` float, `POS_MgO` float, `POS_Al2O3` float, `POS_Co` float, `POS_Cr2O3` float, `POS_MnO` float, `POS_P2O5` float, `YARD_ASSAY_TYPE` nvarchar(101), `YARD_ASSAY_STATUS` varchar(8), `YARD_ASSAY_STATUS_%` float, `YARD_ASSAY_CONTRACTOR` nvarchar(50), `YARD_ASSAY_DATE` date, `YARD_WMT_CERT` float, `YARD_MC` float, `YARD_Ni` float, `YARD_Fe` float, `YARD_SiO2` float, `YARD_MgO` float, `YARD_Al2O3` float, `YARD_Co` float, `YARD_Cr2O3` float, `YARD_MnO` float, `YARD_P2O5` float, `ML_Ni` float, `DIL_BM_MC` float, `DIL_BM_Ni` float, `DIL_BM_Fe` float, `DIL_BM_SiO2` float, `DIL_BM_MgO` float, `DIL_TOS_MC` float, `DIL_TOS_Ni` float, `DIL_TOS_Fe` float, `DIL_TOS_SiO2` float, `DIL_TOS_MgO` float

**Identifier vocabularies:**

- `STOCK_ID` — 93,116 distinct. e.g. `-`, `A`, `A.2573`, `A.2801`, `A.2806`, `A.2838`, `A.2894`, `A.2907`, `A.2909`, `A.2912`, `A.2933`, `A.2936`

**Sample rows** (first 14 of 93 columns):

| LAST_UPDATE | STOCK_TYPE | STOCK_ID | Ni_ | PLAN_MC | PLAN_Ni | PLAN_Fe | PLAN_SiO2 | PLAN_MgO | PLAN_Co | PLAN_Cr2O3 | CF_PLAN_Ni | DEF_ASSAY_TYPE | DEF_MC |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-07-30 09:30:28 | TOS | - |  |  |  |  |  |  |  |  |  |  |  |
| 2026-07-30 09:30:28 | POS | A |  |  |  |  |  |  |  |  |  |  |  |
| 2026-07-30 09:30:28 | TOS | A.2573 |  |  |  |  |  |  |  |  |  |  |  |
| 2026-07-30 09:30:28 | TOS | A.2801 |  |  |  |  |  |  |  |  |  |  |  |
| 2026-07-30 09:30:28 | TOS | A.2806 |  |  |  |  |  |  |  |  |  |  |  |

<a id="wbn-database-tos-follow"></a>

#### `TOS FOLLOW`

**Rows:** 87,045  |  **Columns:** 13  |  **DATE:** 2024-10-01 00:00:00 → 2026-07-22 00:00:00

**Columns:** `ID` int, `ORIGIN` nvarchar(255), `MATERIAL` nvarchar(255), `BLOCK ID` nvarchar(255), `TOS` nvarchar(255), `POS DOME` nvarchar(255), `POS` nvarchar(255), `TRIPS` float, `WMT` float, `STATUS` nvarchar(255), `CONTRACTOR` nvarchar(255), `DATE` datetime, `SHIFT` nvarchar(255)

**Sample rows**:

| ID | ORIGIN | MATERIAL | BLOCK ID | TOS | POS DOME | POS | TRIPS | WMT | STATUS | CONTRACTOR | DATE | SHIFT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5605 | TF | SAP | TF.C.637 | TOS_TF_MTM_02 | ADM.233 | POS 12 EXT | 23.0 | 1162.14 | Continue | CKB | 2024-10-01T00:00:00.000 | 1 |
| 5606 | TF | SAP | TF.C.611 | TOS_TF_MTM_02 | ABM.224 | POS 12 | 21.0 | 1089.07 | Continue | CKB | 2024-10-01T00:00:00.000 | 2 |
| 5607 | KR | SAP | A.5751 | TOS_KR_STM_04 | AA.483 | POS 10 | 47.0 | 1631.06 | CLOSE | GMG | 2024-10-01T00:00:00.000 | 1 |
| 5608 | KR | SAP | A.5752 | TOS_KR_STM_05 EXT | AAM.296 | POS 11 | 52.0 | 1806.12 | CONTINUE | GMG | 2024-10-01T00:00:00.000 | 1 |
| 5609 | KR | SAP | A.5748 | TOS_KR_10 | AA.483 | POS 10 | 20.0 | 659.5 | CONTINUE | GMG | 2024-10-01T00:00:00.000 | 1 |

<a id="wbn-database-omr-qc"></a>

#### `OMR_QC`

**Rows:** 85,995  |  **Columns:** 15  |  **DATE:** 2024-10-01 → 2026-07-22

**Columns:** `ID` int, `DATE` date, `SHIFT` int, `CONTRACTOR_HAUL` nvarchar(255), `MATERIAL` nvarchar(255), `TOS_PILE` nvarchar(255), `TOS` nvarchar(255), `RIT` float, `TF` float, `DOME` nvarchar(255), `POS/PLANT` nvarchar(255), `STATUS` nvarchar(255), `CONTRACTOR_PROD` nvarchar(50), `PIT` nvarchar(50), `REMARK` nvarchar(255)

**Sample rows** (first 14 of 15 columns):

| ID | DATE | SHIFT | CONTRACTOR_HAUL | MATERIAL | TOS_PILE | TOS | RIT | TF | DOME | POS/PLANT | STATUS | CONTRACTOR_PROD | PIT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 134349 | 2024-10-01T00:00:00.000 | 1 | HJS | SAP | BB.D.1719 | TOS_CBB_RIM_13 | 19.0 |  | LGS.CBB194 | POS UNI-UNI | CLOSE | HJS | CBB |
| 134350 | 2024-10-01T00:00:00.000 | 1 | HJS | SAP | BB.D.1719 | TOS_CBB_RIM_13 | 29.0 |  | LGS.CBB197 | POS UNI-UNI | CLOSE | HJS | CBB |
| 134351 | 2024-10-01T00:00:00.000 | 1 | HJS | SAP | BB.D.1657 | TOS_CBB_RIM_13 | 28.0 |  | LGS.CBB197 | POS UNI-UNI | CLOSE | HJS | CBB |
| 134352 | 2024-10-01T00:00:00.000 | 1 | HJS | SAP | BB.D.1782 | TOS_CBB_RIM_01 | 23.0 |  | LGS.CBB195 | POS BIRI-BIRI | CLOSE | HJS | CBB |
| 134353 | 2024-10-01T00:00:00.000 | 1 | HJS | SAP | BB.D.1749 | TOS_CBB_RIM_01 | 64.0 |  | LGS.CBB195 | POS BIRI-BIRI | CONTINUE | HJS | CBB |

<a id="wbn-database-dispatch-feni-plan---actual"></a>

#### `DISPATCH FeNi PLAN & ACTUAL`

**Rows:** 84,384  |  **Columns:** 11  |  **DATE:** 2024-10-01 → 2026-07-29

**Columns:** `ID` int, `DATE` date, `SHIFT` int, `TYPE` nvarchar(50), `POS` nvarchar(50), `DESTINATON` nvarchar(50), `NB DOMES` int, `NB DT` int, `TRIPS` float, `TF` float, `WMT ACT` float

**Sample rows**:

| ID | DATE | SHIFT | TYPE | POS | DESTINATON | NB DOMES | NB DT | TRIPS | TF | WMT ACT |
|---|---|---|---|---|---|---|---|---|---|---|
| 15178 |  | 1 | ACTUAL | POS.11 | 15KM | 0 | 0 |  | 40.0 |  |
| 15195 |  | 2 | ACTUAL | Tekindo | 0KM | 1 | 9 |  | 40.0 |  |
| 25052 | 2024-10-01T00:00:00.000 | 1 | PLAN | ????? | 0KM | 20 | 120 | 3.7679558011 | 40.0 |  |
| 25053 | 2024-10-01T00:00:00.000 | 1 | PLAN | EOS?? | 0KM | 0 | 0 | 0.0 | 40.0 |  |
| 25054 | 2024-10-01T00:00:00.000 | 1 | PLAN | ???? | 0KM | 10 | 88 | 4.7040816327 | 40.0 |  |

<a id="wbn-database-distance-mining"></a>

#### `DISTANCE_MINING`

**Rows:** 83,462  |  **Columns:** 14  |  **DATE:** 2024-02-25 00:00:00 → 2025-09-27 00:00:00

**Columns:** `ID` int, `DATE` datetime, `CONTRACTOR` nvarchar(255), `SHIFT` float, `PIT` nvarchar(255), `DIGGER` nvarchar(255), `BLOCK_ID` nvarchar(255), `MATERIAL` nvarchar(255), `MATERIAL2` nvarchar(255), `DUMPING_AREA` nvarchar(255), `RIT` float, `DISTANCE` float, `WMT` float, `BCM` float

**Identifier vocabularies:**

- `BLOCK_ID` — 14,092 distinct. e.g. `807_B54_S99`, `807_B55_S101`, `823_B61_S97`, `881_B82_S91`, `691_B11_S108`, `707_B15_S89`, `739_B26_S85`, `759_B32_S82`, `751_B31_S83`, `755_B31_S82`, `771_B36_S84`, `811_B49_S97`

**Sample rows**:

| ID | DATE | CONTRACTOR | SHIFT | PIT | DIGGER | BLOCK_ID | MATERIAL | MATERIAL2 | DUMPING_AREA | RIT | DISTANCE | WMT | BCM |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2025-04-28T00:00:00.000 | SMA | 1.0 | TF | EXC 908 |  | SAP |  | TOS_TF_SMA_04 | 20.0 | 1100.0 | 600.0 | 338.9830508475 |
| 2 | 2025-04-28T00:00:00.000 | SMA | 1.0 | TF | EXC 908 |  | SAP |  | TOS_TF_SMA_02 | 28.0 | 700.0 | 840.0 | 474.5762711864 |
| 3 | 2025-04-28T00:00:00.000 | SMA | 1.0 | TF | EXC 908 |  | LIM |  | LD_TF_04 | 26.0 | 1000.0 | 780.0 | 440.6779661017 |
| 4 | 2025-04-28T00:00:00.000 | SMA | 1.0 | TF | EXC 908 |  | TS |  | TEMP_SD_TF_SMA_01 | 2.0 | 1400.0 | 60.0 | 33.8983050847 |
| 5 | 2025-04-28T00:00:00.000 | SMA | 1.0 | TF | EXC 908 |  | SAP |  | TOS_TF_SMA_02 | 35.0 | 700.0 | 1050.0 | 593.2203389831 |

<a id="wbn-database-daily-quality-dispatch"></a>

#### `DAILY_QUALITY_DISPATCH`

**Rows:** 66,774  |  **Columns:** 19  |  **DATE:** 2025-02-27 → 2026-07-22

**Columns:** `ID` int, `DATE` date, `SHIFT` float, `PIT` nvarchar(50), `CONTRACTOR` nvarchar(50), `TOS_PILE` nvarchar(50), `CATEGORY` nvarchar(50), `CATEGORY_2` nvarchar(50), `WMT` float, `Ni_TOS` float, `Ni_BM` float, `Ni_Plan` float, `DOME` nvarchar(50), `DESTINATION` nvarchar(50), `STATUS` nvarchar(50), `EXCA` nvarchar(50), `DT` float, `HAUL_CONFIDENCE` nvarchar(50), `TYPE` nvarchar(50)

**Sample rows** (first 14 of 19 columns):

| ID | DATE | SHIFT | PIT | CONTRACTOR | TOS_PILE | CATEGORY | CATEGORY_2 | WMT | Ni_TOS | Ni_BM | Ni_Plan | DOME | DESTINATION |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2025-02-27T00:00:00.000 | 2.0 | KR | RIM | KR.CS.78 | CS | CS | 200.0 | 0.6 | 0.6 | 0.6 |  | FENI KM15 |
| 2 | 2025-02-27T00:00:00.000 | 2.0 | KR | RIM | KR.CS.79 | CS | CS | 800.0 | 0.6 | 0.6 | 0.6 |  | FENI KM15 |
| 3 | 2025-02-27T00:00:00.000 | 2.0 | KR | PPP | KR.I.1440 |  |  | 300.0 | 1.59 | 0.87 | 1.05 | AAM.323 | POS 6 |
| 4 | 2025-02-27T00:00:00.000 | 2.0 | KR | PPP | KR.I.1459 |  |  | 450.0 | 1.56 | 1.38 | 1.425 | AAM.323 | POS 6 |
| 5 | 2025-02-27T00:00:00.000 | 2.0 | KR | RIM | KR. I.1555 |  |  | 450.0 | 2.38 | 1.5 | 1.72 |  | FENI KM15 |

<a id="wbn-database-piles-shared-feni"></a>

#### `PILES_SHARED_FENI`

**Rows:** 66,571  |  **Columns:** 7  |  **DATE_SHARE:** 2024-11-19 00:00:00 → 2026-05-29 00:00:00

**Columns:** `ID` int, `DATE_SHARE` datetime, `PILE_ID` nvarchar(255), `TOS_LOCATION` nvarchar(255), `CLASS` nvarchar(255), `CATEGORY` nvarchar(255), `WMT` float

**Identifier vocabularies:**

- `PILE_ID` — 15,371 distinct. e.g. `BLB.D.1052`, `BLB.D.1050`, `BLB.G.4435`, `BLB.G.4425`, `BLB.G.4431`, `BLB.G.4422`, `TF.G.1197`, `TF.G.1265`, `TF.G.1272`, `TF.G.1273`, `TF.G.1274`, `TF.G.1279`

**Sample rows**:

| ID | DATE_SHARE | PILE_ID | TOS_LOCATION | CLASS | CATEGORY | WMT |
|---|---|---|---|---|---|---|
| 1 | 2025-07-27T00:00:00.000 | BLB.D.1052 |  | HGS | ADM | 1600.0 |
| 2 | 2025-07-27T00:00:00.000 | BLB.D.1050 |  | HGS | ADM | 1200.0 |
| 3 | 2025-07-27T00:00:00.000 | BLB.G.4435 |  | LIM | LIM1 | 360.0 |
| 4 | 2025-07-27T00:00:00.000 | BLB.G.4425 |  | LIM | LIM1 | 150.0 |
| 5 | 2025-07-27T00:00:00.000 | BLB.G.4431 |  | LIM | LIM1 | 720.0 |

<a id="wbn-database-exc-trimming"></a>

#### `EXC_TRIMMING`

**Rows:** 59,362  |  **Columns:** 9  |  **Date:** 2024-11-13 00:00:00 → 2026-07-11 00:00:00

**Columns:** `ID` int, `Date` datetime, `Contractor` nvarchar(255), `Shift` float, `PIT` nvarchar(255), `Location` nvarchar(255), `Jumlah Exc` float, `UNIT_ID` nvarchar(255), `STATUS` nvarchar(255)

**Identifier vocabularies:**

- `UNIT_ID` — 1,442 distinct. e.g. `KOMATSU 259`, `KOMATSU 105`, `LIUGONG 095`, `KOMATSU 238`, `SANY 6209`, `SANY 6210`, `SANY 6215`, `SANY 6216`, `CAT 320`, `SANY 215`, `VOLVO 228`, `KOMATSU 224`

**Sample rows**:

| ID | Date | Contractor | Shift | PIT | Location | Jumlah Exc | UNIT_ID | STATUS |
|---|---|---|---|---|---|---|---|---|
| 338 | 2024-11-13T00:00:00.000 | PPP | 1.0 | TF | TOS_TF_PPP_01 | 3.0 |  |  |
| 339 | 2024-11-13T00:00:00.000 | PPP | 1.0 | TF | TOS_TF_STM_01 | 1.0 |  |  |
| 340 | 2024-11-13T00:00:00.000 | SSS | 1.0 | TF | TOS_TF_SMA_03 | 1.0 |  |  |
| 341 | 2024-11-13T00:00:00.000 | SSS | 1.0 | TF | TOS_TF_STM_04 | 1.0 |  |  |
| 342 | 2024-11-13T00:00:00.000 | SSS | 1.0 | TF | TOS_TF_STM_03 | 1.0 |  |  |

<a id="wbn-database-rainfall"></a>

#### `RAINFALL`

**Rows:** 55,934  |  **Columns:** 9  |  **DATE:** 2002-01-01 → 2026-04-11

**Columns:** `ID` int, `CONTRACTOR` nvarchar(50), `DATE` date, `AREA` nvarchar(255), `STATION` nvarchar(255), `H2O_mm` float, `X` float, `Y` float, `DURASI` float

**Coordinate extent:** `X` 375228.0 → 406823.0; `Y` 52145.9962754764 → 90924.0

**Sample rows**:

| ID | CONTRACTOR | DATE | AREA | STATION | H2O_mm | X | Y | DURASI |
|---|---|---|---|---|---|---|---|---|
| 40135 | ENVIRO | 2024-11-01T00:00:00.000 | COASTAL | TG. ULIE | 26.0 | 387192.0 | 53352.0 |  |
| 40136 | ENVIRO | 2024-11-01T00:00:00.000 | COASTAL | UNI UNI | 16.5 | 382998.0 | 53854.0 |  |
| 40137 | ENVIRO | 2024-11-01T00:00:00.000 | KAO RAHAI | CAMP_KR | 18.7 | 385963.0 | 72202.0 |  |
| 40138 | ENVIRO | 2024-11-01T00:00:00.000 | TOFU | CAMP MTM | 6.5 | 391856.0 | 89638.0 | 2.3 |
| 40139 | ENVIRO | 2024-11-01T00:00:00.000 | TOFU | PIT TOFU3_MTM | 8.5 | 392327.0 | 88755.0 | 3.1 |

<a id="wbn-database-survey-pos"></a>

#### `SURVEY POS`

**Rows:** 50,385  |  **Columns:** 19  |  **DATE:** 2024-10-05 00:00:00 → 2026-07-25 00:00:00

**Columns:** `ID` int, `DATE` datetime, `TYPE OF SURVEY` nvarchar(255), `SURVEY WEEK` float, `LOCATION` nvarchar(255), `DOME` nvarchar(255), `DOME ID` nvarchar(255), `SURVEY METHOD` nvarchar(255), `PIT DETAILS` nvarchar(255), `PIT` nvarchar(255), `ROCKY VOLUME` float, `VOLUME (LCM)` float, `VOLUME (BCM)` float, `ORIGINAL DENSITY` float, `ADJUSTED DENSITY` float, `WMT` float, `STOCK TYPE` nvarchar(255), `GET_DOME_CRUSH` nvarchar(255), `REMARK` nvarchar(255)

**Sample rows** (first 14 of 19 columns):

| ID | DATE | TYPE OF SURVEY | SURVEY WEEK | LOCATION | DOME | DOME ID | SURVEY METHOD | PIT DETAILS | PIT | ROCKY VOLUME | VOLUME (LCM) | VOLUME (BCM) | ORIGINAL DENSITY |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 146540 | 2024-10-05T00:00:00.000 | WEEKLY | 40.0 |  | LGS.G | LGS.G | Drone | CSTL | CSTL |  | 141091.1617803738 | 135015.4658185395 | 1.5914308471 |
| 146541 | 2024-10-05T00:00:00.000 | WEEKLY | 40.0 |  | LGS.CLIFFDUMP CSW2B | LGS CLIFF DUMP CSW2B | Drone | CSW | CSTL |  | 17971.493 | 17197.6009569378 | 1.5417694933 |
| 146542 | 2024-10-05T00:00:00.000 | WEEKLY | 40.0 |  | LGO 1 | LGO | Drone | CNU | CSTL |  | 40561.685 | 38815.009569378 | 1.5914308471 |
| 146543 | 2024-10-05T00:00:00.000 | WEEKLY | 40.0 |  | LGO 7 | LGO | Ground | CNU | CSTL |  | 25393.3962196262 | 24299.9006886375 | 1.5914308471 |
| 146544 | 2024-10-05T00:00:00.000 | WEEKLY | 40.0 |  | LGO GOMDI | LGO GOMDI | Drone | CSTL | CSTL |  | 10118.32 | 9682.6028708134 | 1.5914308471 |

<a id="wbn-database-haulage-m-dome-2026-iwip-plan"></a>

#### `HAULAGE_M_DOME_2026_IWIP_PLAN`

**Rows:** 44,289  |  **Columns:** 15  |  **TIME_LOADED:** 2026-03-05 20:11:55 → 2026-04-06 00:56:51

**Columns:** `WB_DATE` float, `WB_ID` nvarchar(255), `TICKET_NO` nvarchar(255), `TRUCK_ID` nvarchar(255), `ORIGIN_ID` nvarchar(255), `DESTINATION_ID` nvarchar(255), `CONTRACTOR` nvarchar(255), `KG_LOADED` float, `KG_EMPTY` float, `KG_NET` float, `TIME_LOADED` datetime, `TIME_EMPTY` datetime, `ORI_AREA` nvarchar(255), `DEST_AREA` nvarchar(255), `DATE` datetime

**Identifier vocabularies:**

- `WB_ID` — 9 distinct. e.g. `T12`, `T15`, `T16`, `T18`, `T19`, `T7`, `T13`, `T11`, `T14`
- `TRUCK_ID` — 1,451 distinct. e.g. `R700`, `R711`, `R704`, `R699`, `R695`, `R706`, `R702`, `R696`, `R692`, `R710`, `R709`, `R707`
- `ORIGIN_ID` — 875 distinct. e.g. `TF.A.7887`, `TF.A.7874`, `TF.A.7891`, `TF.A.7886`, `TF.A.7876`, `TF.A.7867`, `TF.B.5465`, `TF.A.7898`, `TF.A.7923`, `TF.A.7931`, `TF.A.7919`, `TF.A. 7925`
- `DESTINATION_ID` — 80 distinct. e.g. `M4_POS16_001`, `M3_POS16_001`, `M1_POS12_009`, `M1_POS12_005`, `M3_POS12_010`, `M3_POS12_012`, `M1_POS12_017`, `M1_POS12_020`, `M4_POS12_005`, `M3_POS12_005`, `M1_POS10_01`, `M1_POS10_001`

**Sample rows** (first 14 of 15 columns):

| WB_DATE | WB_ID | TICKET_NO | TRUCK_ID | ORIGIN_ID | DESTINATION_ID | CONTRACTOR | KG_LOADED | KG_EMPTY | KG_NET | TIME_LOADED | TIME_EMPTY | ORI_AREA | DEST_AREA |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 20260326.0 | T19 | 19A20260326172447 | R700 |  | M4_POS16_001 | RIM | 77600.0 | 29980.0 | 47620.0 | 2026-03-26T17:24:47.000 | 2026-03-26T22:27:29.000 | BLB TOS-WBN??? | POS16-WBN??? |
| 20260326.0 | T19 | 19A20260326173949 | R711 |  | M3_POS16_001 | RIM | 78240.0 | 29100.0 | 49140.0 | 2026-03-26T17:39:49.000 | 2026-03-26T22:07:09.000 | BLB TOS-WBN??? | POS16-WBN??? |
| 20260326.0 | T19 | 19A20260326181108 | R704 |  | M3_POS16_001 | RIM | 79660.0 | 29420.0 | 50240.0 | 2026-03-26T18:11:06.000 | 2026-03-26T21:05:41.000 | BLB TOS-WBN??? | POS16-WBN??? |
| 20260326.0 | T19 | 19A20260326174703 | R699 |  | M4_POS16_001 | RIM | 79340.0 | 28160.0 | 51180.0 | 2026-03-26T17:47:03.000 | 2026-03-26T21:04:57.000 | BLB TOS-WBN??? | POS16-WBN??? |
| 20260326.0 | T19 | 19A20260326175732 | R695 |  | M4_POS16_001 | RIM | 78540.0 | 29560.0 | 48980.0 | 2026-03-26T17:57:32.000 | 2026-03-26T21:01:51.000 | BLB TOS-WBN??? | POS16-WBN??? |

<a id="wbn-database-autotos-survey-estimation"></a>

#### `autoTOS_SURVEY_ESTIMATION`

**Rows:** 43,187  |  **Columns:** 19  |  **DATE:** 2026-05-02 00:00:00 → 2026-07-30 00:00:00

**Columns:** `LAST_UPDATE` nvarchar(50), `DATE` datetime, `SHIFT` int, `DATETIME` datetime, `STOCK_TYPE` nvarchar(50), `STOCK_AREA` nvarchar(50), `STOCK_ID` nvarchar(50), `STATUS` nvarchar(50), `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `RIT` float, `TF` float, `WMT_SURVEY_EST` float, `WMT_SURVEY_GAP` float, `WMT_SURVEY` float, `WMT_TRANSFER` float, `WMT_ORI` float, `WMT` float

**Identifier vocabularies:**

- `STOCK_ID` — 422 distinct. e.g. ``, `BLB.G.6765`, `BLB.G.6796`, `BLB.G.6829`, `BLB.G.6833`, `BLB.G.6850`, `BLB.G.6852`, `BLB.G.6854`, `BLB.G.6856`, `BLB.G.6865`, `BLB.G.6870`, `BLB.G.6879`

**Sample rows** (first 14 of 19 columns):

| LAST_UPDATE | DATE | SHIFT | DATETIME | STOCK_TYPE | STOCK_AREA | STOCK_ID | STATUS | CONTRACTOR | ACTIVITY | MATERIAL | RIT | TF | WMT_SURVEY_EST |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-07-30 10:30:00 | 2026-05-02T00:00:00.000 | 1 | 2026-05-02T07:00:00.000 | TOS | LD_TF_004 |  | OPEN |  |  |  |  |  |  |
| 2026-07-30 10:30:00 | 2026-05-02T00:00:00.000 | 1 | 2026-05-02T07:00:00.000 | TOS | TOS_BLB_03 | BLB.G.6765 | COMPLETE |  |  |  |  |  |  |
| 2026-07-30 10:30:00 | 2026-05-02T00:00:00.000 | 1 | 2026-05-02T07:00:00.000 | TOS | TOS_BLB_10 | BLB.G.6796 | COMPLETE |  |  |  |  |  |  |
| 2026-07-30 10:30:00 | 2026-05-02T00:00:00.000 | 1 | 2026-05-02T07:00:00.000 | TOS | TOS_BLB_10 | BLB.G.6829 | COMPLETE |  |  |  |  |  |  |
| 2026-07-30 10:30:00 | 2026-05-02T00:00:00.000 | 1 | 2026-05-02T07:00:00.000 | TOS | TOS_BLB_11 | BLB.G.6833 | TRANSFER | RIM | HAULING | WST | -30.0 | 35.0 |  |

<a id="wbn-database-qc-tos-data-ml"></a>

#### `QC_TOS_DATA_ML`

**Rows:** 38,001  |  **Columns:** 33

**Columns:** `LAST_UPDATE` nvarchar(50), `TYPE_DATA` varchar(-1), `TYPE` varchar(-1), `TOS LOCATION` varchar(-1), `LOCATION` varchar(-1), `CONTRACTOR` varchar(-1), `PILE ID` varchar(-1), `PLAN_Ni` float, `TOS_CaO` float, `TOS_Co` float, `TOS_Fe` float, `TOS_MC` float, `TOS_MgO` float, `TOS_MnO` float, `TOS_Ni` float, `TOS_p2o5` float, `TOS_sio2` float, `BM_WMT` float, `BM_al2o3` float, `BM_cao` float, `BM_Co` float, `BM_cr2o3` float, `BM_Fe` float, `BM_MC` float, `BM_MgO` float, `BM_mno` float, `BM_Ni` float, `BM_p2o5` float, `BM_SiO2` float, `BM_PROP` float, `WMT` float, `MATERIAL` varchar(-1), `ML_PREDICTED_Ni` float

**Sample rows** (first 14 of 33 columns):

| LAST_UPDATE | TYPE_DATA | TYPE | TOS LOCATION | LOCATION | CONTRACTOR | PILE ID | PLAN_Ni | TOS_CaO | TOS_Co | TOS_Fe | TOS_MC | TOS_MgO | TOS_MnO |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-02-02 08:44:45 | TOS/BM | NON-GRIZZLY | TOS_TF_10 | TF | RIM | TF.G.2001 | 1.8910757324 | 0.03 | 0.1024 | 23.1524 | 40.1732 | 16.9784 | 0.794 |
| 2026-02-02 08:44:45 | TOS/BM | NON-GRIZZLY | TOS_TF_10 | TF | RIM | TF.G.2007 | 1.912261391 | 0.0431818182 | 0.0742045455 | 19.5081818182 | 34.2190909091 | 18.9684090909 | 0.5679545455 |
| 2026-02-02 08:44:45 | TOS/BM | NON-GRIZZLY | TOS_TF_08 | TF | RIM | TF.G.2008 | 1.9022591295 | 0.049 | 0.0796 | 18.068 | 33.783 | 18.955 | 0.621 |
| 2026-02-02 08:44:45 | TOS/BM | NON-GRIZZLY | TOS_TF_10 | TF | RIM | TF.G.2009 | 1.9116635828 | 0.04 | 0.0569148936 | 15.6608510638 | 33.5161702128 | 22.1331914894 | 0.4414893617 |
| 2026-02-02 08:44:45 | TOS/BM | NON-GRIZZLY | TOS_TF_10 | TF | RIM | TF.G.2020 | 1.7298906979 | 0.0436363636 | 0.0527272727 | 14.9204545455 | 31.6018181818 | 20.5745454545 | 0.4322727273 |

<a id="wbn-database-pp-remain-inpit-mineout"></a>

#### `PP_REMAIN_INPIT_MINEOUT`

**Rows:** 36,206  |  **Columns:** 13

**Columns:** `PIT` varchar(50), `X` float, `Y` float, `Z` float, `classification_no` float, `size (X)` float, ` size(Y)` float, ` size(Z)` float, `block_id` nvarchar(255), `pp_inside_pit_remain` float, `YEAR_UPDATED` float, `WEEK_UPDATED` float, `remarks` varchar(500)

**Identifier vocabularies:**

- `block_id` — 18,138 distinct. e.g. `N442_B72_S325`, `N430_B77_S325`, `N450_B86_S321`, `418_B23_S157`, `N450_B95_S319`, `N442_B92_S277`, `N454_B93_S277`, `N458_B103_S331`, `N434_B99_S317`, `450_B40_S140`, `N434_B105_S307`, `N434_B105_S306`

**Coordinate extent:** `X` 391750.0 → 393006.25; `Y` 87843.75 → 90456.25

**Sample rows**:

| PIT | X | Y | Z | classification_no | size (X) |  size(Y) |  size(Z) | block_id | pp_inside_pit_remain | YEAR_UPDATED | WEEK_UPDATED | remarks |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TF | 392231.25 | 88181.25 | 444.0 | 1.0 | 12.5 | 12.5 | 4.0 | N442_B72_S325 | 0.89 | 2025.0 | 34.0 | dsgn1014 |
| TF | 392293.75 | 88181.25 | 432.0 | 1.0 | 12.5 | 12.5 | 4.0 | N430_B77_S325 | 0.75 | 2025.0 | 34.0 | dsgn1014 |
| TF | 392406.25 | 88231.25 | 452.0 | 1.0 | 12.5 | 12.5 | 4.0 | N450_B86_S321 | 0.09 | 2025.0 | 34.0 | dsgn1014 |
| TF | 392025.0 | 88250.0 | 420.0 | 1.0 | 25.0 | 25.0 | 4.0 | 418_B23_S157 | 0.08 | 2025.0 | 34.0 | dsgn1014 |
| TF | 392518.75 | 88256.25 | 452.0 | 1.0 | 12.5 | 12.5 | 4.0 | N450_B95_S319 | 0.03 | 2025.0 | 34.0 | dsgn1014 |

<a id="wbn-database-pp-mined-ytd-ok"></a>

#### `PP_MINED_YTD_OK`

**Rows:** 35,922  |  **Columns:** 12

**Columns:** `X` float, `Y` float, `Z` float, `classification_no` float, `size (X)` float, ` size(Y)` float, ` size(Z)` float, `block_id` nvarchar(255), `pp_mined_progress` float, `YEAR` int, `MONTH` int, `WEEK` int

**Identifier vocabularies:**

- `block_id` — 35,922 distinct. e.g. `N454_B147_S657`, `N434_B137_S645`, `N430_B137_S641`, `N434_B137_S641`, `N430_B139_S643`, `N450_B147_S651`, `N446_B147_S649`, `N450_B147_S649`, `N430_B139_S645`, `N454_B137_S645`, `N458_B137_S645`, `N454_B139_S647`

**Coordinate extent:** `X` 391343.75 → 393831.25; `Y` 87243.75 → 92231.25

**Sample rows**:

| X | Y | Z | classification_no | size (X) |  size(Y) |  size(Z) | block_id | pp_mined_progress | YEAR | MONTH | WEEK |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 392256.25 | 88131.25 | 456.0 | 1.0 | 12.5 | 12.5 | 4.0 | N454_B147_S657 | 0.576 | 2025 | 6 | 26 |
| 392193.75 | 88206.25 | 436.0 | 1.0 | 12.5 | 12.5 | 4.0 | N434_B137_S645 | 0.127 | 2025 | 6 | 26 |
| 392193.75 | 88231.25 | 432.0 | 1.0 | 12.5 | 12.5 | 4.0 | N430_B137_S641 | 0.838 | 2025 | 6 | 26 |
| 392193.75 | 88231.25 | 436.0 | 1.0 | 12.5 | 12.5 | 4.0 | N434_B137_S641 | 1.0 | 2025 | 6 | 26 |
| 392206.25 | 88218.75 | 432.0 | 1.0 | 12.5 | 12.5 | 4.0 | N430_B139_S643 | 0.436 | 2025 | 6 | 26 |

<a id="wbn-database-tss"></a>

#### `TSS`

**Rows:** 35,218  |  **Columns:** 19  |  **DATE:** 2024-10-01 00:00:00 → 2026-04-11 00:00:00

**Columns:** `ID` int, `CONTRACTOR` nvarchar(50), `DATE` datetime, `AREA` nvarchar(255), `SUB_AREA` nvarchar(255), `MANAGER` nvarchar(255), `TYPE` nvarchar(255), `MINE` nvarchar(255), `STATION` nvarchar(255), `TSS` float, `PH` float, `TEMPERATURE` float, `CONDUCTIVITY` float, `TDS` float, `TURBIDITY_NTU` float, `TSS_LIMIT` float, `COMPLIANCE` float, `X` float, `Y` float

**Coordinate extent:** `X` 1.68 → 405634.0; `Y` 52126.0 → 90874.9015

**Sample rows** (first 14 of 19 columns):

| ID | CONTRACTOR | DATE | AREA | SUB_AREA | MANAGER | TYPE | MINE | STATION | TSS | PH | TEMPERATURE | CONDUCTIVITY | TDS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 850 | ENVIRO | 2025-01-31T00:00:00.000 | PINTO | Ake Yonelo |  | River | WBN | AP-06' (Actual) | 5.0 |  |  |  |  |
| 851 | ENVIRO | 2025-01-31T00:00:00.000 | KAO RAHAI | HR Coastal - KR KM 18 |  | River | WBN | AP-SL-04 | 5.0 | 8.53 | 25.0 | 288.0 | 144.0 |
| 852 | ENVIRO | 2025-01-31T00:00:00.000 | KAO RAHAI | Ake Mein |  | River | WBN | AP-09 | 12.0 | 8.29 | 23.5 | 185.0 | 93.0 |
| 853 | ENVIRO | 2025-01-31T00:00:00.000 | COASTAL | Ake Wosea |  | River | WBN | AP2 | 18.0 | 8.59 | 25.3 | 309.0 | 155.0 |
| 854 | ENVIRO | 2025-01-31T00:00:00.000 | COASTAL | Ake Wosea |  | River | WBN | AP3 | 31.0 | 8.58 | 25.0 | 346.0 | 173.0 |

<a id="wbn-database-hrm-inspection"></a>

#### `HRM_INSPECTION`

**Rows:** 30,610  |  **Columns:** 14  |  **DATE:** 2024-10-01 00:00:00 → 2025-12-11 00:00:00

> Road-condition observations by KM, severity and type since 2024-10. Exogenous to deployment, so usable as a cycle-time feature.

**Columns:** `ID` int, `DATE` datetime, `SHIFT` float, `LOCATION` nvarchar(50), `KM_START` float, `KM_END` float, `DIRECTION` nvarchar(50), `CONTRACTOR` nvarchar(50), `TYPE` nvarchar(-1), `SEVERITY` float, `STATUS` nvarchar(50), `DETAILS` nvarchar(250), `STA` nvarchar(50), `IDLINK` nvarchar(50)

**Sample rows**:

| ID | DATE | SHIFT | LOCATION | KM_START | KM_END | DIRECTION | CONTRACTOR | TYPE | SEVERITY | STATUS | DETAILS | STA | IDLINK |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5464 | 2024-10-01T00:00:00.000 | 1.0 | KR | 15.5 | 16.0 | LOADED & EMPTY | RIM | BUMPY ROAD | 1.0 | ON MAINTENANCE | spot undulated (1) on maintenance (con… | 15+500 | KR15+500 |
| 5465 | 2024-10-01T00:00:00.000 | 1.0 | KR | 16.7 | 17.0 | LOADED & EMPTY | RIM | BUMPY ROAD | 1.0 | NEED MAINTENANCE | undulated road (1) need to grading and… | 16+700 | KR16+700 |
| 5466 | 2024-10-01T00:00:00.000 | 1.0 | KR | 17.8 | 17.9 | LOADED & EMPTY | RIM | BUMPY ROAD | 2.0 | NEED MAINTENANCE | undulated road (2) need to maintenance… | 17+800 | KR17+800 |
| 5467 | 2024-10-01T00:00:00.000 | 1.0 | KR | 18.15 | 18.3 | EMPTY | RIM | BUMPY ROAD | 1.0 | ON MAINTENANCE | undulated road (1), on maintenance | 18+150 | KR18+150 |
| 5468 | 2024-10-01T00:00:00.000 | 1.0 | KR | 18.6 | 18.9 | LOADED & EMPTY | RIM | CLOGGED DRAINAGE | 2.0 | ON MAINTENANCE | Undulated road (1), need grading & com… | 18+600 | KR18+600 |

<a id="wbn-database-distance-hauling"></a>

#### `DISTANCE_HAULING`

**Rows:** 30,587  |  **Columns:** 12  |  **DATE:** 2025-04-28 00:00:00 → 2025-09-27 00:00:00

> Real per-haul distances by origin/destination with date, tonnage and trip count. Candidate replacement for the placeholder distance_km.

**Columns:** `ID` int, `DATE` datetime, `CONTRACTOR` nvarchar(255), `ORIGIN_ID` nvarchar(255), `ORIGIN_AREA` nvarchar(255), `DESTINATION_ID` nvarchar(255), `DESTINATION_AREA` nvarchar(255), `DISTANCE` float, `WMT` float, `RIT` float, `SPV_WBN` nvarchar(255), `SPV_CONTRACTOR` nvarchar(255)

**Identifier vocabularies:**

- `ORIGIN_ID` — 6,231 distinct. e.g. `TF.B.2596`, `TF.A.3211`, `TF.B.2553`, `TF.A.3215`, `TF.B.2601`, `TF.B.2595`, `TF.G.513`, `TF.B.2608`, `TF.A.3240`, `TF.G.521`, `TF.B.2616`, `TF.G.501`
- `DESTINATION_ID` — 864 distinct. e.g. `ADM.472`, `ADM.469`, `ADM.480`, `AD.323`, `ABM.341`, `ADM.486`, `AD.327`, `POS.WCO.035`, `ABM.345`, `AD.331`, `ADM.498`, `ADM.503`

**Sample rows**:

| ID | DATE | CONTRACTOR | ORIGIN_ID | ORIGIN_AREA | DESTINATION_ID | DESTINATION_AREA | DISTANCE | WMT | RIT | SPV_WBN | SPV_CONTRACTOR |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2025-04-28T00:00:00.000 | SMA | TF.B.2596 | TOS_TF_SMA_02 | ADM.472 | POS 12 | 44.0 | 491.78 | 12.0 | INDRA SAMUEL SIANTURI | VELKY AMBITAN |
| 2 | 2025-04-28T00:00:00.000 | SMA | TF.A.3211 | TOS_TF_STM_04 | ADM.469 | POS 12 | 43.3 | 1184.02 | 32.0 | INDRA SAMUEL SIANTURI | VELKY AMBITAN |
| 3 | 2025-04-28T00:00:00.000 | SMA | TF.B.2553 | TOS_TF_SMA_02 | ADM.472 | POS 12 | 44.0 | 2068.16 | 56.0 | INDRA SAMUEL SIANTURI | VELKY AMBITAN |
| 4 | 2025-04-28T00:00:00.000 | SMA | TF.A.3215 | TOS_TF_STM_01 | ADM.472 | POS 12 | 42.5 | 1648.14 | 50.0 | INDRA SAMUEL SIANTURI | VELKY AMBITAN |
| 5 | 2025-04-28T00:00:00.000 | SMA | TF.B.2601 | TOS_TF_SMA_02 | ADM.472 | POS 12 | 44.0 | 486.14 | 13.0 | INDRA SAMUEL SIANTURI | VELKY AMBITAN |

<a id="wbn-database-crusher-loipoloy"></a>

#### `CRUSHER LOIPOLOY`

**Rows:** 27,353  |  **Columns:** 17  |  **DATE:** 2024-10-01 → 2026-07-27

**Columns:** `ID` int, `CONTRACTOR` nvarchar(-1), `DATE` date, `SHIFT` int, `LOCATION` nvarchar(-1), `CRUSHER` nvarchar(-1), `LINE` int, `FEEDING_ID` int, `RECORDED_MATERIAL` nvarchar(-1), `PRODUCT` nvarchar(-1), `STOCK_ID` nvarchar(-1), `BUCKET` int, `BF` int, `TRUCK` int, `TF` int, `BCM` float, `WMT` float

**Identifier vocabularies:**

- `STOCK_ID` — 839 distinct. e.g. `2-3 Line 1`, `1-2 Line 1`, `0-1 Line 1`, `BC 2-3 Line 2`, `5-7 Line 3`, `2-3 Line 3`, `1-2 Line 3`, `0-1 Line 3`, `BC 5-7 Line 2`, ``, `5-7 Line 2`, `0-1 Line 2`

**Sample rows** (first 14 of 17 columns):

| ID | CONTRACTOR | DATE | SHIFT | LOCATION | CRUSHER | LINE | FEEDING_ID | RECORDED_MATERIAL | PRODUCT | STOCK_ID | BUCKET | BF | TRUCK |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 583 | PMKI | 2024-10-13T00:00:00.000 | 1 |  | CRUSHER LOYPOLOY KM16 | 1 | 1 | FEED |  |  | 33 | 2 | 0 |
| 584 | PMKI | 2024-10-13T00:00:00.000 | 1 |  | CRUSHER LOYPOLOY KM16 | 1 | 1 | OUTPUT | 2-3 | 2-3 Line 1 | 13 | 2 | 0 |
| 585 | PMKI | 2024-10-13T00:00:00.000 | 1 |  | CRUSHER LOYPOLOY KM16 | 1 | 1 | OUTPUT | 1-2 | 1-2 Line 1 | 4 | 2 | 0 |
| 586 | PMKI | 2024-10-13T00:00:00.000 | 1 |  | CRUSHER LOYPOLOY KM16 | 1 | 1 | OUTPUT | 0-1 | 0-1 Line 1 | 16 | 2 | 0 |
| 587 | PMKI | 2024-10-13T00:00:00.000 | 2 |  | CRUSHER LOYPOLOY KM16 | 1 | 1 | FEED |  |  | 67 | 2 | 0 |

<a id="wbn-database-dispatch-wbn-plan-shift"></a>

#### `DISPATCH WBN PLAN SHIFT`

**Rows:** 27,058  |  **Columns:** 15  |  **DATE:** 2024-10-01 → 2026-07-22

**Columns:** `ID` int, `CONTRACTOR` nvarchar(50), `DATE` date, `SHIFT` int, `TYPE DATA` nvarchar(50), `TYPE` nvarchar(50), `MATERIAL` nvarchar(50), `COMPANY` nvarchar(50), `DISPATCH ZONE` nvarchar(50), `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `BUYER` nvarchar(50), `NB DT` float, `TF` float, `PRODUCTIVITY TARGET` float

**Sample rows** (first 14 of 15 columns):

| ID | CONTRACTOR | DATE | SHIFT | TYPE DATA | TYPE | MATERIAL | COMPANY | DISPATCH ZONE | ORIGIN | DESTINATION | BUYER | NB DT | TF |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 16865 | GMG | 2024-10-01T00:00:00.000 | 1 | PLAN | HAULAGE | SAP | WBN | KR to KM 17 | KR | POS 10 |  | 55.0 | 33.0 |
| 16866 | HJS | 2024-10-01T00:00:00.000 | 1 | PLAN | HAULAGE | SAP | WBN | CBB to CUU | CBB | POS UNI-UNI |  | 30.0 | 21.0 |
| 16867 | HJS | 2024-10-01T00:00:00.000 | 1 | PLAN | HAULAGE | SAP | WBN | CBB to CBB | CBB | POS CBB |  | 25.0 | 21.0 |
| 16868 | PPP | 2024-10-01T00:00:00.000 | 1 | PLAN | DIRECT | LIM | WBN | KR to HUAFEI | KR | HUAFEI.C01 |  | 20.0 | 25.0 |
| 16869 | PPP | 2024-10-01T00:00:00.000 | 1 | PLAN | DIRECT | CS | WBN | KR to KM 15 | KR | FENI KM15 |  | 15.0 | 25.0 |

<a id="wbn-database-qc-sample-data"></a>

#### `QC SAMPLE DATA`

**Rows:** 25,425  |  **Columns:** 15  |  **DATE_IN:** 2024-01-12 → 2025-02-17

**Columns:** `ID` int, `JOB-QC` nvarchar(50), `SHIFT` int, `DATE_IN` date, `PILE ID` nvarchar(50), `COMPOSITE` nvarchar(50), `TYPE SAMPLE` nvarchar(50), `RIT` int, `SAMPLE WEIGHT` float, `ROCKY WEIGHT` float, `EARTHY WEIGHT` float, `DATE` date, `SAMPLE CODE` nvarchar(50), `TYPE ANALYSIS` nvarchar(50), `TESTED SAMPLE` nvarchar(50)

**Identifier vocabularies:**

- `SAMPLE CODE` — 25,393 distinct. e.g. `BLB-IWIP-3994`, `BLB-IWIP-3995`, `BLB-IWIP-3996`, `BLB-IWIP-3995PD`, `BLB-IWIP-3996GD`, `BLB-IWIP-3990`, `BLB-IWIP-3991`, `BLB-IWIP-3990PD`, `BLB-IWIP-3991GD`, `BLB-LIM-3992`, `BLB-LIM-3993`, `BLB-LIM-3992PD`

**Sample rows** (first 14 of 15 columns):

| ID | JOB-QC | SHIFT | DATE_IN | PILE ID | COMPOSITE | TYPE SAMPLE | RIT | SAMPLE WEIGHT | ROCKY WEIGHT | EARTHY WEIGHT | DATE | SAMPLE CODE | TYPE ANALYSIS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 65120 | BLB-IWIP-1000 | 2 | 2025-02-06T00:00:00.000 | BLB.G.1573 |  | ORIGINAL | 30.0 | 450.0 | 150.0 | 300.0 | 2025-02-07T00:00:00.000 | BLB-IWIP-3994 | GA |
| 65121 | BLB-IWIP-1000 | 2 | 2025-02-06T00:00:00.000 | BLB.G.1573 |  | DUPLICATE 1 |  |  |  |  | 2025-02-07T00:00:00.000 | BLB-IWIP-3995 | GA |
| 65122 | BLB-IWIP-1000 | 2 | 2025-02-06T00:00:00.000 | BLB.G.1577 |  | ORIGINAL | 49.0 | 735.0 | 245.0 | 490.0 | 2025-02-07T00:00:00.000 | BLB-IWIP-3996 | GA |
| 65123 | BLB-IWIP-1000 | 2 | 2025-02-06T00:00:00.000 | BLB.G.1573 |  | PULP DUPLICATE |  |  |  |  | 2025-02-07T00:00:00.000 | BLB-IWIP-3995PD | PD |
| 65124 | BLB-IWIP-1000 | 2 | 2025-02-06T00:00:00.000 | BLB.G.1577 |  | GROUND DUPLICATE |  |  |  |  | 2025-02-07T00:00:00.000 | BLB-IWIP-3996GD | GD |

<a id="wbn-database-very-very-short-term-pit-service"></a>

#### `VERY VERY SHORT TERM PIT SERVICE`

**Rows:** 21,064  |  **Columns:** 16  |  **DATE:** 2024-10-01 00:00:00 → 2026-07-27 00:00:00

**Columns:** `ID` int, `DATE` datetime, `SHIFT` nvarchar(255), `CONTRACTOR` nvarchar(255), `PIT` nvarchar(255), `LOCATION` nvarchar(255), `EXCA` float, `ADT` float, `DT` float, `BULL` float, `GRADER` nvarchar(255), `COMPACTOR` float, `LOADER` nvarchar(255), `QUARRY_WMT` float, `SP_WST_WMT` float, `TMM__WMT` float

**Identifier vocabularies:**

- `LOADER` — 2 distinct. e.g. `1`, `0`

**Sample rows** (first 14 of 16 columns):

| ID | DATE | SHIFT | CONTRACTOR | PIT | LOCATION | EXCA | ADT | DT | BULL | GRADER | COMPACTOR | LOADER | QUARRY_WMT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3720 | 2024-10-01T00:00:00.000 | DS | HJS | CBB | CBB | 2.0 | 8.0 | 8.0 |  |  |  |  | 4644.0 |
| 3721 | 2024-10-01T00:00:00.000 | DS | HJS | CSW | BLB | 1.0 | 0.0 | 6.0 |  |  |  |  | 360.0 |
| 3722 | 2024-10-01T00:00:00.000 | DS | MTM | TF | PIT/TOS/MESS | 1.0 | 1.0 |  |  |  |  |  |  |
| 3723 | 2024-10-01T00:00:00.000 | DS | PPP | KR | AKSES JALAN |  |  |  | 1.0 |  |  |  |  |
| 3724 | 2024-10-01T00:00:00.000 | DS | PPP | KR | PIT KAORAHAI 3 | 1.0 |  |  | 2.0 |  |  |  |  |

<a id="wbn-database-assays-niton-ggsheet"></a>

#### `ASSAYS_NITON_GGSHEET`

**Rows:** 19,700  |  **Columns:** 25  |  **LAST_UPDATE:** 2026-01-28 14:00:16 → 2026-07-30 05:00:48

**Columns:** `LAST_UPDATE` datetime, `DATE` date, `SHIFT` nvarchar(50), `JOB QC` nvarchar(50), `CODE ID` nvarchar(50), `ID DOME` nvarchar(50), `DATE ANALYSIS` nvarchar(50), `DATE REPORT` nvarchar(50), `CONTRACTOR` nvarchar(50), `ID BLOCK` nvarchar(50), `Ni Dry 1` float, `Fe2O3 Dry 1` float, `Ni Dry 2` float, `Fe2O3 Dry2` float, `Mc` float, `Column1` nvarchar(50), `Ni Average` float, `Fe2O3 Average` float, `Tfe` float, `Ni` float, `Fe2O3` float, `Mc2` float, `TFe2` float, `SAMPLE_TYPE` nvarchar(50), `ID` int

**Identifier vocabularies:**

- `CODE ID` — 14,418 distinct. e.g. `TF-38859`, `TF-38860`, `BLB-IWIP-16426`, `BLB-LIM-16477`, `BLB-LIM-16479`, `BLB-LIM-16480`, `BLB-LIM-16481`, `BLB-IWIP-16487`, `BLB-IWIP-16489`, `BLB-IWIP-16491`, `BLB-IWIP-16494`, `BLB-IWIP-16496`

**Sample rows** (first 14 of 25 columns):

| LAST_UPDATE | DATE | SHIFT | JOB QC | CODE ID | ID DOME | DATE ANALYSIS | DATE REPORT | CONTRACTOR | ID BLOCK | Ni Dry 1 | Fe2O3 Dry 1 | Ni Dry 2 | Fe2O3 Dry2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|  | 2025-09-29T00:00:00.000 | DS | WBN.TF-1119 | TF-38859 | AR/TF.G.2073 |  |  | RIM |  | 1.31 | 56.08 | 1.47 | 50.73 |
|  | 2025-09-29T00:00:00.000 | DS | WBN.TF-1119 | TF-38860 | AR/TF.G.2085 |  |  | RIM |  | 1.07 | 61.63 | 1.13 | 63.37 |
| 2026-01-28T14:00:16.410 | 2026-01-24T00:00:00.000 | NS | BLB-IWIP-3378 | BLB-IWIP-16426 | BLB.G.6284T | 1/24/2026 21:36:00 | 1/24/2026 5:00:00 | PT.RIM |  | 1.82 | 42.86 | 1.83 | 42.96 |
| 2026-01-28T14:00:16.410 | 2026-01-26T00:00:00.000 | NS | BLB-IWIP-3391 | BLB-LIM-16477 | E/BLB.G.3310 A | 1/26/2026 21:37:00 | 1/26/2026 5:00:00 | PT.RIM |  | 1.07 | 68.54 | 1.02 | 68.28 |
| 2026-01-28T14:00:16.410 | 2026-01-26T00:00:00.000 | NS | BLB-IWIP-3391 | BLB-LIM-16479 | E/BLB.G.3306 B1 | 1/26/2026 21:47:00 | 1/26/2026 5:00:00 | PT.RIM |  | 1.09 | 74.03 | 1.03 | 73.29 |

<a id="wbn-database-production-pit-prelim-auto"></a>

#### `PRODUCTION_PIT_PRELIM_auto`

**Rows:** 15,887  |  **Columns:** 19  |  **DATE:** 2025-11-17 00:00:00 → 2026-03-23 00:00:00

**Columns:** `CONTRACTOR` nvarchar(255), `DATE` datetime, `SHIFT` float, `ACTIVITY` nvarchar(255), `PIT` nvarchar(255), `SUBPIT` nvarchar(255), `BLOCK_TYPE` nvarchar(255), `BLOCK_STATUS` nvarchar(255), `BLOCK_ID` nvarchar(255), `PROD_ID` nvarchar(255), `MATERIAL` nvarchar(255), `MATERIAL_CLASS` nvarchar(255), `RIT` float, `TF` float, `WMT` float, `DESTINATION` nvarchar(255), `TOS_PILE` nvarchar(255), `BLAST_STATUS` nvarchar(255), `BLAST_ID` nvarchar(255)

**Identifier vocabularies:**

- `BLOCK_ID` — 7,982 distinct. e.g. `REHANDLING_LD_TF_001`, `N454_B138_S35`, `N454_B139_S36`, `N454_B138_S36`, `N454_B138_S37`, `N458_B141_S39`, `N458_B142_S39`, `N458_B143_S40`, `N458_B142_S40`, `N458_B143_S41`, `N458_B142_S41`, `N458_B143_S42`
- `PROD_ID` — 7,981 distinct. e.g. `REHANDLING_LD_TF_001`, `N454_B138_S35`, `N454_B139_S36`, `N454_B138_S36`, `N454_B138_S37`, `N458_B141_S39`, `N458_B142_S39`, `N458_B143_S40`, `N458_B142_S40`, `N458_B143_S41`, `N458_B142_S41`, `N458_B143_S42`

**Sample rows** (first 14 of 19 columns):

| CONTRACTOR | DATE | SHIFT | ACTIVITY | PIT | SUBPIT | BLOCK_TYPE | BLOCK_STATUS | BLOCK_ID | PROD_ID | MATERIAL | MATERIAL_CLASS | RIT | TF |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PRELIM | 2026-01-28T00:00:00.000 | 2.0 | MINING | TF | TF3 | BLOCK | CONTINUE | REHANDLING_LD_TF_001 | REHANDLING_LD_TF_001 | LIM |  | 50.0 | 32.5 |
| PRELIM | 2026-01-28T00:00:00.000 | 2.0 | MINING | TF | TF3 | BLOCK | CONTINUE | REHANDLING_LD_TF_001 | REHANDLING_LD_TF_001 | LIM |  | 50.0 | 32.5 |
| PRELIM | 2026-01-28T00:00:00.000 | 2.0 | MINING | TF | TF3 | BLOCK | CONTINUE | REHANDLING_LD_TF_001 | REHANDLING_LD_TF_001 | LIM |  | 59.0 | 32.5 |
| PRELIM | 2026-01-28T00:00:00.000 | 2.0 | MINING | TF | TF3 | BLOCK | CONTINUE | REHANDLING_LD_TF_001 | REHANDLING_LD_TF_001 | LIM |  | 163.0 | 32.5 |
| PRELIM | 2026-01-28T00:00:00.000 | 2.0 | MINING | TF | TF3 | BLOCK | CONTINUE | REHANDLING_LD_TF_001 | REHANDLING_LD_TF_001 | LIM |  | 193.0 | 32.5 |

<a id="wbn-database-stock-status"></a>

#### `STOCK_STATUS`

**Rows:** 14,720  |  **Columns:** 12  |  **DATE_OPEN:** 1900-01-01 → 2026-07-15

**Columns:** `CONTRACTOR` nvarchar(50), `ORIGIN_PIT` nvarchar(50), `STOCK_TYPE` nvarchar(50), `STOCK_AREA` nvarchar(255), `STOCK_ID` nvarchar(255), `MATERIAL` nvarchar(50), `DATE_OPEN` date, `DATE_COMPLETE` date, `DATE_TRANSFER` date, `DATE_FINISH` date, `REMARK` nvarchar(255), `PAD_ID` nvarchar(50)

**Identifier vocabularies:**

- `STOCK_ID` — 14,720 distinct. e.g. `A`, `AA`, `AA.01.2302`, `AA.01.2303`, `AA.02.2302`, `AA.02.2303`, `AA.02.2304`, `AA.10`, `AA.100`, `AA.101`, `AA.102`, `AA.103`

**Sample rows**:

| CONTRACTOR | ORIGIN_PIT | STOCK_TYPE | STOCK_AREA | STOCK_ID | MATERIAL | DATE_OPEN | DATE_COMPLETE | DATE_TRANSFER | DATE_FINISH | REMARK | PAD_ID |
|---|---|---|---|---|---|---|---|---|---|---|---|
| WBN |  | POS | OLD EOS | A | SAP | 2021-04-28T00:00:00.000 | 2021-04-28T00:00:00.000 |  | 2021-05-01T00:00:00.000 |  |  |
| WBN | KR | POS | POS 3 | AA | SAP | 2021-03-27T00:00:00.000 | 2021-03-27T00:00:00.000 |  | 2021-04-10T00:00:00.000 |  |  |
| WBN | KR | POS | EOS | AA.01.2302 | SAP | 2023-02-11T00:00:00.000 | 2023-03-01T00:00:00.000 | 2023-03-01T00:00:00.000 | 2023-03-04T00:00:00.000 |  |  |
| WBN | KR | POS | EOS | AA.01.2303 | SAP | 2023-02-26T00:00:00.000 | 2023-03-10T00:00:00.000 | 2023-03-10T00:00:00.000 | 2023-03-13T00:00:00.000 |  |  |
| WBN | KR | POS | EOS | AA.02.2302 | SAP | 2023-02-18T00:00:00.000 | 2023-03-06T00:00:00.000 | 2023-03-06T00:00:00.000 | 2023-03-09T00:00:00.000 |  |  |

<a id="wbn-database-blasting-drilling"></a>

#### `blasting_drilling`

**Rows:** 14,648  |  **Columns:** 22  |  **Date:** 2024-11-25 00:00:00 → 2026-03-19 00:00:00

**Columns:** `ID` int, `drilling_machine` nvarchar(255), `year` nvarchar(255), `month` nvarchar(255), `week` nvarchar(255), `Date` datetime, `Shift` nvarchar(255), `start` datetime, `end` datetime, `duration_h` int, `downtime_rest_h` int, `Kegiatan` nvarchar(255), `Location` nvarchar(255), `mining_contractor` nvarchar(255), `drilling_contractor` nvarchar(255), `blasting_contractor` nvarchar(255), `pit` nvarchar(255), `subpit` nvarchar(255), `block_id` nvarchar(255), `number_of_holes` float, `depth_m` float, `comment` nvarchar(255)

**Identifier vocabularies:**

- `drilling_machine` — 301 distinct. e.g. `D-33 K-38`, `D-32 K-37`, `D-30 K-35`, `D-31 K-36`, `D-04 K-04`, `D-25 K-26`, `D-27 K-23`, `K-04`, `D-26 K-25`, `K-25`, `K-26`, `D-32 K-36`
- `block_id` — 4 distinct. e.g. `16`, `B 5 JALAN 10 RIM`, `BLB 5 JALAN 10 RIM`, `CBB 4 Jalan 3 RIM`

**Sample rows** (first 14 of 22 columns):

| ID | drilling_machine | year | month | week | Date | Shift | start | end | duration_h | downtime_rest_h | Kegiatan | Location | mining_contractor |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6941 | D-33 K-38 | 2024 | Nov | 48 | 2024-11-25T00:00:00.000 | DAY | 1899-12-30T06:30:00.000 | 1899-12-30T17:00:00.000 | 0 |  | Drilling | PT PPP KR |  |
| 6942 | D-32 K-37 | 2024 | Nov | 48 | 2024-11-25T00:00:00.000 | DAY | 1899-12-30T06:30:00.000 | 1899-12-30T17:00:00.000 | 0 |  | Drilling | PT PPP KR |  |
| 6943 | D-30 K-35 | 2024 | Nov | 48 | 2024-11-25T00:00:00.000 | DAY | 1899-12-30T06:30:00.000 | 1899-12-30T17:00:00.000 | 0 |  | Drilling | PT PPP KR |  |
| 6944 | D-31 K-36 | 2024 | Nov | 48 | 2024-11-25T00:00:00.000 | DAY | 1899-12-30T06:30:00.000 | 1899-12-30T17:00:00.000 | 0 |  | Drilling | PT PPP KR |  |
| 6945 | D-04 K-04 | 2024 | Nov | 48 | 2024-11-25T00:00:00.000 | DAY | 1899-12-30T06:30:00.000 | 1899-12-30T17:00:00.000 | 0 |  | Drilling | PT PPP KR |  |

<a id="wbn-database-wbn-database-st-log-on"></a>

#### `WBN_DATABASE_ST_LOG_ON`

**Rows:** 13,681  |  **Columns:** 3  |  **datetime:** 2026-06-18 08:07:35 → 2026-07-30 12:08:23

**Columns:** `datetime` datetime, `name` varchar(-1), `page` varchar(-1)

**Sample rows**:

| datetime | name | page |
|---|---|---|
| 2026-07-24T14:34:13.707 | ALL | production_pit-prod |
| 2026-07-24T14:34:17.817 | ALL | production_pit-prod |
| 2026-07-24T14:36:03.480 | ALL | production_haulage-table |
| 2026-07-24T14:36:06.953 | ALL | production_haulage-table |
| 2026-07-24T15:24:37.053 | WBN | production_pit-tos |

<a id="wbn-database-old-very-short-term"></a>

#### `OLD_VERY_SHORT_TERM`

**Rows:** 13,470  |  **Columns:** 16  |  **DATE:** 2024-10-05 → 2025-11-27

**Columns:** `ID` int, `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `DISPATCH_TABLE` nvarchar(50), `MATERIAL` nvarchar(50), `COMPANY` nvarchar(50), `ORIGIN` nvarchar(50), `BLOCK_ID` nvarchar(50), `TOS` nvarchar(50), `DESTINATION_POS_DOME` nvarchar(50), `DESTINATION_POS` nvarchar(50), `TRIPS` int, `WMT` float, `NB_DT` float, `STATUS` nvarchar(50)

**Identifier vocabularies:**

- `BLOCK_ID` — 1,913 distinct. e.g. `LD_KR_003`, `KR-CS.43`, `I.2323`, `I.2341`, `I.2356`, `I.2337`, `I.2374`, `I.2385`, `TF.B.504`, `TF.B.669`, `TF.B.673`, `TF.B.656`

**Sample rows** (first 14 of 16 columns):

| ID | DATE | SHIFT | CONTRACTOR | DISPATCH_TABLE | MATERIAL | COMPANY | ORIGIN | BLOCK_ID | TOS | DESTINATION_POS_DOME | DESTINATION_POS | TRIPS | WMT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 30 | 2024-10-05T00:00:00.000 | 1 | PPP | DISPATCH_ACTUAL | SAP | WBN | TF |  |  |  | POS 12 EXT | 101 | 4310.44 |
| 31 | 2024-10-05T00:00:00.000 | 1 | PPP | DISPATCH_ACTUAL | SAP | WBN | KR |  |  |  | FENI | 48 | 1146.16 |
| 32 | 2024-10-05T00:00:00.000 | 1 | PPP | DISPATCH_ACTUAL | LIM | WBN | KR |  |  |  | HUAFEI C.01 | 45 | 1357.71 |
| 33 | 2024-10-05T00:00:00.000 | 1 | PPP | DISPATCH_ACTUAL |  | WBN | TOTAL |  |  |  |  | 194 | 6814.31 |
| 34 | 2024-10-05T00:00:00.000 | 1 | PPP | TOS_FOLLOW | LIM | WBN | KR | LD_KR_003 | LD_KR | LD_KR_003 | HUAFEI C.01 | 45 | 1357.71 |

<a id="wbn-database-haulage-report"></a>

#### `HAULAGE_REPORT`

**Rows:** 13,459  |  **Columns:** 16  |  **DATE:** 2024-10-05 → 2025-11-26

**Columns:** `DATE` date, `SHIFT` int, `CONTRACTOR` nvarchar(50), `TABLE` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `COMPANY` nvarchar(50), `ORIGIN` nvarchar(50), `BLOCK_ID` nvarchar(50), `TOS` nvarchar(50), `DESTINATION_POS_DOME` nvarchar(50), `DESTINATION_POS` nvarchar(50), `TRIPS` int, `WMT` float, `NB_DT` float, `STATUS` nvarchar(50)

**Identifier vocabularies:**

- `BLOCK_ID` — 1,908 distinct. e.g. `TF.B.3850`, `TF.B.3836`, `TF.A.6046`, `TF.G.2296`, `TF.B.3852`, `TF.B.4023`, `TF.B.4010`, `TF.A.6290`, `TF.B.4033`, `TF.B.4053`, `TF.B.4179`, `TF.A.6381`

**Sample rows** (first 14 of 16 columns):

| DATE | SHIFT | CONTRACTOR | TABLE | ACTIVITY | MATERIAL | COMPANY | ORIGIN | BLOCK_ID | TOS | DESTINATION_POS_DOME | DESTINATION_POS | TRIPS | WMT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-10-22T00:00:00.000 | 1 | SMA | DISPATCH_ACTUAL |  | SAP | WBN | TF |  |  |  | POS 12 | 100 | 4319.18 |
| 2025-10-22T00:00:00.000 | 1 | SMA | DISPATCH_ACTUAL |  |  | WBN | TOTAL |  |  |  |  | 100 | 4319.18 |
| 2025-10-22T00:00:00.000 | 1 | SMA | TOS_FOLLOW |  | SAP | WBN | TF | TF.B.3850 | TF_SMA_02 | ACM.588 | POS 12 EXT | 48 | 2136.62 |
| 2025-10-22T00:00:00.000 | 1 | SMA | TOS_FOLLOW |  | SAP | WBN | TF | TF.B.3836 | TF_SMA_02 | ACM.588 | POS 12 EXT | 52 | 2182.56 |
| 2025-10-22T00:00:00.000 | 1 | SMA | TOS_FOLLOW |  |  | WBN | TOTAL |  |  |  |  | 100 | 4319.18 |

<a id="wbn-database-quarry-production"></a>

#### `QUARRY PRODUCTION`

**Rows:** 12,646  |  **Columns:** 14  |  **DATE:** 2024-10-01 → 2025-09-10

**Columns:** `ID` int, `CONTRACTOR` nvarchar(-1), `DATE` date, `SHIFT` int, `QUARRY` nvarchar(-1), `SUBQUARRY` nvarchar(-1), `AREA_ID` nvarchar(-1), `MATERIAL` nvarchar(-1), `RIT` int, `TF (BCM)` float, `DESTINATION` nvarchar(-1), `DESTINATION 2` nvarchar(-1), `PILE ID` nvarchar(-1), `TYPE_TRANSPORT` nvarchar(-1)

**Sample rows**:

| ID | CONTRACTOR | DATE | SHIFT | QUARRY | SUBQUARRY | AREA_ID | MATERIAL | RIT | TF (BCM) | DESTINATION | DESTINATION 2 | PILE ID | TYPE_TRANSPORT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1376 | PPP | 2024-10-01T00:00:00.000 | 1 | QUARRY LOYPOLOY KM16 |  |  | LAMINATING | 51 | 15.0 | POS 10 | PAD LGS KR 60 |  |  |
| 1377 | PPP | 2024-10-01T00:00:00.000 | 1 | QUARRY LOYPOLOY KM16 |  |  | BOULDER | 50 | 15.0 | CRUSHER LOYPOLOY KM 16 | LINE 3 |  |  |
| 1378 | PPP | 2024-10-01T00:00:00.000 | 1 | QUARRY LOYPOLOY KM16 |  |  | BOULDER | 48 | 15.0 | CRUSHER LOYPOLOY KM 16 | LINE 2 |  |  |
| 1379 | PPP | 2024-10-01T00:00:00.000 | 1 | QUARRY LOYPOLOY KM16 |  |  | BOULDER | 37 | 15.0 | CRUSHER LOYPOLOY KM 16 | STOCKPILE LANTAI 2 |  |  |
| 1380 | PPP | 2024-10-01T00:00:00.000 | 1 | QUARRY LOYPOLOY KM16 |  |  | BOULDER | 19 | 15.0 | CRUSHER KAORAHAI KM 38 | CRUSHER KM 38 |  |  |

<a id="wbn-database-prod-very-very-short-term"></a>

#### `PROD VERY VERY SHORT TERM`

**Rows:** 11,180  |  **Columns:** 29  |  **DATE:** 2024-10-01 → 2026-07-29

**Columns:** `ID` int, `DATE` date, `CONTRACTOR` nvarchar(50), `SHIFT` nvarchar(50), `PIT` nvarchar(50), `LOCATION` nvarchar(50), `TF` float, `EXCA` float, `ADT` float, `BMS` float, `SAP` float, `RSAP` float, `LIM` float, `WCO` float, `WST` float, `TS` float, `SPOIL ORE` float, `SPOIL WST` float, `TMM` float, `DOZER` float, `DT` float, `QUARRY` float, `LIM_REHAND` float, `WST_REHAND` float, `TS_REHAND` float, `BLDR_REHAND` float, `QUARRY _REHAND` float, `DEPARTMEN` nvarchar(50), `SAP_REHAND` float

**Sample rows** (first 14 of 29 columns):

| ID | DATE | CONTRACTOR | SHIFT | PIT | LOCATION | TF | EXCA | ADT | BMS | SAP | RSAP | LIM | WCO |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3801 | 2024-10-01T00:00:00.000 | HJS | DS | PIT CBB | CBB | 36.0 | 6.0 | 28.0 |  | 304.0 |  | 35.0 |  |
| 3802 | 2024-10-01T00:00:00.000 | HJS | NS | PIT CBB | CBB | 36.0 | 7.0 | 25.0 |  | 291.0 |  | 52.0 |  |
| 3803 | 2024-10-01T00:00:00.000 | MTM | DS | TF | TOFU | 31.0 | 3.0 | 6.0 |  | 29.0 |  | 87.0 |  |
| 3804 | 2024-10-01T00:00:00.000 | MTM | NS | TF | TOFU | 31.0 | 2.0 | 4.0 |  |  |  | 87.0 |  |
| 3805 | 2024-10-01T00:00:00.000 | PPP | DS | KR | KR | 30.0 | 6.0 | 19.0 |  | 243.0 |  |  |  |

<a id="wbn-database-rsf-survey"></a>

#### `RSF_SURVEY`

**Rows:** 9,103  |  **Columns:** 20  |  **DATE:** 2024-10-04 00:00:00 → 2025-06-20 00:00:00

**Columns:** `ID` int, `DATE` datetime, `YEAR` int, `MONTH` int, `WEEK` int, `LAYER` nvarchar(50), `LOCATION` nvarchar(50), `NAME` nvarchar(50), `ELEVATION` float, `RL_ELEVATION` float, `CROSSECTION` nvarchar(50), `ITEM` nvarchar(50), `MATERIAL_TYPE` nvarchar(50), `PROGRESS_VOLUME` float, `CUMMULATIVE` float, `X` float, `Y` float, `Z` float, `MAX_CAPACITY` float, `STATUS` nvarchar(50)

**Coordinate extent:** `X` 380343.742 → 380736.271; `Y` 66458.995 → 66739.302

**Sample rows** (first 14 of 20 columns):

| ID | DATE | YEAR | MONTH | WEEK | LAYER | LOCATION | NAME | ELEVATION | RL_ELEVATION | CROSSECTION | ITEM | MATERIAL_TYPE | PROGRESS_VOLUME |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 3057 | 2024-10-04T00:00:00.000 | 2024 | 10 | 40 | 3 | Cell | C1 | 75.0 |  |  | Disposal | Dry Stack |  |
| 3058 | 2024-10-04T00:00:00.000 | 2024 | 10 | 40 | 3 | Cell | C2 | 75.0 |  |  | Disposal | Dry Stack | 663.244 |
| 3059 | 2024-10-04T00:00:00.000 | 2024 | 10 | 40 | 3 | Cell | C3 | 75.0 |  |  | Disposal | Dry Stack |  |
| 3060 | 2024-10-04T00:00:00.000 | 2024 | 10 | 40 | 3 | Cell | C4 | 75.0 |  |  | Disposal | Dry Stack |  |
| 3061 | 2024-10-04T00:00:00.000 | 2024 | 10 | 40 | 3 | Cell | C5 | 75.0 |  |  | Disposal | Dry Stack |  |

<a id="wbn-database-autoqc-cf-bm-tos"></a>

#### `autoQC_CF_BM_TOS`

**Rows:** 8,249  |  **Columns:** 20  |  **LAST_UPDATE:** 2026-07-06 08:46:58 → 2026-07-30 10:30:56

**Columns:** `LAST_UPDATE` datetime, `DATE` date, `MATERIAL` nvarchar(50), `ORIGIN_PIT` nvarchar(50), `CONTRACTOR_PILE` nvarchar(50), `DIL_BM_MC` float, `DIL_BM_Ni` float, `DIL_BM_Fe` float, `DIL_BM_SiO2` float, `DIL_BM_MgO` float, `DIL_BM_Co` float, `DIL_BM_Cr2O3` float, `DIL_TOS_MC` float, `DIL_TOS_Ni` float, `DIL_TOS_Fe` float, `DIL_TOS_SiO2` float, `DIL_TOS_MgO` float, `DIL_TOS_Co` float, `DIL_TOS_Cr2O3` float, `DIL_PROP_BM_Ni` float

**Sample rows** (first 14 of 20 columns):

| LAST_UPDATE | DATE | MATERIAL | ORIGIN_PIT | CONTRACTOR_PILE | DIL_BM_MC | DIL_BM_Ni | DIL_BM_Fe | DIL_BM_SiO2 | DIL_BM_MgO | DIL_BM_Co | DIL_BM_Cr2O3 | DIL_TOS_MC | DIL_TOS_Ni |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-07-06T08:46:58.357 | 2024-03-29T00:00:00.000 | SAP | CBB | RIM | 1.0306948167 | 0.9472451623 | 0.8159249271 | 1.0302367428 | 1.4239958801 | 0.8066875203 | 0.7268254051 | 1.0143754946 | 0.8950076186 |
| 2026-07-06T08:46:58.357 | 2024-03-30T00:00:00.000 | SAP | CBB | RIM | 1.0306948167 | 0.9472451623 | 0.8159249271 | 1.0302367428 | 1.4239958801 | 0.8066875203 | 0.7268254051 | 1.0143754946 | 0.8950076186 |
| 2026-07-06T08:46:58.357 | 2024-03-31T00:00:00.000 | SAP | CBB | RIM | 1.0306948167 | 0.9472451623 | 0.8159249271 | 1.0302367428 | 1.4239958801 | 0.8066875203 | 0.7268254051 | 1.0143754946 | 0.8950076186 |
| 2026-07-06T08:46:58.357 | 2024-04-01T00:00:00.000 | SAP | CBB | RIM | 1.0306948167 | 0.9472451623 | 0.8159249271 | 1.0302367428 | 1.4239958801 | 0.8066875203 | 0.7268254051 | 1.0143754946 | 0.8950076186 |
| 2026-07-06T08:46:58.357 | 2024-04-02T00:00:00.000 | SAP | CBB | RIM | 1.0306948167 | 0.9472451623 | 0.8159249271 | 1.0302367428 | 1.4239958801 | 0.8066875203 | 0.7268254051 | 1.0143754946 | 0.8950076186 |

<a id="wbn-database-reclassification"></a>

#### `RECLASSIFICATION`

**Rows:** 7,789  |  **Columns:** 5

**Columns:** `RECL` nvarchar(10), `DOME` nvarchar(255), `TYPE` nvarchar(255), `SURVEY MONTH` datetime, `OLD_RECL` nvarchar(10)

**Sample rows**:

| RECL | DOME | TYPE | SURVEY MONTH | OLD_RECL |
|---|---|---|---|---|
| SAP* | A | POS | 2022-09-01T00:00:00.000 | HGS* |
| WCO* | AA | POS | 2021-03-01T00:00:00.000 | WCO* |
| SAP* | AA.01.2302 | POS | 2023-02-01T00:00:00.000 | HGS* |
| SAP* | AA.01.2303 | POS | 2023-03-01T00:00:00.000 | VHGS* |
| SAP* | AA.02.2302 | POS | 2023-02-01T00:00:00.000 | HGS* |

<a id="wbn-database-equipments"></a>

#### `EQUIPMENTS`

**Rows:** 7,221  |  **Columns:** 15

> WBN equipment register.

**Columns:** `ID` nvarchar(50), `CONTRACTOR` nvarchar(50), `ID_EQ` nvarchar(50), `OWNER` nvarchar(50), `SERIAL_NO` nvarchar(255), `TYPE` nvarchar(50), `DIGIT` int, `MANUFACTURER` nvarchar(50), `MODEL` nvarchar(50), `CAPACITY` int, `NB_TYRES` int, `BUILD_YEAR` int, `DIVISION` nvarchar(50), `NEW_ID_EQ` nvarchar(50), `HEAVY_LIGHT` varchar(5)

**Identifier vocabularies:**

- `ID` — 7,221 distinct. e.g. `ATC-AC-301`, `ATC-AC-302`, `ATC-AC-303`, `ATC-AC-304`, `ATC-AC-305`, `ATC-AC-306`, `ATC-ACO-301`, `ATC-ACO-302`, `ATC-ACO-303`, `ATC-ACO-304`, `ATC-ACO-305`, `ATC-ACO-307`

**Sample rows** (first 14 of 15 columns):

| ID | CONTRACTOR | ID_EQ | OWNER | SERIAL_NO | TYPE | DIGIT | MANUFACTURER | MODEL | CAPACITY | NB_TYRES | BUILD_YEAR | DIVISION | NEW_ID_EQ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ATC-AC-301 | ATC | ATC-P3-GKT-01 |  |  | Air Conditioner |  | GREE | GVC-48STS(S)ECO/I |  |  | 2023 |  |  |
| ATC-AC-302 | ATC | ATC-P3-GKT-02 |  |  | Air Conditioner |  | GREE | GVC-48STS(S)ECO/I |  |  | 2023 |  |  |
| ATC-AC-303 | ATC | ATC-P3-GKT-03 |  |  | Air Conditioner |  | GREE | GVC-48STS(S)ECO/I |  |  | 2023 |  |  |
| ATC-AC-304 | ATC | ATC-P3-GKT-04 |  |  | Air Conditioner |  | GREE | ??:GWC-12MOO5 1.5P |  |  | 2023 |  |  |
| ATC-AC-305 | ATC | ATC-P3-GKT-05 |  |  | Air Conditioner |  | GREE | ??:GWC-12MOO5 1.5P |  |  | 2023 |  |  |

<a id="wbn-database-feni-requests"></a>

#### `FENI_REQUESTS`

**Rows:** 7,196  |  **Columns:** 7  |  **DATE_REQUESTS_BY_IWIP:** 2025-07-01 00:00:00 → 2026-05-29 00:00:00

**Columns:** `ID` int, `STOCK_ID` nvarchar(255), `ORIGIN_AREA` nvarchar(255), `DESTINATION_ID` nvarchar(255), `SHIFT_REQUESTS` nvarchar(255), `DATE_REQUESTS_BY_IWIP` datetime, `WMT` float

**Identifier vocabularies:**

- `STOCK_ID` — 4,806 distinct. e.g. `TF.G.1344`, `TF.G.1334`, `TF.G.1335`, `BLB.G.4559`, `TF.A.4735`, `TF.B.3221`, `TF.A.4740`, `TF.B.3196`, `TF.A.4699`, `TF.B.2929`, `TF.B.3225`, `TF.A.4755`
- `DESTINATION_ID` — 1,382 distinct. e.g. `TF-M.06`, `TF-H.06`, `TF-Q.15`, `BLB-W.65`, `TF-U1.117`, `TF-M.07`, `TF-L2.06`, `TF-O2.03`, `TF-U1.118`, `TF-U1.119`, `TF-W.146`, `TF-C.11`

**Sample rows**:

| ID | STOCK_ID | ORIGIN_AREA | DESTINATION_ID | SHIFT_REQUESTS | DATE_REQUESTS_BY_IWIP | WMT |
|---|---|---|---|---|---|---|
| 43 | TF.G.1344 | TOS_TF_MTM_01 | TF-M.06 | 1 | 2025-08-01T00:00:00.000 |  |
| 44 | TF.G.1334 | TOS_TF_08 | TF-H.06 | 1 | 2025-08-01T00:00:00.000 |  |
| 45 | TF.G.1335 | TOS_TF_MTM_01 | TF-Q.15 | 1 | 2025-08-01T00:00:00.000 |  |
| 46 | BLB.G.4559 | TOS_BLB_03 | BLB-W.65 | 1 | 2025-08-01T00:00:00.000 |  |
| 47 | TF.A.4735 | TOS_TF_STM_01 | TF-U1.117 | 1 | 2025-08-01T00:00:00.000 |  |

<a id="wbn-database-qs-lims-rim-ck"></a>

#### `QS_LIMS_RIM_CK`

**Rows:** 6,131  |  **Columns:** 19  |  **FETCH_DATE:** 2026-06-10 11:32:21 → 2026-07-30 11:30:05

**Columns:** `FETCH_DATE` datetime, `DATE` datetime, `JOB_QC` nvarchar(255), `SAMPLE_ID` nvarchar(50), `Ni` float, `Co` float, `AL2O3` float, `CaO` float, `Cr2O3` float, `Fe2O3` float, `TFe` float, `MgO` float, `MnO` float, `P2O5` float, `SiO2` float, `SiO2/MgO` float, `C` float, `MC` float, `DATE_RECEIVED` nvarchar(255)

**Identifier vocabularies:**

- `SAMPLE_ID` — 6,131 distinct. e.g. `BLB-14891`, `BLB-14892`, `BLB-14893`, `BLB-14893GD`, `BLB-14894`, `BLB-14895`, `BLB-14896`, `BLB-14897`, `BLB-14898`, `BLB-14899`, `BLB-14900`, `BLB-14901`

**Sample rows** (first 14 of 19 columns):

| FETCH_DATE | DATE | JOB_QC | SAMPLE_ID | Ni | Co | AL2O3 | CaO | Cr2O3 | Fe2O3 | TFe | MgO | MnO | P2O5 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-06-10T11:32:21.677 | 2025-11-13T00:00:00.000 | IWIP-BLB-2921 | BLB-14891 | 1.664 | 0.07 | 2.34 | 0.16 | 1.67 | 32.4 | 22.68 | 18.78 | 0.57 | 0.001 |
| 2026-06-10T11:32:21.677 | 2025-11-13T00:00:00.000 | IWIP-BLB-2921 | BLB-14892 | 1.641 | 0.07 | 2.29 | 0.16 | 1.68 | 31.21 | 21.84 | 19.22 | 0.6 | 0.001 |
| 2026-06-10T11:32:21.677 | 2025-11-13T00:00:00.000 | IWIP-BLB-2921 | BLB-14893 | 1.745 | 0.093 | 2.48 | 0.12 | 1.68 | 34.59 | 24.2 | 19.52 | 0.75 | 0.001 |
| 2026-06-10T11:32:21.677 | 2025-11-13T00:00:00.000 | IWIP-BLB-2921 | BLB-14893GD | 1.748 | 0.094 | 2.45 | 0.12 | 1.65 | 34.62 | 24.22 | 19.61 | 0.76 | 0.001 |
| 2026-06-10T11:32:21.677 | 2025-11-13T00:00:00.000 | IWIP-BLB-2922 | BLB-14894 | 1.269 | 0.198 | 6.4 | 0.08 | 3.1 | 63.29 | 44.29 | 2.75 | 1.42 | 0.005 |

<a id="wbn-database-daronne-htemp"></a>

#### `DARONNE_Htemp`

**Rows:** 5,812  |  **Columns:** 19  |  **DATE:** 2026-05-01 00:00:00 → 2026-06-30 00:00:00

**Columns:** `ID` int, `DATE` datetime, `SHIFT` int, `CONTRACTOR` nvarchar(50), `ACTIVITY` nvarchar(50), `MATERIAL` nvarchar(50), `TRUCK_ID` nvarchar(50), `TIME_LOADED` time, `TIME_EMPTY` time, `RIT` int, `ORIGIN_AREA` nvarchar(50), `ORIGIN_ID` nvarchar(50), `DESTINATION_AREA` nvarchar(50), `DESTINATION_ID` nvarchar(50), `KG_LOADED` float, `KG_EMPTY` float, `KG_NET` float, `WMT` float, `CUM_WMT` float

**Identifier vocabularies:**

- `TRUCK_ID` — 406 distinct. e.g. `N049`, `N038`, `R307`, `R316`, `R690`, `R696`, `N062`, `R711`, `R707`, `R327`, `R319`, `R568`
- `ORIGIN_ID` — 136 distinct. e.g. `BLB.G.6939`, `BLB.G.6951`, `TF.B.5884`, `KRENE.I.3189`, `KRENE.I.3200`, `KRENE.I.3194`, `KRENE.I.3182`, `KRENE.I.3213`, `KRENE.I.3197`, `KRENE.I.3199`, `KRENE.I.3198`, `KRENE.I.3206`
- `DESTINATION_ID` — 47 distinct. e.g. `BLB-A.241`, `BLB-A.242`, `ADM.779`, `ACM.673`, `ACM.674`, `ADM.780`, `KRENE-A.70`, `ABM.470`, `KRENE-A.71`, `AC.426`, `ACM.675`, `BLB-A.243`

**Sample rows** (first 14 of 19 columns):

| ID | DATE | SHIFT | CONTRACTOR | ACTIVITY | MATERIAL | TRUCK_ID | TIME_LOADED | TIME_EMPTY | RIT | ORIGIN_AREA | ORIGIN_ID | DESTINATION_AREA | DESTINATION_ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 11912321 | 2026-05-01T00:00:00.000 | 1 | RIM | DIRECT | SAP | N049 | 10:41:08 | 11:57:08 | 1 | TOS_BLB_11 | BLB.G.6939 | FENI A | BLB-A.241 |
| 11912324 | 2026-05-01T00:00:00.000 | 1 | RIM | DIRECT | SAP | N038 | 11:00:11 | 12:04:20 | 1 | TOS_BLB_11 | BLB.G.6939 | FENI A | BLB-A.241 |
| 11912325 | 2026-05-01T00:00:00.000 | 1 | RIM | DIRECT | SAP | R307 | 11:08:04 | 12:25:40 | 1 | TOS_BLB_11 | BLB.G.6939 | FENI A | BLB-A.241 |
| 11912346 | 2026-05-01T00:00:00.000 | 1 | RIM | DIRECT | SAP | R316 | 14:21:53 | 15:38:43 | 1 | TOS_BLB_11 | BLB.G.6939 | FENI A | BLB-A.241 |
| 11912355 | 2026-05-01T00:00:00.000 | 1 | RIM | DIRECT | SAP | R690 | 15:56:44 | 17:01:17 | 1 | TOS_BLB_11 | BLB.G.6939 | FENI A | BLB-A.241 |

<a id="wbn-database-equipments-old"></a>

#### `EQUIPMENTS_OLD`

**Rows:** 5,658  |  **Columns:** 14

**Columns:** `ID` nvarchar(50), `CONTRACTOR` nvarchar(50), `ID_EQ` nvarchar(50), `OWNER` nvarchar(50), `TYPE` nvarchar(50), `DIGIT` int, `MANUFACTURER` nvarchar(50), `MODEL` nvarchar(50), `CAPACITY` int, `NB_TYRES` int, `BUILD_YEAR` int, `DIVISION` nvarchar(50), `NEW_ID_EQ` nvarchar(50), `HEAVY_LIGHT` varchar(5)

**Identifier vocabularies:**

- `ID` — 5,658 distinct. e.g. `CKB-MTM-C-481`, `CKB-MTM-C-482`, `CKB-MTM-C-483`, `CKB-MTM-C-484`, `CKB-MTM-C-485`, `CKB-MTM-C-486`, `CKB-MTM-C-487`, `CKB-MTM-C-488`, `CKB-MTM-C-489`, `CKB-MTM-C-490`, `CKB-MTM-C-501`, `CKB-MTM-C-502`

**Sample rows**:

| ID | CONTRACTOR | ID_EQ | OWNER | TYPE | DIGIT | MANUFACTURER | MODEL | CAPACITY | NB_TYRES | BUILD_YEAR | DIVISION | NEW_ID_EQ | HEAVY_LIGHT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CKB-MTM-C-481 | CKB | MTM-C-481 | WBN | DT | 481 | SHACMAN | X3000 | 40 | 12 |  | HAULING |  | HEAVY |
| CKB-MTM-C-482 | CKB | MTM-C-482 | WBN | DT | 482 | SHACMAN | X3000 | 40 | 12 |  | HAULING |  | HEAVY |
| CKB-MTM-C-483 | CKB | MTM-C-483 | WBN | DT | 483 | SHACMAN | X3000 | 40 | 12 |  | HAULING |  | HEAVY |
| CKB-MTM-C-484 | CKB | MTM-C-484 | WBN | DT | 484 | SHACMAN | X3000 | 40 | 12 |  | HAULING |  | HEAVY |
| CKB-MTM-C-485 | CKB | MTM-C-485 | WBN | DT | 485 | SHACMAN | X3000 | 40 | 12 |  | HAULING |  | HEAVY |

<a id="wbn-database-wmt-for-3rd-party"></a>

#### `WMT_FOR_3RD_PARTY`

**Rows:** 5,529  |  **Columns:** 12  |  **DATE_VERIFICATION:** 2023-12-13 00:00:00 → 2026-07-20 00:00:00

**Columns:** `ID` int, `DATE_VERIFICATION` datetime, `STOCK_TYPE` nvarchar(50), `DOME` nvarchar(50), `CONTRACTOR` nvarchar(50), `WMT ORIGINAL` float, `RATE APPLIED` float, `WMT TOTAL` float, `CLAIM` datetime, `ACTIVITY` nvarchar(50), `DESTINATION` nvarchar(50), `REMARK` nvarchar(50)

**Sample rows**:

| ID | DATE_VERIFICATION | STOCK_TYPE | DOME | CONTRACTOR | WMT ORIGINAL | RATE APPLIED | WMT TOTAL | CLAIM | ACTIVITY | DESTINATION | REMARK |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 13789 | 2023-12-13T00:00:00.000 | POS | AA.393.A | AWK | 20939.859 |  |  |  | HAULAGE |  | Yes |
| 13790 | 2023-12-13T00:00:00.000 | POS | AA.398 | AWK | 36808.2739999999 |  |  |  | HAULAGE |  | Yes |
| 13791 | 2023-12-13T00:00:00.000 | POS | AA.399 | AWK | 89565.8889999999 |  |  |  | HAULAGE |  | Yes |
| 13792 | 2023-12-13T00:00:00.000 | POS | AA.401 | AWK | 38696.97 |  |  |  | HAULAGE |  | Yes |
| 13793 | 2023-12-13T00:00:00.000 | POS | AA.402 | AWK | 50260.89 |  |  |  | HAULAGE |  | Yes |

<a id="wbn-database-batch"></a>

#### `BATCH`

**Rows:** 4,931  |  **Columns:** 3

**Columns:** `ID` int, `BATCH ID` nvarchar(255), `SAMPLE ID` nvarchar(255)

**Sample rows**:

| ID | BATCH ID | SAMPLE ID |
|---|---|---|
| 1 | AA.23 | A.1287 |
| 2 | AA.23 | A.1288 |
| 3 | AA.23 | A.1289 |
| 4 | BB.14 | B.735 |
| 5 | BB.14 | B.736 |

<a id="wbn-database-drafts"></a>

#### `DRAFTS`

**Rows:** 4,848  |  **Columns:** 30  |  **DATE:** 2023-10-03 00:00:00 → 2026-07-07 00:00:00

**Columns:** `DATE` datetime, `JOB_ID` nvarchar(255), `DOME` nvarchar(255), `MC` float, `Ni` float, `Co` float, `MgO` float, `CaO` float, `Fe` float, `P` float, `S` float, `SiO2` float, `Al2O3` float, `Cr2O3` float, `Fe2O3` float, `K2O` float, `MnO` float, `Na2O` float, `P2O5` float, `TiO2` float, `LOI` float, `WMT` float, `CONTRACTOR` nvarchar(255), `NB_SUBLOT` float, `TRUCKS` float, `VERIFICATION` nvarchar(50), `VERIFICATION_DATE` datetime, `DESTINATION` nvarchar(50), `PROCESS_TYPE` nvarchar(50), `ORIGIN` nvarchar(50)

**Identifier vocabularies:**

- `JOB_ID` — 3,533 distinct. e.g. `SO-54539`, `SO-55415`, `N1525021504`, `N1525021549`, `N1525031922`, `N1525031982`, `N1525031984`, `N1525032079`, `N1525032132`, `N1525032325`, `N1525042713`, `N1525042741`

**Sample rows** (first 14 of 30 columns):

| DATE | JOB_ID | DOME | MC | Ni | Co | MgO | CaO | Fe | P | S | SiO2 | Al2O3 | Cr2O3 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-05-19T00:00:00.000 |  | ABM.259.0125 | 34.1631024248 | 1.2495778242 | 0.0574241781 | 23.905360541 | 0.214778232 | 16.6517668923 | 0.0 | 0.0918875969 | 34.9969350315 | 2.1542214868 | 1.39265152 |
| 2025-05-19T00:00:00.000 |  | ABM.281.0225 | 34.67 | 1.18865276 | 0.0582971706 | 23.99236008 | 0.4663624515 | 17.35453735 | 0.0 | 0.0706 | 33.85857077 | 2.9280471951 | 2.2270461481 |
| 2025-05-19T00:00:00.000 |  | ACM.321.0125 | 32.3343403827 | 1.32856536 | 0.0692914459 | 22.359863165 | 0.1677215754 | 19.65242211 | 0.0006331878 | 0.09755 | 32.49590907 | 2.5790987994 | 1.6064698147 |
| 2025-05-19T00:00:00.000 |  | ACM.374.0225 | 34.1657207719 | 1.30934304 | 0.0641918479 | 20.87405709 | 0.2037062291 | 18.60496787 | 0.0 | 0.06965 | 35.87399526 | 2.8227503095 | 1.8349007448 |
| 2025-05-19T00:00:00.000 |  | ADM.263.0225 | 35.6450578281 | 1.3021092 | 0.0931582737 | 18.9848009 | 0.0970505535 | 23.10947011 | 0.0 | 0.18105 | 30.20924552 | 2.7824230339 | 2.666137724 |

<a id="wbn-database-tos-survey"></a>

#### `TOS_SURVEY`

**Rows:** 4,804  |  **Columns:** 18  |  **DATE:** 2026-03-28 00:00:00 → 2026-07-10 00:00:00

**Columns:** `SURVEY_TYPE` nvarchar(255), `SURVEY_WEEK` float, `DATE` datetime, `PILE_ID` nvarchar(255), `LCM` float, `BCM` float, `WMT` float, `TC` float, `CATEGORY` nvarchar(255), `LOCATION` nvarchar(255), `MATERIAL` nvarchar(255), `2NDHAUL` datetime, `SHIFT` nvarchar(255), `Ni` float, `SUBPIT` nvarchar(255), `PIT` nvarchar(255), `ID` bigint, `REMARK` nvarchar(50)

**Identifier vocabularies:**

- `PILE_ID` — 1,110 distinct. e.g. `KRENE.I.2840`, `KRENE.I.2839`, `KRENE.I.2835`, `KRENE.I.2804`, `KRENE.I.2843`, `KRENE.I.2850`, `KRENE.I.2818`, `KRENE.I.2821`, `KRENE.I.2838`, `KRENE.I.2822`, `KRENE.I.2832`, `KRENE.I.2823`

**Sample rows** (first 14 of 18 columns):

| SURVEY_TYPE | SURVEY_WEEK | DATE | PILE_ID | LCM | BCM | WMT | TC | CATEGORY | LOCATION | MATERIAL | 2NDHAUL | SHIFT | Ni |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MONTHLY | 13.0 | 2026-03-28T00:00:00.000 | KRENE.I.2840 | 1654.585 | 1390.4075630252 | 2888.2389136055 | 2450.0 | AAM | TOS_KRENE_06 | NON-GRIZZLY |  |  | 1.5870522678 |
| MONTHLY | 13.0 | 2026-03-28T00:00:00.000 | KRENE.I.2839 | 1601.295 | 1345.6260504202 | 2795.2160397695 | 2100.0 | AAM | TOS_KRENE_06 | NON-GRIZZLY |  |  | 1.6533969221 |
| MONTHLY | 13.0 | 2026-03-28T00:00:00.000 | KRENE.I.2835 | 1731.849 | 1455.3352941176 | 3023.1107342861 | 2310.0 | AAM | TOS_KRENE_06 | NON-GRIZZLY |  |  | 1.6138258421 |
| MONTHLY | 13.0 | 2026-03-28T00:00:00.000 | KRENE.I.2804 | 475.889 | 399.9067226891 | 830.7104974098 | 875.0 | ABM | TOS_KRENE_05 | NON-GRIZZLY |  |  | 1.5872960006 |
| MONTHLY | 13.0 | 2026-03-28T00:00:00.000 | KRENE.I.2843 | 1411.355 | 1186.012605042 | 2463.6573109944 | 1785.0 | ABM | TOS_KRENE_06 | NON-GRIZZLY |  |  | 1.4961015455 |

<a id="wbn-database-s123-stock-shape"></a>

#### `S123_STOCK_SHAPE`

**Rows:** 4,785  |  **Columns:** 11  |  **UPDATE_DATE:** 2026-07-30 09:45:53 → 2026-07-30 09:45:53

**Columns:** `UPDATE_DATE` datetime, `OBJECTID` int, `FID` int, `name` nvarchar(255), `CreationDa` datetime, `Creator` nvarchar(255), `EditDate` datetime, `geom` geography(-1), `new_dome_i` nvarchar(255), `old_dome_i` nvarchar(255), `menggantik` nvarchar(255)

*Sample unavailable: could not serialise*

<a id="wbn-database-stock-status-haulage-ggsheet"></a>

#### `STOCK_STATUS_HAULAGE_GGSHEET`

**Rows:** 4,750  |  **Columns:** 17  |  **UPDATE_DATETIME:** 2026-07-18 15:04:49 → 2026-07-18 15:04:49

**Columns:** `No` float, `dome` varchar(-1), `Location` varchar(-1), `Open Date` varchar(-1), `Close Date` varchar(-1), `Material Type` varchar(-1), `Status Haulage` varchar(-1), `Contractor` varchar(-1), `Map` varchar(-1), `OLD DOME` varchar(-1), `REMARK` varchar(-1), `Unnamed: 12` varchar(-1), `UPDATE_DATETIME` datetime, `OPEN_DATE` datetime, `CLOSE_DATE` datetime, `numbers` varchar(-1), `DOME_CLEANED` varchar(-1)

**Sample rows** (first 14 of 17 columns):

| No | dome | Location | Open Date | Close Date | Material Type | Status Haulage | Contractor | Map | OLD DOME | REMARK | Unnamed: 12 | UPDATE_DATETIME | OPEN_DATE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1.0 | LGS.SWG6 | GOMDI |  | 12/9/2022 | Non Grizzly | Close |  |  |  |  |  | 2026-07-18T15:04:49.303 |  |
| 2.0 | LGS.SW10 | CLIFF DUMP |  | 12/9/2022 | Non Grizzly | Close |  |  |  |  |  | 2026-07-18T15:04:49.303 |  |
| 3.0 | LGS.KR8 | GOMDI |  |  | Non Grizzly | Close |  |  |  |  |  | 2026-07-18T15:04:49.303 |  |
| 4.0 | LGS.KR15 | POS 10 |  |  | Non Grizzly | Close |  |  |  |  |  | 2026-07-18T15:04:49.303 |  |
| 5.0 | LGS.CUU2 | GOMDI |  | 15/11/2022 | Non Grizzly | Close |  |  |  |  |  | 2026-07-18T15:04:49.303 |  |

<a id="wbn-database-stock-requests"></a>

#### `STOCK_REQUESTS`

**Rows:** 4,735  |  **Columns:** 9  |  **DATE_SHARE:** 2025-06-20 00:00:00 → 2025-08-03 00:00:00

**Columns:** `ID` int, `DATE_SHARE` datetime, `ORIGIN_ID` nvarchar(55), `WMT` float, `DESTINATION_ID` nvarchar(55), `DESTINATION_AREA` nvarchar(55), `SHIFT_REQUESTS` float, `DATE_REQUESTS_BY_IWIP` datetime, `REQUESTED_BY_IWIP` nvarchar(55)

**Identifier vocabularies:**

- `ORIGIN_ID` — 1,891 distinct. e.g. `BLB.D.842`, `TF.G.931`, `KR.I.2033`, `BLB.D.848`, `BLB.D.850`, `BLB.G.3806`, `BLB.G.3821`, `TF.A.3921`, `TF.A.3919`, `TF.A.3918`, `TF.B.2931`, `TF.B.2930`
- `DESTINATION_ID` — 190 distinct. e.g. `TF-C.04
`, `KR-Q.10`, `TF-W.113`, `TF-W.112`, `TF-E.02`, `TF-R.07`, `TF-U1.88`, `TF-R.07
`, `TF-W.113
`, `TF-O1.06
`, `TF-Q.13
`, `TF-L1.20
`

**Sample rows**:

| ID | DATE_SHARE | ORIGIN_ID | WMT | DESTINATION_ID | DESTINATION_AREA | SHIFT_REQUESTS | DATE_REQUESTS_BY_IWIP | REQUESTED_BY_IWIP |
|---|---|---|---|---|---|---|---|---|
| 22535 | 2025-06-20T00:00:00.000 | BLB.D.842 | 1578.0 |  |  |  |  | NO |
| 22536 | 2025-06-21T00:00:00.000 | TF.G.931 | 600.0 | TF-C.04  | FENI C |  | 2025-06-23T00:00:00.000 | YES |
| 22537 | 2025-06-21T00:00:00.000 | KR.I.2033 | 510.0 | KR-Q.10 | FENI Q |  | 2025-06-22T00:00:00.000 | YES |
| 22538 | 2025-06-21T00:00:00.000 | BLB.D.848 | 736.0 |  |  |  |  | NO |
| 22539 | 2025-06-21T00:00:00.000 | BLB.D.850 | 1750.0 |  |  |  |  | NO |

<a id="wbn-database-3rd-party-activities-reclaim"></a>

#### `3RD_PARTY_ACTIVITIES_RECLAIM`

**Rows:** 4,162  |  **Columns:** 16  |  **DATE:** 2024-12-22 00:00:00 → 2026-07-29 00:00:00

**Columns:** `ID` int, `DATE` datetime, `SHIFT` nvarchar(50), `SAMPLED_INC` int, `SAMPLE_TO_PREPARATION` int, `PREPARED_WET_SAMPLE` int, `LOT_TO_OVEN` int, `PULP_PREPARATION` int, `ANALYSIS` int, `MP_SAMPLING` int, `MP_TRANSPORT` int, `MP_WET_PREPARATION` int, `MP_DRY_PREP` int, `MP_ANALYSIS` int, `CONTRACTOR` nvarchar(50), `REMARK` nvarchar(50)

**Sample rows** (first 14 of 16 columns):

| ID | DATE | SHIFT | SAMPLED_INC | SAMPLE_TO_PREPARATION | PREPARED_WET_SAMPLE | LOT_TO_OVEN | PULP_PREPARATION | ANALYSIS | MP_SAMPLING | MP_TRANSPORT | MP_WET_PREPARATION | MP_DRY_PREP | MP_ANALYSIS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2024-12-22T00:00:00.000 | Day | 71 | 204 |  |  |  |  | 29 | 4 |  |  |  |
| 2 | 2024-12-22T00:00:00.000 | Night | 830 | 998 |  |  |  |  | 39 | 4 |  |  |  |
| 3 | 2024-12-23T00:00:00.000 | Day | 431 | 245 |  |  |  |  | 39 | 4 |  |  |  |
| 4 | 2024-12-23T00:00:00.000 | Night | 424 | 206 | 300.0 |  |  |  | 38 | 4 |  |  |  |
| 5 | 2024-12-24T00:00:00.000 | Day | 516 | 393 | 460.0 |  |  |  | 26 | 4 | 17.0 |  |  |

<a id="wbn-database-request"></a>

#### `REQUEST`

**Rows:** 3,920  |  **Columns:** 6  |  **DATE:** 2021-01-01 00:00:00 → 2026-07-01 00:00:00

**Columns:** `DOME` nvarchar(255), `DATE` datetime, `REQUEST` nvarchar(255), `COMPANY` nvarchar(255), `SALES_%` float, `REMARK` nvarchar(255)

**Sample rows**:

| DOME | DATE | REQUEST | COMPANY | SALES_% | REMARK |
|---|---|---|---|---|---|
| A | 2021-06-27T00:00:00.000 | SOLD | LAN |  |  |
| AA.01.2302 | 2023-02-01T00:00:00.000 | SOLD | MKUI |  |  |
| AA.02.2302 | 2023-02-01T00:00:00.000 | SOLD | KRS |  |  |
| AA.02.2303 | 2023-03-01T00:00:00.000 | SOLD | LIPE |  |  |
| AA.100 | 2022-07-01T00:00:00.000 | SOLD | AMI |  |  |

<a id="wbn-database-ore-stock-sales"></a>

#### `ORE STOCK SALES`

**Rows:** 3,800  |  **Columns:** 21  |  **Date of Sales:** 2021-02-20 00:00:00 → 2025-06-20 00:00:00

**Columns:** `STOCK TYPE` nvarchar(255), `POS CODE` nvarchar(255), `Date of Sales` datetime, `Month Of Sales` datetime, `Buying Plant` nvarchar(255), `WMT` float, `Ni` float, `Fe` float, `Co` float, `Al2O3` float, `CaO` float, `Cr2O3` float, `Fe2O3` float, `MgO` float, `MnO` float, `P2O5` float, `SiO2` float, `SiO2/MgO` float, `MC` float, `Sales Status` nvarchar(255), `SALES TYPE` nvarchar(255)

**Identifier vocabularies:**

- `POS CODE` — 3,800 distinct. e.g. `A`, `AA.01.2302`, `AA.02.2302`, `AA.02.2303`, `AA.100`, `AA.101`, `AA.106`, `AA.107`, `AA.109`, `AA.110`, `AA.111`, `AA.112`

**Sample rows** (first 14 of 21 columns):

| STOCK TYPE | POS CODE | Date of Sales | Month Of Sales | Buying Plant | WMT | Ni | Fe | Co | Al2O3 | CaO | Cr2O3 | Fe2O3 | MgO |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| OLD LOGISTIC | A | 2021-06-27T00:00:00.000 | 2021-06-27T00:00:00.000 | LAN |  | 1.8690215665 | 20.4325901945 | 0.0798903913 | 1.1720567699 | 29.2311733826 | 17.3731473565 |  | 2.0897896899 |
| LOGISTIC | AA.01.2302 | 2023-02-25T00:00:00.000 | 2023-02-01T00:00:00.000 | MKUI |  | 2.4297347371 | 10.2938526065 | 0.038004969 | 0.0 | 0.0 | 0.0 | 0.0 | 23.5765083827 |
| LOGISTIC | AA.02.2302 | 2023-02-25T00:00:00.000 | 2023-02-01T00:00:00.000 | KRS |  | 2.3441905379 | 11.2568025189 | 0.0395312338 | 0.0 | 0.0 | 0.0 | 0.0 | 25.1410642754 |
| LOGISTIC | AA.02.2303 | 2023-03-29T00:00:00.000 | 2023-03-01T00:00:00.000 | LIPE |  | 1.8371582305 | 9.1734553361 | 0.0230249448 | 0.0 | 0.0 | 0.0 | 0.0 | 28.7759929607 |
| LOGISTIC | AA.100 | 2022-07-28T00:00:00.000 | 2022-07-01T00:00:00.000 | AMI |  | 1.68 | 11.25 | 0.06 | 0.0 | 0.0 | 0.0 | 0.0 | 23.78 |

<a id="wbn-database-s123-tos-status"></a>

#### `S123_TOS_STATUS`

**Rows:** 3,589  |  **Columns:** 11  |  **UPDATE_DATE:** 2026-07-30 09:45:32 → 2026-07-30 09:45:32

**Columns:** `UPDATE_DATE` datetime, `OBJECTID` bigint, `GLOBALID` nvarchar(50), `EDIT_DATE` datetime, `PILE_ID` nvarchar(50), `STOCK_AREA` nvarchar(50), `OLD_PILE` nvarchar(50), `STOCKPILE_TEAM` nvarchar(50), `DATE` date, `STATUS` nvarchar(50), `GEOM` geography(-1)

**Identifier vocabularies:**

- `PILE_ID` — 3,048 distinct. e.g. `TF..A.8356`, `TF.B.5810`, `TF.B.5811`, `TF.B.5809`, `TF.B.5796`, `TF.B.5807`, `TF.B.5808`, `TF.B.5814`, `TF.B.5815`, `TF.A.8362`, `TF.A.8360`, `TF.A.8358`

*Sample unavailable: could not serialise*

<a id="wbn-database-crusher-blending-data"></a>

#### `CRUSHER_BLENDING_DATA`

**Rows:** 3,332  |  **Columns:** 11  |  **DATE:** 2024-10-01 → 2025-05-25

**Columns:** `ID` int, `CRUSHER_LOCATION` nvarchar(50), `DATE` date, `SHIFT` nvarchar(50), `STOCK_LOCATION` nvarchar(50), `PILE_ID` nvarchar(50), `NB_BUCKET` float, `BF` float, `BCM` float, `STOCK_ID` nvarchar(50), `STOCK_PRODUCT` nvarchar(50)

**Identifier vocabularies:**

- `PILE_ID` — 8 distinct. e.g. `5-7 Line 3`, `1-2 Line 1`, `0-1 Line 3`, `2-3 Line 3`, `0-1 Line 1`, `2-3 Line 1`, `BC 5-7 Line 2`, `1-2 Line 3`
- `STOCK_ID` — 4 distinct. e.g. `BC 2-3 Line 1`, `BC 2-3 Line 3`, `BC 5-7 Line 3`, `BC 5-7 Line 2`

**Sample rows**:

| ID | CRUSHER_LOCATION | DATE | SHIFT | STOCK_LOCATION | PILE_ID | NB_BUCKET | BF | BCM | STOCK_ID | STOCK_PRODUCT |
|---|---|---|---|---|---|---|---|---|---|---|
| 351 | CRUSHER LOYPOLOY KM16 | 2024-10-01T00:00:00.000 | 1 | KM16 Line 1 | 0-1 Line 1 | 0.0 | 3.0 | 0.0 | BC 2-3 Line 1 | BASE COURSE 2-3 |
| 352 | CRUSHER LOYPOLOY KM16 | 2024-10-01T00:00:00.000 | 1 | KM16 Line 1 | 1-2 Line 1 | 0.0 | 3.0 | 0.0 | BC 2-3 Line 1 | BASE COURSE 2-3 |
| 353 | CRUSHER LOYPOLOY KM16 | 2024-10-01T00:00:00.000 | 1 | KM16 Line 1 | 2-3 Line 1 | 0.0 | 3.0 | 0.0 | BC 2-3 Line 1 | BASE COURSE 2-3 |
| 354 | CRUSHER LOYPOLOY KM16 | 2024-10-01T00:00:00.000 | 1 | KM16 Line 2 | BC 5-7 Line 2 | 35.0 | 3.0 | 105.0 | BC 5-7 Line 2 | BASE COURSE 5-7 |
| 355 | CRUSHER LOYPOLOY KM16 | 2024-10-01T00:00:00.000 | 1 | KM16 Line 3 | 0-1 Line 3 | 28.0 | 3.0 | 84.0 | BC 2-3 Line 3 | BASE COURSE 2-3 |

<a id="wbn-database-3rd-party-activities"></a>

#### `3RD_PARTY_ACTIVITIES`

**Rows:** 3,318  |  **Columns:** 15  |  **DATE:** 2024-10-01 00:00:00 → 2026-07-29 00:00:00

**Columns:** `ID` int, `DATE` datetime, `SHIFT` nvarchar(10), `SAMPLED_INC` int, `SAMPLE_TO_PREPARATION` int, `PREPARED_WET_SAMPLE` int, `LOT_TO_OVEN` int, `PULP_PREPARATION` int, `ANALYSIS` int, `MP_SAMPLING` int, `MP_TRANSPORT` int, `MP_WET_PREPARATION` int, `MP_DRY_PREP` int, `MP_ANALYSIS` int, `CONTRACTOR` nvarchar(50)

**Sample rows** (first 14 of 15 columns):

| ID | DATE | SHIFT | SAMPLED_INC | SAMPLE_TO_PREPARATION | PREPARED_WET_SAMPLE | LOT_TO_OVEN | PULP_PREPARATION | ANALYSIS | MP_SAMPLING | MP_TRANSPORT | MP_WET_PREPARATION | MP_DRY_PREP | MP_ANALYSIS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1493 | 2024-10-01T00:00:00.000 | Day | 1235 | 1200 | 1300 | 14.0 | 5.0 | 14.0 | 34 | 4 | 16 | 7 | 6.0 |
| 1494 | 2024-10-01T00:00:00.000 | Night | 1465 | 744 | 2077 | 18.0 | 20.0 | 8.0 | 32 | 4 | 34 | 7 | 6.0 |
| 1495 | 2024-10-01T00:00:00.000 | Day | 879 | 942 | 580 |  | 8.0 | 4.0 | 23 | 1 | 10 | 4 | 2.0 |
| 1496 | 2024-10-01T00:00:00.000 | Night | 789 | 534 | 700 | 32.0 |  |  | 21 | 1 | 14 | 4 |  |
| 1497 | 2024-10-02T00:00:00.000 | Day | 1469 | 1129 | 1344 | 14.0 | 14.0 | 2.0 | 32 | 4 | 42 | 7 | 6.0 |

<a id="wbn-database-haul-road-sta"></a>

#### `HAUL_ROAD_STA`

**Rows:** 3,122  |  **Columns:** 11

> Haul-road chainage every 25 m with WKT POINT Z geometry. Defines the road centreline by road code and SectionKM.

**Columns:** `OBJECTID` float, `NAME` varchar(-1), `LAYER` varchar(-1), `ELEVATION` varchar(-1), `DIRECTION` varchar(50), `IDLINK` varchar(-1), `SectionKM` float, `CONTRACTOR` nvarchar(50), `DISP.ROAD` nvarchar(50), `wkt` varchar(-1), `GEOM` geography(-1)

*Sample unavailable: could not serialise*

<a id="wbn-database-calendar-for-exploitation"></a>

#### `Calendar_For_Exploitation`

**Rows:** 2,665  |  **Columns:** 7  |  **DATE:** 2019-09-12 00:00:00 → 2026-12-28 00:00:00

**Columns:** `DATE` datetime, `YEAR` float, `MONTH` float, `WEEK` float, `exercice` nvarchar(255), `NBDAYS` float, `MONTH_SALES` float

**Sample rows**:

| DATE | YEAR | MONTH | WEEK | exercice | NBDAYS | MONTH_SALES |
|---|---|---|---|---|---|---|
| 2019-09-12T00:00:00.000 | 2019.0 | 9.0 | 37.0 | 19-M09 | 16.0 |  |
| 2019-09-13T00:00:00.000 | 2019.0 | 9.0 | 37.0 | 19-M09 | 16.0 |  |
| 2019-09-14T00:00:00.000 | 2019.0 | 9.0 | 38.0 | 19-M09 | 16.0 |  |
| 2019-09-15T00:00:00.000 | 2019.0 | 9.0 | 38.0 | 19-M09 | 16.0 |  |
| 2019-09-16T00:00:00.000 | 2019.0 | 9.0 | 38.0 | 19-M09 | 16.0 |  |

<a id="wbn-database-s123-enviro-tss"></a>

#### `S123_ENVIRO_TSS`

**Rows:** 2,366  |  **Columns:** 33  |  **LAST_UPDATE:** 2026-06-08 06:53:31 → 2026-06-25 14:53:36

**Columns:** `LAST_UPDATE` datetime, `OBJECTID` bigint, `GLOBALID` varchar(-1), `WAKTU` datetime, `PENGAMATAN` varchar(-1), `COLLECTOR` varchar(-1), `STATION` varchar(-1), `LAT_CALC` varchar(-1), `LONG_CALC` varchar(-1), `GEOPOINT_CALC` varchar(-1), `NILAI_TSS` float, `LIMIT_TSS_CALC` varchar(-1), `LIMIT_TSS` float, `TINGGI_LUMPUR` varchar(-1), `AKTIVITAS_DI_SEDPOND` varchar(-1), `NILAI_RAINFALL` float, `FE_GW` float, `MN_GW` float, `CHROM2_GW` float, `NI_GW` float, `CO_GW` float, `SULFIDE_GW` float, `CREATIONDATE` datetime, `CREATOR` varchar(-1), `EDITDATE` datetime, `EDITOR` varchar(-1), `NILAI_TURBIDITY` float, `TEMUAN_DEVIATION` varchar(-1), `TINDAKAN_DEVIATION` varchar(-1), `NILAI_PH` float, `KETINGGIAN_AIR` varchar(-1), `X` float, `Y` float

**Coordinate extent:** `X` 127.900805 → 128.050757; `Y` 0.47731 → 0.832062

**Sample rows** (first 14 of 33 columns):

| LAST_UPDATE | OBJECTID | GLOBALID | WAKTU | PENGAMATAN | COLLECTOR | STATION | LAT_CALC | LONG_CALC | GEOPOINT_CALC | NILAI_TSS | LIMIT_TSS_CALC | LIMIT_TSS | TINGGI_LUMPUR |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-06-25T14:53:36.623 | 26 | e8f042b3-1fad-47a4-87b8-569db3bd2e06 | 2026-04-01T11:55:00.000 | sediment pond | Enviro | SP-LDKR-02 | 0.654405 | 127.981682 | 0.654405 127.981682 0 0 | 1.0 | 100 | 100.0 | Lumpur <20% (Good) |
| 2026-06-25T14:53:36.623 | 27 | 83bc098e-5b58-41e1-81ad-c6dc3ecee4f0 | 2026-04-01T11:57:00.000 | sediment pond | Enviro | SP-KM35-01 | 0.648415 | 127.97249 | 0.648415 127.97249 0 0 | 20.0 | 200 | 200.0 | Lumpur <20% (Good) |
| 2026-06-25T14:53:36.623 | 28 | 4765cc55-981a-4db3-8b4a-3f8a4193bc1e | 2026-04-01T11:57:00.000 | sungai (river) | Enviro | Sungai Ake Sangaji - Hilir | 0.783461 | 128.050757 | 0.783461 128.050757 0 0 | 7.0 | 50 | 50.0 |  |
| 2026-06-25T14:53:36.623 | 29 | 9b797551-f226-4938-863a-3081ceddbddb | 2026-04-01T11:58:00.000 | sungai (river) | Enviro | Sungai Ake Sangaji - Hulu | 0.796117 | 128.013722 | 0.796117 128.013722 0 0 | 3.0 | 50 | 50.0 |  |
| 2026-06-25T14:53:36.623 | 30 | 489184f1-e2ba-410f-8844-b6fccc2a2d75 | 2026-02-15T12:00:00.000 | kimia air tanah (groundwater chemical) | Enviro | SP-1 | 0.803003572 | 128.025663 | 0.803003572 128.025663 0 0 | 28.0 | 200 | 200.0 |  |

<a id="wbn-database-mining-plan-3mrmp"></a>

#### `MINING_PLAN_3MRMP`

**Rows:** 2,295  |  **Columns:** 45  |  **DATE:** 2026-03-29 → 2026-05-14

**Columns:** `YEAR` float, `QUARTER` nvarchar(255), `MONTH` float, `DEPOSIT` nvarchar(255), `PIT` nvarchar(255), `SUBPIT` nvarchar(255), `IPPKH` nvarchar(255), `BM_ESTIMATION` nvarchar(255), `CONTRACTOR` nvarchar(255), `MATERIAL` nvarchar(255), `FSAP_RSAP` nvarchar(255), `CATEGORY` nvarchar(255), `CATEGORY_ROM` nvarchar(255), `BLOCK_ID` nvarchar(255), `BCM` float, `WMT_INSITU` float, `DMT` float, `Ni` float, `Fe` float, `SM` float, `SiO2` float, `MgO` float, `Co` float, `Al2O3` float, `Cr2O3` float, `MnO` float, `H2O` float, `DRY_DENSITY` float, `WET_DENSITY` float, `MINE_RECOVERY_1` float, `MINE_RECOVERY_2` float, `BCM_ROM` float, `WMT_ROM` float, `DMT_ROM` float, `Ni_DILUTION` float, `Fe_DILUTION` float, `MgO_DILUTION` float, `H2O_DILUTION` float, `Ni_ROM` float, `Fe_ROM` float, `MgO_ROM` float, `H2O_ROM` float, `REMARK` nvarchar(255), `TYPE` varchar(20), `DATE` date

**Identifier vocabularies:**

- `BLOCK_ID` — 1 distinct. e.g. `XXX_XXX_XXX`

**Sample rows** (first 14 of 45 columns):

| YEAR | QUARTER | MONTH | DEPOSIT | PIT | SUBPIT | IPPKH | BM_ESTIMATION | CONTRACTOR | MATERIAL | FSAP_RSAP | CATEGORY | CATEGORY_ROM | BLOCK_ID |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026.0 | Q1 | 1.0 | KRENE | KRENE | KRENE |  | Resource | PPP | SAP | FSAP | HGO |  |  |
| 2026.0 | Q1 | 1.0 | KRENE | KRENE | KRENE |  | Resource | PPP | WST | FSAP/RSAP | WCO |  |  |
| 2026.0 | Q1 | 1.0 | KRENE | KRENE | KRENE |  | Resource | PPP | WST | WST | WST |  |  |
| 2026.0 | Q1 | 2.0 | TOFU | TOFU | TOFU |  | Resource | STM | WST | WST | WST |  |  |
| 2026.0 | Q1 | 2.0 | TOFU | TOFU | TOFU |  | Resource | STM | WST | WST | BRK |  |  |

<a id="wbn-database-blasting-parameters"></a>

#### `blasting_parameters`

**Rows:** 2,081  |  **Columns:** 20  |  **blast_date:** 2023-02-01 00:00:00 → 2025-05-04 00:00:00

**Columns:** `ID` int, `year` nvarchar(255), `month` nvarchar(255), `week` nvarchar(255), `blast_date` datetime, `blast_time` datetime, `blasting_contractor` nvarchar(255), `location` nvarchar(255), `pit` nvarchar(255), `subpit` nvarchar(255), `block_id` nvarchar(255), `nb_drillholes_used` int, `type` nvarchar(255), `sub_type` nvarchar(255), `detonator_lenght_m` float, `unit` nvarchar(255), `qtt_ready` float, `qtt_used` float, `qtt_not_used` float, `comment` nvarchar(255)

**Identifier vocabularies:**

- `unit` — 2 distinct. e.g. `pcs`, `kg`

**Sample rows** (first 14 of 20 columns):

| ID | year | month | week | blast_date | blast_time | blasting_contractor | location | pit | subpit | block_id | nb_drillholes_used | type | sub_type |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2023 | Jul | 30 | 2023-07-28T00:00:00.000 | 1899-12-30T12:30:00.000 | MBN | Km 37 kaorahai MTM | KR |  |  |  | DYN | daya gel 0.2kg |
| 2 | 2023 | Jul | 30 | 2023-07-28T00:00:00.000 | 1899-12-30T12:30:00.000 | MBN | Km 37 kaorahai MTM | KR |  |  |  | electric detonator | detonator 6 |
| 3 | 2023 | Jun | 25 | 2023-06-17T00:00:00.000 | 1899-12-30T13:00:00.000 | MBN | Km 37 kaorahai MTM | KR |  |  |  | electric detonator | detonator 9 |
| 4 | 2023 | Jun | 25 | 2023-06-18T00:00:00.000 | 1899-12-30T13:00:00.000 | MBN | Km 37 kaorahai SMA | KR |  |  |  | ANFO |  |
| 5 | 2023 | Jun | 25 | 2023-06-18T00:00:00.000 | 1899-12-30T13:00:00.000 | MBN | Km 37 kaorahai SMA | KR |  |  |  | DYN | daya gel 0.2kg |

<a id="wbn-database-equipments-plan"></a>

#### `EQUIPMENTS_PLAN`

**Rows:** 2,071  |  **Columns:** 12  |  **DATE:** 2025-12-29 → 2026-05-14

**Columns:** `TEAM` nvarchar(255), `TYPE` nvarchar(255), `DATE` date, `YEAR` float, `MONTH` float, `WEEK` float, `ACTIVITY` nvarchar(255), `ORIGIN` nvarchar(255), `CONTRACTOR` nvarchar(255), `MATERIAL` nvarchar(255), `UNIT_TYPE` nvarchar(255), `NB_UNIT` float

**Identifier vocabularies:**

- `UNIT_TYPE` — 4 distinct. e.g. `EXCA`, `DOZER`, `ADT`, `DT`

**Sample rows**:

| TEAM | TYPE | DATE | YEAR | MONTH | WEEK | ACTIVITY | ORIGIN | CONTRACTOR | MATERIAL | UNIT_TYPE | NB_UNIT |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MINING | PLAN | 2026-04-02T00:00:00.000 | 2026.0 | 4.0 | 14.0 | MINING | TOFU | SMA | ALL | EXCA | 8.0 |
| MINING | PLAN | 2026-04-02T00:00:00.000 | 2026.0 | 4.0 | 14.0 | MINING | TOFU | SMA | ALL | ADT | 36.0 |
| MINING | PLAN | 2026-04-03T00:00:00.000 | 2026.0 | 4.0 | 14.0 | MINING | BLB | RIM | ALL | EXCA | 15.0 |
| MINING | PLAN | 2026-04-03T00:00:00.000 | 2026.0 | 4.0 | 14.0 | MINING | BLB | RIM | ALL | ADT | 43.0 |
| MINING | PLAN | 2026-04-03T00:00:00.000 | 2026.0 | 4.0 | 14.0 | MINING | KRENE | PPP | ALL | EXCA | 6.0 |

<a id="wbn-database-calendar-svy-topo-by-deposit"></a>

#### `Calendar_Svy_topo_by_deposit`

**Rows:** 1,839  |  **Columns:** 5  |  **Date:** 2024-12-28 00:00:00 → 2026-07-28 00:00:00

**Columns:** `PIT` varchar(50), `Date` datetime, `YEAR` float, `MONTH` float, `WEEK` float

**Sample rows**:

| PIT | Date | YEAR | MONTH | WEEK |
|---|---|---|---|---|
| BLB | 2026-06-06T00:00:00.000 | 2026.0 | 6.0 | 24.0 |
| BLB | 2026-06-07T00:00:00.000 | 2026.0 | 6.0 | 24.0 |
| BLB | 2026-06-08T00:00:00.000 | 2026.0 | 6.0 | 24.0 |
| BLB | 2026-06-09T00:00:00.000 | 2026.0 | 6.0 | 24.0 |
| BLB | 2026-06-10T00:00:00.000 | 2026.0 | 6.0 | 24.0 |

<a id="wbn-database-day-works-plan-daily"></a>

#### `DAY_WORKS_PLAN_DAILY`

**Rows:** 1,773  |  **Columns:** 17  |  **DATE:** 2026-06-28 00:00:00 → 2026-07-30 00:00:00

**Columns:** `ID` int, `ACTUAL_PLAN` nvarchar(255), `DATE` datetime, `WEEK` float, `ACTIVITY` nvarchar(255), `STATUS` nvarchar(255), `AREA` nvarchar(255), `SECTION_ROAD` nvarchar(255), `LOCATION_JOB` nvarchar(255), `EQUIPMENT_TYPE` nvarchar(255), `UNIT_TYPE` nvarchar(255), `UNIT_ID` nvarchar(255), `MAIN_ISSUE` nvarchar(255), `ACTION` nvarchar(255), `REMARKS` nvarchar(255), `UPDATE_DATE` datetime, `UPDATE_BY` nvarchar(255)

**Identifier vocabularies:**

- `EQUIPMENT_TYPE` — 6 distinct. e.g. `Dump Truck`, `Excavator`, `Motor Grader`, `Water Truck`, `COMPACTOR`, `Compact`
- `UNIT_TYPE` — 1 distinct. e.g. `Unit`
- `UNIT_ID` — 88 distinct. e.g. `B591`, `B596`, `E479`, `E691`, `E692`, `E693`, `E774`, `E811`, `E813`, `E814`, `E818`, `E819`

**Sample rows** (first 14 of 17 columns):

| ID | ACTUAL_PLAN | DATE | WEEK | ACTIVITY | STATUS | AREA | SECTION_ROAD | LOCATION_JOB | EQUIPMENT_TYPE | UNIT_TYPE | UNIT_ID | MAIN_ISSUE | ACTION |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Daily Plan | 2026-06-28T00:00:00.000 | 25.0 | HRM | Maintenance | KR | KM 18-35 | KM 23-25 | Dump Truck | Unit | B591 | Jalan bergelombang & spoil | load  material LPA 2 Rit & load spoil |
| 2 | Daily Plan | 2026-06-29T00:00:00.000 | 25.0 | HRM | Maintenance | KR | KM 18-35 | KM 18-21 | Dump Truck | Unit | B591 | Jalan bergelombang & spoil | load  material LPA 2 Rit & load spoil |
| 3 | Daily Plan | 2026-06-30T00:00:00.000 | 26.0 | HRM | Maintenance | KR | KM 18-35 | KM 23-25 | Dump Truck | Unit | B591 | Jalan bergelombang & spoil | load  material LPA 2 Rit & load spoil |
| 4 | Daily Plan | 2026-06-28T00:00:00.000 | 25.0 | HRM | Maintenance | KR | KM 18-35 | KM 26-29 | Dump Truck | Unit | B596 | Jalan bergelombang & spoil | load  material LPA 2 Rit & load spoil |
| 5 | Daily Plan | 2026-06-29T00:00:00.000 | 25.0 | HRM | Maintenance | KR | KM 18-35 | KM 30-33 | Dump Truck | Unit | B596 | Jalan bergelombang & spoil | load  material LPA 2 Rit & load spoil |

<a id="wbn-database-ore-stock-sales-moissonneuse-batteuse"></a>

#### `ORE_STOCK_SALES_MOISSONNEUSE_BATTEUSE`

**Rows:** 1,585  |  **Columns:** 7  |  **DATE:** 2021-01-01 00:00:00 → 2025-06-01 00:00:00

**Columns:** `DOME` nvarchar(255), `AREA` nvarchar(255), `WMT` float, `Ni` float, `MC` float, `DATE` datetime, `COMPANY` nvarchar(255)

**Sample rows**:

| DOME | AREA | WMT | Ni | MC | DATE | COMPANY |
|---|---|---|---|---|---|---|
| ABM.323 | POS 12 EXT | 13545.71 | 1.5473341046 | 35.042949762 | 2025-03-01T00:00:00.000 | YII |
| ABM.319 | POS 12 EXT | 20211.33 | 1.5904100017 | 33.5070454868 | 2025-03-01T00:00:00.000 | JMNE |
| ADM.324.A | ADM.324.A | 18730.8132103846 | 1.521 | 32.29 | 2025-03-01T00:00:00.000 | JMNE |
| ACM.416 | POS 14 | 15526.62 | 1.38 | 34.51 | 2025-03-01T00:00:00.000 | ANI |
| ADM.355 | POS 11 | 23974.3 | 1.7595147826 | 34.1125284305 | 2025-03-01T00:00:00.000 | ANI |

<a id="wbn-database-rsf-per-location"></a>

#### `RSF_PER_LOCATION`

**Rows:** 1,489  |  **Columns:** 15  |  **DATE:** 2024-10-01 00:00:00 → 2024-12-16 00:00:00

**Columns:** `ID` int, `DATE` datetime, `SHIFT` nvarchar(50), `LAYER` nvarchar(50), `ELEVATION` float, `LOCATION` nvarchar(50), `ITEM` nvarchar(50), `MATERIAL_TYPE` nvarchar(50), `Z_MAX` float, `Z_MIN` float, `RIT` float, `STATUS` nvarchar(50), `OFFICER` nvarchar(50), `REMARK` nvarchar(50), `ACTIVITY` nvarchar(50)

**Sample rows** (first 14 of 15 columns):

| ID | DATE | SHIFT | LAYER | ELEVATION | LOCATION | ITEM | MATERIAL_TYPE | Z_MAX | Z_MIN | RIT | STATUS | OFFICER | REMARK |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6181 | 2024-10-01T00:00:00.000 | DAY | 4 | 70.0 | IF08 | Uncrushed Material | Quarry | 80.08 | 79.92 | 81.0 |  | NIKANOR TUTUDUK |  |
| 6182 | 2024-10-01T00:00:00.000 | DAY | 3 | 70.0 | C22 | Uncrushed Material | Quarry | 73.07 | 72.27 | 81.0 |  | ALAN FEBRIANTO |  |
| 6183 | 2024-10-01T00:00:00.000 | DAY | 4 | 70.0 | IF01 | Disposal | Dry Stack | 85.58 | 84.02 | 106.0 |  | SILVESTER SAIYA |  |
| 6184 | 2024-10-01T00:00:00.000 | DAY | 4 | 70.0 | C02 | Disposal | Dry Stack | 83.02 | 80.37 | 105.0 |  | YEVEN NYONG |  |
| 6185 | 2024-10-01T00:00:00.000 | DAY | 4 | 70.0 | C01 | Disposal | Dry Stack | 80.59 | 78.06 | 105.0 |  | LA KARDIANTO |  |

<a id="wbn-database-class2025"></a>

#### `CLASS2025`

**Rows:** 1,438  |  **Columns:** 7  |  **MIN_DATE:** 2024-12-29 00:00:00 → 2025-07-12 00:00:00

**Columns:** `STOCK_ID` nvarchar(255), `SURVEY_CLASS2` nvarchar(255), `ORIGIN_PIT` nvarchar(255), `WMT` float, `MIN_DATE` datetime, `MAX_DATE` datetime, `Ni` float

**Identifier vocabularies:**

- `STOCK_ID` — 1,438 distinct. e.g. `TF-W.103`, `TF-W.104`, `TF-W.105`, `TF-W.106`, `TF-W.107`, `TF-W.108`, `TF-W.109`, `TF-W.11`, `TF-W.110`, `TF-W.111`, `TF-W.112`, `TF-W.113`

**Sample rows**:

| STOCK_ID | SURVEY_CLASS2 | ORIGIN_PIT | WMT | MIN_DATE | MAX_DATE | Ni |
|---|---|---|---|---|---|---|
| TF-W.103 | HGS | TF | 6538.14 | 2025-06-09T00:00:00.000 | 2025-06-10T00:00:00.000 | 1.7986821721 |
| TF-W.104 | HGS | TF | 5652.2 | 2025-06-10T00:00:00.000 | 2025-06-11T00:00:00.000 | 1.7802286256 |
| TF-W.105 | HGS | TF | 8304.74 | 2025-06-11T00:00:00.000 | 2025-06-12T00:00:00.000 | 1.9848248313 |
| TF-W.106 | LGS | TF | 7462.0 | 2025-06-12T00:00:00.000 | 2025-06-14T00:00:00.000 | 1.4792040019 |
| TF-W.107 | HGS | TF | 6005.18 | 2025-06-14T00:00:00.000 | 2025-06-15T00:00:00.000 | 1.8080159792 |

<a id="wbn-database-consolidated-survey"></a>

#### `CONSOLIDATED SURVEY`

**Rows:** 1,188  |  **Columns:** 15

**Columns:** `ID` int, `YEAR` float, `MONTH` float, `CONTRACTOR` nvarchar(255), `DEPOSIT` nvarchar(255), `PIT` nvarchar(255), `MATERIAL` nvarchar(255), `MATERIAL_ID` nvarchar(255), `BCM_SURVEY` float, `BCM_CLAIM (CLOSE MONTH)` float, `WMT_SURVEY` float, `WMT_CLAIM (CLOSE MONTH)` float, `WET_DENSITY` float, `COMMENT` nvarchar(255), `NEXT_MONTH_CORRECTION` nvarchar(255)

**Identifier vocabularies:**

- `MATERIAL_ID` — 8 distinct. e.g. `Quarry`, `TS`, `REHAND_LIM`, `LIM`, `WCO`, `WST`, `RSAP`, `SAP`

**Sample rows** (first 14 of 15 columns):

| ID | YEAR | MONTH | CONTRACTOR | DEPOSIT | PIT | MATERIAL | MATERIAL_ID | BCM_SURVEY | BCM_CLAIM (CLOSE MONTH) | WMT_SURVEY | WMT_CLAIM (CLOSE MONTH) | WET_DENSITY | COMMENT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 480 | 2024.0 | 1.0 | STM | KR | KR | Top Soil | TS | 10718.949 | 10718.949 | 15006.5286 | 15006.5286 | 1.4 |  |
| 481 | 2024.0 | 1.0 | STM | KR | KR | Over burden | WST | 120173.5520000048 | 120173.5520000048 | 223522.8067200089 | 223522.8067200089 | 1.86 |  |
| 482 | 2024.0 | 1.0 | STM | KR | KR | Limonite | LIM | 60173.22 | 60173.22 | 114843.2006783834 | 114843.2006783834 | 1.9085433799 |  |
| 483 | 2024.0 | 1.0 | STM | KR | KR | Saprolite | SAP | 422458.095 | 422458.095 | 888232.711853668 | 888232.711853668 | 2.1025344818 |  |
| 484 | 2024.0 | 1.0 | SMA | KR | KR | Top Soil | TS | 24159.1859385634 | 24159.1859385634 | 33822.8603139888 | 33822.8603139888 | 1.4 |  |

<a id="wbn-database-water-management"></a>

#### `WATER_MANAGEMENT`

**Rows:** 1,074  |  **Columns:** 12  |  **DATE:** 2025-06-24 → 2025-10-07

**Columns:** `ID` int, `DATE` date, `CONTRACTOR` nvarchar(50), `PIT` nvarchar(50), `PLANT_ID` nvarchar(50), `PLANT_TYPE` nvarchar(50), `DT_ID` nvarchar(50), `LOADING_AREA` nvarchar(50), `UNLOADING_AREA` nvarchar(50), `MATERIAL` nvarchar(50), `RIT` int, `JOB_TYPE` nvarchar(50)

**Identifier vocabularies:**

- `PLANT_ID` — 54 distinct. e.g. `E285`, `E152`, `E613`, `W241`, `W285`, `E614`, `W955`, `LA 99`, `Ex 204`, `X081`, `E931`, `E151`
- `DT_ID` — 239 distinct. e.g. `K431`, `K433`, `K447`, `K456`, `K446`, `K443`, `K581`, `JK094`, `N059`, `L957`, `L763`, `L776`

**Sample rows**:

| ID | DATE | CONTRACTOR | PIT | PLANT_ID | PLANT_TYPE | DT_ID | LOADING_AREA | UNLOADING_AREA | MATERIAL | RIT | JOB_TYPE |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 2025-06-24T00:00:00.000 | SMA | TF | E285 | EXCA | K431 | BBSP01 | BBSP01 | QUARRY | 19 | LOAD & HAUL |
| 11 | 2025-06-24T00:00:00.000 | SMA | TF | E152 | EXCA | K433 | CBB 3???? | BBSP02 | QUARRY | 3 | LOAD & HAUL |
| 12 | 2025-06-24T00:00:00.000 | SMA | TF | E152 | EXCA | K447 | CBB 3???? | BBSP02 | QUARRY | 3 | LOAD & HAUL |
| 13 | 2025-06-24T00:00:00.000 | SMA | TF | E152 | EXCA | K456 | CBB 3???? | BBSP02 | QUARRY | 1 | LOAD & HAUL |
| 14 | 2025-06-24T00:00:00.000 | SMA | TF | E152 | EXCA | K446 | CBB 3???? | BBSP02 | QUARRY | 1 | LOAD & HAUL |

<a id="wbn-database-quarry-plan"></a>

#### `QUARRY_PLAN`

**Rows:** 1,060  |  **Columns:** 11  |  **DATE:** 2026-06-01 00:00:00 → 2026-08-02 00:00:00

**Columns:** `ID` int, `TYPE` varchar(50), `DATE` datetime, `TEAM` nvarchar(255), `ORIGIN_AREA` nvarchar(255), `ORIGIN` nvarchar(255), `DESTINATION_AREA` nvarchar(255), `DESTINATION` varchar(50), `MATERIAL` nvarchar(255), `BCM` float, `RIT` float

**Sample rows**:

| ID | TYPE | DATE | TEAM | ORIGIN_AREA | ORIGIN | DESTINATION_AREA | DESTINATION | MATERIAL | BCM | RIT |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | PLAN_DELIVERY | 2026-06-29T00:00:00.000 | HRM | KR | STOCK_KR_ROAD | KR_KM18-35 | KR_KM23-25 | LPA | 30.0 | 2.0 |
| 2 | PLAN_DELIVERY | 2026-06-29T00:00:00.000 | HRM | KR | STOCK_KR_ROAD | KR_KM18-35 | KR_KM26-28 | LPA | 30.0 | 2.0 |
| 3 | PLAN_DELIVERY | 2026-06-29T00:00:00.000 | HRM | TF | CRUSHER_TF | TF_KM35-72 | TF_KM61 | LPA | 30.0 | 2.0 |
| 4 | PLAN_DELIVERY | 2026-06-29T00:00:00.000 | HRM | BLB | CRUSHER_BLB | ROAD COASTAL | CBB_KM16 | LPB | 30.0 | 2.0 |
| 5 | PLAN_DELIVERY | 2026-06-29T00:00:00.000 | HRM | BLB | CRUSHER_BLB | ROAD COASTAL | BLB_KM9 | LPA | 30.0 | 2.0 |

<a id="wbn-database-old-prod-correction-factor-access"></a>

#### `OLD_prod_correction_factor_ACCESS`

**Rows:** 957  |  **Columns:** 6

**Columns:** `YEAR` float, `MONTH` float, `contractor` nvarchar(50), `deposit_code` nvarchar(50), `material` nvarchar(50), `CF` float

**Identifier vocabularies:**

- `deposit_code` — 7 distinct. e.g. `CSW`, `KRENE`, `TF`, `CBB`, `CAS`, `BLB`, `KR`

**Sample rows**:

| YEAR | MONTH | contractor | deposit_code | material | CF |
|---|---|---|---|---|---|
| 2024.0 | 1.0 | HJS | CAS | LIM | 1.6413906358 |
| 2024.0 | 1.0 | HJS | CAS | SAP | 1.3761168641 |
| 2024.0 | 1.0 | HJS | CAS | TS | 0.7800243134 |
| 2024.0 | 1.0 | HJS | CAS | WST | 0.6869109446 |
| 2024.0 | 1.0 | HJS | CBB | LIM | 0.9444206781 |

<a id="wbn-database-rolling-mine-plan"></a>

#### `ROLLING_MINE_PLAN`

**Rows:** 834  |  **Columns:** 20  |  **UPDATE:** 2023-11-13 → 2024-07-26

**Columns:** `ID` int, `YEAR` int, `MONTH` int, `CONTRACTOR` nvarchar(50), `DEPOSIT` nvarchar(50), `PIT` nvarchar(50), `PIT_ID` nvarchar(50), `MATERIAL` nvarchar(50), `WMT_ROM` float, `Ni` float, `Fe` float, `Co` float, `SiO2` float, `MgO` float, `MnO` float, `Cr2O3` float, `Al2O3` float, `SM` float, `MC` float, `UPDATE` date

**Identifier vocabularies:**

- `PIT_ID` — 8 distinct. e.g. `CSW`, `KRENE`, `TF`, `CBB`, `CAS`, `TOFU`, `BLB`, `KR`

**Sample rows** (first 14 of 20 columns):

| ID | YEAR | MONTH | CONTRACTOR | DEPOSIT | PIT | PIT_ID | MATERIAL | WMT_ROM | Ni | Fe | Co | SiO2 | MgO |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1746 | 2024 | 1 | RIM | CBB | CBB | CBB | VHGS | 115319.3027099576 |  |  |  |  |  |
| 1747 | 2024 | 1 | RIM | CBB | CBB | CBB | HGS | 370370.3303266747 |  |  |  |  |  |
| 1748 | 2024 | 1 | RIM | CBB | CBB | CBB | LGS1 | 309195.2954262806 |  |  |  |  |  |
| 1749 | 2024 | 1 | RIM | CBB | CBB | CBB | LGS2 | 11305.2036984002 |  |  |  |  |  |
| 1750 | 2024 | 1 | RIM | CBB | CBB | CBB | LIM1 | 370474.892866795 |  |  |  |  |  |

<a id="wbn-database-iwip-requests-date"></a>

#### `IWIP_REQUESTS_DATE`

**Rows:** 772  |  **Columns:** 3  |  **DATE_OUT:** 2025-06-01 00:00:00 → 2026-05-02 00:00:00

**Columns:** `ID` int, `DATE_OUT` datetime, `STOCK_ID` nvarchar(50)

**Identifier vocabularies:**

- `STOCK_ID` — 720 distinct. e.g. `AB.455`, `ACM.477`, `ACM.478`, `AD.337`, `ADM.503`, `ACM.473`, `AD.331`, `AD.336`, `AB.452`, `AD.334`, `ADM.508`, `ABM.344`

**Sample rows**:

| ID | DATE_OUT | STOCK_ID |
|---|---|---|
| 1 | 2025-06-12T00:00:00.000 | AB.455 |
| 2 | 2025-06-12T00:00:00.000 | ACM.477 |
| 3 | 2025-06-12T00:00:00.000 | ACM.478 |
| 4 | 2025-06-12T00:00:00.000 | AD.337 |
| 5 | 2025-06-12T00:00:00.000 | ADM.503 |

<a id="wbn-database-transhipment-wbn-ore"></a>

#### `TRANSHIPMENT_WBN_ORE`

**Rows:** 573  |  **Columns:** 7  |  **DATE:** 2023-04-11 00:00:00 → 2026-07-19 00:00:00

**Columns:** `DOME` nvarchar(255), `DATE` datetime, `DESTINATION` nvarchar(255), `WMT` int, `ANTICIPATED` nvarchar(255), `GOTBACK` nvarchar(255), `TYPE` nvarchar(50)

**Sample rows**:

| DOME | DATE | DESTINATION | WMT | ANTICIPATED | GOTBACK | TYPE |
|---|---|---|---|---|---|---|
| AA.396.A | 2023-12-13T00:00:00.000 | WBN | 20000 | NO |  |  |
| AA.455 | 2024-06-03T00:00:00.000 | DBNI | 13298 | YES |  |  |
| AA.456 | 2024-06-03T00:00:00.000 | SNMI | 22919 | YES |  |  |
| AA.458 | 2024-06-09T00:00:00.000 | WBN | 28036 | NO |  |  |
| AA.463 | 2024-07-17T00:00:00.000 | DBNI | 29182 | NO |  |  |

<a id="wbn-database-id-dt-huafei"></a>

#### `ID_DT_HUAFEI`

**Rows:** 485  |  **Columns:** 1

**Columns:** `ID_DT` nchar(10)

**Sample rows**:

| ID_DT |
|---|
| K045       |
| K046       |
| K047       |
| K048       |
| K049       |

<a id="wbn-database-summary-survey"></a>

#### `SUMMARY_SURVEY`

**Rows:** 460  |  **Columns:** 12

**Columns:** `CONTRACTOR` nvarchar(255), `PIT` nvarchar(255), `YEAR` float, `MONTH` float, `MATERIAL` nvarchar(255), `DENSITY` float, `TC_WMT` float, `TC_BCM` float, `SURVEY_BCM` float, `SURVEY_WMT` float, `CF_BCM` float, `CF_WMT` float

**Sample rows**:

| CONTRACTOR | PIT | YEAR | MONTH | MATERIAL | DENSITY | TC_WMT | TC_BCM | SURVEY_BCM | SURVEY_WMT | CF_BCM | CF_WMT |
|---|---|---|---|---|---|---|---|---|---|---|---|
| RIM | TF | 2025.0 | 9.0 | Quarry | 2.15 |  | 0.0 | 0.0 | 0.0 |  |  |
| PPRE | KRENE | 2025.0 | 9.0 | Top Soil | 1.4 | 150885.0 | 107775.0 | 68344.7684210526 | 95682.6757894737 | 0.6341430612 | 0.6341430612 |
| PPRE | KRENE | 2025.0 | 9.0 | Over burden | 1.86 | 391710.0 | 210596.7741935484 | 89038.2728722836 | 165611.1875424476 | 0.4227902978 | 0.4227902978 |
| PPRE | KRENE | 2025.0 | 9.0 | Limonite | 1.63 | 39815.0 | 24426.3803680982 | 18442.8203192226 | 30061.7971203329 | 0.755036974 | 0.755036974 |
| PPRE | KRENE | 2025.0 | 9.0 | Saprolite | 2.0940576123 | 414985.0 | 198172.6756542125 | 188868.1913874412 | 395500.8738928091 | 0.9530486015 | 0.9530486015 |

<a id="wbn-database-blasting-prod"></a>

#### `BLASTING_PROD`

**Rows:** 433  |  **Columns:** 12  |  **DATE:** 2026-01-02 00:00:00 → 2026-05-27 00:00:00

**Columns:** `DEPOSIT` nvarchar(255), `DATE` datetime, `CONTRACTOR` nvarchar(255), `MATERIAL` nvarchar(255), `AREA_PIT` nvarchar(255), `ID_BLASTING` nvarchar(255), `HOLE_NUMBER_MBN` float, `BURDEN` float, `SPACING` float, `DEPTH` float, `CALCULATED_VOLUME` float, `VOLUME_CLAIM_BCM` float

**Sample rows**:

| DEPOSIT | DATE | CONTRACTOR | MATERIAL | AREA_PIT | ID_BLASTING | HOLE_NUMBER_MBN | BURDEN | SPACING | DEPTH | CALCULATED_VOLUME | VOLUME_CLAIM_BCM |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Kaorahai | 2026-01-03T00:00:00.000 | RSF | Quarry | KR3 | 16-P5 | 47.0 | 6.0 | 5.5 | 6.838 | 10605.738 | 10605.738 |
| Kaorahai | 2026-01-03T00:00:00.000 | RSF | Quarry | KR3 | 16-P5 | 19.0 | 3.0 | 3.0 | 3.053 | 522.063 | 522.063 |
| Kaorahai | 2026-01-04T00:00:00.000 | RIM | Quarry | KRENE 1 | 20 | 30.0 | 7.0 | 6.0 | 5.26 | 6627.6 | 6627.6 |
| Kaorahai | 2026-01-05T00:00:00.000 | RIM QUARRY | Quarry | KR3 | 5-P3 | 5.0 | 7.0 | 6.0 | 3.42 | 718.2 | 718.2 |
| Kaorahai | 2026-01-05T00:00:00.000 | RIM QUARRY | Quarry | KR3 | 5-P3 | 5.0 | 3.0 | 3.0 | 3.12 | 140.4 | 140.4 |

<a id="wbn-database-dispatch-plan-wb"></a>

#### `DISPATCH_PLAN_WB`

**Rows:** 432  |  **Columns:** 15  |  **DATE:** 2026-01-07 00:00:00 → 2026-07-22 00:00:00

**Columns:** `ID` int, `DATE` datetime, `SHIFT` float, `CONTRACTOR` nvarchar(255), `EXCAVATOR` nvarchar(255), `DT_UNIT` nvarchar(255), `MATERIAL` nvarchar(255), `TOS_LOCATION` nvarchar(255), `ORIGIN_ID` nvarchar(255), `ORIGIN_AREA` nvarchar(255), `DESTINATION_ID` nvarchar(255), `DESTINATION_AREA` nvarchar(255), `WB_ID` nvarchar(255), `SAMPLE_HOUSE` nvarchar(255), `REMARK` nvarchar(255)

**Identifier vocabularies:**

- `EXCAVATOR` — 3 distinct. e.g. `E042`, `E049`, `E377`
- `DT_UNIT` — 87 distinct. e.g. `R945`, `R946`, `R944`, `R943`, `R940`, `R941`, `R939`, `R938`, `R947`, `R707`, `R708`, `R710`
- `ORIGIN_ID` — 12 distinct. e.g. `KRENE.I.3291`, `KRENE.I.3293`, `TF.A.8345`, `TF.A.8419`, `TF.A.8422`, `TF.A.8424`, `TF.B.5044`, `TF.B.5244`, `TF.B.5747`, `TF.B.5789`, `TF.B.5868`, `TF.B.5872`
- `DESTINATION_ID` — 2 distinct. e.g. `ACM.684`, `ADM.782`
- `WB_ID` — 1 distinct. e.g. `WB_IWIP_T15`

**Sample rows** (first 14 of 15 columns):

| ID | DATE | SHIFT | CONTRACTOR | EXCAVATOR | DT_UNIT | MATERIAL | TOS_LOCATION | ORIGIN_ID | ORIGIN_AREA | DESTINATION_ID | DESTINATION_AREA | WB_ID | SAMPLE_HOUSE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-01-07T00:00:00.000 | 1.0 | RIM | E042 | R945 | SAP | TOS_KRENE_06 | KRENE.I.3291 | KRENE | ACM.684 | POS 12 | WB_IWIP_T15 | SHB KM28 |
| 2 | 2026-01-07T00:00:00.000 | 1.0 | RIM | E042 | R946 | SAP | TOS_KRENE_06 | KRENE.I.3291 | KRENE | ACM.684 | POS 12 | WB_IWIP_T15 | SHB KM28 |
| 3 | 2026-01-07T00:00:00.000 | 1.0 | RIM | E042 | R944 | SAP | TOS_KRENE_06 | KRENE.I.3291 | KRENE | ACM.684 | POS 12 | WB_IWIP_T15 | SHB KM28 |
| 4 | 2026-01-07T00:00:00.000 | 1.0 | RIM | E042 | R943 | SAP | TOS_KRENE_06 | KRENE.I.3291 | KRENE | ACM.684 | POS 12 | WB_IWIP_T15 | SHB KM28 |
| 5 | 2026-01-07T00:00:00.000 | 1.0 | RIM | E042 | R940 | SAP | TOS_KRENE_06 | KRENE.I.3291 | KRENE | ACM.684 | POS 12 | WB_IWIP_T15 | SHB KM28 |

<a id="wbn-database-color-chemical"></a>

#### `COLOR_CHEMICAL`

**Rows:** 404  |  **Columns:** 4

**Columns:** `CHEMICAL` nvarchar(255), `GRADE_CLASS` float, `COLOR` nvarchar(255), `COLOR_HEXA` nvarchar(255)

**Sample rows**:

| CHEMICAL | GRADE_CLASS | COLOR | COLOR_HEXA |
|---|---|---|---|
| Fe | 85.0 |  | #45ad5a |
| Fe | 86.0 |  | #45ad5a |
| Fe | 87.0 |  | #45ad5a |
| Fe | 88.0 |  | #45ad5a |
| Fe | 89.0 |  | #45ad5a |

<a id="wbn-database-wbn-database-essentials"></a>

#### `WBN_DATABASE_ESSENTIALS`

**Rows:** 334  |  **Columns:** 3

**Columns:** `ID` int, `OBJECT_NAME` nvarchar(50), `OBJECT_TYPE` nvarchar(50)

**Sample rows**:

| ID | OBJECT_NAME | OBJECT_TYPE |
|---|---|---|
| 1 | _ore_screened_or_not |  |
| 2 | blasting_parameters |  |
| 3 | blasting_drilling |  |
| 4 | STOCK_COMPOSITION_SCREEN_INFO_VIA_BM |  |
| 5 | _LIMONITE_DAILY_STOCK |  |

<a id="wbn-database-autoqc-plan-ni-cf-old"></a>

#### `autoQC_PLAN_NI_CF_OLD`

**Rows:** 264  |  **Columns:** 21

**Columns:** `LAST_UPDATE` nvarchar(50), `YEAR` int, `MONTH` int, `ORIGIN_PIT` nvarchar(50), `CONTRACTOR_PILE` nvarchar(50), `MATERIAL` nvarchar(50), `DIL_BM_MC` float, `DIL_BM_Ni` float, `DIL_BM_Fe` float, `DIL_BM_SiO2` float, `DIL_BM_MgO` float, `DIL_BM_Co` float, `DIL_BM_Cr2O3` float, `DIL_TOS_MC` float, `DIL_TOS_Ni` float, `DIL_TOS_Fe` float, `DIL_TOS_SiO2` float, `DIL_TOS_MgO` float, `DIL_TOS_Co` float, `DIL_TOS_Cr2O3` float, `DIL_PROP_BM_Ni` float

**Sample rows** (first 14 of 21 columns):

| LAST_UPDATE | YEAR | MONTH | ORIGIN_PIT | CONTRACTOR_PILE | MATERIAL | DIL_BM_MC | DIL_BM_Ni | DIL_BM_Fe | DIL_BM_SiO2 | DIL_BM_MgO | DIL_BM_Co | DIL_BM_Cr2O3 | DIL_TOS_MC |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-07-06 06:00:29 | 2024 | 4 | CBB | RIM | SAP | 1.0306948167 | 0.9472451623 | 0.8159249271 | 1.0302367428 | 1.4239958801 | 0.8066875203 | 0.7268254051 | 1.0143754946 |
| 2026-07-06 06:00:29 | 2024 | 5 | CBB | RIM | SAP | 1.0306948167 | 0.9472451623 | 0.8159249271 | 1.0302367428 | 1.4239958801 | 0.8066875203 | 0.7268254051 | 1.0143754946 |
| 2026-07-06 06:00:29 | 2024 | 6 | BLB | RIM | LIM | 0.9804304638 | 0.9369220482 | 1.068074469 | 4.0847502668 | 5.0308294698 | 1.6531775082 | 1.1371111284 | 1.0077919262 |
| 2026-07-06 06:00:29 | 2024 | 6 | CBB | RIM | LIM | 0.9160127804 | 0.9208806506 | 0.8889803039 | 1.5899192882 | 2.6837016804 | 0.8401210696 | 0.672121515 | 0.9392778258 |
| 2026-07-06 06:00:29 | 2024 | 6 | KR | PPP | SAP | 0.8955586055 | 0.9386833184 | 0.8666429844 | 1.0597551811 | 1.3508521004 | 0.9966751879 | 0.9300444575 | 0.8902882299 |

<a id="wbn-database-dispatch-haulage-tf"></a>

#### `DISPATCH HAULAGE TF`

**Rows:** 264  |  **Columns:** 5

**Columns:** `ID` int, `YEAR` int, `MONTH` int, `CONTRACTOR` nvarchar(50), `TF` float

**Sample rows**:

| ID | YEAR | MONTH | CONTRACTOR | TF |
|---|---|---|---|---|
| 1 | 2024 | 3 | GMG | 32.0 |
| 2 | 2024 | 3 | TCI | 42.0 |
| 3 | 2024 | 3 | RIM | 37.0 |
| 4 | 2024 | 3 | SMA | 40.0 |
| 5 | 2024 | 3 | STM | 40.0 |

<a id="wbn-database-dispatch-roads-old"></a>

#### `DISPATCH ROADS OLD`

**Rows:** 254  |  **Columns:** 36

**Columns:** `TYPE` nvarchar(255), `COMPANY` nvarchar(255), `MATERIAL` nvarchar(10), `DISPATCH ZONE` nvarchar(255), `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `KM ORI` float, `KM DEST` float, `DISTANCE GROSS (KM)` float, `CRD KM0 - KM2,5` float, `CRD KM2,5 - KM5,5` float, `CRD KM5,5 - KM7` float, `CSW KM3 - KM4` float, `CSW KM4 - KM5,7` float, `GOMDI KM3,7 - KM3,8` float, `BLB KM2,5 - KM5,7` float, `BLB KM5,7 - KM10` float, `BLB KM17 - KM20` float, `HFC KM5,5 - KM6,4` float, `CBB KM7 - KM9` float, `CBB KM9 - KM15` float, `CBB KM15 - KM17` float, `CBBB KM15 - KM17,5` float, `KR KM7 - KM12` float, `KR KM12 - KM15` float, `KR KM15 - KM17` float, `KR KM17 - KM21` float, `KR KM21 - KM26` float, `KR KM26 - KM27` float, `KR KM27 - KM32` float, `KR KM32 - KM37` float, `KR KM37 - KM39` float, `TF KM39 - KM45` float, `TF KM45 - KM52` float, `TF KM52 - KM60` float, `TF KM60 - KM68` float

**Sample rows** (first 14 of 36 columns):

| TYPE | COMPANY | MATERIAL | DISPATCH ZONE | ORIGIN | DESTINATION | KM ORI | KM DEST | DISTANCE GROSS (KM) | CRD KM0 - KM2,5 | CRD KM2,5 - KM5,5 | CRD KM5,5 - KM7 | CSW KM3 - KM4 | CSW KM4 - KM5,7 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| QUARRY | WBN | BC | KR to FeNi U | KR | FENI KM15 | 37.0 | 15.0 | 22.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| QUARRY | WBN | BC | KR to KR | KR | KR | 38.0 | 38.0 | 1.0 |  |  |  |  |  |
| QUARRY | WBN | BC | KR to LOYPOLOY | KR | LOYPOLOY | 38.0 | 16.0 | 22.0 |  |  |  |  |  |
| QUARRY | WBN | BC | KR to KM 17 | KR | POS 10 | 37.0 | 17.0 | 20.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| QUARRY | WBN | BC | KR to KM 17 | KR | POS 11 | 37.0 | 17.0 | 20.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

<a id="wbn-database-autohaulage-vs-prod-monthly-cf"></a>

#### `autoHAULAGE_VS_PROD_MONTHLY_CF`

**Rows:** 223  |  **Columns:** 6  |  **LAST_UPDATE:** 2026-07-29 16:00:22 → 2026-07-29 16:00:22

**Columns:** `LAST_UPDATE` datetime, `CONTRACTOR` nvarchar(50), `DATE` date, `PIT` nvarchar(50), `MATERIAL` nvarchar(50), `CF` float

**Sample rows**:

| LAST_UPDATE | CONTRACTOR | DATE | PIT | MATERIAL | CF |
|---|---|---|---|---|---|
| 2026-07-29T16:00:22.000 | HJS | 2024-10-01T00:00:00.000 | CBB | LIM | 1.2282516403 |
| 2026-07-29T16:00:22.000 | HJS | 2024-11-01T00:00:00.000 | CBB | LIM | 1.1292418773 |
| 2026-07-29T16:00:22.000 | HJS | 2024-11-01T00:00:00.000 | CBB | SAP | 1.0723382894 |
| 2026-07-29T16:00:22.000 | HJS | 2024-12-01T00:00:00.000 | CBB | LIM | 1.0469020374 |
| 2026-07-29T16:00:22.000 | HJS | 2024-12-01T00:00:00.000 | CBB | SAP | 1.0372884266 |

<a id="wbn-database-dispatch-roads"></a>

#### `DISPATCH ROADS`

**Rows:** 222  |  **Columns:** 33

> Per origin-destination pair, the FRACTION of the haul crossing each of 27 named sections. A ready-made route-to-segment decomposition.

**Columns:** `ORIGIN` nvarchar(50), `DESTINATION` nvarchar(50), `DISPATCH ZONE` nvarchar(255), `KM ORI` float, `KM DEST` float, `DISTANCE GROSS (KM)` float, `CRD KM0 - KM2,5` float, `CRD KM2,5 - KM5,5` float, `CRD KM5,5 - KM7` float, `CSW KM3 - KM4` float, `CSW KM4 - KM5,7` float, `GOMDI KM3,7 - KM3,8` float, `BLB KM2,5 - KM5,7` float, `BLB KM5,7 - KM10` float, `BLB KM17 - KM20` float, `HFC KM5,5 - KM6,4` float, `CBB KM7 - KM9` float, `CBB KM9 - KM15` float, `CBB KM15 - KM17` float, `CBBB KM15 - KM17,5` float, `KR KM7 - KM12` float, `KR KM12 - KM15` float, `KR KM15 - KM17` float, `KR KM17 - KM21` float, `KR KM21 - KM26` float, `KR KM26 - KM27` float, `KR KM27 - KM32` float, `KR KM32 - KM37` float, `KR KM37 - KM39` float, `TF KM39 - KM45` float, `TF KM45 - KM52` float, `TF KM52 - KM60` float, `TF KM60 - KM68` float

**Sample rows** (first 14 of 33 columns):

| ORIGIN | DESTINATION | DISPATCH ZONE | KM ORI | KM DEST | DISTANCE GROSS (KM) | CRD KM0 - KM2,5 | CRD KM2,5 - KM5,5 | CRD KM5,5 - KM7 | CSW KM3 - KM4 | CSW KM4 - KM5,7 | GOMDI KM3,7 - KM3,8 | BLB KM2,5 - KM5,7 | BLB KM5,7 - KM10 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| BLB | BLB | BLB to BLB | 20.0 | 19.0 | 0.99 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| BLB | BSE | BLB to CSTL | 20.0 | 5.0 | 12.9 | 0.0 | 0.1860465116 | 0.0 | 0.0 | 0.0 | 0.0 | 0.2480620155 | 0.3333333333 |
| BLB | CRUSHER | BLB to CSTL | 20.0 | 5.0 | 7.3 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.5890410959 |
| BLB | CUU_KM_10 | BLB to CSTL | 20.0 | 10.0 | 11.9 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| BLB | EOS | BLB to CSTL | 20.0 | 4.0 | 12.0 | 0.0 | 0.125 | 0.0 | 0.0 | 0.0 | 0.0 | 0.2666666667 | 0.3583333333 |

<a id="wbn-database-hrm-contract-equipment"></a>

#### `HRM_CONTRACT_EQUIPMENT`

**Rows:** 198  |  **Columns:** 8

> Equipment committed per road section by contractor.

**Columns:** `ID` int, `ROAD` nchar(10), `SECTION` nvarchar(50), `CONTRACTOR` nchar(10), `FLEET` nchar(10), `UNIT_TYPE` nvarchar(50), `DETAIL` nchar(10), `QUANTITY` int

**Identifier vocabularies:**

- `UNIT_TYPE` — 5 distinct. e.g. `COMPACTOR`, `DT`, `EXCA`, `GRADER`, `WT`

**Sample rows**:

| ID | ROAD | SECTION | CONTRACTOR | FLEET | UNIT_TYPE | DETAIL | QUANTITY |
|---|---|---|---|---|---|---|---|
| 24 | CSW        | CSW KM4-KM5.7 | RIM        | RIM F1     | EXCA | Exca 20T   | 1 |
| 25 | CSW        | CSW KM4-KM5.7 | RIM        | RIM F1     | EXCA | Exca ?     | 0 |
| 26 | CSW        | CSW KM4-KM5.7 | RIM        | RIM F1     | DT |  | 3 |
| 27 | CSW        | CSW KM4-KM5.7 | RIM        | RIM F1     | GRADER |  | 1 |
| 28 | CSW        | CSW KM4-KM5.7 | RIM        | RIM F1     | COMPACTOR |  | 1 |

<a id="wbn-database-projects-supervision"></a>

#### `PROJECTS_SUPERVISION`

**Rows:** 198  |  **Columns:** 23  |  **DATE_START:** 2025-08-21 → 2025-11-24

**Columns:** `ID` int, `UPDATE_TYPE` nvarchar(50), `SECTION` nvarchar(50), `PROJECT_ITEM` nvarchar(50), `PROJECT_GROUP` nvarchar(255), `PROJECT_CATEGORY` nvarchar(50), `PROJECT_DESCRIPTION` nvarchar(255), `TASK_ID` int, `TASK_DESCRIPTION` nvarchar(255), `TASK_ASSIGN_TO` nvarchar(50), `TASK_PRIORITY` nvarchar(50), `TASK_PROGRESS_%` float, `TASK_STATUS` nvarchar(50), `DATE_START` date, `DATE_END` date, `DAILY_PLAN_PROGRESS` float, `LOCATION_AREA` nvarchar(50), `LOCATION_DETAILS` nvarchar(255), `CHECK_DATE` datetime, `CHECK_AGENT_NAME` nvarchar(50), `CHECK_NB_UNIT` float, `CHECK_IMAGE_ID` nvarchar(255), `CHECK_REMARK` nvarchar(255)

**Identifier vocabularies:**

- `CHECK_IMAGE_ID` — 102 distinct. e.g. `_res_images\supervision_projects\task_1_`, `_res_images\supervision_projects\task_1_`, `_res_images\supervision_projects\task_1_`, `_res_images\supervision_projects\task_1_`, `_res_images\supervision_projects\task_10`, `_res_images\supervision_projects\task_10`, `_res_images\supervision_projects\task_10`, `_res_images\supervision_projects\task_10`, `_res_images\supervision_projects\task_10`, `_res_images\supervision_projects\task_10`, `_res_images\supervision_projects\task_10`, `_res_images\supervision_projects\task_10`

**Sample rows** (first 14 of 23 columns):

| ID | UPDATE_TYPE | SECTION | PROJECT_ITEM | PROJECT_GROUP | PROJECT_CATEGORY | PROJECT_DESCRIPTION | TASK_ID | TASK_DESCRIPTION | TASK_ASSIGN_TO | TASK_PRIORITY | TASK_PROGRESS_% | TASK_STATUS | DATE_START |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | PLAN | HRM | POS |  | DEVELOPMENT | NEW 5 PAD | 1 | Monitor |  | HIGH |  | OPEN | 2025-08-21T00:00:00.000 |
| 8 | PROGRESS | HRM | POS |  | DEVELOPMENT | NEW 5 PAD | 1 | Monitor |  | HIGH | 90.0 | OPEN | 2025-08-21T00:00:00.000 |
| 11 | PROGRESS | HRM | POS |  | DEVELOPMENT | NEW 5 PAD | 1 | Monitor |  | HIGH | 95.0 | OPEN | 2025-08-21T00:00:00.000 |
| 13 | PROGRESS | HRM | POS |  | DEVELOPMENT | NEW 5 PAD | 1 | Monitor |  | HIGH | 97.0 | OPEN | 2025-08-21T00:00:00.000 |
| 14 | PLAN | HAULAGE | ROAD |  | CONSTRUCTION | Install tyre di area escape way km 34-… | 14 | Melakukan pemasangan tyre di area esca… |  | MEDIUM |  | OPEN | 2025-08-28T00:00:00.000 |

<a id="wbn-database-mbar"></a>

#### `MBAR`

**Rows:** 173  |  **Columns:** 12

**Columns:** `Tanggal` datetime, `Pit` nvarchar(255), `PIT CODE` nvarchar(255), `Type` nvarchar(255), `Category` nvarchar(255), `Material` nvarchar(255), `WMT` float, `Ni%` float, `Fe%` float, `Co%` float, `MC%` float, `DMT` float

**Identifier vocabularies:**

- `PIT CODE` — 5 distinct. e.g. `BLB`, `CBB`, `KR`, `KRENE`, `TF`

**Sample rows**:

| Tanggal | Pit | PIT CODE | Type | Category | Material | WMT | Ni% | Fe% | Co% | MC% | DMT |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2025-02-18T00:00:00.000 | Bukit Limber Barat | BLB | Ore | Saprolite | Saprolite | 25537.21 | 1.48 | 20.14 | 0.07 |  |  |
| 2025-02-18T00:00:00.000 | Bukit Limber Barat | BLB | Ore | Limonite | Limonite | 54222.28 | 1.14 | 43.05 | 0.16 |  |  |
| 2025-02-25T00:00:00.000 | Biri-Biri | CBB | Ore | Saprolite | Saprolite | 104834.83 | 1.59 | 19.59 | 0.06 |  |  |
| 2025-02-25T00:00:00.000 | Biri-Biri | CBB | Ore | Limonite | Limonite | 1460.92 | 1.3 | 38.24 | 0.12 |  |  |
| 2025-02-25T00:00:00.000 | Kao Rahai Barat Daya | KR | Ore | Saprolite | Saprolite | 77032.6 | 1.65 | 9.19 | 0.03 |  |  |

<a id="wbn-database-hrm-major-roadwork"></a>

#### `HRM_MAJOR_ROADWORK`

**Rows:** 149  |  **Columns:** 11  |  **DATE:** 2024-10-15 → 2024-11-03

> Roadwork campaigns by KM range with fleet, material and percent complete.

**Columns:** `ID` int, `DATE` date, `CONTRACTOR` nvarchar(50), `KM_START` int, `KM_END` int, `FLEET` nvarchar(50), `MATERIAL` nvarchar(-1), `PROGRESS` nvarchar(-1), `PERCENTAGE` float, `EQUIPMENT` nvarchar(-1), `DUE_DATE` date

**Identifier vocabularies:**

- `EQUIPMENT` — 18 distinct. e.g. `ADDITIONAL MAN POWER 
(OPERATOR AND FORE`, `ADDITIONAL: 
EXC FROM MTM
10x DTH
10x PP`, `DT FOR HAULING THE MATERIALS 
BY CKB, MT`, `DT HAULING BASE COURSE FROM KR 38 - 66 B`, `EXCA MTM`, `MG 15, VB 18, EX 197`, `MG 17, VB 11, WT 27`, `MG 18, VB 22, WT 18, EX 148`, `MG 19, VB 23, WT 23`, `MG 20, VB 27, WT 20, EX 166`, `MG 23, VB 07,WT 20, EX 3025
DT STM 1033,`, `MG 6001, VB 21, WT 29, EX 3036`

**Sample rows**:

| ID | DATE | CONTRACTOR | KM_START | KM_END | FLEET | MATERIAL | PROGRESS | PERCENTAGE | EQUIPMENT | DUE_DATE |
|---|---|---|---|---|---|---|---|---|---|---|
| 64 | 2024-10-15T00:00:00.000 | STM | 27 | 39 | 3 FLEET | BASE COURSE  STOCK MATERIAL IN KM 42 | CONTINUE MAINTENANCE REGULAR LOADING S… | 0.89 |  | 2024-10-17T00:00:00.000 |
| 65 | 2024-10-15T00:00:00.000 | RIM | 39 | 47 | 4 FLEET | BASE COURSE | CONTUNUE MAINTENANCE REGULAR LOADING S… | 0.8 | PLAN 4 FLEET, RUNNING TODAY 2X MG, 2X … | 2024-10-17T00:00:00.000 |
| 66 | 2024-10-15T00:00:00.000 | RIM | 39 | 47 |  |  | MAINTENANCE DRAINAGE | 0.6 |  | 2024-10-17T00:00:00.000 |
| 67 | 2024-10-15T00:00:00.000 | STM | 47 | 57 | 5 FLEET | BASE COURSE BOULDER | CONTINUE JOB PRIORITY MAJOR ISSUES MAI… | 0.8 | ADDITIONAL MAN POWER  (OPERATOR AND FO… | 2024-10-17T00:00:00.000 |
| 68 | 2024-10-15T00:00:00.000 | STM | 55 | 60 |  | BASE COURSE BOULDER | SPREADING THE MATERIALS IN LOADED LINE… | 0.35 | DT FOR HAULING THE MATERIALS  BY CKB, … | 2024-10-17T00:00:00.000 |

<a id="wbn-database-lme"></a>

#### `LME`

**Rows:** 145  |  **Columns:** 4  |  **DATE:** 2026-01-02 00:00:00 → 2026-07-29 00:00:00

**Columns:** `DATE` datetime, `LME_Ni_USD` float, `LME_Ni_3MONTH_USD` float, `LME_Ni_STOCK_ASSET` float

**Sample rows**:

| DATE | LME_Ni_USD | LME_Ni_3MONTH_USD | LME_Ni_STOCK_ASSET |
|---|---|---|---|
| 2026-07-29T00:00:00.000 | 17000.0 | 17195.0 | 267522.0 |
| 2026-07-28T00:00:00.000 | 16860.0 | 17080.0 | 267522.0 |
| 2026-07-27T00:00:00.000 | 17165.0 | 17380.0 | 267342.0 |
| 2026-07-24T00:00:00.000 | 17205.0 | 17430.0 | 267342.0 |
| 2026-07-23T00:00:00.000 | 17200.0 | 17420.0 | 268548.0 |

<a id="wbn-database-lme-gold"></a>

#### `LME_GOLD`

**Rows:** 143  |  **Columns:** 2  |  **DATE:** 2026-01-02 00:00:00 → 2026-07-29 00:00:00

**Columns:** `DATE` datetime, `GOLD` float

**Sample rows**:

| DATE | GOLD |
|---|---|
| 2026-07-29T00:00:00.000 | 111850.0 |
| 2026-07-28T00:00:00.000 | 112360.0 |
| 2026-07-27T00:00:00.000 | 113500.0 |
| 2026-07-24T00:00:00.000 | 112510.0 |
| 2026-07-23T00:00:00.000 | 113320.0 |

<a id="wbn-database-tss-point"></a>

#### `TSS_POINT`

**Rows:** 121  |  **Columns:** 36

**Columns:** `FID` float, `FID1` float, `FID_` float, `OBJECTID` float, `Station` nvarchar(255), `Monitoring` nvarchar(255), `Sub_Monito` nvarchar(255), `Category` nvarchar(255), `MANAGER` nvarchar(255), `Area` nvarchar(255), `Sub_Area` nvarchar(255), `Type` nvarchar(255), `Sub_Catego` nvarchar(255), `Outfall` nvarchar(255), `Quantity` float, `Mine` nvarchar(255), `X` float, `Y` float, `Long` nvarchar(255), `Lat` nvarchar(255), `Scope` nvarchar(255), `Frequency_` nvarchar(255), `Status_1` nvarchar(255), `Status_2` nvarchar(255), `Added` float, `Mark` nvarchar(255), `IPPKH_Conv` nvarchar(255), `Change__Id` nvarchar(255), `Change_Poi` nvarchar(255), `Change__St` nvarchar(255), `Change__Sc` nvarchar(255), `Note` nvarchar(255), `Longitude` nvarchar(255), `Latitude` float, `POINT_X` float, `POINT_Y` float

**Identifier vocabularies:**

- `Change__Id` — 31 distinct. e.g. ` `, `20230902_SP-01-CBBT`, `20230902_SP-OTBB-08`, `20230902_SP-OTUN-04`, `20230902_SP-WDBB-02`, `20230902_X. 385931.6727 Y. 74790.8653`, `20240108_BAID-01`, `20240127_POS-10-01`, `20240127_POS-10-02`, `20240229_SP-KR1-01`, `20240229_SP-KR6-02`, `20240712_AP TOFU 1 BAWAH`

**Coordinate extent:** `X` 375228.0 → 394377.80562; `Y` 52631.0 → 90596.059627; `Latitude` 53658.0394286 → 90596.0596272

**Sample rows** (first 14 of 36 columns):

| FID | FID1 | FID_ | OBJECTID | Station | Monitoring | Sub_Monito | Category | MANAGER | Area | Sub_Area | Type | Sub_Catego | Outfall |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 7.0 |  |  | 25.0 | AP-AM-09 | RIVER | River | River |  | KAO RAHAI | Ake Mein | AMDAL | River Ake Mein | Ake Mein |
| 5.0 |  |  | 16.0 | AP-SL-01 | RIVER | River | River |  | KAO RAHAI | Ake Seloi | AMDAL | River Ake Seloi | Ake Seloi |
| 6.0 |  |  | 17.0 | AP-SL-04 | RIVER | River | River |  | COASTAL | Creek Ake Seloi | AMDAL | River Creek Ake Seloi | Creek Ake Seloi |
| 8.0 |  |  | 33.0 | AP-WS-01 | RIVER | River | River |  | COASTAL | Ake Wosea | AMDAL | River Ake Wosea | Ake Wosea |
| 2.0 |  |  | 12.0 | AP-WS-02 | RIVER | River | River |  | COASTAL | Ake Wosea | AMDAL | River Ake Wosea | Ake Wosea |

<a id="wbn-database-tos-dump-coordinates"></a>

#### `TOS_DUMP_COORDINATES`

**Rows:** 118  |  **Columns:** 7

**Columns:** `TOS_PIT` nvarchar(255), `TOS_NAME` nvarchar(255), `TOS_TYPE` nvarchar(50), `POINT_X` int, `POINT_Y` int, `TOS_NUMBER` int, `TOS_CONTRACTOR` nvarchar(255)

**Sample rows**:

| TOS_PIT | TOS_NAME | TOS_TYPE | POINT_X | POINT_Y | TOS_NUMBER | TOS_CONTRACTOR |
|---|---|---|---|---|---|---|
| TF | Backfill_Waste_TF2_1_STM | BACKFILL | 391979 | 88233 | 2 |  |
| TF | Backfill_TF_SMA_04 | BACKFILL | 392673 | 89292 | 4 |  |
| TF | Backfill_Waste_TF5_STM | BACKFILL | 392096 | 89862 | 5 |  |
| CBB |  | BMS | 380896 | 57063 | 1 |  |
| CBB |  | BMS | 382658 | 56271 | 6 |  |

<a id="wbn-database-tss-crosstable"></a>

#### `TSS_CROSSTABLE`

**Rows:** 109  |  **Columns:** 5

**Columns:** `SP_ID` nvarchar(255), `RIVER_ID` nvarchar(255), `CA_ID` nvarchar(255), `CONTRACTOR` nvarchar(255), `RAINFALL_REPRESENTATIVE` nvarchar(255)

**Identifier vocabularies:**

- `SP_ID` — 108 distinct. e.g. `AP-SL-01`, `AP-SL-04`, `AP-WS-01`, `AP-WS-02`, `BAID-01`, `BAM-01`, `BAM-02`, `BAM-04`, `BAM-04.1`, `BAMM-03`, `BJR-03`, `BJR-04`
- `RIVER_ID` — 30 distinct. e.g. `AP-SL-01`, `AP-SL-04`, `AP-WS-01`, `AP-WS-02`, `AP-WS-03`, `AP-WS-31`, `BAM-01 (Ake Mein)`, `BAM-02 (Ake Mein Creek)`, `BDM-03 (DomaMidStream)`, `BGY-01`, `BJR-03 (Djira Mid)`, `BJR-04`
- `CA_ID` — 50 distinct. e.g. `CA-BB1`, `CA-BB10`, `CA-BB11`, `CA-BB12`, `CA-BB13`, `CA-BB14`, `CA-BB15`, `CA-BB16`, `CA-BB17`, `CA-BB20`, `CA-BB21`, `CA-BB22`

**Sample rows**:

| SP_ID | RIVER_ID | CA_ID | CONTRACTOR | RAINFALL_REPRESENTATIVE |
|---|---|---|---|---|
| AP-SL-01 | BSL-04 (Seloi) |  |  | BUKIT LIMBER 3 |
| AP-SL-04 | BSL-04.2 |  |  |  |
| AP-WS-01 | AP-WS-02 |  |  | CAS6 |
| AP-WS-02 | AP-WS-03 |  |  | BIRI-BIRI_SMA |
| AP-WS-02 | AP-WS-03 |  |  | BIRI-BIRI_SMA |

<a id="wbn-database-mining-flash-report-fleet-prod"></a>

#### `MINING_FLASH_REPORT_FLEET_PROD`

**Rows:** 108  |  **Columns:** 8  |  **DATE:** 2025-11-28 00:00:00 → 2025-11-30 00:00:00

**Columns:** `DATE` datetime, `DEPOSIT` nvarchar(255), `CONTRACTOR` nvarchar(255), `SHIFT` float, `EXC ID` nvarchar(255), `MATERIAL` nvarchar(255), `ACT PRODUCTIVITY` float, `ACT DISTANCE` float

**Sample rows**:

| DATE | DEPOSIT | CONTRACTOR | SHIFT | EXC ID | MATERIAL | ACT PRODUCTIVITY | ACT DISTANCE |
|---|---|---|---|---|---|---|---|
| 2025-11-28T00:00:00.000 | KRENE | PPP | 1.0 | EX-466 | WST | 1715.0 | 940.625 |
| 2025-11-28T00:00:00.000 | KRENE | PPP | 1.0 | EX-501 | SAP | 2450.0 | 800.0 |
| 2025-11-28T00:00:00.000 | KRENE | PPP | 1.0 | EX-501 | WST | 560.0 | 800.0 |
| 2025-11-28T00:00:00.000 | KRENE | PPP | 1.0 | EX-502 | SAP | 3430.0 | 836.3636363636 |
| 2025-11-28T00:00:00.000 | KRENE | PPP | 1.0 | EX-502 | WST | 175.0 | 800.0 |

<a id="wbn-database-mining-flash-report-equipment"></a>

#### `MINING_FLASH_REPORT_EQUIPMENT`

**Rows:** 102  |  **Columns:** 9  |  **DATE:** 2025-11-28 00:00:00 → 2025-11-30 00:00:00

**Columns:** `DATE` datetime, `DEPOSIT` nvarchar(255), `CONTRACTOR` nvarchar(255), `SHIFT` float, `ACTIVITY` nvarchar(255), `UNIT TYPE` nvarchar(255), `RUNNING` float, `BREAKDOWN` float, `STANDBY` float

**Identifier vocabularies:**

- `UNIT TYPE` — 13 distinct. e.g. `ADT`, `COMPACTOR`, `DOZER`, `DT`, `EXC 20T`, `EXC 30T`, `EXC 40T`, `EXC LONGARM`, `FLEET MINING`, `GRADER`, `GRAPPLE`, `LOADER`

**Sample rows**:

| DATE | DEPOSIT | CONTRACTOR | SHIFT | ACTIVITY | UNIT TYPE | RUNNING | BREAKDOWN | STANDBY |
|---|---|---|---|---|---|---|---|---|
| 2025-11-28T00:00:00.000 | KRENE | PPP | 1.0 | MINING | FLEET MINING | 8.0 | 2.0 | 1.0 |
| 2025-11-28T00:00:00.000 | KRENE | PPP | 1.0 | HAULER | ADT | 28.0 | 8.0 | 0.0 |
| 2025-11-28T00:00:00.000 | KRENE | PPP | 1.0 | SUPPORT | EXC 20T | 7.0 | 3.0 | 1.0 |
| 2025-11-28T00:00:00.000 | KRENE | PPP | 1.0 | SUPPORT | EXC 30T | 4.0 | 1.0 | 1.0 |
| 2025-11-28T00:00:00.000 | KRENE | PPP | 1.0 | SUPPORT | EXC 40T | 2.0 | 1.0 | 1.0 |

<a id="wbn-database-blasting-remaining"></a>

#### `BLASTING_REMAINING`

**Rows:** 98  |  **Columns:** 7  |  **DATE_REMAINING_BCM:** 2026-05-27 00:00:00 → 2026-05-27 00:00:00

**Columns:** `DEPOSIT` nvarchar(255), `DATE_REMAINING_BCM` datetime, `CONTRACTOR` nvarchar(255), `MATERIAL` nvarchar(255), `AREA_PIT` nvarchar(255), `ID_BLASTING` float, `REMAIN_BCM` float

**Sample rows**:

| DEPOSIT | DATE_REMAINING_BCM | CONTRACTOR | MATERIAL | AREA_PIT | ID_BLASTING | REMAIN_BCM |
|---|---|---|---|---|---|---|
| Kaorahai | 2026-05-27T00:00:00.000 | RSF | Quarry | KR3 | 71.0 | 12804.334 |
| Tofu | 2026-05-27T00:00:00.000 | SMA | Quarry | TOFU1 | 82.0 | 4341.687 |
| Tofu | 2026-05-27T00:00:00.000 | STM | Quarry | TOFU1 | 83.0 | 9681.079 |
| Kaorahai | 2026-05-27T00:00:00.000 | PP QUARRY | Quarry | KR3 | 67.0 | 11693.974 |
| BLB | 2026-05-27T00:00:00.000 | RIM | Quarry | BLB5 | 67.0 | 4041.37 |

<a id="wbn-database-contractor-deposit"></a>

#### `CONTRACTOR_DEPOSIT`

**Rows:** 84  |  **Columns:** 4

**Columns:** `ID` int, `CONTRACTOR` nvarchar(50), `DEPOSIT` nvarchar(50), `SHIFT` nvarchar(50)

**Sample rows**:

| ID | CONTRACTOR | DEPOSIT | SHIFT |
|---|---|---|---|
| 1 | STM | KR | DS |
| 2 | STM | TF | DS |
| 3 | STM | CSW | DS |
| 4 | STM | CAS | DS |
| 5 | STM | BLB | DS |

<a id="wbn-database-equipments-works"></a>

#### `EQUIPMENTS_WORKS`

**Rows:** 82  |  **Columns:** 14  |  **DATE:** 2024-09-06 → 2024-10-14

**Columns:** `ID` int, `CONTRACTOR` nvarchar(50), `DATE` date, `SHIFT` int, `ID_EQ` nvarchar(50), `WORK_DONE` nvarchar(255), `WORK_CONTEXT` nvarchar(255), `ISSUE_DETAILS` nvarchar(255), `ISSUE_DATE_START` date, `HOUR_METER` float, `COMPARTMENT` nvarchar(50), `PART_CHANGED` nvarchar(50), `PART_REPAIRED` nvarchar(50), `REMARK` nvarchar(255)

**Sample rows**:

| ID | CONTRACTOR | DATE | SHIFT | ID_EQ | WORK_DONE | WORK_CONTEXT | ISSUE_DETAILS | ISSUE_DATE_START | HOUR_METER | COMPARTMENT | PART_CHANGED | PART_REPAIRED | REMARK |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SMA | 2024-09-25T00:00:00.000 |  | MG09 | BOLT TYRE POS 2 BROKEN | BREAKDOWN |  | 2024-08-18T00:00:00.000 | 2501.0 | TYRE | TYRE | TYRE |  |
| 2 | SMA | 2024-09-06T00:00:00.000 |  | DZ16 | RECOIL SPRING LH BROKEN | BREAKDOWN |  | 2024-09-05T00:00:00.000 | 2879.8 | UNDERCARRIAGE | UNDERCARRIAGE | UNDERCARRIAGE |  |
| 3 | SMA |  |  | DT16 | VESSEL DUMP PROBLEM | BREAKDOWN | *CHECK CONDITION UNIT *REPLACE VESSEL … | 2024-04-16T00:00:00.000 | 18225.0 | DUMP BODY | DUMP BODY | DUMP BODY |  |
| 4 | SMA | 2024-09-20T00:00:00.000 |  | DZ23 | OIL LEAK AREA FINAL DRIVE | BREAKDOWN |  | 2024-08-07T00:00:00.000 | 9378.2 | FINAL DRIVE | FINAL DRIVE | FINAL DRIVE |  |
| 5 | SMA | 2024-09-06T00:00:00.000 |  | DT41 | KING PIN PROBLEM & PM 1000 HRS SERVICE | PREVENTIVE MAINTENANCE | *CHECK CONDITION UNIT *CARRY OUT PM SE… | 2024-09-05T00:00:00.000 | 17405.0 | PREVENTIVE MAINTENANCE | PREVENTIVE MAINTENANCE | PREVENTIVE MAINTENANCE |  |

<a id="wbn-database-wbn-database-procedure-queue"></a>

#### `WBN_DATABASE_PROCEDURE_QUEUE`

**Rows:** 79  |  **Columns:** 3

**Columns:** `PROCEDURE_NAME` nvarchar(100), `PROCEDURE_STATUS` nvarchar(50), `LAST_EXECUTED` datetime

**Sample rows**:

| PROCEDURE_NAME | PROCEDURE_STATUS | LAST_EXECUTED |
|---|---|---|
| autoQC_STOCK_ALL_VIA_ALLupdate | Completed | 2025-05-12T17:30:13.443 |
| autoQC_STOCK_ALL_VIA_ALLupdate | Completed | 2025-05-13T17:30:16.120 |
| autoQC_STOCK_ALL_VIA_ALLupdate | Completed | 2025-05-14T11:30:12.950 |
| autoQC_STOCK_ALL_VIA_ALLupdate | Completed | 2025-05-14T17:30:12.510 |
| autoQC_STOCK_ALL_VIA_ALLupdate | Completed | 2025-05-15T11:30:12.710 |

<a id="wbn-database-team-plan"></a>

#### `TEAM_PLAN`

**Rows:** 78  |  **Columns:** 8  |  **DATE:** 2024-12-29 00:00:00 → 2025-02-14 00:00:00

**Columns:** `ID` int, `DATE` datetime, `LOCATION_TYPE` nvarchar(255), `LOCATION_AREA` nvarchar(255), `DS_NAME1` nvarchar(255), `DS_NAME2` nvarchar(255), `NS_NAME1` nvarchar(255), `NS_NAME2` nvarchar(255)

**Sample rows**:

| ID | DATE | LOCATION_TYPE | LOCATION_AREA | DS_NAME1 | DS_NAME2 | NS_NAME1 | NS_NAME2 |
|---|---|---|---|---|---|---|---|
| 1 | 2024-12-29T00:00:00.000 | ROAD | KR | GAT BURNAMA |  |  |  |
| 2 | 2024-12-29T00:00:00.000 | ROAD | TF | ANANG |  |  |  |
| 3 | 2024-12-29T00:00:00.000 | ROAD | BLB | IVAN |  |  |  |
| 4 | 2024-12-29T00:00:00.000 | POS | 14 | YUFARDI ABBAS |  |  |  |
| 5 | 2024-12-29T00:00:00.000 | POS | 12 | ICHAL |  |  |  |

<a id="wbn-database-companies"></a>

#### `COMPANIES`

**Rows:** 73  |  **Columns:** 7

**Columns:** `COMPANY` nvarchar(255), `DESCRIPTION` nvarchar(255), `PLANT` nvarchar(255), `PLANT_TYPE` nvarchar(50), `PLANT_LOCATION` nvarchar(50), `COMMENT` nvarchar(255), `AVG_Ni` float

**Sample rows**:

| COMPANY | DESCRIPTION | PLANT | PLANT_TYPE | PLANT_LOCATION | COMMENT | AVG_Ni |
|---|---|---|---|---|---|---|
| AJK | ARIE JAYA KENCANA |  |  |  |  |  |
| AMI | PT. ANDALAN METAL INDUSTRY  | F2 | FENI | KM0 |  | 1.495399448 |
| ANI | PT. ANGEL NICKEL INDUSTRY | G | FENI | KM0 |  | 1.499291767 |
| BSE | PT. BLUE SPARKING ENERGY  | BSE | HPAL |  |  |  |
| CMI | PT. COSAN METAL INDUSTRY  | U2 | FENI | KM15 |  | 1.725908031 |

<a id="wbn-database-daronnetemp"></a>

#### `DARONNEtemp`

**Rows:** 61  |  **Columns:** 3  |  **DATE:** 2026-05-01 00:00:00 → 2026-06-30 00:00:00

**Columns:** `DATE` datetime, `WMT_TARGET` float, `CUM_WMT_TARGET` float

**Sample rows**:

| DATE | WMT_TARGET | CUM_WMT_TARGET |
|---|---|---|
| 2026-05-01T00:00:00.000 | 38873.82 | 38873.82 |
| 2026-05-02T00:00:00.000 | 7873.18 | 46747.0 |
| 2026-05-03T00:00:00.000 | 0.0 | 46747.0 |
| 2026-05-04T00:00:00.000 | 0.0 | 46747.0 |
| 2026-05-05T00:00:00.000 | 0.0 | 46747.0 |

<a id="wbn-database-ni-color"></a>

#### `Ni_COLOR`

**Rows:** 45  |  **Columns:** 3

**Columns:** `Ni_CLASS` float, `COLOR` nvarchar(255), `COLOR_HEXA` nvarchar(255)

**Sample rows**:

| Ni_CLASS | COLOR | COLOR_HEXA |
|---|---|---|
| 0.0 |  | #FF7F00 |
| 0.1 |  | #FF7F00 |
| 0.2 |  | #FF7F00 |
| 0.3 |  | #FF7F00 |
| 0.4 |  | #FF7F00 |

<a id="wbn-database-mining-flash-report-production"></a>

#### `MINING_FLASH_REPORT_PRODUCTION`

**Rows:** 42  |  **Columns:** 8  |  **DATE:** 2025-11-28 00:00:00 → 2025-11-30 00:00:00

**Columns:** `DATE` datetime, `DEPOSIT` nvarchar(255), `CONTRACTOR` nvarchar(255), `SHIFT` float, `MATERIAL` nvarchar(255), `PLANNED PROD` float, `ACTUAL PROD` float, `DEVIATON` float

**Sample rows**:

| DATE | DEPOSIT | CONTRACTOR | SHIFT | MATERIAL | PLANNED PROD | ACTUAL PROD | DEVIATON |
|---|---|---|---|---|---|---|---|
| 2025-11-28T00:00:00.000 | KRENE | PPP | 1.0 | SAP | 13850.0 | 13090.0 | 760.0 |
| 2025-11-28T00:00:00.000 | KRENE | PPP | 1.0 | WCO | 1837.0806451613 | 0.0 | 1837.0806451613 |
| 2025-11-28T00:00:00.000 | KRENE | PPP | 1.0 | LIM | 2132.8548387097 | 0.0 | 2132.8548387097 |
| 2025-11-28T00:00:00.000 | KRENE | PPP | 1.0 | WST | 4727.2419354839 | 7385.0 | -2657.7580645161 |
| 2025-11-28T00:00:00.000 | KRENE | PPP | 1.0 | TS AND BMS | 503.4757440076 | 3780.0 | -3276.5242559924 |

<a id="wbn-database-activities-mat"></a>

#### `ACTIVITIES_MAT`

**Rows:** 39  |  **Columns:** 4

**Columns:** `ACTIVITY` nvarchar(20), `MATERIAL` nvarchar(10), `ORIGIN_TYPE` nvarchar(50), `DESTINATION_TYPE` nvarchar(50)

**Sample rows**:

| ACTIVITY | MATERIAL | ORIGIN_TYPE | DESTINATION_TYPE |
|---|---|---|---|
| BEDDING | SAP |  |  |
| CONSTRUCTION | BASALT | CRUSHER | INFRA |
| CONSTRUCTION | QUARRY | CRUSHER | INFRA |
| DIRECT | CS | CRUSHER | YARD |
| DIRECT | LIM | TOS | YARD |

<a id="wbn-database-location-wb-sh"></a>

#### `LOCATION_WB_SH`

**Rows:** 39  |  **Columns:** 6

**Columns:** `ITEM_TYPE` nvarchar(50), `ITEM_ID` nvarchar(50), `COMPANY` nvarchar(50), `LOCATION` nvarchar(50), `KM_LOADED` float, `KM_EMPTY` float

**Identifier vocabularies:**

- `ITEM_ID` — 39 distinct. e.g. `BLB`, `CBB`, `KR`, `POS 10`, `POS 11`, `POS 12`, `POS 14`, `POS 6`, `SH04`, `SH05`, `SH06`, `SH07`

**Sample rows**:

| ITEM_TYPE | ITEM_ID | COMPANY | LOCATION | KM_LOADED | KM_EMPTY |
|---|---|---|---|---|---|
| PIT | BLB | WBN | BLB | 20.0 | 20.0 |
| PIT | CBB | WBN | CBB | 15.0 | 15.0 |
| PIT | KR | WBN | KR | 37.0 | 37.0 |
| POS | POS 10 | WBN | KR | 17.0 | 17.0 |
| POS | POS 11 | WBN | KR | 17.0 | 17.0 |

<a id="wbn-database-dt-density-hr-model-"></a>

#### `DT_DENSITY_HR_MODEL$`

**Rows:** 37  |  **Columns:** 15  |  **DATE:** 2025-09-13 00:00:00 → 2025-09-13 00:00:00

**Columns:** `ORIGIN raw` nvarchar(255), `ORIGIN` nvarchar(255), `DESTINATION` nvarchar(255), `CONTRACTOR` nvarchar(255), `DATE` datetime, `TYPE` nvarchar(255), `MATERIAL` nvarchar(255), `NB_SHIFT` float, `WMT` float, `RIT` float, `NB_DT` float, `TF` float, `DT PLAN` nvarchar(255), `TARGET TRIP` float, `PLAN WMT` nvarchar(255)

**Sample rows** (first 14 of 15 columns):

| ORIGIN raw | ORIGIN | DESTINATION | CONTRACTOR | DATE | TYPE | MATERIAL | NB_SHIFT | WMT | RIT | NB_DT | TF | DT PLAN | TARGET TRIP |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TF | TF | POS 12 | CKB | 2025-09-13T00:00:00.000 | HAULAGE | SAP | 2.0 | 6627.44 | 148.0 | 45.0 | 45.0 |  | 1.6 |
| KRENE | KRENE | POS 12 | GMG | 2025-09-13T00:00:00.000 | HAULAGE | SAP | 2.0 | 2155.78 | 65.0 | 10.0 | 36.0 |  | 5.0 |
| BLB | BLB | FENI KM15 | HJS | 2025-09-13T00:00:00.000 | DIRECT | SAP | 1.0 | 989.2 | 24.0 | 10.0 | 31.0 |  | 3.0 |
| BLB | BLB | POS 14 | HJS | 2025-09-13T00:00:00.000 | HAULAGE | SAP | 2.0 | 1786.29 | 46.0 | 5.0 | 31.0 |  | 5.0 |
| BLB | BLB | FENI | HJS | 2025-09-13T00:00:00.000 | DIRECT | SAP | 2.0 | 2331.62 | 49.0 | 10.0 | 31.0 |  | 3.0 |

<a id="wbn-database-team"></a>

#### `TEAM`

**Rows:** 34  |  **Columns:** 5

**Columns:** `ID` int, `NAME` nvarchar(255), `SUPERVISE` nvarchar(255), `CONTACT` nvarchar(255), `AREA` nvarchar(255)

**Sample rows**:

| ID | NAME | SUPERVISE | CONTACT | AREA |
|---|---|---|---|---|
| 1 | AINUL SAPUTRA |  |  | COASTAL |
| 2 | ANANG |  |  | KR |
| 3 | DENAL |  |  | KR |
| 4 | FADLI ABDULLAH |  |  | TF |
| 5 | FANDI |  |  | KR |

<a id="wbn-database-mining-eq-target-3mrmp"></a>

#### `MINING_EQ_TARGET_3MRMP`

**Rows:** 30  |  **Columns:** 5

**Columns:** `YEAR` float, `MONTH` float, `CONTRACTOR` nvarchar(255), `EQ_CLASS` nvarchar(255), `NUMBER` float

**Sample rows**:

| YEAR | MONTH | CONTRACTOR | EQ_CLASS | NUMBER |
|---|---|---|---|---|
| 2025.0 | 4.0 | HJS | EXC MINING | 7.0 |
| 2025.0 | 4.0 | HJS | ADT MINING | 29.0 |
| 2025.0 | 4.0 | PPP | EXC MINING | 6.0 |
| 2025.0 | 4.0 | PPP | ADT MINING | 24.0 |
| 2025.0 | 4.0 | RIM | EXC MINING | 18.0 |

<a id="wbn-database-all-hr-km-sections"></a>

#### `ALL_HR_KM_SECTIONS`

**Rows:** 27  |  **Columns:** 8

> The 27 named road sections with KM_START/KM_END and their origin/destination junctions. The authoritative segment vocabulary.

**Columns:** `ROAD_NAME` nvarchar(255), `ORIGIN` nvarchar(255), `DESTINATION` nvarchar(255), `SECTION_NAME` nvarchar(255), `SECTION_ID` nvarchar(255), `KM_START` float, `KM_END` float, `APPROX_DISTANCE` float

**Identifier vocabularies:**

- `SECTION_ID` — 27 distinct. e.g. `BLB KM17 - KM20`, `BLB KM2,5 - KM5,7`, `BLB KM5,7 - KM10`, `CBB KM15 - KM17`, `CBB KM7 - KM9`, `CBB KM9 - KM15`, `CBBB KM15 - KM17,5`, `CRD KM0 - KM2,5`, `CRD KM2,5 - KM5,5`, `CRD KM5,5 - KM7`, `CSW KM3 - KM4`, `CSW KM4 - KM5,7`

**Sample rows**:

| ROAD_NAME | ORIGIN | DESTINATION | SECTION_NAME | SECTION_ID | KM_START | KM_END | APPROX_DISTANCE |
|---|---|---|---|---|---|---|---|
| Coastal Road | FENI | CRD/BLB ROAD JUNCTION | FENI - CRD/BLB ROAD JUNCTION | CRD KM0 - KM2,5 | 0.0 | 2.5 | 2.5 |
| Coastal Road | CRD/BLB ROAD JUNCTION | HUAFEI.C01 JUNCTION | CRD/BLB ROAD JUNCTION - HUAFEI.C01 JUN… | CRD KM2,5 - KM5,5 | 2.5 | 5.5 | 3.0 |
| Coastal Road | HUAFEI.C01 JUNCTION | T JUNCTION | HUAFEI.C01 JUNCTION - T JUNCTION | CRD KM5,5 - KM7 | 5.5 | 7.0 | 1.5 |
| Coastal Sakewest | FENI | COASTAL CRUSHER JUNCTION | FENI - COASTAL CRUSHER JUNCTION | CSW KM3 - KM4 | 3.0 | 4.0 | 1.0 |
| Coastal Sakewest | COASTAL CRUSHER JUNCTION | POS 14 | COASTAL CRUSHER JUNCTION - POS 14 | CSW KM4 - KM5,7 | 4.0 | 5.7 | 1.7 |

<a id="wbn-database-assay-class"></a>

#### `ASSAY_CLASS`

**Rows:** 27  |  **Columns:** 8  |  **date:** 2020-01-01 → 2025-01-01

**Columns:** `id` int, `date` date, `cat` nvarchar(255), `material` nvarchar(255), `element` nvarchar(255), `ore_class` nvarchar(255), `ore_class_description` nvarchar(255), `grade` float

**Sample rows**:

| id | date | cat | material | element | ore_class | ore_class_description | grade |
|---|---|---|---|---|---|---|---|
| 1 | 2025-01-01T00:00:00.000 | CAT | SAP | Ni | VHGS | Very High Grade Saprolite | 1.7 |
| 2 | 2025-01-01T00:00:00.000 | CAT | SAP | Ni | HGS | High Grade Saprolite | 1.4 |
| 3 | 2025-01-01T00:00:00.000 | CAT | SAP | Ni | WCO | Waste Conservation Ore | 1.2 |
| 5 | 2025-01-01T00:00:00.000 | CAT | SAP | Ni | WST | Waste | 0.0 |
| 6 | 2025-01-01T00:00:00.000 | CAT | SAP | Fe | VLFe | Very Low Iron | 0.0 |

<a id="wbn-database-shape-stock-area"></a>

#### `SHAPE_STOCK_AREA`

**Rows:** 26  |  **Columns:** 5

**Columns:** `TYPE` varchar(-1), `AREA` varchar(-1), `STOCK_AREA` varchar(-1), `Area_ha` float, `GEOM` geography(-1)

*Sample unavailable: could not serialise*

<a id="wbn-database-hrm-request-material"></a>

#### `HRM_REQUEST_MATERIAL`

**Rows:** 25  |  **Columns:** 10  |  **DATE:** 2024-11-08 → 2024-11-09

**Columns:** `ID` int, `DATE` date, `SHIFT` int, `ORIGIN` nvarchar(50), `TEAM` nchar(50), `CONTRACTOR` nchar(10), `PROJECT` nvarchar(-1), `MATERIAL` nchar(50), `BCM` float, `NB_DT` int

**Sample rows**:

| ID | DATE | SHIFT | ORIGIN | TEAM | CONTRACTOR | PROJECT | MATERIAL | BCM | NB_DT |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2024-11-08T00:00:00.000 | 1 | LOYPOLOY | HRM/Construction                      … | RIM        | KM9 | Laminating                            … | 300.0 | 1 |
| 2 | 2024-11-08T00:00:00.000 | 2 | LOYPOLOY | HRM/Construction                      … | RIM        | KM9 | Laminating                            … | 300.0 | 1 |
| 3 | 2024-11-09T00:00:00.000 | 1 | LOYPOLOY | Civil Construction                    … | STM        | Coolstorage KM38 | 0-1                                   … | 12.0 | 1 |
| 4 | 2024-11-08T00:00:00.000 | 1 | LOYPOLOY | HRM/Construction                      … | RIM        | KM38-42 | Base Course                           … | 200.0 | 8 |
| 5 | 2024-11-08T00:00:00.000 | 2 | LOYPOLOY | HRM/Construction                      … | RIM        | KM38-42 | Base Course                           … | 200.0 | 8 |

<a id="wbn-database-team-fb"></a>

#### `TEAM_FB`

**Rows:** 25  |  **Columns:** 6  |  **DATE_START:** 2025-08-07 → 2026-05-01

**Columns:** `ID` int, `NAME` nvarchar(50), `DATE_START` date, `DATE_END` date, `VALIDATED` nvarchar(50), `REMARK` nvarchar(255)

**Sample rows**:

| ID | NAME | DATE_START | DATE_END | VALIDATED | REMARK |
|---|---|---|---|---|---|
| 4 | JULIEN | 2025-09-29T00:00:00.000 | 2025-10-19T00:00:00.000 | YES |  |
| 6 | THOMAS | 2025-08-07T00:00:00.000 | 2025-08-30T00:00:00.000 | YES |  |
| 9 | CINDHA | 2025-09-15T00:00:00.000 | 2025-09-29T00:00:00.000 | YES |  |
| 10 | CINDHA | 2026-01-11T00:00:00.000 | 2026-02-01T00:00:00.000 | NO |  |
| 11 | HUGO | 2025-09-14T00:00:00.000 | 2025-10-05T00:00:00.000 | YES |  |

<a id="wbn-database-pos-possibility-for-haulage"></a>

#### `POS POSSIBILITY For HAULAGE`

**Rows:** 23  |  **Columns:** 3

**Columns:** `ID` int, `TOS LOCATION` nvarchar(50), `POS LOCATION` nvarchar(50)

**Sample rows**:

| ID | TOS LOCATION | POS LOCATION |
|---|---|---|
| 1 | CBB | POS BIRI-BIRI |
| 2 | CBB | POS UNI-UNI |
| 3 | CBB | POS GOMDI |
| 4 | CBB | EOS |
| 5 | CBB | POS 14 |

<a id="wbn-database-request-sales-late-2025"></a>

#### `REQUEST_SALES_LATE_2025`

**Rows:** 18  |  **Columns:** 3  |  **REQUEST_DATE:** 2025-11-01 00:00:00 → 2025-11-01 00:00:00

**Columns:** `STOCK_ID` nvarchar(50), `REQUEST` nvarchar(50), `REQUEST_DATE` datetime

**Identifier vocabularies:**

- `STOCK_ID` — 18 distinct. e.g. `ABM.346`, `ACM.386`, `ACM.509`, `ADM.334`, `ADM.574`, `ADM.618`, `ADM.662`, `LGS.KR280`, `POS.WCO.031`, `POS.WCO.037`, `POS.WCO.038`, `POS.WCO.040`

**Sample rows**:

| STOCK_ID | REQUEST | REQUEST_DATE |
|---|---|---|
| ABM.346 | SOLD | 2025-11-01T00:00:00.000 |
| ACM.386 | SOLD | 2025-11-01T00:00:00.000 |
| ACM.509 | SOLD | 2025-11-01T00:00:00.000 |
| ADM.334 | SOLD | 2025-11-01T00:00:00.000 |
| ADM.574 | SOLD | 2025-11-01T00:00:00.000 |

<a id="wbn-database-block-id-xyparam"></a>

#### `BLOCK_ID_XYPARAM`

**Rows:** 16  |  **Columns:** 8

**Columns:** `PIT` nvarchar(255), `B_XORIGIN` float, `B_INCREMENT` float, `S_YORIGIN` float, `S_INCREMENT` float, `N_ZORIGIN` float, `N_INCREMENT` float, `INFO` nvarchar(255)

**Sample rows**:

| PIT | B_XORIGIN | B_INCREMENT | S_YORIGIN | S_INCREMENT | N_ZORIGIN | N_INCREMENT | INFO |
|---|---|---|---|---|---|---|---|
| CBB | 380312.5 | 12.5 | 60225.0 | -12.5 | 1.0 | 2.0 | EPSG:32652 (UTM 52N ): X,Y= origin + i… |
| CUU | 381100.0 | 12.5 | 54975.0 | -12.5 | 1.0 | 2.0 | EPSG:32652 (UTM 52N ): X,Y= origin + i… |
| CSW | 383950.0 | 12.5 | 55775.0 | -12.5 | 1.0 | 2.0 | EPSG:32652 (UTM 52N ): X,Y= origin + i… |
| CAS5 | 385425.0 | 12.5 | 55212.5 | -12.5 | 1.0 | 2.0 | EPSG:32652 (UTM 52N ): X,Y= origin + i… |
| CAS6 | 384325.0 | 12.5 | 56975.0 | -12.5 | 1.0 | 2.0 | EPSG:32652 (UTM 52N ): X,Y= origin + i… |

<a id="wbn-database-crusher-survey-loypoloy"></a>

#### `CRUSHER_SURVEY_LOYPOLOY`

**Rows:** 16  |  **Columns:** 13  |  **DATE:** 2024-10-13 → 2024-10-13

**Columns:** `ID` int, `DATE` date, `TYPE_OF_SURVEY` nvarchar(50), `SURVEY_WEEK` nvarchar(50), `MATERIAL_ID` nvarchar(50), `SURVEY_METHOD` nvarchar(50), `LOCATION` nvarchar(50), `VOLUME (LCM)` float, `VOLUME (BCM)` float, `DENSITY` float, `ADJUSTED_DENSITY` float, `WMT` float, `STOCK_TYPE` nvarchar(50)

**Identifier vocabularies:**

- `MATERIAL_ID` — 8 distinct. e.g. `0-1 Line 3`, `1-2 Line 1`, `1-2 Line 3`, `2-3 Line 1`, `2-3 Line 3`, `BC 2-3 Line 3`, `BC 5-7 Line 2`, `TOS`

**Sample rows**:

| ID | DATE | TYPE_OF_SURVEY | SURVEY_WEEK | MATERIAL_ID | SURVEY_METHOD | LOCATION | VOLUME (LCM) | VOLUME (BCM) | DENSITY | ADJUSTED_DENSITY | WMT | STOCK_TYPE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 8 | 2024-10-13T00:00:00.000 | PONCTUAL |  | TOS | Ground | CRUSHER LOYPOLOY KM16 | 5415.534 | 5415.534 |  |  |  | STOCK TOS |
| 9 | 2024-10-13T00:00:00.000 | PONCTUAL |  | TOS | Ground | CRUSHER LOYPOLOY KM16 | 977.984 | 977.984 |  |  |  | STOCK TOS |
| 10 | 2024-10-13T00:00:00.000 | PONCTUAL |  | BC 2-3 Line 3 | Ground | CRUSHER LOYPOLOY KM16 | 10.105 | 10.105 |  |  |  | STOCK BLEND |
| 11 | 2024-10-13T00:00:00.000 | PONCTUAL |  | BC 2-3 Line 3 | Ground | CRUSHER LOYPOLOY KM16 | 4.507 | 4.507 |  |  |  | STOCK BLEND |
| 12 | 2024-10-13T00:00:00.000 | PONCTUAL |  | 1-2 Line 3 | Ground | CRUSHER LOYPOLOY KM16 | 1.56 | 1.56 |  |  |  | STOCK CRUSHED |

<a id="wbn-database-activities"></a>

#### `ACTIVITIES`

**Rows:** 13  |  **Columns:** 3

**Columns:** `ACTIVITY` nvarchar(20), `ORIGIN_TYPE` nvarchar(50), `DESTINATION_TYPE` nvarchar(50)

**Sample rows**:

| ACTIVITY | ORIGIN_TYPE | DESTINATION_TYPE |
|---|---|---|
| BEDDING |  |  |
| CONSTRUCTION | CRUSHER | INFRA |
| DIRECT | TOS | YARD |
| DIRECT IWIP DATA | TOS | YARD |
| HAULAGE | TOS | POS |

<a id="wbn-database-haulage-contractors"></a>

#### `HAULAGE CONTRACTORS`

**Rows:** 11  |  **Columns:** 2

**Columns:** `ID` int, `CONTRACTOR` nvarchar(50)

**Sample rows**:

| ID | CONTRACTOR |
|---|---|
| 1 | GMG |
| 2 | STM |
| 3 | SMA |
| 4 | PPP |
| 5 | RIM |

<a id="wbn-database-supervision-safety-actions"></a>

#### `SUPERVISION_SAFETY_ACTIONS`

**Rows:** 6  |  **Columns:** 23  |  **ACTION_DUE_DATE:** 2025-09-10 00:00:00 → 2025-09-30 00:00:00

**Columns:** `ID` int, `EVENT_NO` int, `HPO_HPI` nvarchar(50), `HPO_HPI_CLASSIFICATION` nvarchar(50), `ACTION_ID` float, `EVENT_TITLE` nvarchar(-1), `EVENT_DESCRIPTION` nvarchar(-1), `ACTION_PRIORITY` nvarchar(50), `ACTION_CORRECTIVE` nvarchar(-1), `ACTION_DEPARTMENT` nvarchar(-1), `ACTION_ASSIGN_TO` nvarchar(-1), `ACTION_DUE_DATE` datetime, `ACTION_PROGRESS_%` float, `ACTION_STATUS` nvarchar(-1), `ACTION_VERIFICATION_DATE` datetime, `ACTION_OUTSTANDING_DAYS` nvarchar(-1), `ACTION_OWNER` nvarchar(-1), `ACTION_OWNER_POSITION` nvarchar(-1), `ACTION_OWNER_DEPARTMENT` nvarchar(-1), `ACTION_RESPONSIBLE_SPT` nvarchar(-1), `ACTION_RESPONSIBLE_SPV` nvarchar(-1), `ACTION_REMARK` nvarchar(-1), `PHOTO_PATH` nvarchar(500)

**Sample rows** (first 14 of 23 columns):

| ID | EVENT_NO | HPO_HPI | HPO_HPI_CLASSIFICATION | ACTION_ID | EVENT_TITLE | EVENT_DESCRIPTION | ACTION_PRIORITY | ACTION_CORRECTIVE | ACTION_DEPARTMENT | ACTION_ASSIGN_TO | ACTION_DUE_DATE | ACTION_PROGRESS_% | ACTION_STATUS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 4 | 87193 | HPO | HPO | 78717.0 | No Safety Fence at KM 22 Safety Post | With the expansion of the Haul Road Wi… | MEDIUM | Install a new Fence along the ledge to… | TEST | Douglas, Douglas (60005842) | 2025-09-30T00:00:00.000 | 100.0 | OPEN |
| 5 | 86687 | HPI | Property Damage | 78801.0 | DT 6626 Contact With CT B683 | On Saturday, August 2, 2025, at 3:30 P… | MEDIUM | De-commission Huafei towing truck from… | Administration | SITORUS, Irwan Edel F. (EXTSHAL0019) | 2025-09-15T00:00:00.000 | 10.0 | OPEN |
| 6 | 88126 | Incident non HPI | First Aid | 79287.0 | Leg Injury Due to Jack Slippage | The victim was working to install an e… | HIGH | DDT Training | Haulage Operation | RAHUL DHIMAN (RAHUL) | 2025-09-10T00:00:00.000 | 20.0 | OPEN |
| 7 | 88126 | Incident non HPI | First Aid | 79287.0 | Leg Injury Due to Jack Slippage | The victim was working to install an e… | HIGH | DDT Training | Haulage Operation | RAHUL DHIMAN (RAHUL) | 2025-09-11T00:00:00.000 | 0.0 | OPEN |
| 8 | 89524 | Incident non HPI | First Aid | 79516.0 | Radiator Overheating Burn Incident | The driver of DT N441 stopped the unit… | Critical | Retrain all drivers on radiator risks … | HAULAGE OPERATION | RAHUL DHIMAN | 2025-09-15T00:00:00.000 | 0.0 | Open |

<a id="wbn-database-crusher-cf"></a>

#### `CRUSHER_CF`

**Rows:** 3  |  **Columns:** 3

**Columns:** `ID` int, `MATERIAL` nvarchar(255), `CF` float

**Sample rows**:

| ID | MATERIAL | CF |
|---|---|---|
| 1 | CS | 1.12 |
| 2 | SS1 | 1.21 |
| 3 | SS2 | 1.21 |

<a id="wbn-database-haulage-adj"></a>

#### `HAULAGE_ADJ`

**Rows:** 3  |  **Columns:** 8  |  **DATE:** 2025-02-01 00:00:00 → 2025-02-01 00:00:00

**Columns:** `YEAR` float, `MONTH` float, `DATE` datetime, `MATERIAL_CLASS` nvarchar(255), `WMT_SURVEY` float, `WMT_HAULAGE` float, `WMT_TC` float, `ADJ_TC` float

**Sample rows**:

| YEAR | MONTH | DATE | MATERIAL_CLASS | WMT_SURVEY | WMT_HAULAGE | WMT_TC | ADJ_TC |
|---|---|---|---|---|---|---|---|
| 2025.0 | 2.0 | 2025-02-01T00:00:00.000 | HGS | 1951143.0215260943 | 1975839.124233704 |  | 0.87 |
| 2025.0 | 2.0 | 2025-02-01T00:00:00.000 | LGS | 365833.5282214447 | 375319.1250000001 |  | 0.86 |
| 2025.0 | 2.0 | 2025-02-01T00:00:00.000 | CS |  |  |  |  |

<a id="wbn-database-autoqc-cf-bm-prop"></a>

#### `autoQC_CF_BM_PROP`

**Rows:** 0  |  **Columns:** 17

**Columns:** `DATETIME` datetime, `ORIGIN_PIT` nvarchar(10), `MATERIAL` varchar(3), `BM_MC_PROP` float, `BMC_MC_PROP` float, `BM_Ni_PROP` float, `BMC_Ni_PROP` float, `BM_Fe_PROP` float, `BMC_Fe_PROP` float, `BM_SiO2_PROP` float, `BMC_SiO2_PROP` float, `BM_MgO_PROP` float, `BMC_MgO_PROP` float, `BM_Co_PROP` float, `BMC_Co_PROP` float, `BM_Cr2O3_PROP` float, `BMC_Cr2O3_PROP` float

*Empty table.*

<a id="wbn-database-blasting-production"></a>

#### `blasting_production`

**Rows:** 0  |  **Columns:** 19

**Columns:** `ID` int, `Contractor` nvarchar(255), `Year` float, `Month` nvarchar(255), `Week` float, `Date` datetime, `Shift` nvarchar(255), `Pit` nvarchar(255), `Sub_Pit` nvarchar(255), `Prod ID` nvarchar(255), `BM ID` nvarchar(255), `Class BM` nvarchar(255), `Rit` float, `TF` float, `Wmt` float, `Type` nvarchar(255), `TOS_pile` nvarchar(255), `Destination` nvarchar(255), `sample_id` nvarchar(255)

*Empty table.*

<a id="wbn-database-corrective-actions"></a>

#### `CORRECTIVE_ACTIONS`

**Rows:** 0  |  **Columns:** 12

**Columns:** `id` int, `safety_event_id` int, `action_text` varchar(-1), `status` varchar(50), `severity` varchar(20), `due_date` date, `completed_at` datetimeoffset, `owner_user_id` int, `owner_name` varchar(150), `owner_company` varchar(150), `created_at` datetimeoffset, `updated_at` datetimeoffset

*Empty table.*

<a id="wbn-database-daywork-request"></a>

#### `DAYWORK_REQUEST`

**Rows:** 0  |  **Columns:** 11

**Columns:** `ID` int, `SECTION` nvarchar(50), `DATE` date, `CONTRACTOR` nvarchar(50), `RESPONSIBLE` nvarchar(50), `TYPE` nvarchar(50), `DESCRIPTION` text(2147483647), `EXCA` int, `DT` int, `DOZER` int, `GRADER` int

*Empty table.*

<a id="wbn-database-fms-tos-status"></a>

#### `FMS_TOS_STATUS`

**Rows:** 0  |  **Columns:** 11

**Columns:** `UPDATE_DATE` datetime, `OBJECTID` bigint, `GLOBALID` nvarchar(50), `EDIT_DATE` datetime, `PILE_ID` nvarchar(50), `STOCK_AREA` nvarchar(50), `OLD_PILE` nvarchar(50), `STOCKPILE_TEAM` nvarchar(50), `DATE` date, `STATUS` nvarchar(50), `GEOM` geography(-1)

*Empty table.*

<a id="wbn-database-production-pit-mining-distance"></a>

#### `PRODUCTION_PIT_MINING_DISTANCE`

**Rows:** 0  |  **Columns:** 14

**Columns:** `ID` int, `CONTRACTOR` nvarchar(255), `DATE` date, `SHIFT` int, `PIT` nvarchar(255), `BLOCK_ID` nvarchar(255), `MATERIAL` nvarchar(255), `DESTINATION` nvarchar(255), `EXCAVATOR_ID` nvarchar(255), `RIT` float, `DISTANCE_KM` float, `WMT` float, `VOLUME_BCM` float, `REMARK` nvarchar(255)

*Empty table.*

<a id="wbn-database-start-lim-stock"></a>

#### `START LIM STOCK`

**Rows:** 0  |  **Columns:** 16

**Columns:** `ID` int, `DATE` datetime, `DOME` nvarchar(255), `WMT` float, `Ni` float, `Fe` float, `SM` float, `SiO2` float, `MgO` float, `Co` float, `Al2O3` float, `CaO` float, `Cr2O3` float, `MnO` float, `P2O5` float, `MC` float

*Empty table.*

<a id="wbn-database-team-profile"></a>

#### `TEAM_PROFILE`

**Rows:** 0  |  **Columns:** 12

**Columns:** `id` int, `user_id` int, `availability_pct` int, `workload_pct` int, `skills` varchar(-1), `contractor_company` varchar(150), `full_name` varchar(150), `email` varchar(100), `due_date` date, `completed_at` datetimeoffset, `created_at` datetimeoffset, `updated_at` datetimeoffset

*Empty table.*

<a id="wbn-database-temphaulage-iwip"></a>

#### `tempHAULAGE_IWIP`

**Rows:** 0  |  **Columns:** 1

**Columns:** `No` nvarchar(255)

*Empty table.*

<a id="wbn-database-tos"></a>

#### `TOS`

**Rows:** 0  |  **Columns:** 11

**Columns:** `UPDATE_DATE` datetime, `OBJECTID` bigint, `GLOBALID` nvarchar(50), `EDIT_DATE` datetime, `PILE_ID` nvarchar(50), `STOCK_AREA` nvarchar(50), `OLD_PILE` nvarchar(50), `STOCKPILE_TEAM` nvarchar(50), `DATE` date, `STATUS` nvarchar(50), `GEOM` geography(-1)

*Empty table.*

<a id="wbn-database-wbn-database-error-procedure"></a>

#### `WBN_DATABASE_ERROR_PROCEDURE`

**Rows:** 0  |  **Columns:** 8

**Columns:** `Id` int, `ErrorNumber` int, `ErrorSeverity` int, `ErrorState` int, `ErrorProcedure` nvarchar(200), `ErrorLine` int, `ErrorMessage` nvarchar(-1), `ErrorDate` datetime

*Empty table.*

### WBN_DATABASE — views (418)

<details><summary>Column lists for all 418 views</summary>

- **`3rd_PARTY_DUPLICATES_ANALYSIS`** (37 cols): `DOME_STATUS`, `ANALYSIS_DATE`, `CONTRACTOR`, `DOME`, `SUBLOT`, `MC`, `Ni`, `Co`, `MgO`, `CaO`, `Fe2O3`, `SiO2`, `Al2O3`, `Cr2O3`, `MnO`, `LOI`, `DEPOSIT`, `RIT`, `SAMPLE_R_WEIGHT`, `SAMPLE_E_WEIGHT`, `SAMPLE_TOT_WEIGHT`, `ID_SAMPLE`, `DUP_ANALYSIS_DATE`, `DUP_CONTRACTOR`, `TYPE_ASSAYS`, `MC_DUP`, `Ni_DUP`, `Co_DUP`, `MgO_DUP`, `CaO_DUP`, `Fe2O3_DUP`, `SiO2_DUP`, `Al2O3_DUP`, `Cr2O3_DUP`, `MnO_DUP`, `LOI_DUP`, `ID_SAMPLE_DUP`
- **`ARCGIS_EQUIPMENTS_INFO_APP`** (14 cols): `EQUIPMENT_ID`, `CONTRACTOR`, `OWNER`, `EQUIPMENT_TYPE`, `MANUFACTURER`, `MODEL`, `CAPACITY`, `NB_TYRES`, `BUILD_YEAR`, `DIVISION`, `COMMISSIONING_DATE`, `COMMISSIONING_EXPIRATION`, `COMMISSIONING_STATUS`, `COMMISIONING_REMAINING_DAYS`
- **`ASSAYS CONSOLIDATED`** (16 cols): `BLOCK ID`, `Ni`, `Fe`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `Fe2O3`, `MgO`, `MnO`, `P2O5`, `SiO2`, `SiO2/MgO`, `MC`, `DATA CHECK`, `DATE_TOS`
- **`ASSAYS CONSOLIDATED VIA BM`** (16 cols): `BLOCK ID`, `Ni`, `Fe`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `Fe2O3`, `MgO`, `MnO`, `P2O5`, `SiO2`, `SiO2/MgO`, `MC`, `DATA CHECK`, `DATE_TOS`
- **`ASSAYS SAMPLING BRIDGE`** (38 cols): `DOME_STATUS`, `CONTRACTOR_STATUS`, `DATE`, `JOB_ID`, `CONTRACTOR`, `TYPE_ASSAYS`, `DOME`, `ARRIVAL_DATE`, `ANALYSIS_DATE`, `SUBLOT`, `MC`, `Ni`, `Co`, `MgO`, `CaO`, `Fe`, `P`, `S`, `SiO2`, `Al2O3`, `Cr2O3`, `Fe2O3`, `K2O`, `MnO`, `Na2O`, `P2O5`, `TiO2`, `LOI`, `TOTAL`, `WMT`, `DMT`, `DEPOSIT`, `RIT`, `Quantity`, `SAMPLE_R_WEIGHT`, `SAMPLE_E_WEIGHT`, `SAMPLE_TOT_WEIGHT`, `SM`
- **`ASSAYS SAMPLING BRIDGE FILTERED`** (38 cols): `DOME_STATUS`, `CONTRACTOR_STATUS`, `DATE`, `JOB_ID`, `CONTRACTOR`, `TYPE_ASSAYS`, `DOME`, `ARRIVAL_DATE`, `ANALYSIS_DATE`, `SUBLOT`, `MC`, `Ni`, `Co`, `MgO`, `CaO`, `Fe`, `P`, `S`, `SiO2`, `Al2O3`, `Cr2O3`, `Fe2O3`, `K2O`, `MnO`, `Na2O`, `P2O5`, `TiO2`, `LOI`, `TOTAL`, `WMT`, `DMT`, `DEPOSIT`, `RIT`, `Quantity`, `SAMPLE_R_WEIGHT`, `SAMPLE_E_WEIGHT`, `SAMPLE_TOT_WEIGHT`, `SM`
- **`ASSAYS SAMPLING BRIDGE RAW DATA`** (40 cols): `DOME_STATUS`, `CONTRACTOR_STATUS`, `DATE`, `DATE_PR`, `JOB_ID`, `CONTRACTOR`, `TYPE_ASSAYS`, `DOME`, `ARRIVAL_DATE`, `ANALYSIS_DATE`, `SUBLOT`, `MC`, `Ni`, `Co`, `MgO`, `CaO`, `Fe`, `P`, `S`, `SiO2`, `Al2O3`, `Cr2O3`, `Fe2O3`, `K2O`, `MnO`, `Na2O`, `P2O5`, `TiO2`, `LOI`, `TOTAL`, `WMT`, `DMT`, `DEPOSIT`, `RIT`, `Quantity`, `SAMPLE_R_WEIGHT`, `SAMPLE_E_WEIGHT`, `SAMPLE_TOT_WEIGHT`, `SM`, `PROCESS_TYPE`
- **`ASSAYS TOS`** (30 cols): `ID`, `SAMPLE ID`, `BLOCK ID`, `Ni`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `Fe2O3`, `MgO`, `MnO`, `P2O5`, `SiO2`, `SiO2/MgO`, `MC`, `JOB ID`, `Date`, `CLASS`, `SAMPLE ID_1`, `NB_DT`, `SAMPLE_WEIGHT`, `R_SAP_WEIGHT`, `E_SAP_WEIGHT`, `Fe`, `DATA CHECK`, `DUPLICATE`, `QC01`, `product`, `PIT_SHEET`, `C`
- **`ASSAYS TOS FILTERED`** (21 cols): `DATE_TOS`, `BLOCK ID`, `Ni`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `Fe2O3`, `Fe`, `MgO`, `MnO`, `P2O5`, `SiO2`, `SM`, `MC`, `C`, `RIT`, `SAMPLE_TOT_WEIGHT`, `SAMPLE_R_WEIGHT`, `SAMPLE_E_WEIGHT`, `DATA CHECK`
- **`ASSAYS_MISSING_`** (36 cols): `ID`, `CONTRACTOR`, `DATE_RECEIVED`, `DATE_ANALYSIS`, `ASSAY_TYPE`, `ASSAY_STATUS`, `ACTIVITY`, `ORIGIN`, `DESTINATION`, `SAMPLE_ID`, `SAMPLE_JOB`, `STOCK_TYPE`, `STOCK_ID`, `STOCK_SUBLOT`, `RIT`, `WMT`, `Ni`, `Fe`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `Fe2O3`, `MnO`, `P2O5`, `SiO2`, `MgO`, `C`, `P`, `S`, `K2O`, `Na2O`, `TiO2`, `LOI`, `MC`, `REMARK`
- **`ASSAYS_MISSING_2`** (1 cols): `ORIGIN_ID`
- **`ASSAYS_NITON_CLEAN`** (5 cols): `PILE_ID`, `DATE ANALYSIS`, `NTN_MC`, `NTN_Ni`, `NTN_Fe`
- **`ASSAYS_NONULL`** (39 cols): `ID`, `CONTRACTOR`, `DATE_RECEIVED`, `DATE_ANALYSIS`, `ASSAY_TYPE`, `ASSAY_STATUS`, `ACTIVITY`, `ORIGIN`, `DESTINATION`, `SAMPLE_ID`, `SAMPLE_JOB`, `STOCK_TYPE`, `STOCK_ID`, `STOCK_SUBLOT`, `MATERIAL`, `RIT`, `RIT_RAW`, `WMT`, `DMT`, `MC`, `Ni`, `Fe`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `Fe2O3`, `MnO`, `P2O5`, `SiO2`, `MgO`, `C`, `P`, `S`, `K2O`, `Na2O`, `TiO2`, `LOI`, `REMARK`
- **`ASSAYS_PDF`** (38 cols): `ID`, `CONTRACTOR`, `DATE_RECEIVED`, `DATE_ANALYSIS`, `ASSAY_TYPE`, `ASSAY_STATUS`, `ACTIVITY`, `ORIGIN`, `DESTINATION`, `SAMPLE_ID`, `SAMPLE_JOB`, `STOCK_TYPE`, `STOCK_ID`, `STOCK_SUBLOT`, `RIT`, `WMT`, `Ni`, `Fe`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `Fe2O3`, `MnO`, `P2O5`, `SiO2`, `MgO`, `C`, `P`, `S`, `K2O`, `Na2O`, `TiO2`, `LOI`, `MC`, `REMARK`, `PDF_NAME`, `PDF_PATH`
- **`ASSAYS_YARD_ORIGINAL_DOME`** (25 cols): `CONTRACTOR`, `DATE`, `ASSAY_TYPE`, `ASSAY_STATUS`, `STOCK_ID`, `STOCK_ID_LEFT`, `STOCK_ID_RIGHT`, `STOCK_ID_MMYY`, `ORIGINAL_STOCK`, `IS_ORIGINAL`, `RIT`, `WMT`, `DMT`, `Ni`, `Fe`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `Fe2O3`, `MnO`, `P2O5`, `SiO2`, `MgO`, `MC`
- **`ASSAY_CLASS_IN`** (9 cols): `date`, `date_end`, `cat`, `material`, `element`, `ore_class`, `ore_class_description`, `grade_min`, `grade_max`
- **`ASSAY_PROGRESS`** (28 cols): `DATE`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `ASSAY_CONTRACTOR`, `ASSAY_TYPE`, `ASSAY_STATUS`, `ASSAY_ACTIVITY`, `SAMPLE_ID`, `STOCK_TYPE`, `STOCK_ID`, `STOCK_SUBLOT`, `Ni`, `Fe`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `Fe2O3`, `MnO`, `P2O5`, `SiO2`, `MgO`, `MC`
- **`ATC_ORACLE_ASSAYS`** (24 cols): `Kode Sampel`, `Batch`, `Entrustment Date`, `Reporting Date`, `Entrusting Department`, `Ni`, `Co`, `AL2O3`, `CaO`, `Cr2O3`, `Fe2O3`, `TFe`, `MgO`, `MnO`, `P2O5`, `SiO2`, `SiO2/MgO`, `MC`, `REMARKS`, `Ritase Sampling`, `Berat`, `Transfer Date`, `Transfer Location`, `Starting Pit`
- **`AVG_RAIN_BY_DATE_AREA`** (8 cols): `Year`, `Month`, `Week`, `DATE`, `Area`, `H2O`, `RF_H2O_MONTHLY`, `RF_H2O_WEEKLY`
- **`AVG_RAIN_BY_DATE_AREA_RAW`** (8 cols): `Year`, `Month`, `Week`, `DATE`, `Area`, `H2O`, `RF_H2O_MONTHLY`, `RF_H2O_WEEKLY`
- **`AVG_RAIN_BY_DAY_ALL_AREA`** (2 cols): `DATE`, `DAILY_ALL_AREA_AVG_mmH2O`
- **`BATCH COMPOSITES`** (15 cols): `MaxOfDate`, `BATCH ID`, `Ni`, `Fe`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `Fe2O3`, `MgO`, `MnO`, `P2O5`, `SiO2`, `SM`, `MC`
- **`BLOCK_CLASS_OF_TOS_PILE`** (3 cols): `TOS_PILE`, `BM_MIX_DEGREE`, `BM_MIX_CLASS`
- **`BLOCK_OF_TOS_PILE`** (2 cols): `TOS_PILE`, `BLOCKS`
- **`BLOCK_PROD_FOR_PROD`** (10 cols): `CONTRACTOR`, `DATE`, `shift`, `ORIGIN_AREA`, `ORIGIN_ID`, `MATERIAL`, `DESTINATION_AREA`, `DESTINATION_ID`, `RIT`, `WMT`
- **`BLOCK_PROD_QC_BM_TOS`** (63 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `CONTRACTOR`, `SHIFT`, `DEPOSIT`, `SUBPIT`, `prod_ID`, `BLOCK_ID`, `block_ID_2`, `RIT`, `TF_1`, `TF_2`, `WMT`, `DMT`, `BCM`, `destination`, `DESTINATION_AREA`, `TOS_PILE`, `STATUS HAULAGE`, `status`, `status_blast`, `TYPE_PROD`, `BLAST_ID`, `RSAP`, `CF`, `MC`, `Ni`, `Fe`, `SiO2`, `MgO`, `Co`, `P2O5`, `Cr2O3`, `BM_MC`, `BM_Ni`, `BM_Fe`, `BM_SiO2`, `BM_MgO`, `BM_Co`, `BM_Cr2O3`, `TOS_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `TOS_Co`, `TOS_Cr2O3`, `MATERIAL`, `MATERIAL_CLASS`, `MATERIAL_CLASS_PROD`, `MATERIAL_BM`, `MATERIAL_CLASS_BM`, `MATERIAL_TOS`, `MATERIAL_CLASS_TOS`, `MATERIAL_PROD_CLASS`, `HAUL_CONFIDENCE`, `MATERIAL_PLAN`, `MATERIAL_CLASS_PLAN`, `MATERIAL_PLAN_NO_WA`, `MATERIAL_PLAN_NO_WA_DTL`, `MATERIAL_CLASS_PLAN_NO_WA`
- **`BLOCK_PROD_QC_BM_TOS_CORR`** (66 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `CONTRACTOR`, `SHIFT`, `DEPOSIT`, `SUBPIT`, `prod_ID`, `BLOCK_ID`, `block_ID_2`, `MATERIAL`, `MATERIAL_CLASS`, `MATERIAL_CLASS_PROD`, `MATERIAL_BM`, `MATERIAL_CLASS_BM`, `MATERIAL_TOS`, `MATERIAL_CLASS_TOS`, `MATERIAL_PROD_CLASS`, `HAUL_CONFIDENCE`, `MATERIAL_PLAN`, `MATERIAL_CLASS_PLAN`, `MATERIAL_PLAN_NO_WA`, `MATERIAL_PLAN_NO_WA_DTL`, `MATERIAL_CLASS_PLAN_NO_WA`, `RIT`, `TF_1`, `TF_2`, `WMT`, `DMT`, `BCM`, `destination`, `DESTINATION_AREA`, `TOS_PILE`, `STATUS_MINING`, `STATUS HAULAGE`, `status_blast`, `TYPE_PROD`, `BLAST_ID`, `RSAP`, `CF`, `MC`, `Ni`, `Fe`, `SiO2`, `MgO`, `Co`, `P2O5`, `Cr2O3`, `BM_MC`, `BM_Ni`, `BM_Fe`, `BM_SiO2`, `BM_MgO`, `BM_Co`, `BM_Cr2O3`, `TOS_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `TOS_Co`, `TOS_Cr2O3`, `MATERIAL_FINAL`, `WET_DENSITY`, `WMT_FINAL`
- **`BLOCK_PROD_QC_BM_TOS_CORR_TARGET`** (62 cols): `YEAR`, `MONTH`, `WEEK`, `CONTRACTOR`, `DATE`, `DEPOSIT`, `MATERIAL`, `TARGET_WMT`, `SHIFT`, `SUBPIT`, `prod_ID`, `BLOCK_ID`, `block_ID_2`, `MATERIAL_CLASS`, `MATERIAL_CLASS_PROD`, `MATERIAL_BM`, `MATERIAL_CLASS_BM`, `MATERIAL_TOS`, `MATERIAL_CLASS_TOS`, `MATERIAL_PROD_CLASS`, `HAUL_CONFIDENCE`, `MATERIAL_PLAN`, `MATERIAL_CLASS_PLAN`, `MATERIAL_PLAN_NO_WA`, `MATERIAL_PLAN_NO_WA_DTL`, `MATERIAL_CLASS_PLAN_NO_WA`, `RIT`, `TF_1`, `TF_2`, `WMT`, `DMT`, `destination`, `DESTINATION_AREA`, `TOS_PILE`, `STATUS`, `status_blast`, `TYPE_PROD`, `BLAST_ID`, `RSAP`, `CF`, `MC`, `Ni`, `Fe`, `SiO2`, `MgO`, `Co`, `P2O5`, `Cr2O3`, `BM_MC`, `BM_Ni`, `BM_Fe`, `BM_SiO2`, `BM_MgO`, `TOS_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `MATERIAL_FINAL`, `WET_DENSITY`, `BM_Co`, `TOS_Co`
- **`BLOCK_PROD_QC_BM_TOS_GROUP`** (30 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `CONTRACTOR`, `DEPOSIT`, `DESTINATION`, `RSAP`, `WMT`, `DMT`, `TOS_PILE`, `Ni`, `Fe`, `SiO2`, `MgO`, `Co`, `P2O5`, `Cr2O3`, `BM_MC`, `BM_Ni`, `BM_Fe`, `BM_SiO2`, `BM_MgO`, `BM_Co`, `TOS_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `TOS_Co`
- **`BLOCK_PROD_QC_BM_TOS_GROUP_CAT`** (33 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `CONTRACTOR`, `DEPOSIT`, `DESTINATION`, `WMT`, `DMT`, `TOS_PILE`, `Ni`, `Fe`, `SiO2`, `MgO`, `Co`, `P2O5`, `Cr2O3`, `BM_MC`, `BM_Ni`, `BM_Fe`, `BM_SiO2`, `BM_Co`, `BM_MgO`, `TOS_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `TOS_Co`, `MATERIAL_PLAN`, `MATERIAL_PLAN_NO_WA`, `MATERIAL_CLASS_PLAN`, `MATERIAL_CLASS_PLAN_NO_WA`
- **`BLOCK_PROD_QC_BM_TOS_GROUP_CAT_CORR`** (35 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `CONTRACTOR`, `DEPOSIT`, `DESTINATION`, `WMT`, `DMT`, `MC`, `TOS_PILE`, `Ni`, `Fe`, `SiO2`, `MgO`, `Co`, `P2O5`, `Cr2O3`, `BM_MC`, `BM_Ni`, `BM_Co`, `BM_Fe`, `BM_SiO2`, `BM_MgO`, `TOS_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `TOS_Co`, `MATERIAL_PLAN`, `MATERIAL_PLAN_NO_WA`, `MATERIAL_CLASS_PLAN`, `MATERIAL_CLASS_PLAN_NO_WA`, `CF`
- **`BLOCK_PROD_QC_BM_TOS_OLD`** (61 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `CONTRACTOR`, `SHIFT`, `DEPOSIT`, `SUBPIT`, `prod_ID`, `BLOCK_ID`, `block_ID_2`, `RIT`, `TF_1`, `TF_2`, `WMT`, `DMT`, `WMT2`, `CLASS_BM`, `destination`, `DESTINATION_AREA`, `TOS_PILE`, `status`, `status_blast`, `TYPE_PROD`, `BLAST_ID`, `RSAP`, `CF`, `MATERIAL`, `MATERIAL_CLASS`, `MATERIAL_CLASS_PROD`, `MATERIAL_BM`, `MATERIAL_CLASS_BM`, `MATERIAL_TOS`, `MATERIAL_CLASS_TOS`, `MATERIAL_PROD_CLASS`, `HAUL_CONFIDENCE`, `MATERIAL_PLAN`, `MATERIAL_CLASS_PLAN`, `MATERIAL_PLAN_NO_WA`, `MATERIAL_PLAN_NO_WA_DTL`, `MATERIAL_CLASS_PLAN_NO_WA`, `MC`, `Ni`, `Fe`, `SiO2`, `MgO`, `Co`, `P2O5`, `Cr2O3`, `BM_MC`, `BM_Ni`, `BM_Fe`, `BM_SiO2`, `BM_MgO`, `BM_Co`, `TOS_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `TOS_Co`
- **`BLOCK_PROD_QC_BM_TOS_SURVEY_ADJ`** (66 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `CONTRACTOR`, `SHIFT`, `DEPOSIT`, `SUBPIT`, `prod_ID`, `BLOCK_ID`, `block_ID_2`, `MATERIAL`, `MATERIAL_CLASS`, `MATERIAL_CLASS_PROD`, `MATERIAL_BM`, `MATERIAL_CLASS_BM`, `MATERIAL_TOS`, `MATERIAL_CLASS_TOS`, `MATERIAL_PROD_CLASS`, `HAUL_CONFIDENCE`, `MATERIAL_PLAN`, `MATERIAL_CLASS_PLAN`, `MATERIAL_PLAN_NO_WA`, `MATERIAL_PLAN_NO_WA_DTL`, `MATERIAL_CLASS_PLAN_NO_WA`, `RIT`, `TF_1`, `TF_2`, `WMT`, `DMT`, `BCM`, `destination`, `DESTINATION_AREA`, `TOS_PILE`, `STATUS_MINING`, `STATUS HAULAGE`, `status_blast`, `TYPE_PROD`, `BLAST_ID`, `RSAP`, `CF`, `MC`, `Ni`, `Fe`, `SiO2`, `MgO`, `Co`, `P2O5`, `Cr2O3`, `BM_MC`, `BM_Ni`, `BM_Fe`, `BM_SiO2`, `BM_MgO`, `BM_Co`, `BM_Cr2O3`, `TOS_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `TOS_Co`, `TOS_Cr2O3`, `MATERIAL_FINAL`, `WET_DENSITY`, `WMT_FINAL`
- **`BLOCK_PROD_TOS`** (17 cols): `CONTRACTOR`, `DATE`, `SHIFT`, `PIT`, `SUBPIT`, `prod_ID`, `BLOCK_ID`, `MATERIAL`, `MATERIAL_CLASS`, `RIT`, `TF`, `WMT`, `DESTINATION`, `TOS_PILE`, `BLOCK_STATUS`, `BLAST_STATUS`, `BLAST_ID`
- **`BLOCK_PROD_TOS_ASSAYS`** (35 cols): `contractor`, `Date`, `shift`, `deposit_code`, `pit`, `subpit`, `prod_ID`, `block_id`, `block_ID_2`, `CLASS_BM`, `MATERIAL`, `MATERIAL_CLASS`, `RIT`, `TF_1`, `TF_2`, `WMT`, `WMT2`, `destination`, `TOS_PILE`, `status`, `status_blast`, `TYPE_PROD`, `BLAST_ID`, `DMT`, `al2o3`, `cao`, `co`, `cr2o3`, `MC`, `mno`, `Ni`, `Fe`, `SiO2`, `MgO`, `p2o5`
- **`BM`** (63 cols): `UPDATE_DATE`, `X`, `Y`, `Z`, `size (X)`, ` size(Y)`, ` size(Z)`, `Deposit`, `block_id`, `al2o3_brk`, `al2o3_fsap`, `al2o3_lim`, `al2o3_rsap`, `cao_brk`, `cao_fsap`, `cao_lim`, `cao_rsap`, `co_brk`, `co_fsap`, `co_lim`, `co_rsap`, `cr2o3_brk`, `cr2o3_fsap`, `cr2o3_lim`, `cr2o3_rsap`, `dd_brk_tc0`, `dd_fsap_tc0`, `dd_lim_tc0`, `dd_rsap_tc0`, `fe_brk_tc0`, `fe_fsap_tc0`, `fe_lim_tc0`, `fe_rsap_tc0`, `h2o_brk`, `h2o_fsap`, `h2o_lim`, `h2o_rsap`, `mgo_brk`, `mgo_fsap`, `mgo_lim`, `mgo_rsap`, `mno_brk`, `mno_fsap`, `mno_lim`, `mno_rsap`, `ni_brk_tc0`, `ni_fsap_tc0`, `ni_lim_tc0`, `ni_rsap_tc0`, `p2o5_brk`, `p2o5_fsap`, `p2o5_lim`, `p2o5_rsap`, `pp_brk_tc0`, `pp_fsap_tc0`, `pp_lim_tc0`, `pp_rsap_tc0`, `sio2_brk`, `sio2_fsap`, `sio2_lim`, `sio2_rsap`, `class_res`, `block_confidence_dh_close`
- **`BM_CARROT2`** (8 cols): `DEPOSIT`, `BLOCK_ID`, `H2O`, `Ni`, `Fe`, `SiO2`, `MgO`, `Co`
- **`BM_ESTIMATION_CONFIDENCE`** (6 cols): `X`, `Y`, `Z`, `DEPOSIT`, `classification_no`, `block_confidence_dh_close`
- **`BM_KRENE_FOR_RESERVES_LIM`** (15 cols): `x`, `y`, `z`, `MATERIAL`, `TC`, `BCM`, `WMT`, `DMT`, `Fe`, `MC`, `Ni`, `PROP`, `MgO`, `SiO2`, `Co`
- **`BM_KRENE_TREATED_0`** (60 cols): `X`, `y`, `z`, `size (X)`, ` size(Y)`, ` size(Z)`, `co_brk`, `co_fsap`, `co_lim`, `co_rsap`, `co_wst`, `dd_brk_tc0`, `dd_fsap_tc09`, `dd_lim_tc07`, `dd_lim_tc08`, `dd_rsap_tc09`, `dd_wst`, `fe_brk_tc0`, `fe_fsap_tc09`, `fe_lim_tc07`, `fe_lim_tc08`, `fe_rsap_tc09`, `fe_wst`, `h2o_brk`, `h2o_fsap`, `h2o_lim`, `h2o_rsap`, `h2o_wst`, `mgo_brk`, `mgo_fsap`, `mgo_lim`, `mgo_rsap`, `mgo_wst`, `ni_brk_tc0`, `ni_fsap_tc09`, `ni_lim_tc07`, `ni_lim_tc08`, `ni_rsap_tc09`, `ni_wst`, `pp_brk_tc0`, `pp_fsap_tc09`, `pp_lim_tc07`, `pp_lim_tc08`, `pp_rsap_tc09`, `pp_wst`, `sio2_brk`, `sio2_fsap`, `sio2_lim`, `sio2_rsap`, `sio2_wst`, `wd_brk_tc0`, `wd_fsap_tc09`, `wd_lim`, `wd_rsap_tc09`, `wd_wst`, `prop_wst`, `prop_fsap`, `prop_lim_tc07`, `prop_lim_tc08`, `prop_rsap`
- **`BM_LONG_TERM`** (61 cols): `X`, `Y`, `Z`, `size (X)`, ` size(Y)`, ` size(Z)`, `Deposit`, `block_id`, `al2o3_brk`, `al2o3_fsap`, `al2o3_lim`, `al2o3_rsap`, `cao_brk`, `cao_fsap`, `cao_lim`, `cao_rsap`, `co_brk`, `co_fsap`, `co_lim`, `co_rsap`, `cr2o3_brk`, `cr2o3_fsap`, `cr2o3_lim`, `cr2o3_rsap`, `dd_brk_tc0`, `dd_fsap_tc`, `dd_lim_tc`, `dd_rsap_tc`, `fe_brk_tc0`, `fe_fsap_tc`, `fe_lim_tc`, `fe_rsap_tc`, `h2o_brk`, `h2o_fsap`, `h2o_lim`, `h2o_rsap`, `mgo_brk`, `mgo_fsap`, `mgo_lim`, `mgo_rsap`, `mno_fsap`, `mno_lim`, `mno_rsap`, `ni_brk_tc0`, `ni_fsap_tc`, `ni_lim_tc`, `ni_rsap_tc`, `p2o5_brk`, `p2o5_fsap`, `p2o5_lim`, `p2o5_rsap`, `pp_brk_tc0`, `pp_fsap_tc`, `pp_lim_tc`, `pp_rsap_tc`, `sio2_brk`, `sio2_fsap`, `sio2_lim`, `sio2_rsap`, `class_res`, `block_confidence_dh_close`
- **`BM_OK_PREPARED`** (80 cols): `X`, `Y`, `Z`, `DEPOSIT`, `size (X)`, ` size(Y)`, ` size(Z)`, `block_id`, `PROP_VHGS`, `ni_VHGS`, `fe_VHGS`, `dd_VHGS`, `sio2_VHGS`, `mgo_VHGS`, `co_VHGS`, `wd_VHGS`, `h2o_VHGS`, `PROP_HGS`, `ni_HGS`, `fe_HGS`, `dd_HGS`, `sio2_HGS`, `mgo_HGS`, `co_HGS`, `wd_HGS`, `h2o_HGS`, `PROP_HGRS`, `ni_HGRS`, `fe_HGRS`, `dd_HGRS`, `sio2_HGRS`, `mgo_HGRS`, `co_HGRS`, `wd_HGRS`, `h2o_HGRS`, `PROP_WCO`, `ni_WCO`, `fe_WCO`, `dd_WCO`, `sio2_WCO`, `mgo_WCO`, `co_WCO`, `wd_WCO`, `h2o_WCO`, `PROP_WST_SAP`, `Ni_WST_SAP`, `fe_WST_SAP`, `dd_WST_SAP`, `sio2_WST_SAP`, `mgo_WST_SAP`, `co_WST_SAP`, `wd_WST_SAP`, `h2o_WST_SAP`, `PROP_LIM_ORE`, `ni_LIM_ORE`, `fe_LIM_ORE`, `dd_LIM_ORE`, `sio2_LIM_ORE`, `mgo_LIM_ORE`, `co_LIM_ORE`, `wd_LIM_ORE`, `h2o_LIM_ORE`, `PROP_WST_LIM`, `ni_WST_LIM`, `fe_WST_LIM`, `dd_WST_LIM`, `sio2_WST_LIM`, `mgo_WST_LIM`, `co_WST_LIM`, `wd_WST_LIM`, `h2o_WST_LIM`, `PROP_WST`, `ni_WST`, `fe_WST`, `dd_WST`, `sio2_WST`, `mgo_WST`, `co_WST`, `wd_WST`, `h2o_WST`
- **`BM_OK_TREATED_0`** (65 cols): `X`, `Y`, `Z`, `DEPOSIT`, `size (X)`, ` size(Y)`, ` size(Z)`, `block_id`, `al2o3_brk`, `al2o3_fsap`, `al2o3_lim`, `al2o3_rsap`, `cao_brk`, `cao_fsap`, `cao_lim`, `cao_rsap`, `co_brk`, `co_fsap`, `co_lim`, `co_rsap`, `cr2o3_brk`, `cr2o3_fsap`, `cr2o3_lim`, `cr2o3_rsap`, `dd_brk_tc0`, `dd_fsap_tc0`, `dd_lim_tc0`, `dd_rsap_tc0`, `fe_brk_tc0`, `fe_fsap_tc0`, `fe_lim_tc0`, `fe_rsap_tc0`, `h2o_brk`, `h2o_fsap`, `h2o_lim`, `h2o_rsap`, `mgo_brk`, `mgo_fsap`, `mgo_lim`, `mgo_rsap`, `mno_fsap`, `mno_lim`, `mno_rsap`, `ni_brk_tc0`, `ni_fsap_tc0`, `ni_lim_tc0`, `ni_rsap_tc0`, `p2o5_brk`, `p2o5_fsap`, `p2o5_lim`, `p2o5_rsap`, `pp_brk_tc0`, `pp_fsap_tc0`, `pp_lim_tc0`, `pp_rsap_tc0`, `sio2_brk`, `sio2_fsap`, `sio2_lim`, `sio2_rsap`, `prop_wst`, `prop_fsap`, `prop_lim`, `prop_rsap`, `class_res`, `block_confidence_dh_close`
- **`BM_OK_TREATED_1`** (29 cols): `X`, `Y`, `Z`, `block_id`, `MATERIAL`, `BCM`, `WMT`, `DMT`, `Fe`, `MC`, `Ni`, `PROP`, `WD`, `MgO`, `SiO2`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `MnO`, `P2O5`, `YEAR`, `MONTH`, `WEEK`, `pp_mined_progress`, `PROP_FSAP`, `PROP_RSAP`, `class_res`, `block_confidence_dh_close`
- **`BM_OK_TREATED_1_via_OLD_PP_MENG_CONVERTED`** (38 cols): `PIT`, `X`, `Y`, `Z`, `block_id`, `MATERIAL`, `BCM`, `WMT`, `DMT`, `Fe`, `MC`, `Ni`, `prop`, `WD`, `MgO`, `SiO2`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `MnO`, `P2O5`, `YEAR`, `MONTH`, `WEEK`, `pp_mined_progress`, `PROP_FSAP`, `PROP_RSAP`, `class_res`, `block_confidence_dh_close`, `VOI`, `block_id_new`, `prop_lim`, `prop_sap`, `prop_wst`, `under_VOI`, `Ni_RSAP`, `Ni_FSAP`
- **`BM_PP_FOR_RECONCIL`** (6 cols): `UPDATE_DATE`, `DEPOSIT`, `block_id`, `pp_inside_pit_clean`, `pp_mined_clean`, `pp_remain`
- **`BM_PP_FOR_RECONCIL_LAST_UPDATE`** (6 cols): `UPDATE_DATE`, `DEPOSIT`, `block_id`, `pp_inside_pit_clean`, `pp_mined_clean`, `pp_remain`
- **`BM_PP_LAST_ADJUST`** (7 cols): `UPDATE_DATE`, `DEPOSIT`, `VOLUME`, `WMT`, `block_id`, `ADJUST_WMT`, `PP_REMAIN_ADJUST`
- **`BM_PRODUCTION`** (32 cols): `LAST_UPDATE`, `DEPOSIT`, `block_id`, `size (X)`, ` size(Y)`, ` size(Z)`, `VOLUME`, `MATERIAL_CLASS`, `DENSITY`, `WMT`, `DMT`, `Al2O3`, `CaO`, `Co`, `Cr2O3`, `Fe_ORI`, `Fe`, `H2O_ORI`, `H2O`, `MgO_ORI`, `MgO`, `MnO`, `Ni_ORI`, `Ni`, `P2O5`, `PROP`, `SiO2_ORI`, `SiO2`, `Z`, `B`, `S`, `N`
- **`BM_RECONCIL_LT_TREATED_0`** (65 cols): `X`, `Y`, `Z`, `DEPOSIT`, `size (X)`, ` size(Y)`, ` size(Z)`, `block_id`, `al2o3_brk`, `al2o3_fsap`, `al2o3_lim`, `al2o3_rsap`, `cao_brk`, `cao_fsap`, `cao_lim`, `cao_rsap`, `co_brk`, `co_fsap`, `co_lim`, `co_rsap`, `cr2o3_brk`, `cr2o3_fsap`, `cr2o3_lim`, `cr2o3_rsap`, `dd_brk_tc0`, `dd_fsap_tc`, `dd_lim_tc`, `dd_rsap_tc`, `fe_brk_tc0`, `fe_fsap_tc`, `fe_lim_tc`, `fe_rsap_tc`, `h2o_brk`, `h2o_fsap`, `h2o_lim`, `h2o_rsap`, `mgo_brk`, `mgo_fsap`, `mgo_lim`, `mgo_rsap`, `mno_fsap`, `mno_lim`, `mno_rsap`, `ni_brk_tc0`, `ni_fsap_tc`, `ni_lim_tc`, `ni_rsap_tc`, `p2o5_brk`, `p2o5_fsap`, `p2o5_lim`, `p2o5_rsap`, `pp_brk_tc0`, `pp_fsap_tc`, `pp_lim_tc`, `pp_rsap_tc`, `sio2_brk`, `sio2_fsap`, `sio2_lim`, `sio2_rsap`, `prop_wst`, `prop_fsap`, `prop_lim`, `prop_rsap`, `class_res`, `block_confidence_dh_close`
- **`BM_RECONCIL_LT_TREATED_1`** (31 cols): `PIT`, `X`, `Y`, `Z`, `block_id`, `MATERIAL`, `BCM`, `WMT`, `DMT`, `Fe`, `MC`, `Ni`, `PROP`, `WD`, `MgO`, `SiO2`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `MnO`, `P2O5`, `YEAR`, `MONTH`, `WEEK`, `pp_mined_progress`, `PROP_FSAP`, `PROP_RSAP`, `class_res`, `block_confidence_dh_close`, `VOI`
- **`BM_RECONCIL_TC0`** (75 cols): `UPDATE_DATE`, `DEPOSIT`, `size (X)`, ` size(Y)`, ` size(Z)`, `block_id`, `al2o3_brk`, `al2o3_fsap`, `al2o3_lim`, `al2o3_rsap`, `cao_brk`, `cao_fsap`, `cao_lim`, `cao_rsap`, `cf_fsap`, `co_brk`, `co_fsap`, `co_lim`, `co_rsap`, `co_wst`, `cr2o3_brk`, `cr2o3_fsap`, `cr2o3_lim`, `cr2o3_rsap`, `dd_brk_tc0`, `dd_fsap_tc0`, `dd_lim_tc0`, `dd_rsap_tc0`, `dd_wst`, `fe_brk_tc0`, `fe_fsap_tc0`, `fe_lim_tc0`, `fe_rsap_tc0`, `fe_wst`, `h2o_brk`, `h2o_fsap`, `h2o_lim`, `h2o_rsap`, `h2o_wst`, `mgo_brk`, `mgo_fsap`, `mgo_lim`, `mgo_rsap`, `mgo_wst`, `mno_brk`, `mno_fsap`, `mno_lim`, `mno_rsap`, `ni_brk_tc0`, `ni_fsap_tc0`, `ni_lim_tc0`, `ni_rsap_tc0`, `ni_wst`, `p2o5_brk`, `p2o5_fsap`, `p2o5_lim`, `p2o5_rsap`, `pp_brk_tc0`, `pp_fsap_tc0`, `pp_lim_tc0`, `pp_rsap_tc0`, `pp_wst`, `sio2_brk`, `sio2_fsap`, `sio2_lim`, `sio2_rsap`, `sio2_wst`, `wd_hgs`, `wd_lgs1`, `wd_lgs2`, `wd_lim`, `wd_sap_tc1`, `wd_vhgs`, `wd_vlgs`, `wd_wst`
- **`BM_RECONCIL_TC0_TREATED_0`** (78 cols): `UPDATE_DATE`, `DEPOSIT`, `size (X)`, ` size(Y)`, ` size(Z)`, `block_id`, `al2o3_brk`, `al2o3_fsap`, `al2o3_lim`, `al2o3_rsap`, `cao_brk`, `cao_fsap`, `cao_lim`, `cao_rsap`, `cf_fsap`, `co_brk`, `co_fsap`, `co_lim`, `co_rsap`, `co_wst`, `cr2o3_brk`, `cr2o3_fsap`, `cr2o3_lim`, `cr2o3_rsap`, `dd_brk_tc0`, `dd_fsap_tc0`, `dd_lim_tc0`, `dd_rsap_tc0`, `dd_wst`, `fe_brk_tc0`, `fe_fsap_tc0`, `fe_lim_tc0`, `fe_rsap_tc0`, `fe_wst`, `h2o_brk`, `h2o_fsap`, `h2o_lim`, `h2o_rsap`, `h2o_wst`, `mgo_brk`, `mgo_fsap`, `mgo_lim`, `mgo_rsap`, `mgo_wst`, `mno_brk`, `mno_fsap`, `mno_lim`, `mno_rsap`, `ni_brk_tc0`, `ni_fsap_tc0`, `ni_lim_tc0`, `ni_rsap_tc0`, `ni_wst`, `p2o5_brk`, `p2o5_fsap`, `p2o5_lim`, `p2o5_rsap`, `pp_brk_tc0`, `pp_fsap_tc0`, `pp_lim_tc0`, `pp_rsap_tc0`, `sio2_brk`, `sio2_fsap`, `sio2_lim`, `sio2_rsap`, `sio2_wst`, `wd_hgs`, `wd_lgs1`, `wd_lgs2`, `wd_lim`, `wd_sap_tc1`, `wd_vhgs`, `wd_vlgs`, `wd_wst`, `prop_wst`, `prop_fsap`, `prop_lim`, `prop_rsap`
- **`BM_RECONCIL_TC0_TREATED_1`** (23 cols): `PIT`, `block_id`, `MATERIAL`, `BCM`, `WMT`, `DMT`, `Fe`, `MC`, `Ni`, `PROP`, `WD`, `MgO`, `SiO2`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `MnO`, `P2O5`, `YEAR`, `MONTH`, `WEEK`, `pp_mined_progress`
- **`BM_RECONCIL_TC0_TREATED_1_FULL`** (29 cols): `PIT`, `block_id`, `MATERIAL`, `BCM`, `WMT`, `DMT`, `Fe`, `MC`, `Ni`, `PROP`, `WD`, `MgO`, `SiO2`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `MnO`, `P2O5`, `YEAR`, `MONTH`, `WEEK`, `pp_mined_progress`, `VOI`, `prop_lim`, `PROP_SAP`, `prop_wst`, `prop_fsap`, `prop_rsap`
- **`BM_REDUCED_FOR_RECONCIL_GROUP`** (40 cols): `LAST_UPDATE`, `DEPOSIT`, `block_id`, `size (X)`, ` size(Y)`, ` size(Z)`, `VOLUME`, `MATERIAL_CLASS`, `DENSITY`, `WMT`, `DMT`, `Al2O3`, `CaO`, `Co`, `Co_ORI`, `Cr2O3`, `Cr2O3_ORI`, `Fe_ORI`, `Fe`, `H2O_ORI`, `H2O`, `MgO_ORI`, `MgO`, `MnO`, `Ni_ORI`, `Ni`, `P2O5`, `PROP`, `SiO2_ORI`, `SiO2`, `CARROT_H2O`, `CARROT_Ni`, `CARROT_Fe`, `CARROT_SiO2`, `CARROT_MgO`, `CARROT_Co`, `Z`, `B`, `S`, `N`
- **`BM_REMAINING_RESERVES_TC0`** (20 cols): `DEPOSIT`, `block_id`, `MATERIAL`, `MP`, `BCM`, `WMT`, `DMT`, `Fe`, `MC`, `Ni`, `PROP`, `WD`, `MgO`, `SiO2`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `MnO`, `P2O5`
- **`BM_RESSOURCES_KRENE_TC07_TC08`** (52 cols): `X`, `Y`, `Z`, `co_brk`, `co_fsap`, `co_lim`, `co_rsap`, `co_wst`, `dd_brk_tc0`, `dd_fsap_tc09`, `dd_lim_tc07`, `dd_lim_tc08`, `dd_rsap_tc09`, `dd_wst`, `fe_brk_tc0`, `fe_fsap_tc09`, `fe_lim_tc07`, `fe_lim_tc08`, `fe_rsap_tc09`, `fe_wst`, `h2o_brk`, `h2o_fsap`, `h2o_lim`, `h2o_rsap`, `h2o_wst`, `mgo_brk`, `mgo_fsap`, `mgo_lim`, `mgo_rsap`, `mgo_wst`, `ni_brk_tc0`, `ni_fsap_tc09`, `ni_lim_tc07`, `ni_lim_tc08`, `ni_rsap_tc09`, `ni_wst`, `pp_brk_tc0`, `pp_fsap_tc09`, `pp_lim_tc07`, `pp_lim_tc08`, `pp_rsap_tc09`, `pp_wst`, `sio2_brk`, `sio2_fsap`, `sio2_lim`, `sio2_rsap`, `sio2_wst`, `wd_brk_tc0`, `wd_fsap_tc09`, `wd_lim`, `wd_rsap_tc09`, `wd_wst`
- **`BM_TC0_LAST`** (58 cols): `UPDATE_DATE`, `DEPOSIT`, `size (X)`, ` size(Y)`, ` size(Z)`, `block_id`, `al2o3_brk`, `al2o3_fsap`, `al2o3_lim`, `al2o3_rsap`, `cao_brk`, `cao_fsap`, `cao_lim`, `cao_rsap`, `co_brk`, `co_fsap`, `co_lim`, `co_rsap`, `cr2o3_brk`, `cr2o3_fsap`, `cr2o3_lim`, `cr2o3_rsap`, `dd_brk_tc0`, `dd_fsap_tc0`, `dd_lim_tc0`, `dd_rsap_tc0`, `fe_brk_tc0`, `fe_fsap_tc0`, `fe_lim_tc0`, `fe_rsap_tc0`, `h2o_brk`, `h2o_fsap`, `h2o_lim`, `h2o_rsap`, `mgo_brk`, `mgo_fsap`, `mgo_lim`, `mgo_rsap`, `mno_brk`, `mno_fsap`, `mno_lim`, `mno_rsap`, `ni_brk_tc0`, `ni_fsap_tc0`, `ni_lim_tc0`, `ni_rsap_tc0`, `p2o5_brk`, `p2o5_fsap`, `p2o5_lim`, `p2o5_rsap`, `pp_brk_tc0`, `pp_fsap_tc0`, `pp_lim_tc0`, `pp_rsap_tc0`, `sio2_brk`, `sio2_fsap`, `sio2_lim`, `sio2_rsap`
- **`BM_TC0_REFORMAT_LONG`** (22 cols): `UPDATE_DATE`, `DEPOSIT`, `block_id`, `size (X)`, ` size(Y)`, ` size(Z)`, `MATERIAL`, `Al2O3`, `CaO`, `Co`, `Cr2O3`, `Fe`, `H2O`, `MgO`, `MnO`, `Ni`, `P2O5`, `PP`, `PP_TOT`, `PROP`, `SiO2`, `WD`
- **`BM_TC0_WMT`** (24 cols): `UPDATE_DATE`, `DEPOSIT`, `block_id`, `size (X)`, ` size(Y)`, ` size(Z)`, `WMT`, `DMT`, `MATERIAL_CLASS`, `MATERIAL`, `al2o3`, `cao`, `co`, `cr2o3`, `fe`, `h2o`, `mgo`, `mno`, `ni`, `p2o5`, `prop`, `NULL_OR_1`, `sio2`, `wd`
- **`BM_TC0_WMT_GROUP`** (21 cols): `DEPOSIT`, `block_id`, `size (X)`, ` size(Y)`, ` size(Z)`, `MATERIAL_CLASS`, `DENSITY`, `WMT`, `DMT`, `Al2O3`, `CaO`, `Co`, `Cr2O3`, `Fe`, `H2O`, `MgO`, `MnO`, `Ni`, `P2O5`, `PROP`, `SiO2`
- **`BM_VS_ACTUAL_DEST`** (11 cols): `YEAR`, `MONTH`, `WEEK`, `block_id`, `deposit`, `PROP_SAP`, `PROP_LIM_ORE`, `PROP_LIM_WST`, `RIT_LIM`, `RIT_SAP`, `RIT_WST`
- **`CALENDAR_SHIFT`** (3 cols): `DATE`, `SHIFT`, `DATETIME`
- **`CEK_RIT_HAULAGE`** (6 cols): `DESTINATION_ID`, `WMT`, `RIT`, `RIT_SAMPLING_CONTRACTOR`, `RIT_OMR_QC`, `SUM_DEF`
- **`CF FOR PROD CORR ASSAYS 2`** (8 cols): `YEAR`, `MONTH`, `contractor`, `FINAL_RECLASSIFICATION`, `CF`, `WMT_SURVEY`, `BCM_SURVEY`, `PIT`
- **`CF_CHECK`** (8 cols): `YEAR`, `MONTH`, `CONTRACTOR`, `PIT`, `MATERIAL`, `WMT_PROD`, `WMT_SURVEY`, `CF`
- **`CHECK_BACKCHARGE_HAULAGE_IWIP`** (4 cols): `WMT`, `ORIGIN_AREA`, `COMPANY`, `DESTINATION_AREA`
- **`COMPANIES_PLANT_ONLY`** (6 cols): `COMPANY`, `PLANT`, `PLANT_TYPE`, `PLANT_LOCATION`, `PLANT_FULL`, `PLANT_LOCATION_FULL`
- **`CONTRACTOR FOLLOW UP DATE 2`** (32 cols): `ID`, `Date`, `Contractor`, `Activity`, `Equipment`, `EQ_TYPE`, `Quantity`, `PA`, `Target Fleet`, `RFU`, `Breakdown`, `Act PA`, `Running Average`, `Stand by`, `Actual Utilization`, `Manpower Factor`, `Manpower Budget`, `Manpower`, `Hiring`, `Eq class`, `Eq class 2`, `WEEK`, `MONTH`, `Brand`, `Model`, `Capacity`, `YEAR`, `RFU_VARIATION`, `DT Reclaiming`, `DT OTHER`, `TARGET_RUNNING`, `Manpower On Site`
- **`CONTRACTOR_FOLLOW_UP_DATE`** (28 cols): `ID`, `Date`, `Contractor`, `Activity`, `Equipment`, `Quantity`, `PA`, `Target Fleet`, `RFU`, `Breakdown`, `Act PA`, `Running Average`, `Stand by`, `Actual Utilization`, `Manpower Factor`, `Manpower Budget`, `Manpower`, `Hiring`, `Eq class`, `WEEK`, `MONTH`, `Brand`, `Model`, `Capacity`, `YEAR`, `DT Reclaiming`, `DT OTHER`, `Manpower On Site`
- **`CONTRACTOR_FU_DT_VARIATION`** (3 cols): `date`, `contractor`, `RFU_VARIATION`
- **`CORPSAMPLEASSAY`** (26 cols): `Sampling_Contractor`, `SAMPLING_DATE`, `SAMPLE_ID`, `SAMPLE_TYPE`, `PIT`, `BLOCK_ID`, `STOCK_ID`, `RETURNDATE`, `ASSAY_TYPE`, `ACTIVITY`, `STOCK_TYPE`, `Ni`, `Fe`, `Fe2O3`, `MgO`, `SiO2`, `Al2O3`, `Co`, `CaO`, `Cr2O3`, `P2O5`, `MC`, `MnO`, `PRODUCTION_CONTRACTOR`, `FACIES`, `WMT`
- **`CRUSHER_BLENDING_DATA_TREATED`** (13 cols): `ID`, `CRUSHER_LOCATION`, `DATE`, `SHIFT`, `STOCK_LOCATION`, `PILE_ID`, `GRANULO`, `LINE`, `NB_BUCKET`, `BF`, `BCM`, `STOCK_ID`, `STOCK_PRODUCT`
- **`CRUSHER_STOCKPILE_OUTPUT_DATA_TREATED`** (17 cols): `ID`, `DATE`, `SHIFT`, `CONTRACTOR_HAULING`, `UNIT_ID_HAULER`, `STOCK_ID`, `MATERIAL`, `LINE`, `ORIGIN`, `ORIGIN 2`, `DESTINATION`, `DESTINATION 2`, `DESTINATION 3`, `RIT`, `TF`, `BCM`, `WMT`
- **`Calendar_last_Survey`** (9 cols): `DATE`, `YEAR`, `MONTH`, `WEEK`, `exercice`, `NBDAYS`, `MONTH_SALES`, `MATERIAL`, `SURVEY_DATE`
- **`DAILY_QUALITY_DISPATCH_GROUP`** (3 cols): `MAX_PLAN_HAULAGE_DATE`, `PIT`, `TOS_PILE`
- **`DAILY_QUALITY_DISPATCH_TREATED`** (22 cols): `DATE`, `SHIFT`, `PIT`, `CONTRACTOR`, `TOS_PILE`, `CATEGORY`, `CATEGORY_2`, `WMT`, `Ni_TOS`, `Ni_BM`, `Ni_Plan`, `DOME`, `DESTINATION`, `STATUS`, `EXCA`, `DT`, `HAUL_CONFIDENCE`, `TYPE`, `Ni_`, `BM_Ni`, `TOS_Ni`, `TOS_Fe`
- **`DAILY_STOCK_POS`** (36 cols): `DATE`, `YEAR`, `MONTH`, `WEEK`, `STOCK_AREA`, `STOCK_ID`, `DATE_REQUEST`, `STOCK_LAST_DATE`, `DOME_RAW`, `SURVEY_CLASS`, `REQUEST_DATE`, `REQUEST_PLANT`, `REQUEST_PLANT_CLASS`, `ACTIVITY`, `MATERIAL`, `STOCK_TYPE`, `STOCK_OPEN_DATE`, `STOCK_COMPLETE_DATE`, `STOCK_TRANSFER_DATE`, `STOCK_FINISH_DATE`, `LAST_STATUS`, `LAST_PLAN_DATE`, `STOCK_STATUS`, `WMT`, `WMT_ADJ`, `Ni`, `MC`, `Fe`, `SiO2`, `MgO`, `Co`, `P2O5`, `POS_Ni`, `REQUEST`, `LAST_REQUEST_STATUS`, `STOCK_OWNER`
- **`DARONNE_CLEAN`** (9 cols): `DATE`, `Category`, `MATERIAL`, `PIT`, `PIT_CODE`, `WMT`, `Ni`, `Fe`, `Co`
- **`DARONNE_HAUL`** (25 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY`, `ACTIVITY_TYPE`, `MATERIAL`, `TRUCK_ID`, `TRUCK_TYPE`, `TRUCK_CAPACITY`, `TRUCK_MODEL`, `TIME_LOADED`, `TIME_EMPTY`, `RIT`, `ORIGIN_AREA`, `ORIGIN_ID`, `ORIGIN_PIT`, `DESTINATION_AREA`, `DESTINATION_ID`, `KG_LOADED`, `KG_EMPTY`, `KG_NET`, `WMT`, `BCM`, `WB_ID`, `REMARK`
- **`DARONNE_HAUL_AVG`** (11 cols): `CONTRACTOR`, `SHIFT`, `MATERIAL`, `TRUCK_ID`, `ORIGIN_PIT`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `KG_EMPTY`, `WMT`
- **`DARONNE_LIM`** (5 cols): `YEAR`, `MONTH`, `PIT`, `MATERIAL`, `WMT`
- **`DARONNE_QUERY`** (21 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `TRUCK_ID`, `TIME_LOADED`, `TIME_EMPTY`, `RIT`, `ORIGIN_PIT`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `KG_LOADED`, `KG_EMPTY`, `KG_NET`, `WMT`, `BCM`, `WB_ID`, `REMARK`
- **`DARONNE_QUERY_LIM`** (21 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `TRUCK_ID`, `TIME_LOADED`, `TIME_EMPTY`, `RIT`, `ORIGIN_PIT`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `KG_LOADED`, `KG_EMPTY`, `KG_NET`, `WMT`, `BCM`, `WB_ID`, `REMARK`
- **`DATE HAULAGE RECLAIMING`** (5 cols): `DOME`, `START HAULAGE`, `LAST HAULAGE`, `START RECLAIMING`, `LAST RECLAIMING`
- **`DAY_WORKS_RIM__NO_FMS`** (5 cols): `TYPE`, `ACTIVITY_CAT`, `UNIT_ID`, `COUNT`, `INSTALLED`
- **`DAY_WORK_wEQ_INFO`** (26 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY_CAT`, `ACTIVITY_DESC`, `ACTIVITY_PLANNED`, `ACTIVITY_TIME_START`, `ACTIVITY_TIME_END`, `OPERATOR_ID`, `UNIT_TYPE`, `UNIT_CLASS`, `CAPACITY`, `UNIT_ID`, `UNIT_START_HOUR_METER`, `UNIT_END_HOUR_METER`, `LOCATION_IMPORTED`, `LOCATION`, `ROAD_NAME`, `ROAD_STA_KM`, `ROAD_END_KM`, `ROAD_LANE`, `LOADING_POINT`, `DISTANCE_KM`, `YEAR`, `MONTH`, `WEEK`
- **`DISPATCH FENI & WBN ACTUAL DT SHIFT`** (10 cols): `DATE`, `SHIFT`, `TYPE HAULAGE`, `TYPE DATA`, `CONTRACTOR`, `MATERIAL`, `COMPANY`, `ORIGIN`, `DESTINATION`, `NB DT`
- **`DISPATCH FENI ACTUAL Treated 0`** (7 cols): `DATE`, `SHIFT`, `TYPE`, `ORIGIN`, `DESTINATION`, `NB DT`, `WMT_LOG`
- **`DISPATCH RESULTS DISTANCE`** (38 cols): `YEAR`, `MONTH`, `WEEK`, `COMPANY`, `ORIGIN raw`, `ORIGIN`, `DESTINATION`, `CONTRACTOR`, `DATE`, `TYPE`, `MATERIAL`, `NB_SHIFT`, `HAULING_WMT`, `REHANDLING_WMT`, `VHGS WMT`, `HGS WMT`, `WCO WMT`, `WST WMT`, `LIM2 WMT`, `LIM1 WMT`, `CS WMT`, `TAILS WMT`, `WMT`, `DMT_`, `TOS_DMT`, `BM_DMT`, `Ni_`, `TOS_Ni`, `BM_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `RIT`, `WMT_METHOD`, `NB_DT`, `TF`, `DISTANCE_ORI_DEST`, `DISTANCE_RIT`
- **`DISPATCH RESULTS LITE 2`** (43 cols): `YEAR`, `MONTH`, `WEEK`, `COMPANY`, `ORIGIN raw`, `ORIGIN`, `DESTINATION`, `CONTRACTOR`, `DATE`, `TYPE`, `MATERIAL`, `NB_SHIFT`, `HAULING_WMT`, `REHANDLING_WMT`, `VHGS WMT`, `HGS WMT`, `WCO WMT`, `WST WMT`, `LIM2 WMT`, `LIM1 WMT`, `CS WMT`, `TAILS WMT`, `WMT`, `DMT_`, `TOS_DMT`, `BM_DMT`, `Ni_`, `Fe_`, `TOS_Ni`, `BM_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `RIT`, `WMT_METHOD`, `NB_DT`, `TF`, `TF_PLAN`, `DT PLAN`, `TARGET TRIP`, `PLAN WMT`, `DISTANCE_ORI_DEST`, `DISTANCE_RIT`
- **`DISPATCH RESULTS LITE 2 SECTION`** (46 cols): `YEAR`, `MONTH`, `WEEK`, `COMPANY`, `ORIGIN raw`, `ORIGIN`, `DESTINATION`, `CONTRACTOR`, `DATE`, `TYPE`, `MATERIAL`, `NB_SHIFT`, `WMT`, `RIT`, `NB_DT`, `TF`, `DT PLAN`, `TARGET TRIP`, `PLAN WMT`, `CRD KM0 - KM2,5`, `CRD KM2,5 - KM5,5`, `CRD KM5,5 - KM7`, `CSW KM3 - KM4`, `CSW KM4 - KM5,7`, `GOMDI KM3,7 - KM3,8`, `BLB KM2,5 - KM5,7`, `BLB KM5,7 - KM10`, `BLB KM17 - KM20`, `HFC KM5,5 - KM6,4`, `CBB KM7 - KM9`, `CBB KM9 - KM15`, `CBB KM15 - KM17`, `CBBB KM15 - KM17,5`, `KR KM7 - KM12`, `KR KM12 - KM15`, `KR KM15 - KM17`, `KR KM17 - KM21`, `KR KM21 - KM26`, `KR KM26 - KM27`, `KR KM27 - KM32`, `KR KM32 - KM37`, `KR KM37 - KM39`, `TF KM39 - KM45`, `TF KM45 - KM52`, `TF KM52 - KM60`, `TF KM60 - KM68`
- **`DISPATCH RESULTS LITE 2_OLD`** (37 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `TYPE`, `COMPANY`, `MATERIAL`, `ORIGIN raw`, `ORIGIN`, `DESTINATION`, `CONTRACTOR`, `HAULING_WMT`, `REHANDLING_WMT`, `VHGS WMT`, `HGS WMT`, `WCO WMT`, `WST WMT`, `LIM2 WMT`, `LIM1 WMT`, `CS WMT`, `TAILS WMT`, `WMT`, `DMT_`, `TOS_DMT`, `BM_DMT`, `Ni_`, `TOS_Ni`, `BM_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `RIT`, `TF`, `DT PLAN`, `TARGET TRIP`, `PLAN WMT`, `NB_DT`
- **`DISPATCH RESULTS LITE 3`** (41 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `TYPE`, `COMPANY`, `MATERIAL`, `ORIGIN raw`, `ORIGIN`, `DESTINATION`, `CONTRACTOR`, `HAULING_WMT`, `REHANDLING_WMT`, `VHGS WMT`, `HGS WMT`, `WCO WMT`, `WST WMT`, `LIM2 WMT`, `LIM1 WMT`, `CS WMT`, `TAILS WMT`, `WMT`, `DMT_`, `TOS_DMT`, `BM_DMT`, `Ni_`, `TOS_Ni`, `BM_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `RIT`, `TF`, `DT PLAN`, `TARGET TRIP`, `PLAN WMT`, `NB_DT`, `MATERIAL_PLAN`, `MATERIAL_CLASS_PLAN`, `MATERIAL_TOS`, `MATERIAL_CLASS_TOS`
- **`DISPATCH ROADS & CALENDAR SHIFT`** (39 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `SHIFT`, `ORIGIN`, `DESTINATION`, `KM ORI`, `KM DEST`, `DISTANCE GROSS (KM)`, `CRD KM0 - KM2,5`, `CRD KM2,5 - KM5,5`, `CRD KM5,5 - KM7`, `CSW KM3 - KM4`, `CSW KM4 - KM5,7`, `GOMDI KM3,7 - KM3,8`, `BLB KM2,5 - KM5,7`, `BLB KM5,7 - KM10`, `BLB KM17 - KM20`, `HFC KM5,5 - KM6,4`, `CBB KM7 - KM9`, `CBB KM9 - KM15`, `CBB KM15 - KM17`, `CBBB KM15 - KM17,5`, `KR KM7 - KM12`, `KR KM12 - KM15`, `KR KM15 - KM17`, `KR KM17 - KM21`, `KR KM21 - KM26`, `KR KM26 - KM27`, `KR KM27 - KM32`, `KR KM32 - KM37`, `KR KM37 - KM39`, `TF KM39 - KM45`, `TF KM45 - KM52`, `TF KM52 - KM60`, `TF KM60 - KM68`, `DISPATCH ZONE`, `CONTRACTOR`
- **`DISPATCH RSF ACTUAL Treated`** (10 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `COMPANY`, `NB  DT`, `ACTUAL WMT`, `ORIGIN`, `DESTINATION`, `MATERIAL`, `TYPE HAULAGE`
- **`DISPATCH WBN PLAN`** (14 cols): `CONTRACTOR`, `DATE`, `TYPE`, `MATERIAL`, `ORIGIN`, `DESTINATION`, `TYPE DATA`, `COMPANY`, `DISPATCH ZONE`, `NB DT`, `TF`, `PRODUCTIVITY TARGET 2`, `PRODUCTIVITY TARGET`, `PLAN WMT`
- **`DISPATCH WMT VERY SHORT TERM`** (14 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `SHIFT`, `TYPE`, `COMPANY`, `MATERIAL`, `ORIGIN`, `DESTINATION`, `KM ORI`, `KM DEST`, `WMT`, `CONTRACTOR`
- **`DISPATCH_PRODUCTIVITY_TARGET`** (3 cols): `ORIGIN`, `DESTINATION`, `PRODUCTIVITY`
- **`DISTANCE_HAULING_CHECK`** (13 cols): `TABLE`, `DATE`, `CONTRACTOR`, `MATERIAL`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `DISTANCE`, `WMT`, `RIT`, `SPV_WBN`, `SPV_CONTRACTOR`
- **`DISTANCE_MINING_CHECK`** (16 cols): `TABLE`, `CONTRACTOR`, `DATE`, `SHIFT`, `PIT`, `SUBPIT`, `DIGGER`, `BLOCK_ID`, `MATERIAL`, `MATERIAL2`, `DUMPING_AREA`, `TOS_PILE`, `RIT`, `DISTANCE`, `WMT`, `BCM`
- **`DOME INFO`** (10 cols): `DOME`, `LOCATION`, `STATUS HAULAGE`, `STATUS RECLAIMING`, `HIGH TURN`, `PRIORITY RECLAIM`, `CLOSE_HAULING`, `CLOSE_RECLAIMING`, `MATERIAL`, `REMARK`
- **`DOME WBN`** (1 cols): `DOME`
- **`DT_DENSITY_HAULROAD`** (33 cols): `DATE`, `TYPE`, `COMPANY`, `ORIGIN`, `DESTINATION`, `NB_DT`, `DT ON CRD KM0 - KM2,5`, `DT ON CRD KM2,5 - KM5,5`, `DT ON CRD KM5,5 - KM7`, `DT ON CSW KM3 - KM4`, `DT ON CSW KM4 - KM5,7`, `DT ON GOMDI KM3,7 - KM3,8`, `DT ON BLB KM2,5 - KM5,7`, `DT ON BLB KM5,7 - KM10`, `DT ON BLB KM17 - KM20`, `DT ON HFC KM5,5 - KM6,4`, `DT ON CBB KM7 - KM9`, `DT ON CBB KM9 - KM15`, `DT ON CBB KM15 - KM17`, `DT ON CBBB KM15 - KM17,5`, `DT ON KR KM7 - KM12`, `DT ON KR KM12 - KM15`, `DT ON KR KM15 - KM17`, `DT ON KR KM17 - KM21`, `DT ON KR KM21 - KM26`, `DT ON KR KM26 - KM27`, `DT ON KR KM27 - KM32`, `DT ON KR KM32 - KM37`, `DT ON KR KM37 - KM39`, `DT ON TF KM39 - KM45`, `DT ON TF KM45 - KM52`, `DT ON TF KM52 - KM60`, `DT ON TF KM60 - KM68`
- **`DT_DENSITY_HAULROAD_treated`** (3 cols): `DATE`, `SECTION_NAME`, `Total_DT`
- **`DT_DENSITY_HAULROAD_treated2`** (5 cols): `DATE`, `SECTION_NAME`, `APPROX_DISTANCE`, `Total_DT`, `DT/KM`
- **`DT_DENSITY_Haulage_Reclaiming`** (5 cols): `DATE`, `SECTION_NAME`, `APPROX_DISTANCE`, `Total_DT`, `DT/KM`
- **`DT_DENSITY_RECLAIMING`** (7 cols): `DATE`, `TYPE`, `COMPANY`, `ORIGIN`, `DESTINATION`, `WMT`, `DT`
- **`DT_DENSITY_RECLAIMING_treated`** (35 cols): `DATE`, `TYPE`, `COMPANY`, `ORIGIN`, `DESTINATION`, `WMT`, `DT`, `DISTANCE GROSS (KM)`, `DT ON CRD KM0 - KM2,5`, `DT ON CRD KM2,5 - KM5,5`, `DT ON CRD KM5,5 - KM7`, `DT ON CSW KM3 - KM4`, `DT ON CSW KM4 - KM5,7`, `DT ON GOMDI KM3,7 - KM3,8`, `DT ON BLB KM2,5 - KM5,7`, `DT ON BLB KM5,7 - KM10`, `DT ON BLB KM17 - KM20`, `DT ON HFC KM5,5 - KM6,4`, `DT ON CBB KM7 - KM9`, `DT ON CBB KM9 - KM15`, `DT ON CBB KM15 - KM17`, `DT ON CBBB KM15 - KM17,5`, `DT ON KR KM7 - KM12`, `DT ON KR KM12 - KM15`, `DT ON KR KM15 - KM17`, `DT ON KR KM17 - KM21`, `DT ON KR KM21 - KM26`, `DT ON KR KM26 - KM27`, `DT ON KR KM27 - KM32`, `DT ON KR KM32 - KM37`, `DT ON KR KM37 - KM39`, `DT ON TF KM39 - KM45`, `DT ON TF KM45 - KM52`, `DT ON TF KM52 - KM60`, `DT ON TF KM60 - KM68`
- **`DT_DENSITY_RECLAIMING_treated2`** (3 cols): `DATE`, `SECTION_NAME`, `Total_DT`
- **`DT_DENSITY_RECLAIMING_treated3`** (5 cols): `DATE`, `SECTION_NAME`, `APPROX_DISTANCE`, `Total_DT`, `DT/KM`
- **`EQUIPMENTS_CLEAN`** (17 cols): `ID`, `CONTRACTOR`, `ID_EQ`, `ID_EQ_LETTERS`, `ID_EQ_NUMBERS`, `TYPE_CLEAN`, `ID_EQ_CLEANED`, `OWNER`, `TYPE`, `DIGIT`, `MANUFACTURER`, `MODEL`, `CAPACITY`, `NB_TYRES`, `BUILD_YEAR`, `DIVISION`, `NEW_ID_EQ`
- **`EQUIPMENTS_CLEAN2`** (16 cols): `ID`, `CONTRACTOR`, `ID_EQ`, `ID_EQ_LETTERS`, `ID_EQ_NUMBERS`, `ID_EQ_CLEANED`, `OWNER`, `TYPE`, `DIGIT`, `MANUFACTURER`, `MODEL`, `CAPACITY`, `NB_TYRES`, `BUILD_YEAR`, `DIVISION`, `NEW_ID_EQ`
- **`EQUIPMENTS_HOURLY_STATUS_COMPACT`** (8 cols): `CONTRACTOR`, `DATE`, `SHIFT`, `ACTIVITY`, `NB_UNIT`, `UNIT_TYPE`, `LOCATION`, `STATUS`
- **`EQUIPMENTS_HOURLY_STATUS_DAILY`** (13 cols): `CONTRACTOR`, `DATE`, `SHIFT`, `STATUS`, `ACTIVITY`, `ID_EQ`, `TYPE`, `LOCATION`, `LOCATION_DETAILS`, `WORKING_HOURS`, `STBY_HOURS`, `BD_HOURS`, `PM_HOURS`
- **`EQUIPMENTS_HOURLY_STATUS_SUMMARY`** (14 cols): `CONTRACTOR`, `DATE`, `SHIFT`, `ACTIVITY`, `ID_EQ`, `TYPE`, `LOCATION`, `LOCATION_DETAILS`, `WORKING_HOURS`, `STBY_HOURS`, `BD_HOURS`, `PM_HOURS`, `TOTAL_HOURS`, `STATUS`
- **`EQUIPMENTS_QR_CODE_VALUE`** (3 cols): `ID`, `QR_CODE_VALUE`, `URL`
- **`EQUIPMENTS_STATUS_BREAKDOWN`** (13 cols): `DATE`, `SHIFT`, `DATETIME`, `CONTRACTOR`, `UNIT_ID`, `WORKING_HOURS`, `STBY_HOURS`, `BD_HOURS`, `PM_HOURS`, `OPERATING_HOURS`, `PREV_DATETIME`, `STATUS_BD`, `DIVISION`
- **`EQUIPMENT_LAST_COMMISSIONING`** (8 cols): `EQUIPMENT_ID_CLEAN`, `CONTRACTOR`, `EQUIPMENT_TYPE`, `ODOMETER`, `COMMISSIONING_DATE`, `EXPIRED_DATE`, `STATUS`, `REMAINING`
- **`EQUIPMENT_NEW_ID`** (14 cols): `Company`, `Vender Clasification`, `Brand`, `Model`, `Equipment_Size`, `Finance_Status`, `Equipment_Type`, `TYPE_ACR`, `OEM_PIN `, `OLD_ID`, `OLD_ID_LETTERS`, `OLD_ID_DIGIT`, `NEW_DIGIT`, `NEW_ID`
- **`EQUIPMENT_PLAN_ACTUAL`** (11 cols): `TEAM`, `TYPE`, `YEAR`, `MONTH`, `DATE`, `ACTIVITY`, `ORIGIN`, `CONTRACTOR`, `MATERIAL`, `UNIT_TYPE`, `NB_UNIT`
- **`EQUIPMENT_STATUS_FULL`** (13 cols): `DATE`, `SHIFT`, `ACTIVITY`, `CONTRACTOR`, `UNIT_TYPE`, `MANUFACTURER`, `BUILD_YEAR`, `UNIT_ID`, `WORKING_HOURS`, `STBY_HOURS`, `BD_HOURS`, `PM_HOURS`, `OPERATING_HOURS`
- **`EQUIPMENT_STATUS_WORKING_HOURS`** (13 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `STATUS`, `ACTIVITY`, `UNIT_TYPE`, `UNIT_ID`, `SCH`, `UNSCH`, `STAND BY`, `WORKING HOURS`, `OPERATING HOURS`, `STB_PROP`
- **`EQUIPMENT_STATUS_WORKING_HOURS_2`** (15 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `UNIT_TYPE`, `NB_UNITS`, `STATUS`, `ACTIVITY`, `SCH HOURS`, `UNSCH HOURS`, `STAND BY HOURS`, `WORKING HOURS`, `OPERATING HOURS`, `STB_PROP`, `NB_STB_PROP`, `NB_STB_FULL`
- **`EQ_STATUS_WATER_MANAGEMENT`** (11 cols): `CONTRACTOR`, `DATE`, `SHIFT`, `ID_EQ`, `LOCATION`, `LOCATION_DETAILS`, `SP_ID`, `WORKING_HOURS`, `STBY_HOURS`, `BD_HOURS`, `PM_HOURS`
- **`FENI_RECLAIMING_PLAN_WITH_GRADE`** (15 cols): `DATE`, `SHIFT`, `ORE LOCATION`, `DOME`, `PLAN VEHICULE`, `PLANNED WEIGHBRIDGE`, `PLANNED WMT`, `DESTINATION`, `FENI`, `Ni`, `Fe`, `SiO2`, `MgO`, `MC`, `DMT`
- **`FENI_REQUESTS_FIRST`** (7 cols): `STOCK_ID`, `ORIGIN_AREA`, `DESTINATION_ID`, `DESTINATION_AREA`, `FIRST_REQUEST_SHIFT`, `FIRST_REQUEST_DATE`, `WMT_REQUEST`
- **`FENI_REQUESTS_TREATED`** (6 cols): `STOCK_ID`, `ORIGIN_AREA`, `DESTINATION_ID`, `DESTINATION_AREA`, `SHIFT_REQUEST`, `DATE_REQUEST`
- **`FINANCE_MANAGEMENT`** (47 cols): `TYPE`, `PLAN_ACTUAL`, `TYPE_CLASS`, `TYPE_ITEM`, `YEAR`, `MONTH`, `YEAR_SALES`, `MONTH_SALES`, `WEEK`, `DATE`, `CONTRACTOR_MINING`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `STOCK_TYPE`, `STOCK_AREA`, `PLANT`, `PLANT_COMPANY`, `STOCK_ID`, `REF_NO`, `CONTRACT`, `BATCH_ID`, `ORIGIN_REGION`, `ORIGIN_PIT`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `WMT_METHOD`, `RIT`, `WMT`, `Ni`, `MC`, `Fe`, `SiO2`, `MgO`, `Al2O3`, `Co`, `Cr2O3`, `P2O5`, `POS_ASSAY_TYPE`, `POS_ASSAY_STATUS_%`, `YARD_ASSAY_TYPE`, `YARD_ASSAY_STATUS_%`, `REQUEST`, `REQUEST_COMPANY`, `REJECT_ACTIVITY`
- **`FINANCE_MANAGEMENT_BOD`** (45 cols): `TYPE`, `PLAN_ACTUAL`, `YEAR`, `MONTH`, `YEAR_SALES`, `MONTH_SALES`, `WEEK`, `DATE`, `CONTRACTOR_MINING`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `STOCK_TYPE`, `STOCK_AREA`, `PLANT`, `PLANT_COMPANY`, `STOCK_ID`, `REF_NO`, `CONTRACT`, `BATCH_ID`, `ORIGIN_REGION`, `ORIGIN_PIT`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `WMT_METHOD`, `RIT`, `WMT`, `Ni`, `MC`, `Fe`, `SiO2`, `MgO`, `Co`, `Al2O3`, `P2O5`, `POS_ASSAY_TYPE`, `POS_ASSAY_STATUS_%`, `YARD_ASSAY_TYPE`, `YARD_ASSAY_STATUS_%`, `REQUEST`, `REQUEST_COMPANY`, `REJECT_ACTIVITY`, `CF`
- **`FINANCE_MANAGEMENT_RE`** (48 cols): `TYPE`, `PLAN_ACTUAL`, `TYPE_CLASS`, `TYPE_ITEM`, `YEAR`, `MONTH`, `YEAR_SALES`, `MONTH_SALES`, `WEEK`, `DATE`, `CONTRACTOR_MINING`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `STOCK_TYPE`, `STOCK_AREA`, `PLANT`, `PLANT_COMPANY`, `STOCK_ID`, `REF_NO`, `CONTRACT`, `BATCH_ID`, `ORIGIN_REGION`, `ORIGIN_PIT`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `WMT_METHOD`, `RIT`, `WMT_ORI`, `WMT`, `Ni`, `MC`, `Fe`, `SiO2`, `MgO`, `Al2O3`, `Co`, `Cr2O3`, `P2O5`, `POS_ASSAY_TYPE`, `POS_ASSAY_STATUS_%`, `YARD_ASSAY_TYPE`, `YARD_ASSAY_STATUS_%`, `REQUEST`, `REQUEST_COMPANY`, `REJECT_ACTIVITY`
- **`FINANCE_PHYSICAL_FLOW`** (41 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `STOCK_TYPE`, `STOCK_AREA`, `PLANT`, `PLANT_COMPANY`, `STOCK_ID`, `REJECT_ACTIVITY`, `BATCH_ID`, `ORIGIN_REGION`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `YEAR_SALES`, `MONTH_SALES`, `WMT_METHOD`, `RIT`, `WMT`, `MC`, `Ni`, `Fe`, `SiO2`, `MgO`, `Al2O3`, `Co`, `Cr2O3`, `P2O5`, `POS_ASSAY_TYPE`, `POS_ASSAY_STATUS_%`, `YARD_ASSAY_TYPE`, `YARD_ASSAY_STATUS_%`, `REQUEST`, `REQUEST_COMPANY`, `SALES_%`, `CONTRACTOR_MINING`
- **`FULL HAULAGE`** (12 cols): `TYPE`, `DATE`, `SMU`, `DOME`, `DOME 2`, `WEIGHBRIDGE WMT`, `WBN SURVEY WMT`, `ADJUSTMENT`, `ORIGINAL WMT`, `WMT`, `CONTRACTOR`, `DESTINATION`
- **`FULL_ASSAYS_STOCK`** (26 cols): `ASSAY_DATA`, `ASSAY_TYPE`, `ASSAY_STATUS`, `ASSAY_DATE`, `CONTRACTOR`, `STOCK_SUBLOT`, `STOCK_TYPE`, `STOCK_ID`, `RIT`, `WMT_CERT`, `Al2O3`, `CaO`, `Co`, `Cr2O3`, `Fe_ORI`, `Fe`, `Fe2O3`, `MC`, `MgO_ORI`, `MgO`, `MnO`, `Ni_ORI`, `Ni`, `P2O5`, `SiO2_ORI`, `SiO2`
- **`FULL_FULL_PRODUCTION`** (12 cols): `DATE`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `ORIGIN_TYPE`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_TYPE`, `DESTINATION_AREA`, `DESTINATION_ID`, `RIT`, `WMT`
- **`FULL_PLAN`** (17 cols): `SOURCE_TYPE`, `ACTIVITY`, `DATE`, `CONTRACTOR`, `ENTITY`, `MATERIAL`, `ORIGIN_TYPE`, `ORIGIN_PIT`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_TYPE`, `DESTINATION_AREA`, `DESTINATION_ID`, `WMT_METHOD`, `RIT`, `WMT`, `BCM`
- **`FULL_PRODUCTION`** (17 cols): `DATE`, `CONTRACTOR`, `ACTIVITY`, `SURVEY_TYPE`, `MATERIAL`, `ORIGIN_PIT`, `ORIGIN_TYPE`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_TYPE`, `DESTINATION_AREA`, `DESTINATION_ID`, `DOME`, `RIT`, `WMT`, `WMT_METHOD`, `SURVEY_WEEK`
- **`FULL_PRODUCTION_GROUP`** (21 cols): `DATE`, `YEAR`, `MONTH`, `MONTH_SALES`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `ORIGIN_TYPE`, `ORIGIN_PIT`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_TYPE`, `DESTINATION_AREA`, `DESTINATION_ID`, `DOME`, `WMT_METHOD`, `SURVEY_TYPE`, `SURVEY_WEEK`, `RIT`, `WMT`, `WMT_BALANCE`
- **`FULL_PRODUCTION_ONLY`** (16 cols): `DATE`, `CONTRACTOR`, `ENTITY`, `ACTIVITY`, `MATERIAL`, `ORIGIN_PIT`, `ORIGIN_TYPE`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_TYPE`, `DESTINATION_AREA`, `DESTINATION_ID`, `WMT_METHOD`, `RIT`, `WMT`, `BCM`
- **`FULL_PRODUCTION_RECOMPACT`** (20 cols): `DATE`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `STOCK_POINT`, `STOCK_TYPE`, `STOCK_AREA`, `STOCK_ID`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `WMT_METHOD`, `SURVEY_TYPE`, `BATCH_ID`, `SURVEY_WEEK`, `RIT`, `WMT`, `WMT_DEST`, `WMT_ORI`
- **`FULL_PRODUCTION_REFORMAT`** (18 cols): `OBJECT_NAME`, `DATE`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `STOCK_POINT`, `STOCK_TYPE`, `STOCK_AREA`, `STOCK_ID`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `RIT`, `WMT`, `WMT_METHOD`, `SURVEY_TYPE`, `SURVEY_WEEK`
- **`FULL_PRODUCTION_VS_PLAN`** (17 cols): `SOURCE_TYPE`, `DATE`, `CONTRACTOR`, `ENTITY`, `ACTIVITY`, `MATERIAL`, `ORIGIN_PIT`, `ORIGIN_TYPE`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_TYPE`, `DESTINATION_AREA`, `DESTINATION_ID`, `WMT_METHOD`, `RIT`, `WMT`, `BCM`
- **`FeNi Reclaiming Plan Treated 1`** (10 cols): `DATE`, `SHIFT`, `ORE LOCATION`, `DOME`, `DOME ID FENI`, `PLAN VEHICULE`, `PLANNED WEIGHBRIDGE`, `PLANNED WMT`, `DOME_RAW`, `DESTINATION`
- **`FeNi Reclaiming Plan Treated 2`** (13 cols): `DATE`, `SHIFT`, `ORE LOCATION`, `DOME`, `PLANNED VEHICULE`, `PLANNED WMT`, `Ni`, `MC`, `Fe`, `SiO2`, `MgO`, `DMT`, `WBN OR NOT`
- **`FeNi Reclaiming Plan Treated 3`** (3 cols): `DOME`, `DATE`, `PLANNED WMT`
- **`GEO_TOS_DUPLICATE`** (33 cols): `Contractor_Sample`, `Contractor_Assay`, `Date_Sample`, `SAMPLE_JOB`, `SAMPLE_ID`, `BLOCK_ID`, `SAMPLE_TYPE`, `SAMPLE_CONTRACTOR`, `ANALYSIS_TYPE`, `STOCK_AREA`, `STOCK_ID`, `DATE_RECEIVED`, `DATE_ANALYSIS`, `ASSAY_TYPE`, `ACTIVITY`, `STOCK_TYPE`, `Ni`, `Fe`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `Fe2O3`, `MnO`, `P2O5`, `SiO2`, `MgO`, `K2O`, `Na2O`, `TiO2`, `LOI`, `MC`, `REMARK`
- **`HAUL VERY SHORT TERM TREATED 1`** (12 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `MATERIAL`, `ORIGIN`, `DESTINATION`, `BUYER`, `WMT`, `TYPE HAULAGE`, `DESTINATION YANG BAGUS`, `MATERIAL YANG BAGUS`, `ORIGIN YANG BAGUS`
- **`HAUL VERY SHORT TERM TREATED 2`** (9 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `WMT`, `DESTINATION`, `BUYER`, `MATERIAL`, `ORIGIN`, `TYPE`
- **`HAUL VERY SHORT TERM TREATED 3`** (20 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `TYPE`, `COMPANY`, `MATERIAL`, `ORIGIN`, `DESTINATION`, `KM ORI`, `KM DEST`, `WMT`, `CONTRACTOR`, `NB DT`, `TF`, `PLAN DT`, `TARGET TRIP`, `TF_PLAN`, `PLAN WMT`, `SHIFT`
- **`HAULAGE_BY_CONTRACTOR_TRUCK`** (5 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `TRUCK_ID`, `RIT_PER_DT`
- **`HAULAGE_CLEAN`** (20 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `TRUCK_ID`, `ORIGIN_PIT`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `RIT`, `WMT`, `WMT_METHOD`, `WB_ID`, `TIME_EMPTY`, `TIME_LOADED`, `KG_EMPTY`, `KG_LOADED`, `KG_NET`
- **`HAULAGE_CLEAN2`** (14 cols): `DATE`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `TRUCK_ID`, `ORIGIN_PIT`, `ORIGIN_AREA`, `ORIGIN_ID_ORI`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `RIT`, `WMT`, `WMT_METHOD`
- **`HAULAGE_CLEAN_FOR_DT`** (23 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `TRUCK_ID`, `ORIGIN_PIT`, `ORIGIN_AREA`, `ORIGIN_AREA_GEN`, `STOCK_AREA_ORI`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_AREA_GEN`, `DESTINATION_ID`, `RIT`, `WMT`, `WMT_METHOD`, `WB_ID`, `TIME_EMPTY`, `TIME_LOADED`, `KG_EMPTY`, `KG_LOADED`, `KG_NET`
- **`HAULAGE_COMPLETE`** (24 cols): `TYPE`, `DATE`, `SMU`, `DOME`, `LOCATION`, `WMT`, `ORIGINAL WMT`, `CONTRACTOR`, `DESTINATION`, `ORIGIN`, `MATERIAL`, `MC`, `DMT`, `Ni`, `Fe`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `Fe2O3`, `MgO`, `MnO`, `P2O5`, `SiO2`
- **`HAULAGE_COMPLETE_VIA_BM`** (24 cols): `TYPE`, `DATE`, `SMU`, `DOME`, `LOCATION`, `WMT`, `ORIGINAL WMT`, `CONTRACTOR`, `DESTINATION`, `ORIGIN`, `MATERIAL`, `MC`, `DMT`, `Ni`, `Fe`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `Fe2O3`, `MgO`, `MnO`, `P2O5`, `SiO2`
- **`HAULAGE_ERROR`** (7 cols): `PLEASE_CORRECT`, `ACTIVITY`, `MATERIAL`, `ORIGIN_ID`, `DESTINATION_ID`, `ORI_TYPE`, `DEST_TYPE`
- **`HAULAGE_GET_IWIP_PLAN_TICKET_NO`** (13 cols): `ID`, `DATE`, `IW_DATE`, `CONTRACTOR`, `TRUCK_ID`, `KG_LOADED`, `KG_EMPTY`, `KG_NET`, `TIME_LOADED`, `TIME_EMPTY`, `WB_ID_RAW`, `TICKET_NO`, `IW_TRUCK_ID`
- **`HAULAGE_GET_IWIP_TICKET_NO`** (15 cols): `ID`, `DATE`, `CONTRACTOR`, `TRUCK_ID`, `KG_LOADED`, `KG_EMPTY`, `KG_NET`, `TIME_LOADED`, `TIME_EMPTY`, `WB_ID_RAW`, `IWIP_TIME_LOADED`, `IWIP_TIME_EMPTY`, `IWIP_DESTINATION_ID`, `TICKET_NO`, `IW_TRUCK_ID`
- **`HAULAGE_IWIP_CLEAN`** (33 cols): `SERIAL_NO`, `WB_TIME`, `WB_ID`, `TICKET_NO`, `TRUCK_ID`, `CARGO_NAME`, `DOME_ORIGINAL`, `SELLER`, `BUYER`, `CONTRACTOR`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `WEIGHING_STATUS`, `ACTIVITY`, `MATERIAL`, `GROSS_WEIGHT`, `TARE_WEIGHT`, `NET_WEIGHT`, `WMT`, `IS_NET_VALIDATED`, `FIRST_WB_TIME`, `SECOND_WB_TIME`, `GROSS_WEIGHT_TIME`, `TARE_WEIGHT_TIME`, `GROSS_WEIGHT_POINT`, `TARE_WEIGHT_POINT`, `IS_COMPLETED`, `SHIFT`, `REMARKS`, `HOUR`, `DATE`
- **`HAULAGE_IWIP_VS_RECLAIM`** (5 cols): `DATE`, `ACTIVITY`, `DOME_ORIGINAL`, `WB_IWIP_WMT`, `R_WMT`
- **`HAULAGE_IWIP_WASTE`** (28 cols): `FETCH_DATE`, `SERIAL_NO`, `WB_TIME`, `DATE`, `WB_ID`, `TICKET_NO`, `TRUCK_ID`, `CARGO_NAME`, `ORIGIN_ID`, `SELLER`, `BUYER`, `CONTRACTOR`, `ORIGIN_AREA`, `DESTINATION_AREA`, `WEIGHING_STATUS`, `BUSINESS_TYPE`, `GROSS_WEIGHT`, `TARE_WEIGHT`, `NET_WEIGHT`, `FIRST_WB_TIME`, `SECOND_WB_TIME`, `GROSS_WEIGHT_TIME`, `TARE_WEIGHT_TIME`, `GROSS_WEIGHT_POINT`, `TARE_WEIGHT_POINT`, `IS_COMPLETED`, `SHIFT`, `REMARKS`
- **`HAULAGE_LIM_BATCH`** (2 cols): `DESTINATION_ID`, `BATCH_ID`
- **`HAULAGE_ORIGIN_PIT`** (26 cols): `ID`, `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY`, `ACTIVITY_TYPE`, `MATERIAL`, `TRUCK_ID`, `TRUCK_TYPE`, `TRUCK_CAPACITY`, `TRUCK_MODEL`, `TIME_LOADED`, `TIME_EMPTY`, `RIT`, `ORIGIN_AREA`, `ORIGIN_ID`, `ORIGIN_PIT`, `DESTINATION_AREA`, `DESTINATION_ID`, `KG_LOADED`, `KG_EMPTY`, `KG_NET`, `WMT`, `BCM`, `WB_ID`, `REMARK`
- **`HAULAGE_PER_PILE`** (15 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `ORIGIN_PIT`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `WMT`, `Ni_`, `BM_Ni`, `TOS_Ni`, `TOS_Fe`
- **`HAULAGE_PER_PILE_AND_PLAN`** (24 cols): `DATE`, `SHIFT`, `ACT_CONTRACTOR`, `PLAN_CONTRACTOR`, `ACTIVITY`, `ACT_MATERIAL`, `ACT_PIT`, `PLAN_PIT`, `PIT`, `ORIGIN_AREA`, `ACT_PILE`, `PLAN_PILE`, `PILE`, `COMPLIANCE`, `ACT_DESTINATION`, `PLAN_DESTINATION`, `ACT_DOME`, `ACT_WMT`, `PLAN_WMT`, `Ni_`, `BM_Ni`, `TOS_Ni`, `TOS_Fe`, `CLASS_MATERIAL_PLAN`
- **`HAULAGE_PER_PILE_AND_PLAN_TEMPORAL`** (25 cols): `DATE`, `SHIFT`, `ACT_CONTRACTOR`, `PLAN_CONTRACTOR`, `ACTIVITY`, `ACT_MATERIAL`, `ACT_PIT`, `PLAN_PIT`, `PIT`, `ORIGIN_AREA`, `ACT_PILE`, `PLAN_PILE`, `PILE`, `COMPLIANCE`, `ACT_DESTINATION`, `PLAN_DESTINATION`, `ACT_DOME`, `ACT_WMT`, `PLAN_WMT`, `Ni_`, `BM_Ni`, `TOS_Ni`, `TOS_Fe`, `CLASS_MATERIAL_PLAN`, `CHECK_NEXT`
- **`HAULAGE_PILE_INFO`** (20 cols): `ID`, `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `TRUCK_ID`, `TIME_LOADED`, `TIME_EMPTY`, `RIT`, `ORIGIN_PIT`, `ORIGIN_AREA`, `ORIGIN_ID`, `CONTRACTOR_PILE`, `DESTINATION_AREA`, `DESTINATION_ID`, `KG_LOADED`, `KG_EMPTY`, `KG_NET`, `WMT`
- **`HAULAGE_PIT_ORIGIN_DESTINATION`** (4 cols): `ORIGIN_ID`, `ORIGIN_PIT`, `DESTINATION_ID`, `WMT`
- **`HAULAGE_VS_IWIP_SYSTEM`** (22 cols): `SOURCE_TABLE`, `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `TRUCK_ID`, `TIME_LOADED`, `TIME_EMPTY`, `RIT`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `KG_LOADED`, `KG_EMPTY`, `KG_NET`, `WMT`, `BCM`, `WB_ID`, `REMARK`, `TICKET_NO`
- **`HAULAGE_VS_OMR`** (6 cols): `CONTRACTOR_HAUL`, `TOS_PILE`, `DATE_OMR_MAX`, `DATE_HAUL_MAX`, `OMR_RIT`, `HAUL_RIT`
- **`HAULAGE_VS_OMR_ORI_DEST`** (11 cols): `DATE`, `ACTIVITY`, `MATERIAL`, `CONTRACTOR`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `OMR_RIT`, `HAUL_RIT`, `HAUL_WMT`
- **`HAULAGE_VS_PROD_MONTHLY_CF`** (5 cols): `CONTRACTOR`, `DATE`, `PIT`, `MATERIAL`, `CF`
- **`HAULAGE_VS_PROD_PILES_CF`** (9 cols): `CONTRACTOR`, `DATE`, `PIT`, `TOS_PILE`, `PROD_WMT`, `MATERIAL`, `RIT`, `HAUL_WMT`, `CF_PILE`
- **`HAULAGE_VS_RECLAIM`** (7 cols): `STOCK_ID`, `CONTRACTOR`, `CONTRACTOR_WMT`, `DATE_HAUL`, `WMT_HAUL`, `WMT_RECLAIM`, `CONTRACTOR_DIFF`
- **`HAULAGE_WB_NOT_ON_THE_WAY`** (22 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `TRUCK_ID`, `WMT`, `TIME_LOADED`, `TIME_EMPTY`, `ORIGIN_ID`, `DESTINATION_ID`, `ORIGIN_AREA`, `DESTINATION_AREA`, `WB_ID`, `ORIGIN_ROAD`, `WB_ROAD`, `DESTINATION_ROAD`, `ORIGIN_KM`, `WB_KM`, `DESTINATION_KM`, `DIFF_KM`, `TICKET_NO`
- **`HAULAGE_WITH_DT_TYPES`** (25 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `TRUCK_ID`, `ORIGIN_PIT`, `ORIGIN_AREA`, `ORIGIN_AREA_GEN`, `STOCK_AREA_ORI`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_AREA_GEN`, `DESTINATION_ID`, `RIT`, `WMT`, `WMT_METHOD`, `WB_ID`, `TIME_EMPTY`, `TIME_LOADED`, `KG_EMPTY`, `KG_LOADED`, `KG_NET`, `MANUFACTURER`, `MODEL`
- **`HRM`** (24 cols): `ID`, `UUID`, `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY_CAT`, `ACTIVITY_DESC`, `ACTIVITY_PLANNED`, `ACTIVITY_TIME_START`, `ACTIVITY_TIME_END`, `OPERATOR_ID`, `UNIT_TYPE`, `UNIT_CLASS`, `UNIT_ID`, `UNIT_START_HOUR_METER`, `UNIT_END_HOUR_METER`, `LOCATION`, `ROAD_NAME`, `ROAD_STA_KM`, `ROAD_END_KM`, `ROAD_LANE`, `LOADING_POINT`, `LOADING_RIT`, `DISTANCE_KM`
- **`IMPORT_HEATMAP`** (13 cols): `TABLE`, `DATE`, `SHIFT`, `CKB`, `GMG`, `HJS`, `MTM`, `PPP`, `RIM`, `PS`, `SMA`, `SSS`, `STM`
- **`LIM TOS PILE DOME For HAULAGE`** (2 cols): `TOS_PILE`, `DOME`
- **`LME_FOR_HMA_Ni`** (7 cols): `YEAR`, `MONTH`, `MONTH_DATE`, `DATE`, `LME_Ni_USD`, `LME_Ni_3MONTH_USD`, `LME_Ni_STOCK_ASSET`
- **`LME_NEW_HMA`** (7 cols): `YEAR`, `MONTH`, `MONTH_DATE`, `START`, `END`, `HMA`, `USD`
- **`LME_Ni_USD`** (4 cols): `DATE`, `LME_Ni_USD`, `LME_Ni_3MONTH_USD`, `LME_Ni_STOCK_ASSET`
- **`Lab_Duplicate`** (37 cols): `Sampling_contractor`, `Sampling_date`, `Original_Sample`, `Duplicate_Sample`, `Duplicate_Type`, `Pit`, `Stock_ID`, `ReturnDate`, `Assay_Type`, `Activity`, `Stock_type`, `Production_Contractor`, `Facies`, `Orig_Ni`, `Dup_Ni`, `Orig_Fe`, `Dup_Fe`, `Orig_Fe2O3`, `Dup_Fe2O3`, `Orig_MgO`, `Dup_MgO`, `Orig_SiO2`, `Dup_SiO2`, `Orig_Al2O3`, `Dup_Al2O3`, `Orig_Co`, `Dup_Co`, `Orig_CaO`, `Dup_CaO`, `Orig_Cr2O3`, `Dup_Cr2O3`, `Orig_P2O5`, `Dup_P2O5`, `Orig_MnO`, `Dup_MnO`, `Orig_MC`, `Dup_MC`
- **`MINING_EQUIPMENTS`** (8 cols): `DATE`, `CONTRACTOR`, `ORIGIN_AREA`, `ID_EQ`, `TYPE`, `MODEL`, `CAPACITY`, `DIVISION`
- **`MINING_HAULAGE_PLAN_AND_ACTUAL`** (63 cols): `ACTIVITY`, `ACTIVITY2`, `ACTIVITY3`, `YEAR`, `MONTH`, `WEEK`, `DATE`, `CONTRACTOR`, `PIT`, `SUBPIT`, `MATERIAL_PROD`, `MATERIAL_CLASS_PROD`, `MATERIAL_PLAN`, `MATERIAL_CLASS_PLAN`, `MATERIAL_PLAN_NO_WA`, `MATERIAL`, `BLOCK_ID`, `DESTINATION`, `DESTINATION_AREA`, `DESTINATION_GROUP`, `TOS_PILE`, `HAUL_CONFIDENCE`, `BCM`, `WMT`, `DMT`, `BM_Ni`, `BM_Fe`, `BM_SiO2`, `BM_MgO`, `BM_SM`, `BM_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `TOS_SM`, `TOS_MC`, `Plan_Ni`, `Plan_Fe`, `Plan_SiO2`, `Plan_MgO`, `Plan_SM`, `Plan_MC`, `POS_ASSAY_STATUS_%`, `POS_Ni`, `POS_Fe`, `POS_SiO2`, `POS_MgO`, `POS_SM`, `POS_MC`, `YARD_ASSAY_STATUS_%`, `YARD_Ni`, `YARD_Fe`, `YARD_SiO2`, `YARD_MgO`, `YARD_SM`, `YARD_MC`, `Ni`, `Fe`, `SiO2`, `MgO`, `SM`, `MC`
- **`MINING_PLAN_3MRMP_DAILY`** (44 cols): `YEAR`, `QUARTER`, `MONTH`, `DATE`, `DEPOSIT`, `PIT`, `SUBPIT`, `IPPKH`, `BM_ESTIMATION`, `CONTRACTOR`, `MATERIAL`, `FSAP_RSAP`, `CATEGORY`, `CATEGORY_ROM`, `BLOCK_ID`, `BCM`, `WMT_INSITU`, `DMT`, `Ni`, `Fe`, `SM`, `SiO2`, `MgO`, `Co`, `Al2O3`, `Cr2O3`, `MnO`, `H2O`, `DRY_DENSITY`, `WET_DENSITY`, `MINE_RECOVERY_1`, `MINE_RECOVERY_2`, `BCM_ROM`, `WMT_ROM`, `DMT_ROM`, `Ni_DILUTION`, `Fe_DILUTION`, `MgO_DILUTION`, `H2O_DILUTION`, `Ni_ROM`, `Fe_ROM`, `MgO_ROM`, `H2O_ROM`, `REMARK`
- **`MINING_PLAN_WEEKLY_BLOCKS`** (6 cols): `YEAR`, `WEEK`, `PIT`, `CONTRACTOR`, `BLOCK_ID`, `WMT`
- **`MINING_PLAN_WEEKLY_BLOCKS_VS_ACT`** (8 cols): `P_YEAR`, `P_WEEK`, `PIT`, `CONTRACTOR`, `P_BLOCK_ID`, `ACT_BLOCK_ID`, `P_WMT`, `ACT_WMT`
- **`MINING_PLAN_WEEKLY_WITH_QUALITY`** (36 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `CONTRACTOR`, `PIT`, `SUBPIT`, `MATERIAL`, `FSAP_RSAP`, `CATEGORY`, `BLOCK_ID`, `BCM`, `WMT`, `DMT`, `Ni`, `Fe`, `SM`, `SiO2`, `MgO`, `H2O`, `MINE_RECOVERY`, `WMT_REC`, `BCM_ROM`, `WMT_ROM`, `DMT_ROM`, `Ni_DILUTION`, `Fe_DILUTION`, `MgO_DILUTION`, `H2O_DILUTION`, `Ni_ROM`, `Fe_ROM`, `MgO_ROM`, `H2O_ROM`, `Co_ROM`, `Cr2O3_ROM`, `ID`
- **`NEW_BLOCK_MAP_DIL_0`** (17 cols): `DEPOSIT`, `X`, `Y`, `Z`, `block_id`, `prop_lim`, `Ni_LIM`, `Fe_LIM`, `prop_sap`, `prop_fsap`, `prop_rsap`, `Ni_SAP`, `Fe_SAP`, `prop_wst`, `Ni_WST`, `Fe_WST`, `LEVEL`
- **`NEW_BLOCK_MAP_DIL_1`** (18 cols): `DEPOSIT`, `X`, `Y`, `Z`, `block_id`, `MP_LIM`, `Ni_LIM`, `Fe_LIM`, `MP_SAP`, `Ni_SAP`, `Fe_SAP`, `MP_WST`, `Ni_WST`, `Fe_WST`, `prop_sap`, `prop_lim`, `prop_wst`, `LEVEL`
- **`NEW_BLOCK_MAP_DIL_2`** (20 cols): `DEPOSIT`, `X`, `Y`, `Z`, `block_id`, `MP_LIM`, `Ni_LIM`, `Fe_LIM`, `MP_SAP`, `Ni_SAP`, `Fe_SAP`, `MP_WST`, `Ni_WST`, `Fe_WST`, `prop_sap`, `prop_lim`, `prop_wst`, `LEVEL`, `DOMINANT_PROP`, `SECOND_DOMINANT_PROP`
- **`NEW_BLOCK_MAP_DOM_PROP`** (21 cols): `X`, `Y`, `Z`, `DEPOSIT`, `block_id`, `MP_LIM`, `Ni_LIM`, `Fe_LIM`, `MP_SAP`, `Ni_SAP`, `Fe_SAP`, `MP_WST`, `Ni_WST`, `Fe_WST`, `PROP_SAP`, `PROP_LIM`, `PROP_BRK`, `LEVEL`, `DOMINANT_PROP`, `SECOND_DOMINANT_PROP`, `BLOCK_EST_CONFIDENCE`
- **`NEW_BLOCK_MAP_rev02`** (19 cols): `X`, `Y`, `Z`, `DEPOSIT`, `block_id`, `MP_LIM`, `Ni_LIM`, `Fe_LIM`, `MP_SAP`, `Ni_SAP`, `Fe_SAP`, `MP_WST`, `Ni_WST`, `Fe_WST`, `PROP_SAP`, `PROP_LIM`, `PROP_BRK`, `LEVEL`, `BLOCK_WELL_ESTIMATED`
- **`NEW_BM_OK`** (61 cols): `X`, `Y`, `Z`, `size (X)`, ` size(Y)`, ` size(Z)`, `Deposit`, `block_id`, `al2o3_brk`, `al2o3_fsap`, `al2o3_lim`, `al2o3_rsap`, `cao_brk`, `cao_fsap`, `cao_lim`, `cao_rsap`, `co_brk`, `co_fsap`, `co_lim`, `co_rsap`, `cr2o3_brk`, `cr2o3_fsap`, `cr2o3_lim`, `cr2o3_rsap`, `dd_brk_tc0`, `dd_fsap_tc0`, `dd_lim_tc0`, `dd_rsap_tc0`, `fe_brk_tc0`, `fe_fsap_tc0`, `fe_lim_tc0`, `fe_rsap_tc0`, `h2o_brk`, `h2o_fsap`, `h2o_lim`, `h2o_rsap`, `mgo_brk`, `mgo_fsap`, `mgo_lim`, `mgo_rsap`, `mno_fsap`, `mno_lim`, `mno_rsap`, `ni_brk_tc0`, `ni_fsap_tc0`, `ni_lim_tc0`, `ni_rsap_tc0`, `p2o5_brk`, `p2o5_fsap`, `p2o5_lim`, `p2o5_rsap`, `pp_brk_tc0`, `pp_fsap_tc0`, `pp_lim_tc0`, `pp_rsap_tc0`, `sio2_brk`, `sio2_fsap`, `sio2_lim`, `sio2_rsap`, `class_res`, `block_confidence_dh_close`
- **`NEW_MENG_RECONCIL6_FSAP_RSAP`** (64 cols): `YEAR`, `MONTH`, `WEEK`, `contractor`, `pit`, `block_ID`, `MATERIAL`, `WMT`, `DMT`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `MC`, `CF`, `MnO`, `Cr2O3`, `Al2O3`, `TYPE`, `cat`, `BCM`, `TOS_PILE`, `POS_DOME`, `YARD_ID`, `PROD_DATE`, `IN_DESIGN`, `DOME_STATUS`, `X`, `Y`, `Z`, `MP01_FULLBLOCK`, `MP02_FULLBLOCK`, `PILE_STATUS`, `block_strip`, `elev_base`, `subpit`, `block_new`, `block_SI`, `class_res`, `block_confidence_dh_close`, `MATERIAL_FACIES`, `geology_VOI`, `prop_lim`, `prop_sap`, `prop_brk`, `prop_fsap`, `prop_rsap`, `rit_prod`, `YEAR_HAULAGE_FROM_TOS`, `MONTH_HAULAGE_FROM_TOS`, `WEEK_HAULAGE_FROM_TOS`, `YEAR_HAULAGE_TO_YARD`, `MONTH_HAULAGE_TO_YARD`, `WEEK_HAULAGE_TO_YARD`, `YEAR_HAULAGE_REJECT`, `MONTH_HAULAGE_REJECT`, `WEEK_HAULAGE_REJECT`, `PLAN_Ni`, `PLAN_Fe`, `PLAN_SiO2`, `PLAN_MgO`, `PLAN_SM`, `PLAN_MC`
- **`NEW_MENG_RECONCIL6_FSAP_RSAP_REMIX`** (68 cols): `YEAR`, `MONTH`, `WEEK`, `contractor`, `pit`, `block_ID`, `MATERIAL`, `WMT`, `DMT`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `MC`, `CF`, `MnO`, `Cr2O3`, `Al2O3`, `TYPE`, `cat`, `BCM`, `TOS_PILE`, `POS_DOME`, `YARD_ID`, `PROD_DATE`, `IN_DESIGN`, `DOME_STATUS`, `X`, `Y`, `Z`, `MP01_FULLBLOCK`, `MP02_FULLBLOCK`, `PILE_STATUS`, `block_strip`, `elev_base`, `subpit`, `block_new`, `block_SI`, `class_res`, `block_confidence_dh_close`, `MATERIAL_FACIES`, `geology_VOI`, `prop_lim`, `prop_sap`, `prop_brk`, `prop_fsap`, `prop_rsap`, `rit_prod`, `YEAR_HAULAGE_FROM_TOS`, `MONTH_HAULAGE_FROM_TOS`, `WEEK_HAULAGE_FROM_TOS`, `YEAR_HAULAGE_TO_YARD`, `MONTH_HAULAGE_TO_YARD`, `WEEK_HAULAGE_TO_YARD`, `YEAR_HAULAGE_REJECT`, `MONTH_HAULAGE_REJECT`, `WEEK_HAULAGE_REJECT`, `PLAN_Ni`, `PLAN_Fe`, `PLAN_SiO2`, `PLAN_MgO`, `PLAN_SM`, `PLAN_MC`, `Wetdens_BM`, `Ni_RSAP_BM`, `GRIZZLY`, `Ni_FSAP_BM`
- **`NEW_MENG_RECONCIL6_GC_TC0_Alan_test`** (68 cols): `YEAR`, `MONTH`, `WEEK`, `contractor`, `pit`, `block_ID`, `MATERIAL`, `WMT`, `DMT`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `MC`, `CF`, `MnO`, `Cr2O3`, `Al2O3`, `TYPE`, `cat`, `BCM`, `TOS_PILE`, `POS_DOME`, `YARD_ID`, `PROD_DATE`, `IN_DESIGN`, `DOME_STATUS`, `X`, `Y`, `Z`, `MP01_FULLBLOCK`, `MP02_FULLBLOCK`, `PILE_STATUS`, `block_strip`, `elev_base`, `subpit`, `block_new`, `block_SI`, `class_res`, `block_confidence_dh_close`, `MATERIAL_FACIES`, `geology_VOI`, `prop_lim`, `prop_sap`, `prop_brk`, `prop_fsap`, `prop_rsap`, `rit_prod`, `YEAR_HAULAGE_FROM_TOS`, `MONTH_HAULAGE_FROM_TOS`, `WEEK_HAULAGE_FROM_TOS`, `YEAR_HAULAGE_TO_YARD`, `MONTH_HAULAGE_TO_YARD`, `WEEK_HAULAGE_TO_YARD`, `YEAR_HAULAGE_REJECT`, `MONTH_HAULAGE_REJECT`, `WEEK_HAULAGE_REJECT`, `PLAN_Ni`, `PLAN_Fe`, `PLAN_SiO2`, `PLAN_MgO`, `PLAN_SM`, `PLAN_MC`, `Wetdens_BM`, `Ni_RSAP_BM`, `GRIZZLY`, `Ni_FSAP_BM`
- **`NEW_MENG_RECONCIL6_GC_TC0_NEW_COG_202510_PRIORITY_SAP`** (68 cols): `YEAR`, `MONTH`, `WEEK`, `contractor`, `pit`, `block_ID`, `MATERIAL`, `WMT`, `DMT`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `MC`, `CF`, `MnO`, `Cr2O3`, `Al2O3`, `TYPE`, `cat`, `BCM`, `TOS_PILE`, `POS_DOME`, `YARD_ID`, `PROD_DATE`, `IN_DESIGN`, `DOME_STATUS`, `X`, `Y`, `Z`, `MP01_FULLBLOCK`, `MP02_FULLBLOCK`, `PILE_STATUS`, `block_strip`, `elev_base`, `subpit`, `block_new`, `block_SI`, `class_res`, `block_confidence_dh_close`, `MATERIAL_FACIES`, `geology_VOI`, `prop_lim`, `prop_sap`, `prop_brk`, `prop_fsap`, `prop_rsap`, `rit_prod`, `YEAR_HAULAGE_FROM_TOS`, `MONTH_HAULAGE_FROM_TOS`, `WEEK_HAULAGE_FROM_TOS`, `YEAR_HAULAGE_TO_YARD`, `MONTH_HAULAGE_TO_YARD`, `WEEK_HAULAGE_TO_YARD`, `YEAR_HAULAGE_REJECT`, `MONTH_HAULAGE_REJECT`, `WEEK_HAULAGE_REJECT`, `PLAN_Ni`, `PLAN_Fe`, `PLAN_SiO2`, `PLAN_MgO`, `PLAN_SM`, `PLAN_MC`, `Wetdens_BM`, `Ni_RSAP_BM`, `GRIZZLY`, `Ni_FSAP_BM`
- **`NEW_QC_RECONCIL_FOR_ARCGIS`** (60 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `CONTRACTOR`, `SHIFT`, `PIT`, `prod_ID`, `BLOCK_ID`, `block_ID_CORR`, `MATERIAL`, `RIT`, `TF_1`, `WMT`, `DMT`, `BCM`, `CF`, `destination`, `DESTINATION_AREA`, `TOS_PILE`, `WET_DENSITY`, `MC_for_DMT`, `BM_Ni`, `BM_Fe`, `BM_Co`, `BM_SiO2`, `BM_MgO`, `BM_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_Co`, `TOS_SiO2`, `TOS_MgO`, `TOS_MC`, `PROD_Block_Ni`, `PROD_Block_Fe`, `PROD_Block_Co`, `PROD_Block_SiO2`, `PROD_Block_MgO`, `PROD_Block_MC`, `DIL_Ni`, `DIL_Fe`, `DIL_Co`, `DIL_SiO2`, `DIL_MgO`, `DIL_MC`, `cat_BM`, `cat_PROD`, `X`, `Y`, `Z`, `IN_DESIGN`, `block_strip`, `block_num`, `strip_num`, `elev_base`, `subpit`, `block_new`, `block_SI`, `MATERIAL_FACIES`
- **`OEE MINING WITH DEMOB`** (28 cols): `prodDate`, `contractor`, `unitId_cleaned`, `timeGroup`, `WMT_TMM`, `RIT_SAP`, `WMT_SAP`, `RIT_RSAP`, `WMT_RSAP`, `RIT_LIM`, `WMT_LIM`, `RIT_WST`, `WMT_WST`, `RIT_TS`, `WMT_TS`, `SCH_DT`, `UNSCH_DT`, `STBY`, `PROD_per_ HOUR`, `EQ_CLASS`, `YEAR`, `MONTH`, `WEEK`, `DIVISION GROUP`, `DIVISION`, `activity`, `pit`, `subpit`
- **`OEEDB_AUDB`** (23 cols): `recId`, `prodDate`, `contractor`, `shiftCode`, `timeGroup`, `startHour`, `endHour`, `pit`, `location`, `activity`, `unitId`, `schDowntime`, `schCode`, `uschDowntime`, `uschCode`, `standby`, `standbyCode`, `workHours`, `operatingHours`, `comment`, `unitIdLetters`, `unitIdNumbers`, `unitId_cleaned`
- **`OEEDB_PDB`** (22 cols): `recId`, `prodDate`, `contractor`, `shiftCode`, `timeGroup`, `startHour`, `endHour`, `pit`, `subPit`, `blockId`, `prodId`, `activityType`, `dtId`, `basicTf`, `excId`, `material`, `rit`, `dumpLocation`, `pileId`, `comment`, `dtId_cleaned`, `excId_cleaned`
- **`OEE_HAULAGE_WMT_KM`** (20 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `ORIGIN_PIT`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `WB_ID`, `WORKING_HOURS`, `STBY_HOURS`, `BD_HOURS`, `OPERATING_HOURS`, `RIT`, `KM`, `WMT`, `RIT_PER_DT`, `NB_DT`
- **`OEE_MINING_FULL`** (27 cols): `CONTRACTOR`, `YEAR`, `MONTH`, `WEEK`, `DATE`, `SHIFT`, `UNIT_TYPE`, `TARGET_TRIP_HOUR`, `UNIT_ID`, `UNIT_ID_FULL`, `CAPACITY`, `UNIT_TYPE2`, `ACTIVITY`, `PIT`, `DISTANCE`, `RIT`, `RIT_SAP`, `RIT_LIM`, `RIT_WST`, `TMM`, `WMT_SAP`, `WMT_LIM`, `WMT_WST`, `WORKING_HOURS`, `STBY_HOURS`, `BD_HOURS`, `OPERATING_HOURS`
- **`OEE_MINING_NEW`** (27 cols): `CONTRACTOR`, `ID_EQ`, `TYPE`, `CAPACITY`, `PROD_per_ HOUR`, `EQ_CLASS`, `DIVISION`, `DIVISION GROUP`, `SCH`, `UNSCH_DT`, `STBY`, `WORKING HOURS`, `prodDate`, `SHIFT`, `timeGroup`, `activity`, `PIT`, `subpit`, `RIT`, `RIT_SAP`, `RIT_RSAP`, `RIT_LIM`, `RIT_WST`, `RIT_TS`, `YEAR`, `MONTH`, `WEEK`
- **`OMR_PILE_STATUS_ALL`** (6 cols): `ACTIVITY`, `DATE`, `SHIFT`, `PILE_ID`, `TOS_AREA`, `STATUS`
- **`OMR_PILE_STATUS_ALL_GROUP`** (7 cols): `STOCK_TYPE`, `STOCK_AREA`, `STOCK_ID`, `DATE_OPEN`, `DATE_COMPLETE`, `DATE_TRANSFER`, `DATE_FINISH`
- **`OMR_PILE_STATUS_ALL_GROUP2`** (9 cols): `STOCK_TYPE`, `STOCK_AREA`, `STOCK_ID`, `DATE_OPEN`, `DATE_COMPLETE`, `DATE_TRANSFER`, `DATE_FINISH`, `MIN_DATE`, `MAX_DATE`
- **`OMR_TOS`** (9 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `TOS_PILE`, `RIT`, `TF`, `WMT`
- **`OMR_TOS_CONTINUE`** (16 cols): `DATE`, `SHIFT`, `DATETIME`, `STOCK_TYPE`, `STOCK_AREA`, `STOCK_ID`, `STATUS`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `RIT`, `TF`, `WMT`, `SURVEY_WMT`, `SURVEY_SEGMENT_DATE_START`, `SURVEY_SEGMENT_DATE_END`
- **`PILES_SHARED_FENI_TREATED`** (6 cols): `DATE_SHARE`, `PILE_ID`, `TOS_LOCATION`, `CLASS`, `CATEGORY`, `WMT`
- **`PLAN_DAY_WORKS_CLEAN`** (18 cols): `DATE`, `ACTIVITY`, `STATUS`, `AREA`, `SECTION_ROAD`, `ORIGINAL_LOCATION_JOB`, `SECTION_COUNT`, `HOURS`, `LOCATION_JOB`, `ROAD`, `KILOMETER`, `KM_START`, `KM_END`, `EQUIPMENT_TYPE`, `UNIT_ID`, `MAIN_ISSUE`, `ACTION`, `REMARKS`
- **`POS FOLLOW UP TREATED`** (8 cols): `DATE`, `AREA`, `POS`, `PADS`, `NUMBER`, `AVG`, `EDD`, `PRECISION`
- **`PP_MINED_CLEAN`** (10 cols): `YEAR`, `MONTH`, `WEEK`, `DEPOSIT`, `X`, `Y`, `Z`, `classification_no`, `BLOCK_ID`, `pp_mined_progress`
- **`PP_MINED_NEW_RECONCIL_MENG_CONVERT_NEW_BM`** (11 cols): `YEAR`, `MONTH`, `WEEK`, `PIT`, `X`, `Y`, `Z`, `classification_no`, `block_id`, `block_id_old`, `pp_mined_progress`
- **`PRODUCTION_EQUIPMENT_RUNNING`** (6 cols): `SOURCE_TABLE`, `EQUIPMENT_ID_CLEAN`, `DATE`, `CONTRACTOR`, `ACTIVITY`, `AREA`
- **`PRODUCTION_MINING_PIT`** (11 cols): `DATE`, `CONTRACTOR`, `SHIFT`, `ORIGIN_AREA`, `MATERIAL`, `MATERIAL_CLASS`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `RIT`, `WMT`
- **`PRODUCTION_PIT`** (24 cols): `ID`, `CONTRACTOR`, `DATE`, `SHIFT`, `ACTIVITY`, `PIT`, `SUBPIT`, `BLOCK_TYPE`, `BLOCK_STATUS`, `BLOCK_ID`, `PROD_ID`, `MATERIAL`, `MATERIAL_CLASS`, `RIT`, `TF`, `WMT`, `BCM`, `DESTINATION`, `TOS_PILE`, `BLAST_STATUS`, `BLAST_ID`, `UPDATE_DATE`, `UPDATE_BY`, `REMARK`
- **`PRODUCTION_PIT_BY_EQ_HOUR`** (14 cols): `contractor`, `prodDate`, `SHIFT`, `timeGroup`, `activity`, `PIT`, `subpit`, `RIT`, `RIT_SAP`, `RIT_RSAP`, `RIT_LIM`, `RIT_WST`, `RIT_TS`, `UNIT_ID`
- **`PRODUCTION_PIT_COEF`** (6 cols): `YEAR`, `MONTH`, `contractor`, `deposit_code`, `material`, `CF`
- **`PRODUCTION_PIT_COORDINATES_B_S`** (22 cols): `ID`, `CONTRACTOR`, `DATE`, `SHIFT`, `ACTIVITY`, `PIT`, `SUBPIT`, `BLOCK_TYPE`, `BLOCK_STATUS`, `BLOCK_ID`, `Z`, `B`, `S`, `PROD_ID`, `MATERIAL`, `RIT`, `TF`, `WMT`, `DESTINATION`, `TOS_PILE`, `BLAST_STATUS`, `BLAST_ID`
- **`PRODUCTION_PIT_COORDINATES_X_Y`** (24 cols): `ID`, `CONTRACTOR`, `DATE`, `SHIFT`, `ACTIVITY`, `PIT`, `SUBPIT`, `BLOCK_TYPE`, `BLOCK_STATUS`, `BLOCK_ID`, `Z`, `B`, `S`, `X`, `Y`, `PROD_ID`, `MATERIAL`, `RIT`, `TF`, `WMT`, `DESTINATION`, `TOS_PILE`, `BLAST_STATUS`, `BLAST_ID`
- **`PRODUCTION_PIT_COORDINATES_X_Y_CONVERT_NEW_BM`** (27 cols): `CONTRACTOR`, `DATE`, `SHIFT`, `ACTIVITY`, `PIT`, `SUBPIT`, `BLOCK_TYPE`, `BLOCK_STATUS`, `BLOCK_ID`, `NEW_BLOCK_ID1`, `NEW_BLOCK_ID2`, `NEW_BLOCK_ID3`, `NEW_BLOCK_ID4`, `Z`, `B`, `S`, `X`, `Y`, `PROD_ID`, `MATERIAL`, `RIT`, `TF`, `WMT`, `DESTINATION`, `TOS_PILE`, `BLAST_STATUS`, `BLAST_ID`
- **`PRODUCTION_PIT_DAILY_PLAN`** (10 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `CONTRACTOR`, `PIT`, `TMM`, `PLAN_SAP`, `PLAN_LIM`, `PLAN_WST`
- **`PRODUCTION_PIT_DISTANCE_CALC`** (28 cols): `CONTRACTOR`, `DATE`, `SHIFT`, `ACTIVITY`, `PIT`, `SUBPIT`, `BLOCK_TYPE`, `BLOCK_STATUS`, `BLOCK_ID`, `Z`, `B`, `S`, `X`, `Y`, `PROD_ID`, `MATERIAL`, `RIT`, `TF`, `WMT`, `DESTINATION`, `TOS_TYPE`, `TOS_NUMBER`, `TOS_X`, `TOS_Y`, `DISTANCE`, `TOS_PILE`, `BLAST_STATUS`, `BLAST_ID`
- **`PRODUCTION_PIT_HOURLY`** (20 cols): `ID`, `CONTRACTOR`, `DATE`, `SHIFT`, `TIME_GROUP`, `START_HOUR`, `END_HOUR`, `ACTIVITY_TYPE`, `MATERIAL`, `PIT`, `SUB_PIT`, `BLOCK_ID`, `PROD_ID`, `DESTINATION_AREA`, `PILE_ID`, `DISTANCE`, `TRUCK_ID`, `EXCAVATOR_ID`, `RIT`, `COMMENT`
- **`PRODUCTION_PIT_HOURLY_FULL`** (20 cols): `CONTRACTOR`, `DATE`, `SHIFT`, `TIME_GROUP`, `START_HOUR`, `END_HOUR`, `ACTIVITY_TYPE`, `MATERIAL`, `PIT`, `SUB_PIT`, `BLOCK_ID`, `PROD_ID`, `DESTINATION_AREA`, `PILE_ID`, `DISTANCE`, `UNIT_TYPE`, `UNIT_ID`, `RIT`, `TF`, `COMMENT`
- **`PRODUCTION_PIT_HOURLY_TF`** (20 cols): `CONTRACTOR`, `DATE`, `SHIFT`, `TIME_GROUP`, `START_HOUR`, `END_HOUR`, `ACTIVITY_TYPE`, `MATERIAL`, `PIT`, `SUB_PIT`, `BLOCK_ID`, `PROD_ID`, `DESTINATION_AREA`, `PILE_ID`, `DISTANCE`, `TRUCK_ID`, `EXCAVATOR_ID`, `RIT`, `TF`, `COMMENT`
- **`PRODUCTION_PIT_RECONCIL_PP`** (11 cols): `TABLE`, `YEAR`, `MONTH`, `WEEK`, `DEPOSIT`, `CONTRACTOR`, `BLOCK_ID`, `Z`, `B`, `S`, `PP`
- **`PRODUCTION_PIT_TOS_CLEAN`** (6 cols): `DESTINATION_RAW`, `TOS_TYPE`, `CONTRACTOR`, `TOS_PIT`, `TOS_CONTRACTOR`, `TOS_NUMBER`
- **`PRODUCTION_PIT_VS_OMR`** (8 cols): `CONTRACTOR`, `DATE`, `MATERIAL`, `TOS_PILE`, `BLOCK_ID`, `RIT_PRODUCTION_PIT`, `RIT_QC PIT-TOS OMR`, `IS_GOOD`
- **`PRODUCTION_PIT_WRONG_ELEVATION`** (22 cols): `ID`, `CONTRACTOR`, `DATE`, `SHIFT`, `ACTIVITY`, `PIT`, `SUBPIT`, `BLOCK_TYPE`, `BLOCK_STATUS`, `BLOCK_ID`, `MODULO_Z`, `B`, `S`, `PROD_ID`, `MATERIAL`, `RIT`, `TF`, `WMT`, `DESTINATION`, `TOS_PILE`, `BLAST_STATUS`, `BLAST_ID`
- **`PROD_ASSAYS`** (31 cols): `ID`, `Date`, `contractor`, `deposit_code`, `pit`, `subpit`, `prod_ID`, `block_ID`, `block_ID_2`, `CLASS_BM`, `material`, `RIT`, `TF_1`, `WMT`, `destination`, `TOS_pile`, `status_blast`, `TYPE_PROD`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `SM`, `Cr2O3`, `Al2O3`, `MnO`, `CaO`, `P2O5`, `Fe2O3`, `MC`
- **`PROD_CALENDAR_ASSAYS`** (37 cols): `exercice`, `YEAR`, `MONTH`, `WEEK`, `Date`, `contractor`, `deposit_code`, `pit`, `subpit`, `prod_ID`, `block_ID`, `block_ID_2`, `CLASS_BM`, `material`, `RIT`, `TF_1`, `WMT`, `destination`, `TOS_pile`, `status_blast`, `TYPE_PROD`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `SM`, `MC`, `DMT`, `NBDAYS`, `ID`, `Cr2O3`, `Al2O3`, `MnO`, `CaO`, `P2O5`, `Fe2O3`
- **`PROD_CORR_AND_PLAN`** (34 cols): `ID`, `EXERCICE`, `YEAR`, `MONTH`, `WEEK`, `DATE`, `contractor`, `deposit_code`, `pit`, `subpit`, `prod_ID`, `block_ID`, `block_ID_2`, `CLASS_BM`, `material`, `RIT`, `TF_1`, `WMT`, `destination`, `TOS_pile`, `status_blast`, `TYPE_PROD`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `SM`, `MC`, `CF`, `SAP_COG`, `LIM_COG`, `CAT`, `WMT_ROM`
- **`PROD_CORR_ASSAYS`** (39 cols): `exercice`, `YEAR`, `MONTH`, `WEEK`, `Date`, `contractor`, `deposit_code`, `pit`, `subpit`, `prod_ID`, `block_ID`, `block_ID_2`, `CLASS_BM`, `material`, `RIT`, `TF_1`, `WMT`, `destination`, `TOS_pile`, `status_blast`, `TYPE_PROD`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `SM`, `DMT`, `MC`, `CF`, `NBDAYS`, `ID`, `Cr2O3`, `Al2O3`, `MnO`, `material 2`, `CaO`, `P2O5`, `Fe2O3`
- **`PROD_CORR_ASSAYS_COG`** (39 cols): `ID`, `EXERCICE`, `YEAR`, `MONTH`, `WEEK`, `Date`, `contractor`, `deposit_code`, `pit`, `subpit`, `prod_ID`, `block_ID`, `block_ID_2`, `CLASS_BM`, `material`, `RIT`, `TF_1`, `WMT`, `destination`, `TOS_pile`, `status_blast`, `TYPE_PROD`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `Al2O3`, `Cr2O3`, `MnO`, `CaO`, `Fe2O3`, `P2O5`, `DMT`, `SM`, `CF`, `MC`, `SAP_COG`, `LIM_COG`
- **`PROD_CORR_ASSAYS_COG_2`** (48 cols): `ID`, `EXERCICE`, `YEAR`, `MONTH`, `WEEK`, `DATE`, `contractor`, `deposit_code`, `pit`, `subpit`, `prod_ID`, `block_ID`, `block_ID_2`, `CLASS_BM`, `material`, `RIT`, `TF_1`, `WMT`, `destination`, `TOS_pile`, `status_blast`, `TYPE_PROD`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `SM`, `MC`, `MnO`, `Cr2O3`, `Al2O3`, `CF`, `SAP_COG`, `LIM_COG`, `CLASS_MATERIAL`, `FINAL_RECLASSIFICATION`, `DMT`, `Ni*DMT`, `Fe*DMT`, `Co*DMT`, `MgO*DMT`, `SiO2*DMT`, `MnO*DMT`, `Al2O3*DMT`, `Cr2O3*DMT`, `NBDAYS`, `DENSITY_SURVEY`
- **`PROD_CORR_ASSAYS_COG_3`** (45 cols): `WMT_ROM`, `EXERCICE`, `YEAR`, `MONTH`, `WEEK`, `DATE`, `contractor`, `deposit_code`, `pit`, `subpit`, `prod_ID`, `block_ID`, `block_ID_2`, `CLASS_BM`, `material`, `RIT`, `TF_1`, `WMT`, `destination`, `TOS_pile`, `status_blast`, `TYPE_PROD`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `SM`, `MC`, `CF`, `SAP_COG`, `LIM_COG`, `CLASS_MATERIAL`, `FINAL_RECLASSIFICATION`, `DMT`, `Ni*DMT`, `Fe*DMT`, `Co*DMT`, `MgO*DMT`, `SiO2*DMT`, `NBDAYS`, `MnO`, `Cr2O3`, `Al2O3`, `DENSITY_SURVEY`
- **`PROD_CORR_ASSAYS_COG_4`** (33 cols): `ID`, `EXERCICE`, `YEAR`, `MONTH`, `WEEK`, `DATE`, `contractor`, `deposit_code`, `pit`, `subpit`, `prod_ID`, `block_ID`, `block_ID_2`, `CLASS_BM`, `material`, `RIT`, `TF_1`, `WMT`, `destination`, `TOS_pile`, `status_blast`, `TYPE_PROD`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `SM`, `MC`, `CF`, `SAP_COG`, `LIM_COG`, `CAT`
- **`PROD_VIA_BM`** (38 cols): `EXERCICE`, `YEAR`, `MONTH`, `WEEK`, `DATE`, `contractor`, `deposit_code`, `pit`, `subpit`, `block_ID`, `block_ID_2`, `material`, `prod_ID`, `RIT`, `TF_1`, `destination`, `status_blast`, `TYPE_PROD`, `SAP_COG`, `LIM_COG`, `WMT`, `DMT`, `al2o3`, `cao`, `co`, `cr2o3`, `fe`, `h2o`, `mgo`, `mno`, `Ni`, `p2o5`, `prop`, `sio2`, `MC`, `CLASS_TOS`, `CLASS_BM`, `CF`
- **`PROD_VVST_REPORT_2`** (32 cols): `YEAR`, `MONTH`, `DATE`, `CONTRACTOR`, `DEPARTMEN`, `DEPOSIT`, `SHIFT`, `SAP_ROM_PLAN`, `SAP_PLAN`, `LIM_ROM_PLAN`, `LIM_PLAN`, `WST_ROM_PLAN`, `WST_PLAN`, `DEPOSIT_PRELIM`, `DOZER`, `EXCA`, `ADT`, `TF_vvst`, `SAP_vvst`, `RSAP_vvst`, `LIM_vvst`, `WST_vvst`, `BMS_vvst`, `TS_vvst`, `SpORE_vvst`, `SpWST_vvst`, `QUARRY_vvst`, `TMM_vvst`, `HGS%`, `WCO%`, `SAP_CF`, `LIM_CF`
- **`PROD_VVST_TREATED`** (23 cols): `YEAR`, `MONTH`, `WEEK`, `exercice`, `DATE`, `CONTRACTOR`, `DEPARTMEN`, `SHIFT`, `LOCATION`, `TF_vvst`, `DOZER`, `EXCA`, `ADT`, `BMS_vvst`, `SAP_vvst`, `RSAP_vvst`, `LIM_vvst`, `WST_vvst`, `TS_vvst`, `SpORE_vvst`, `SpWST_vvst`, `QUARRY_vvst`, `TMM_vvst`
- **`PileTonnage`** (10 cols): `PILE_ID`, `PIT`, `WMT`, `Ni`, `MgO`, `Fe`, `SiO2`, `MC`, `Activity`, `DMT`
- **`Prod and Calender`** (26 cols): `MONTH`, `WEEK`, `ID`, `contractor`, `Date`, `shift`, `deposit_code`, `pit`, `subpit`, `prod_ID`, `block_id`, `block_ID_2`, `CLASS_BM`, `material`, `RIT`, `TF_1`, `TF_2`, `WMT`, `WMT2`, `destination`, `TOS_PILE`, `status`, `status_blast`, `TYPE_PROD`, `BLAST_ID`, `YEAR`
- **`QC ALL DATA 2`** (73 cols): `TYPE_DATA`, `TYPE`, `TOS LOCATION`, `LOCATION`, `CONTRACTOR`, `MATERIAL`, `PILE ID`, `Al2O3`, `CaO`, `Co`, `Cr2O3`, `Fe`, `MC`, `Mgo`, `Mno`, `Ni`, `P2O5`, `Sio2`, `SiO2/MgO`, `Plan_SM`, `CF_PLAN_Ni`, `DIL_BM_Ni`, `DIL_TOS_Ni`, `DIL_BM_Fe`, `DIL_TOS_Fe`, `DATE END SAMPLING`, `DATE RECEIVED`, `NTN_MC`, `NTN_Ni`, `NTN_Fe`, `TOS_al2o3`, `TOS_cao`, `TOS_co`, `TOS_cr2o3`, `TOS_fe`, `TOS_MC`, `TOS_mgo`, `TOS_mno`, `TOS_Ni`, `TOS_Ni_ACT`, `TOS_p2o5`, `TOS_sio2`, `BM_WMT`, `BM_al2o3`, `BM_cao`, `BM_co`, `BM_cr2o3`, `BM_fe`, `BM_MC`, `BM_mgo`, `BM_mno`, `BM_Ni`, `BM_Ni_ACT`, `BM_p2o5`, `BM_sio2`, `BM_MC_ORI`, `BM_Ni_ORI`, `BM_Fe_ORI`, `BM_SiO2_ORI`, `BM_MgO_ORI`, `RATIO_WMT_TOS/BM`, `BM_PROP`, `CHECK ASSAYS`, `TYPE SAMPLE`, `WMT`, `PIT`, `COMPLETED STATUS`, `COMP OR NOT`, `CATEGORY 2`, `CATEGORY`, `HAUL_CONFIDENCE`, `SALES_CONFIDENCE`, `MATERIAL_CONFIDENCE`
- **`QC CHECK PIT VS SAMP LD`** (9 cols): `BLOCK ID`, `RIT`, `SAMPLE BLOCK ID`, `SAMPLE RIT`, `DATE PIT`, `DATE SAMPLE`, `CHECK PILE ID`, `CHECK RIT`, `PIT`
- **`QC CHECK PIT VS SAMP TOS`** (9 cols): `PILE ID`, `RIT`, `SAMPLE PILE ID`, `SAMPLE RIT`, `CHECK PILE ID`, `CHECK RIT`, `DATE PIT`, `DATE SAMPLE`, `PIT`
- **`QC PIT-TOS & SAMPLE DATA`** (15 cols): `TYPE`, `TOS LOCATION`, `CONTRACTOR`, `RIT`, `STATUS`, `PILE ID`, `JOB-QC`, `SAMPLE CODE`, `TYPE SAMPLE`, `TYPE DATA`, `RIT SAMPLE`, `PILE ID SAMPLE`, `CHECK RIT`, `CHECK PIT-TOS VS SAMPLE`, `DATE SAMPLE`
- **`QC PIT-TOS OMR SUMMARY`** (23 cols): `TYPE`, `TOS LOCATION`, `CONTRACTOR`, `RIT`, `WMT`, `STATUS`, `PILE_ID`, `MATERIAL`, `DIL_BM_MC`, `DIL_BM_Ni`, `DIL_BM_Fe`, `DIL_BM_SiO2`, `DIL_BM_MgO`, `DIL_BM_Co`, `DIL_BM_Cr2O3`, `DIL_TOS_MC`, `DIL_TOS_Ni`, `DIL_TOS_Fe`, `DIL_TOS_SiO2`, `DIL_TOS_MgO`, `DIL_TOS_Co`, `DIL_TOS_Cr2O3`, `PIT`
- **`QC PIT-TOS OMR SUMMARY 2`** (7 cols): `PROD_DATE`, `CONTRACTOR`, `ASSAYS_ID`, `TOS LOCATION`, `MATERIAL`, `PIT`, `PROD_RIT`
- **`QC PIT-TOS SUM FOR CHECK FOR LD`** (4 cols): `BLOCK ID`, `RIT`, `DATE PIT`, `PIT`
- **`QC PIT-TOS SUM FOR CHECK FOR TOS`** (4 cols): `PILE ID`, `RIT`, `DATE PIT`, `PIT`
- **`QC SAMPLE & ASSAYS`** (24 cols): `PILE ID`, `JOB-QC`, `SAMPLE CODE`, `RIT`, `Ni`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `Fe2O3`, `Fe`, `MgO`, `MnO`, `P2O5`, `SiO2`, `SiO2/MgO`, `MC`, `C`, `DATE`, `DATE_RECEIVED`, `TYPE SAMPLE`, `COMPOSITE`, `RECEIVED ASSAY`, `PIT`
- **`QC SAMPLE & ASSAYS COMPOSITES`** (21 cols): `PILE ID`, `RIT`, `Ni`, `Fe`, `Co`, `MgO`, `SiO2`, `MnO`, `CaO`, `Cr2O3`, `P2O5`, `Al2O3`, `Fe2O3`, `SiO2/MgO`, `MC`, `C`, `DATE END SAMPLING`, `DATE RECEIVED`, `TYPE SAMPLE`, `COMPLETED STATUS`, `COMP OR NOT`
- **`QC SAMPLE SUM FOR CHECK`** (4 cols): `PILE ID`, `RIT`, `TYPE SAMPLE`, `DATE SAMPLE`
- **`QC TOS BALANCE`** (64 cols): `TYPE_DATA`, `PILE ID`, `TOS LOCATION`, `STOCK_AREA`, `CONTRACTOR`, `TYPE`, `CF_PLAN_Ni`, `CF_BM_Ni`, `CF_TOS_Ni`, `CF_BM_Fe`, `CF_TOS_Fe`, `TOS_Ni`, `TOS_fe`, `TOS_Ni_ACT`, `BM_Ni`, `BM_fe`, `BM_Ni_ACT`, `BM_MC_ORI`, `BM_Ni_ORI`, `BM_Fe_ORI`, `BM_SiO2_ORI`, `BM_MgO_ORI`, `Al2O3`, `CaO`, `Co`, `Cr2O3`, `Fe`, `MC`, `Mgo`, `Mno`, `Ni`, `P2O5`, `Sio2`, `SiO2/MgO`, `DATE END SAMPLING`, `DATE_ASSAY`, `NTN_MC`, `NTN_Ni`, `NTN_Fe`, `DATE STOCK`, `STATUS`, `WMT`, `MAX_PLAN_HAULAGE_DATE`, `MATERIAL_CONFIDENCE`, `CATEGORY_QC`, `CATEGORY`, `CATEGORY 2`, `STATUS HAULAGE`, `START HAULAGE`, `LAST HAULAGE`, `DMT`, `RATIO_WMT_TOS/BM`, `BM_PROP`, `SALES_CONFIDENCE`, `HAUL_CONFIDENCE`, `FIRST_DATE_SHARE`, `LATEST_DATE_SHARE`, `DATE_COMPLETE`, `MAX_DATE_REQUEST`, `MIN_DATE_REQUEST`, `MAX_WMT_SHARED`, `MIN_WMT_SHARED`, `LATEST_DESTINATION_ID_REQUESTED`, `LATEST_DESTINATION_AREA_REQUESTED`
- **`QC TOS_PILE STATUS HAULAGE`** (4 cols): `TOS_PILE`, `STATUS HAULAGE`, `LAST HAULAGE`, `START HAULAGE`
- **`QC TOS_VS_POS`** (41 cols): `YEAR`, `MONTH`, `WEEK`, `DOME`, `DOME 2`, `DOME_SIMPLIFIED`, `ASSAYS_ID`, `CONTRACTOR_HAULAGE`, `FIRST_PROD`, `LAST_PROD`, `CONTRACTOR_PROD`, `TOS_LOCATION`, `WMT_PROD`, `WMT`, `Ni`, `Co`, `Fe`, `MgO`, `SiO2`, `Al2O3`, `Cr2O3`, `MnO`, `CaO`, `P2O5`, `C`, `MC`, `SAMPLE_E_WEIGHT`, `SAMPLE_R_WEIGHT`, `SAMPLE_TOT_WEIGHT`, `DATE_ASSAYS`, `TYPE_DATA`, `LOCATION`, `STATUS_HAULAGE`, `STATUS_RECLAIMING`, `FIRST_HAULAGE`, `LAST_HAULAGE`, `DOME_ASSAYS_STATUS`, `CERTIFICATION_DATE`, `CERTIFIED`, `CAT`, `DOME_TYPE`
- **`QC_CF_BM_PROP`** (16 cols): `ORIGIN_PIT`, `MATERIAL`, `BM_MC_PROP`, `BMC_MC_PROP`, `BM_Ni_PROP`, `BMC_Ni_PROP`, `BM_Fe_PROP`, `BMC_Fe_PROP`, `BM_SiO2_PROP`, `BMC_SiO2_PROP`, `BM_MgO_PROP`, `BMC_MgO_PROP`, `BM_Co_PROP`, `BMC_Co_PROP`, `BM_Cr2O3_PROP`, `BMC_Cr2O3_PROP`
- **`QC_CF_BM_TOS`** (18 cols): `MAX_DATE`, `ORIGIN_PIT`, `CONTRACTOR_PILE`, `MATERIAL`, `DIL_BM_MC`, `DIL_BM_Ni`, `DIL_BM_Fe`, `DIL_BM_SiO2`, `DIL_BM_MgO`, `DIL_BM_Cr2O3`, `DIL_BM_Co`, `DIL_TOS_MC`, `DIL_TOS_Ni`, `DIL_TOS_Fe`, `DIL_TOS_SiO2`, `DIL_TOS_MgO`, `DIL_TOS_Cr2O3`, `DIL_TOS_Co`
- **`QC_CF_BM_TOS_OLD`** (24 cols): `YEAR`, `MONTH`, `ORIGIN_PIT`, `CONTRACTOR_PILE`, `MATERIAL`, `DIL_BM_MC`, `DIL_BM_Ni`, `DIL_BM_Fe`, `DIL_BM_SiO2`, `DIL_BM_MgO`, `DIL_BM_Cr2O3`, `DIL_BM_Co`, `DIL_TOS_MC`, `DIL_TOS_Ni`, `DIL_TOS_Fe`, `DIL_TOS_SiO2`, `DIL_TOS_MgO`, `DIL_TOS_Cr2O3`, `DIL_TOS_Co`, `CF_Ni`, `CF_Fe`, `CF_SiO2`, `CF_MgO`, `DIL_PROP_BM_Ni`
- **`QC_COMPOSITE_ALL_STOCK`** (26 cols): `OBJECT_NAME`, `ASSAY_DATA`, `ASSAY_TYPE`, `ASSAY_STATUS`, `ASSAY_STATUS_%`, `CONTRACTOR`, `STOCK_TYPE`, `DATE`, `STOCK_ID`, `COMPO_STOCK_NAMES`, `WMT`, `DMT`, `BM_WMT`, `BM_PROP`, `Al2O3`, `CaO`, `Co`, `Cr2O3`, `Fe`, `Fe2O3`, `MC`, `MgO`, `MnO`, `Ni`, `P2O5`, `SiO2`
- **`QC_COMPOSITE_ASSAY`** (22 cols): `DATE`, `STOCK_ID`, `STOCK_TYPE`, `STOCK_SUBLOT`, `ASSAY_TYPE`, `ASSAY_STATUS`, `CONTRACTOR`, `RIT`, `WMT`, `DMT`, `al2o3`, `cao`, `co`, `cr2o3`, `fe`, `fe2o3`, `MC`, `mgo`, `mno`, `Ni`, `p2o5`, `sio2`
- **`QC_COMPOSITE_BLOCK`** (25 cols): `DATE`, `CONTRACTOR`, `WMT`, `DMT`, `BLOCK_NAME`, `DEPOSIT`, `BLOCK_ID`, `MATERIAL`, `al2o3`, `cao`, `co`, `cr2o3`, `h2O`, `mno`, `Ni`, `Fe`, `SiO2`, `MgO`, `prop`, `p2o5`, `HGS_WMT`, `TOS_TOTAL_SAP`, `NEW_MATERIAL`, `MATERIAL_BM`, `MATERIAL_CLASS_BM`
- **`QC_COMPOSITE_BLOCK_SELECT`** (22 cols): `DATE`, `CONTRACTOR`, `WMT`, `DMT`, `BLOCK_NAME`, `DEPOSIT`, `BLOCK_ID`, `MATERIAL`, `al2o3`, `cao`, `co`, `cr2o3`, `h2O`, `mno`, `Ni`, `Fe`, `SiO2`, `MgO`, `prop`, `p2o5`, `HGS_WMT`, `TOTAL_SAP_TOS_RATIO_HGS`
- **`QC_COMPOSITE_BLOCK_VIA_PIT`** (18 cols): `DEPOSIT`, `BLOCK_ID`, `ASSAY_TYPE`, `DATE`, `MATERIAL`, `WMT`, `DMT`, `Al2O3`, `CaO`, `Co`, `Cr2O3`, `Fe`, `MC`, `MgO`, `MnO`, `Ni`, `P2O5`, `SiO2`
- **`QC_COMPOSITE_DUMP`** (20 cols): `DATE`, `STOCK_TYPE`, `STOCK_ID`, `ASSAY_TYPE`, `ASSAY_STATUS`, `CONTRACTOR`, `WMT`, `DMT`, `al2o3`, `cao`, `co`, `cr2o3`, `fe`, `fe2o3`, `MC`, `mgo`, `mno`, `Ni`, `p2o5`, `sio2`
- **`QC_COMPOSITE_DUMP_VIA_PIT`** (18 cols): `STOCK_ID`, `STOCK_TYPE`, `ASSAY_TYPE`, `DATE`, `WMT`, `DMT`, `Al2O3`, `CaO`, `CO`, `Cr2O3`, `Fe`, `Fe2O3`, `MC`, `MgO`, `MnO`, `Ni`, `P2O5`, `SiO2`
- **`QC_COMPOSITE_HAULAGE`** (20 cols): `DATE`, `STOCK_TYPE`, `STOCK_ID`, `ASSAY_TYPE`, `ASSAY_STATUS`, `CONTRACTOR`, `WMT`, `DMT`, `al2o3`, `cao`, `co`, `cr2o3`, `fe`, `fe2o3`, `MC`, `mgo`, `mno`, `Ni`, `p2o5`, `sio2`
- **`QC_COMPOSITE_POS`** (20 cols): `DATE`, `STOCK_ID`, `ASSAY_TYPE`, `ASSAY_STATUS`, `ASSAY_STATUS_%`, `CONTRACTOR`, `WMT`, `DMT`, `al2o3`, `cao`, `co`, `cr2o3`, `fe`, `fe2o3`, `MC`, `mgo`, `mno`, `Ni`, `p2o5`, `sio2`
- **`QC_COMPOSITE_POS_VIA_BM`** (17 cols): `STOCK_ID`, `ASSAY_TYPE`, `DATE`, `WMT`, `DMT`, `al2o3`, `cao`, `co`, `cr2o3`, `fe`, `fe2o3`, `MC`, `mgo`, `mno`, `Ni`, `p2o5`, `sio2`
- **`QC_COMPOSITE_POS_VIA_ML`** (4 cols): `STOCK_ID`, `WMT`, `DMT`, `Ni`
- **`QC_COMPOSITE_POS_VIA_TOS`** (18 cols): `STOCK_ID`, `STOCK_TYPE`, `ASSAY_TYPE`, `DATE`, `WMT`, `DMT`, `al2o3`, `cao`, `co`, `cr2o3`, `fe`, `fe2o3`, `MC`, `mgo`, `mno`, `Ni`, `p2o5`, `sio2`
- **`QC_COMPOSITE_POS_VIA_YARD`** (19 cols): `STOCK_ID`, `ASSAY_TYPE`, `ASSAY_STATUS`, `ASSAY_CONTRACTOR`, `DATE`, `WMT`, `DMT`, `al2o3`, `cao`, `co`, `cr2o3`, `fe`, `fe2o3`, `MC`, `mgo`, `mno`, `Ni`, `p2o5`, `sio2`
- **`QC_COMPOSITE_TOS`** (20 cols): `Date`, `DATE_ANALYSIS`, `ASSAY_TYPE`, `STOCK_ID`, `WMT`, `DMT`, `Al2O3`, `CaO`, `Co`, `Cr2O3`, `Fe`, `Fe2O3`, `MC`, `MgO`, `MnO`, `Ni`, `P2O5`, `SiO2`, `MATERIAL_TOS`, `MATERIAL_CLASS_TOS`
- **`QC_COMPOSITE_TOS_CERT`** (16 cols): `Date`, `ASSAY_TYPE`, `STOCK_ID`, `WMT`, `DMT`, `Al2O3`, `CaO`, `Co`, `Cr2O3`, `Fe`, `MC`, `MgO`, `MnO`, `Ni`, `P2O5`, `SiO2`
- **`QC_COMPOSITE_TOS_IndividualBlock`** (22 cols): `DATE_RECEIVED_LATEST`, `DATE_ANALYSIS_LATEST`, `DATE_SAMPLING_LATEST`, `PIT`, `PROD_ID`, `MATERIAL_PROD`, `MATERIAL_ASSAYED`, `CAT_ASSAYED`, `WMT`, `DMT`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `MC`, `Fe2O3`, `Al2O3`, `CaO`, `Cr2O3`, `MnO`, `P2O5`
- **`QC_COMPOSITE_TOS_VIA_BM`** (32 cols): `STOCK_ID`, `ASSAY_TYPE`, `DATE`, `WMT`, `DMT`, `Al2O3`, `CaO`, `CO`, `Cr2O3`, `Fe`, `Fe2O3`, `MC`, `MgO`, `MnO`, `Ni`, `P2O5`, `SiO2`, `MC_ORI`, `Ni_ORI`, `Fe_ORI`, `SiO2_ORI`, `MgO_ORI`, `CARROT_MC`, `CARROT_Ni`, `CARROT_Fe`, `CARROT_SiO2`, `CARROT_MgO`, `CLASS_TOS`, `BM_WMT`, `BM_PROP`, `BLOCK_NAMES`, `CLASS_BM`
- **`QC_COMPOSITE_TOS_VIA_BM_ORI`** (29 cols): `STOCK_ID`, `ASSAY_TYPE`, `DATE`, `WMT`, `DMT`, `Al2O3`, `CaO`, `CO`, `Cr2O3`, `Fe`, `Fe2O3`, `MC`, `MgO`, `MnO`, `Ni`, `P2O5`, `SiO2`, `CARROT_MC`, `CARROT_Ni`, `CARROT_Fe`, `CARROT_SiO2`, `CARROT_MgO`, `CARROT_Co`, `CARROT_Cr2O3`, `CLASS_TOS`, `BM_WMT`, `BM_PROP`, `BLOCK_NAMES`, `CLASS_BM`
- **`QC_COMPOSITE_TOS_VIA_HAULAGE`** (15 cols): `TOS_PILE`, `DATE`, `WMT`, `DMT`, `al2o3`, `cao`, `co`, `cr2o3`, `fe`, `MC`, `mgo`, `mno`, `Ni`, `p2o5`, `sio2`
- **`QC_COMPOSITE_TOS_VIA_PIT`** (17 cols): `STOCK_ID`, `ASSAY_TYPE`, `DATE`, `WMT`, `DMT`, `Al2O3`, `CaO`, `CO`, `Cr2O3`, `Fe`, `Fe2O3`, `MC`, `MgO`, `MnO`, `Ni`, `P2O5`, `SiO2`
- **`QC_COMPOSITE_TOS_VIA_POS`** (18 cols): `STOCK_ID`, `STOCK_TYPE`, `ASSAY_TYPE`, `DATE`, `WMT`, `DMT`, `al2o3`, `cao`, `co`, `cr2o3`, `fe`, `fe2o3`, `MC`, `mgo`, `mno`, `Ni`, `p2o5`, `sio2`
- **`QC_COMPOSITE_TOS_VIA_YARD`** (17 cols): `STOCK_ID`, `ASSAY_TYPE`, `DATE`, `WMT`, `DMT`, `Al2O3`, `CaO`, `Co`, `Cr2O3`, `Fe`, `Fe2O3`, `MC`, `MgO`, `MnO`, `Ni`, `P2O5`, `SiO2`
- **`QC_COMPOSITE_WCO`** (22 cols): `DATE`, `TYPE OF SURVEY`, `SURVEY WEEK`, `DOME`, `DOME ID`, `SURVEY METHOD`, `PIT DETAILS`, `PIT`, `WMT`, `ASSAY_TYPE`, `Ni`, `Fe`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `Fe2O3`, `MnO`, `P2O5`, `SiO2`, `MgO`, `MC`
- **`QC_COMPOSITE_YARD`** (21 cols): `DATE`, `STOCK_ID`, `ASSAY_TYPE`, `ASSAY_STATUS`, `ASSAY_STATUS_%`, `CONTRACTOR`, `RIT`, `WMT`, `DMT`, `al2o3`, `cao`, `co`, `cr2o3`, `fe`, `fe2o3`, `MC`, `mgo`, `mno`, `Ni`, `p2o5`, `sio2`
- **`QC_COMPOSITE_YARD_DIRECT`** (20 cols): `DATE`, `STOCK_ID`, `ASSAY_TYPE`, `ASSAY_STATUS`, `ASSAY_STATUS_%`, `CONTRACTOR`, `WMT`, `DMT`, `al2o3`, `cao`, `co`, `cr2o3`, `fe`, `fe2o3`, `MC`, `mgo`, `mno`, `Ni`, `p2o5`, `sio2`
- **`QC_COMPOSITE_YARD_STOCK_ORIGINAL`** (20 cols): `DATE`, `STOCK_ID`, `ASSAY_TYPE`, `ASSAY_STATUS`, `CONTRACTOR`, `RIT`, `WMT`, `DMT`, `al2o3`, `cao`, `co`, `cr2o3`, `fe`, `fe2o3`, `MC`, `mgo`, `mno`, `Ni`, `p2o5`, `sio2`
- **`QC_COMPOSITE_YARD_VIA_BM`** (17 cols): `STOCK_ID`, `ASSAY_TYPE`, `DATE`, `WMT`, `DMT`, `Al2O3`, `CaO`, `CO`, `Cr2O3`, `Fe`, `Fe2O3`, `MC`, `MgO`, `MnO`, `Ni`, `P2O5`, `SiO2`
- **`QC_COMPOSITE_YARD_VIA_POS`** (18 cols): `STOCK_ID`, `ASSAY_TYPE`, `ASSAY_STATUS`, `DATE`, `WMT`, `DMT`, `al2o3`, `cao`, `co`, `cr2o3`, `fe`, `fe2o3`, `MC`, `mgo`, `mno`, `Ni`, `p2o5`, `sio2`
- **`QC_COMPOSITE_YARD_VIA_TOS`** (17 cols): `STOCK_ID`, `ASSAY_TYPE`, `DATE`, `WMT`, `DMT`, `Al2O3`, `CaO`, `CO`, `Cr2O3`, `Fe`, `Fe2O3`, `MC`, `MgO`, `MnO`, `Ni`, `P2O5`, `SiO2`
- **`QC_PLAN_Ni_CF_ALL`** (15 cols): `STOCK_ID`, `DIL_TOS_MC`, `DIL_BM_MC`, `DIL_TOS_Ni`, `DIL_BM_Ni`, `DIL_TOS_Fe`, `DIL_BM_Fe`, `DIL_TOS_SiO2`, `DIL_BM_SiO2`, `DIL_TOS_MgO`, `DIL_BM_MgO`, `DIL_TOS_Co`, `DIL_BM_Co`, `DIL_TOS_Cr2O3`, `DIL_BM_Cr2O3`
- **`QC_POS_DETAILS`** (17 cols): `STOCK_ID`, `POS_BM_Ni`, `POS_TOS_Ni`, `POS_WMT_CERT`, `POS_Ni`, `YARD_WMT_CERT`, `YARD_Ni`, `LOCATION`, `ORIGIN`, `SMU`, `HAUL_WMT`, `TOS_PLAN_Ni`, `TOS_TOS_Ni`, `TOS_BM_Ni`, `BLOCK_ID`, `PROD_WMT`, `PROD_BM_Ni`
- **`QC_STOCK_ALL`** (28 cols): `OBJECT_NAME`, `STOCK_ID`, `STOCK_TYPE`, `ASSAY_DATA`, `ASSAY_DATE`, `ASSAY_TYPE`, `ASSAY_STATUS`, `ASSAY_STATUS_%`, `ASSAY_CONTRACTOR`, `WMT_CERT`, `PROP_WMT`, `PROP_DMT`, `Al2O3`, `CaO`, `Co`, `Cr2O3`, `Fe_ORI`, `Fe`, `Fe2O3`, `MC`, `MgO_ORI`, `MgO`, `MnO`, `Ni_ORI`, `Ni`, `P2O5`, `SiO2_ORI`, `SiO2`
- **`QC_STOCK_ALL_VIA_ALL`** (92 cols): `STOCK_TYPE`, `STOCK_ID`, `Ni_`, `PLAN_MC`, `PLAN_Ni`, `PLAN_Fe`, `PLAN_SiO2`, `PLAN_MgO`, `PLAN_Co`, `PLAN_Cr2O3`, `CF_PLAN_Ni`, `DEF_ASSAY_TYPE`, `DEF_MC`, `DEF_Ni`, `DEF_Fe`, `DEF_SiO2`, `DEF_MgO`, `DEF_Co`, `DEF_Cr2O3`, `DEF_Al2O3`, `DEF_MnO`, `DEF_P2O5`, `BM_ASSAY_TYPE`, `BM_MC`, `BM_Ni`, `BM_Fe`, `BM_SiO2`, `BM_MgO`, `BM_Al2O3`, `BM_Co`, `BM_Cr2O3`, `BM_MnO`, `BM_P2O5`, `BM_Ni_CORR`, `BM_Fe_CORR`, `BM_SiO2_CORR`, `BM_MgO_CORR`, `TOS_ASSAY_TYPE`, `TOS_ASSAY_DATE`, `TOS_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `TOS_Al2O3`, `TOS_Co`, `TOS_Cr2O3`, `TOS_MnO`, `TOS_P2O5`, `POS_ASSAY_TYPE`, `POS_ASSAY_STATUS`, `POS_ASSAY_STATUS_%`, `POS_ASSAY_CONTRACTOR`, `POS_ASSAY_DATE`, `POS_WMT_CERT`, `POS_MC`, `POS_Ni`, `POS_Fe`, `POS_SiO2`, `POS_MgO`, `POS_Al2O3`, `POS_Co`, `POS_Cr2O3`, `POS_MnO`, `POS_P2O5`, `YARD_ASSAY_TYPE`, `YARD_ASSAY_STATUS`, `YARD_ASSAY_STATUS_%`, `YARD_ASSAY_CONTRACTOR`, `YARD_ASSAY_DATE`, `YARD_WMT_CERT`, `YARD_MC`, `YARD_Ni`, `YARD_Fe`, `YARD_SiO2`, `YARD_MgO`, `YARD_Al2O3`, `YARD_Co`, `YARD_Cr2O3`, `YARD_MnO`, `YARD_P2O5`, `ML_Ni`, `DIL_BM_MC`, `DIL_BM_Ni`, `DIL_BM_Fe`, `DIL_BM_SiO2`, `DIL_BM_MgO`, `DIL_TOS_MC`, `DIL_TOS_Ni`, `DIL_TOS_Fe`, `DIL_TOS_SiO2`, `DIL_TOS_MgO`
- **`QC_STOCK_ALL_VIA_ALL_OLD`** (54 cols): `STOCK_TYPE`, `STOCK_ID`, `Ni_`, `PLAN_Ni`, `CF_PLAN_Ni`, `DEF_ASSAY_TYPE`, `DEF_MC`, `DEF_Ni`, `DEF_Fe`, `DEF_SiO2`, `DEF_MgO`, `DEF_Co`, `DEF_P2O5`, `BM_ASSAY_TYPE`, `BM_MC`, `BM_Ni`, `BM_Fe`, `BM_SiO2`, `BM_MgO`, `BM_Co`, `BM_P2O5`, `TOS_ASSAY_TYPE`, `TOS_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `TOS_Co`, `TOS_P2O5`, `POS_ASSAY_TYPE`, `POS_ASSAY_STATUS`, `POS_ASSAY_STATUS_%`, `POS_ASSAY_CONTRACTOR`, `POS_WMT_CERT`, `POS_MC`, `POS_Ni`, `POS_Fe`, `POS_SiO2`, `POS_MgO`, `POS_Co`, `POS_P2O5`, `YARD_ASSAY_TYPE`, `YARD_ASSAY_STATUS`, `YARD_ASSAY_STATUS_%`, `YARD_ASSAY_CONTRACTOR`, `YARD_WMT_CERT`, `YARD_MC`, `YARD_Ni`, `YARD_Fe`, `YARD_SiO2`, `YARD_MgO`, `YARD_Co`, `YARD_P2O5`, `ML_Ni`
- **`QC_STOCK_POS_VIA_ALL`** (41 cols): `STOCK_ID`, `Ni_`, `AVG_Ni`, `BM_ASSAY_TYPE`, `BM_MC`, `BM_Ni`, `BM_Fe`, `BM_SiO2`, `BM_MgO`, `BM_Co`, `BM_P2O5`, `TOS_ASSAY_TYPE`, `TOS_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `TOS_Co`, `TOS_P2O5`, `POS_ASSAY_TYPE`, `POS_ASSAY_STATUS`, `POS_ASSAY_CONTRACTOR`, `POS_WMT_CERT`, `POS_MC`, `POS_Ni`, `POS_Fe`, `POS_SiO2`, `POS_MgO`, `POS_Co`, `POS_P2O5`, `YARD_ASSAY_TYPE`, `YARD_ASSAY_STATUS`, `YARD_ASSAY_CONTRACTOR`, `YARD_WMT_CERT`, `YARD_MC`, `YARD_Ni`, `YARD_Fe`, `YARD_SiO2`, `YARD_MgO`, `YARD_Co`, `YARD_P2O5`
- **`QC_STOCK_TOS_FOR_ANALYZE`** (39 cols): `STOCK_ID`, `MATERIAL`, `PLAN_Ni`, `RATIO_WMT`, `BM_ASSAY_TYPE`, `BM_WMT`, `BM_PROP`, `BM_MC`, `BM_Ni`, `BM_Fe`, `BM_SiO2`, `BM_MgO`, `BM_Co`, `BM_P2O5`, `BM_Cr2O3`, `BM_Al2O3`, `TOS_ASSAY_TYPE`, `TOS_WMT`, `TOS_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `TOS_Co`, `TOS_P2O5`, `TOS_Cr2O3`, `TOS_Al2O3`, `TOS_CERT_ASSAY_TYPE`, `TOS_CERT_MC`, `TOS_CERT_Ni`, `TOS_CERT_Fe`, `TOS_CERT_SiO2`, `TOS_CERT_MgO`, `TOS_CERT_Co`, `TOS_CERT_P2O5`, `TOS_CERT_Cr2O3`, `TOS_CERT_Al2O3`, `BM_PROP_LIM`, `CONTRACTOR`
- **`QC_STOCK_TOS_VIA_ALL`** (36 cols): `STOCK_ID`, `Ni_vieux_Julien`, `Ni_`, `BM_WMT`, `BM_PROP`, `BM_ASSAY_TYPE`, `BM_MC`, `BM_Ni`, `BM_Fe`, `BM_SiO2`, `BM_MgO`, `BM_Co`, `BM_P2O5`, `BM_Cr2O3`, `BM_Al2O3`, `TOS_ASSAY_TYPE`, `TOS_WMT`, `TOS_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `TOS_Co`, `TOS_P2O5`, `TOS_Cr2O3`, `TOS_Al2O3`, `TOS_CERT_ASSAY_TYPE`, `TOS_CERT_MC`, `TOS_CERT_Ni`, `TOS_CERT_Fe`, `TOS_CERT_SiO2`, `TOS_CERT_MgO`, `TOS_CERT_Co`, `TOS_CERT_P2O5`, `TOS_CERT_Cr2O3`, `TOS_CERT_Al2O3`
- **`QUARRY PRODUCTION treated`** (17 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `SHIFT`, `CONTRACTOR`, `SUBQUARRY`, `AREA_ID`, `MATERIAL`, `RIT`, `TF (BCM)`, `DESTINATION`, `DESTINATION 2`, `PILE ID`, `TYPE_TRANSPORT`, `BCM`, `QUARRY`
- **`QUARRY_DAILY_EXTRACTION`** (9 cols): `CONTRACTOR`, `DATE`, `SHIFT`, `QUARRY`, `MATERIAL`, `RIT`, `BCM`, `DESTINATION`, `PILE ID`
- **`QUARRY_STOCK_BLEND_MANAGEMENT`** (13 cols): `YEAR`, `MONTH`, `WEEK`, `DATE_SURVEY`, `DATE`, `SHIFT`, `SURVEY_WEEK`, `TYPE_OF_SURVEY`, `STOCK_ID`, `LOCATION`, `BCM`, `STOCK_PRODUCT`, `DATA_TYPE`
- **`QUARRY_STOCK_BLEND_MANAGEMENT_TREATED`** (16 cols): `DATE_SURVEY`, `DATE`, `YEAR`, `MONTH`, `WEEK`, `SHIFT`, `SURVEY_WEEK`, `TYPE_OF_SURVEY`, `STOCK_ID`, `GRANULO`, `LINE`, `LOCATION`, `BCM`, `BCM_ok`, `STOCK_PRODUCT`, `DATA_TYPE`
- **`QUARRY_STOCK_CRUSHED_MANAGEMENT`** (14 cols): `YEAR`, `MONTH`, `WEEK`, `DATE_SURVEY`, `DATE`, `SHIFT`, `SURVEY_WEEK`, `CRUSHER`, `TYPE_OF_SURVEY`, `LINE`, `PILE_ID`, `LOCATION`, `BCM`, `DATA_TYPE`
- **`QUARRY_STOCK_CRUSHED_MANAGEMENT_TREATED`** (16 cols): `YEAR`, `MONTH`, `WEEK`, `DATE_SURVEY`, `DATE`, `SHIFT`, `SURVEY_WEEK`, `CRUSHER`, `TYPE_OF_SURVEY`, `PILE_ID`, `GRANULO`, `LINE`, `LOCATION`, `BCM`, `BCM_ok`, `DATA_TYPE`
- **`QUARRY_STOCK_TOS_MANAGEMENT`** (15 cols): `YEAR`, `MONTH`, `WEEK`, `TYPE_OF_SURVEY`, `SURVEY_WEEK`, `CONTRACTOR`, `DATE`, `DATE_SURVEY`, `SHIFT`, `STOCK_AREA`, `STOCK_ID`, `MATERIAL`, `VOLUME`, `STOCK_TYPE`, `DATA_TYPE`
- **`QUARRY_STOCK_TOS_MANAGEMENT_TREATED`** (16 cols): `YEAR`, `MONTH`, `WEEK`, `TYPE_OF_SURVEY`, `SURVEY_WEEK`, `CONTRACTOR`, `DATE`, `DATE_SURVEY`, `SHIFT`, `STOCK_AREA`, `STOCK_ID`, `MATERIAL`, `VOLUME`, `VOLUME_ok`, `STOCK_TYPE`, `DATA_TYPE`
- **`RAINFALL_AREA_COORDINATES`** (3 cols): `AREA`, `X_RF`, `Y_RF`
- **`RAINFALL_CONSOLIDATED`** (3 cols): `DATE`, `LOCATION`, `mmH20`
- **`RAINFALL_PREP`** (13 cols): `YEAR`, `MONTH`, `WEEK`, `CONTRACTOR`, `DATE`, `AREA`, `STATION`, `H2O_mm`, `X`, `Y`, `DURASI`, `X_RF`, `Y_RF`
- **`RECLAIMING`** (12 cols): `TYPE`, `DATE`, `WEIGHBRIDGE WMT`, `DOME`, `DESTINATION`, `DESTINATION_ID`, `SELLER`, `BUYER`, `CONTRACTOR`, `DUMPING POINT`, `RIT`, `TF`
- **`RECLAIMING DETAIL`** (19 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `TRUCK_ID`, `RIT`, `ORIGIN`, `ORIGIN_ID`, `DESTINATION`, `WMT`, `DMT`, `Ni`, `Fe`, `SiO2`, `MgO`, `SM`, `Co`, `MC`
- **`RECLAIMING DETAIL 2`** (18 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `NB_DT`, `RIT`, `ORIGIN`, `DESTINATION`, `WMT`, `DMT`, `Ni`, `Fe`, `SM`, `SiO2`, `MgO`, `Co`, `MC`
- **`RECLAIMING DETAIL 3`** (19 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `NB_DT`, `RIT`, `TRIP`, `ORIGIN`, `DESTINATION`, `WMT`, `DMT`, `Ni`, `Fe`, `SM`, `SiO2`, `MgO`, `Co`, `MC`
- **`RECLAIMING DETAIL 4`** (18 cols): `DATE`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `NB_DT`, `RIT`, `TRIP`, `ORIGIN`, `DESTINATION`, `WMT`, `DMT`, `Ni`, `Fe`, `SiO2`, `SM`, `MgO`, `Co`, `MC`
- **`RECLAIMING_MATCH_ASSAY_STOCK_ID2`** (12 cols): `DESTINATION_ID_NEW`, `DATE`, `DOME`, `MMYY`, `MM+1YY`, `MM-1YY`, `DESTINATION`, `DESTINATION_ID`, `STOCK_ID`, `STOCK_ID_MMYY`, `STOCK_ID_LEFT`, `STOCK_ID_RIGHT`
- **`RECLAIMING_ORIGIN_DESTINATION`** (10 cols): `DATE`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `RIT`, `WMT`
- **`RECLAIMING_REJECT_POURCENTAGE`** (5 cols): `YEAR`, `MONTH`, `REJECT_WMT`, `RECLAIMING_WMT`, `%_REJECT_RECLAIMING`
- **`RECLAIMING_REJECT_POURCENTAGE_DATE`** (8 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `ORIGIN_PIT`, `REJECT_WMT`, `RECLAIMING_WMT`, `%_REJECT_RECLAIMING`
- **`RECLAIMING_WB_TREATED_3_JOIN`** (10 cols): `DATE`, `ID_DT`, `DOME_FINAL`, `ORIGIN_DOME`, `COMPANY_DEST`, `NEW_CONTRACTOR`, `DESTINATION`, `WMT`, `SHIFT`, `DT_COMPANY`
- **`RECLAIMNG WB TREATED GROUPED`** (10 cols): `DATE`, `TYPE`, `ID_DT`, `TRIPS`, `NEW_CONTRACTOR`, `ORIGIN`, `DESTINATION`, `WMT`, `SHIFT`, `DT_COMPANY`
- **`RECLASSIFICATION_MISSING`** (14 cols): `CONTRACTOR`, `ORIGIN_PIT`, `STOCK_TYPE`, `SURVEY_CLASS`, `STOCK_AREA`, `STOCK_ID`, `Ni`, `MATERIAL`, `DATE_OPEN`, `DATE_COMPLETE`, `DATE_TRANSFER`, `DATE_FINISH`, `REMARK`, `PAD_ID`
- **`RECLASSIFICATION_TOS_MISSING`** (8 cols): `MATERIAL`, `STOCK_TYPE`, `Ni`, `PLAN_Ni`, `TOS_Ni`, `BM_Ni`, `PLAN_Fe`, `STOCK_ID`
- **`RECONCIL_OK`** (22 cols): `YEAR`, `MONTH`, `WEEK`, `contractor`, `pit`, `block_ID`, `MATERIAL`, `WMT`, `DMT`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `MC`, `CF`, `MnO`, `Cr2O3`, `Al2O3`, `TYPE`, `cat`, `BCM`
- **`RECONCIL_ST_LT`** (43 cols): `YEAR`, `MONTH`, `WEEK`, `contractor`, `pit`, `block_ID`, `MATERIAL`, `WMT`, `DMT`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `MC`, `CF`, `MnO`, `Cr2O3`, `Al2O3`, `TYPE`, `cat`, `BCM`, `TOS_PILE`, `POS_DOME`, `YARD_ID`, `PROD_DATE`, `IN_DESIGN`, `DOME_STATUS`, `X`, `Y`, `Z`, `MP01_FULLBLOCK`, `MP02_FULLBLOCK`, `PILE_STATUS`, `block_strip`, `elev_base`, `subpit`, `block_new`, `block_SI`, `class_res`, `block_confidence_dh_close`, `MATERIAL_FACIES`, `geology_VOI`
- **`RECONCIL_TC0`** (22 cols): `YEAR`, `MONTH`, `WEEK`, `contractor`, `pit`, `block_ID`, `MATERIAL`, `WMT`, `DMT`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `MC`, `CF`, `MnO`, `Cr2O3`, `Al2O3`, `TYPE`, `cat`, `BCM`
- **`REMAINING_RESERVES_BM_OK`** (23 cols): `X`, `Y`, `Z`, `block_id`, `DEPOSIT`, `MATERIAL`, `MP`, `BCM`, `WMT`, `DMT`, `Fe`, `MC`, `Ni`, `PROP`, `WD`, `MgO`, `SiO2`, `Co`, `Al2O3`, `CaO`, `Cr2O3`, `MnO`, `P2O5`
- **`REQUEST_FENI_PLAN`** (3 cols): `DOME`, `DATE`, `REQUEST`
- **`REQUEST_FULL`** (4 cols): `DOME`, `DATE`, `REQUEST`, `COMPANY`
- **`REQUEST_LAST`** (4 cols): `DATE`, `DOME`, `PLANT`, `REQUEST`
- **`REQUEST_VS_HAULAGE`** (9 cols): `STOCK_ID`, `ORIGIN_AREA`, `DESTINATION_ID`, `DESTINATION_AREA`, `FIRST_REQUEST_SHIFT`, `FIRST_REQUEST_DATE`, `WMT_REQUEST`, `DATE_HAULAGE`, `WMT_HAULAGE`
- **`ROLLING_MINE_PLAN_TREATED`** (11 cols): `YEAR`, `MONTH`, `CONTRACTOR`, `DEPOSIT`, `PIT`, `PIT_ID`, `WMT_ROM`, `MATERIAL`, `UPDATE`, `NB_DAYS`, `DAILY_AVERAGE_WMT`
- **`ROLLING_MINE_PLAN_TREATED_2`** (11 cols): `YEAR`, `MONTH`, `CONTRACTOR`, `DEPOSIT`, `LIM_ROM_PLAN`, `SAP_ROM_PLAN`, `WST_ROM_PLAN`, `LIM_PLAN`, `SAP_PLAN`, `WST_PLAN`, `SHIFT`
- **`RSF RSF_REPORT`** (19 cols): `YEAR`, `MONTH`, `WEEK`, `EXERCICE`, `LAST_SURVEY`, `DATE`, `SHIFT`, `LAYER`, `ELEVATION`, `LOCATION`, `ITEM`, `MATERIAL_TYPE`, `RIT`, `OFFICER`, `LAYER_SURVEY`, `LOCATION_SURVEY`, `ITEM_SURVEY`, `MATERIAL_SURVEY`, `VOLUME_SURVEY`
- **`RSF RSF_SURVEY_TREATED`** (6 cols): `LAST_SURVEY`, `LAYER`, `NAME`, `ITEM`, `MATERIAL_TYPE`, `PROGRESS_VOLUME`
- **`RSF_HAULING_DATA_DAILY`** (11 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `UNIT_TYPE`, `ORIGIN`, `DESTINATION`, `RIT`, `YEAR`, `MONTH`, `WEEK`, `TF`
- **`RSF_HAULING_TO_TRAFIC_MGMT`** (12 cols): `DATE`, `SHIFT`, `COMPANY`, `DEPARTEMENT`, `UNIT_TYPE`, `NB_UNIT`, `TRIP_PER_UNIT`, `START_TIME`, `ORIGIN_KM`, `ORIGIN`, `DESTINATION_KM`, `DESTINATION`
- **`RSF_HAULING_TO_TRAFIC_MGMT_CALENDAR`** (16 cols): `DATE`, `SHIFT`, `COMPANY`, `DEPARTEMENT`, `UNIT_TYPE`, `NB_UNIT`, `TRIP_PER_UNIT`, `START_TIME`, `ORIGIN_KM`, `ORIGIN`, `DESTINATION_KM`, `DESTINATION`, `YEAR`, `MONTH`, `WEEK`, `EXERCICE`
- **`RSF_REPORT`** (22 cols): `DATE`, `YEAR`, `MONTH`, `WEEK`, `LAST_DATE`, `LAYER`, `ELEVATION`, `NAME`, `ITEM`, `MATERIAL_TYPE`, `RL_ELEVATION`, `PROGRESS_VOLUME`, `CUMMULATIVE`, `X`, `Y`, `Z`, `STATUS`, `HAULING_DATE`, `SHIFT`, `RIT`, `OFFICER`, `REMARK`
- **`S123_STOCK_SHAPE_QGIS_TEST`** (9 cols): `UPDATE_DATE`, `OBJECTID`, `name`, `CreationDa`, `Creator`, `EditDate`, `new_dome_i`, `GEOM`, `menggantik`
- **`S123_TOS_STATUS_CLEAN`** (9 cols): `UPDATE_DATE`, `GLOBALID`, `EDIT_DATE`, `PILE_ID`, `TOS_AREA`, `OLD_PILE`, `DATE`, `STATUS`, `GEOM`
- **`SAF_OVERSPEED`** (19 cols): `ID`, `SAFETY_COMPANY`, `SAFETY_AGENT`, `DATE`, `SHIFT`, `TIME`, `ROAD`, `KILOMETER`, `ROAD_LANE`, `CONTRACTOR`, `UNIT_TYPE`, `UNIT_ID`, `SPEED`, `SPEED_LIMIT`, `SPEED_LIMIT_CAT`, `OVERSPEED`, `SANCTION`, `REMARK`, `DATETIME_RECEIVED`
- **`SAF_OVERSPEED_LIMIT`** (18 cols): `SAFETY_COMPANY`, `SAFETY_AGENT`, `DATE`, `SHIFT`, `TIME`, `ROAD`, `KILOMETER`, `ROAD_LANE`, `CONTRACTOR`, `UNIT_TYPE`, `UNIT_ID`, `SPEED`, `SPEED_LIMIT`, `SPEED_LIMIT_CAT`, `OVERSPEED`, `SANCTION`, `REMARK`, `DATETIME_RECEIVED`
- **`SAMPLING BRIDGE CERTIFICATE`** (25 cols): `DATE`, `JOB NO`, `DOME`, `Total`, `MC`, `DMT`, `Ni`, `Co`, `MgO`, `CaO`, `Fe`, `P`, `S`, `SiO2`, `Al2O3`, `Cr2O3`, `Fe2O3`, `K2O`, `MnO`, `Na2O`, `P2O5`, `TiO2`, `LOi`, `CONTRACTOR`, `REMARK`
- **`SAMPLING_CONTRACTOR_PREP`** (16 cols): `CONTRACTOR`, `DATE`, `SHIFT`, `ACTIVITY`, `ORIGIN_TYPE`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_TYPE`, `DESTINATION_AREA`, `MATERIAL`, `DESTINATION_ID`, `CONTRACTOR_HAULING`, `RIT`, `SPV_CONTRACTOR`, `SPV_WBN`, `SAMPLING_POINT`
- **`SHORT_TERM_RECONCIL`** (25 cols): `YEAR`, `MONTH`, `WEEK`, `date`, `contractor`, `DEPOSIT`, `SUBPIT`, `block_id`, `DOMINANT_PROP`, `SECOND_DOMINANT_PROP`, `Ni_BM_LIM`, `Ni_BM_SAP`, `PROP_HGS`, `PROP_WCO`, `PROP_WST_SAP`, `PROP_LIM_ORE`, `PROP_WST_LIM`, `PROP_BRK`, `RIT_LIM`, `RIT_SAP`, `RIT_WST`, `RIT_WST_SAP`, `RIT_WST_LIM`, `RIT_WST_BRK`, `TOS_PILE`
- **`STOCK_CERTIFICATE_NEWS`** (15 cols): `STOCK_TYPE`, `STOCK_AREA`, `STOCK_ID`, `STATUS`, `MATERIAL`, `DATE_CERT`, `DATE_OPEN`, `DATE_CLOSE`, `CERT_CONTRACTOR`, `WMT_CARRIED`, `WMT_SURVEY`, `WMT_SENT`, `WMT_CERT`, `ASSAY_TYPE`, `ASSAY_STATUS`
- **`STOCK_INFOS`** (28 cols): `DOME`, `LOCATION`, `STOCK_STATUS`, `STATUS_HAULAGE`, `STATUS_RECLAIMING`, `HIGH_TURN`, `PRIORITY_RECLAIM`, `CLOSE_HAULING`, `CLOSE_RECLAIMING`, `MATERIAL`, `DATE_SIGNED`, `PLANT_SIGNED`, `DATE_SOLD`, `STOCK_TYPE`, `STOCK_SPLIT`, `RECLAIMING_PLANT`, `DATE_HAULAGE_START`, `DATE_HAULAGE_END`, `DATE_RECLAIMING_START`, `DATE_RECLAIMING_END`, `DATE_REJECT_START`, `DATE_REJECT_END`, `ORIGIN_PIT`, `WMT_HAUL`, `WMT_RECLAIM`, `WMT_POS_SENT`, `WMT_YARD_SENT`, `FINISH`
- **`STOCK_INFO_FULL`** (23 cols): `STOCK_TYPE`, `STOCK_ID`, `STOCK_AREA`, `STOCK_STATUS`, `HIGH_TURN`, `PRIORITY_RECLAIM`, `MATERIAL`, `RECL`, `STOCK_LOGISTIC`, `REQUEST_PLANT`, `REQUEST_DATE`, `REQUEST`, `STOCK_PROD_DATE`, `STOCK_SPLIT`, `STOCK_OPEN_DATE`, `STOCK_COMPLETE_DATE`, `STOCK_TRANSFER_DATE`, `STOCK_FINISH_DATE`, `STOCK_LAST_DATE`, `ORIGIN_PIT`, `WMT_HAUL`, `WMT_RECLAIM`, `FINISH`
- **`STOCK_MANAGEMENT`** (109 cols): `YEAR`, `MONTH`, `MONTH_SALES`, `WEEK`, `DATE`, `SURVEY_WEEK`, `SURVEY_TYPE`, `SURVEY_CLASS`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `ORIGIN_PIT`, `ORIGIN_TYPE`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_TYPE`, `DESTINATION_AREA`, `DESTINATION_ID`, `PLANT`, `DOME`, `RIT`, `WMT_METHOD`, `WMT`, `DATE_SIGNED`, `LOCATION`, `DATE_SOLD`, `STOCK_STATUS`, `HIGH_TURN`, `PRIORITY_RECLAIM`, `CLOSE_HAULING`, `CLOSE_RECLAIMING`, `DATE_HAULAGE_START`, `DATE_HAULAGE_END`, `STOCK_TYPE`, `STOCK_SPLIT`, `WMT_POS_SENT`, `WMT_YARD_SENT`, `DATE_RECLAIMING_START`, `DATE_RECLAIMING_END`, `WMT_RECLAIM`, `WMT_BALANCE`, `WMT_ADJ`, `WMT_AUTO_BALANCE`, `SALE_FORECAST_TYPE`, `CERTIFIED`, `ASSAY_TYPE`, `Ni`, `MC`, `Fe`, `SiO2`, `MgO`, `Co`, `Cr2O3`, `P2O5`, `PLAN_Ni`, `Plan_MC`, `Plan_Fe`, `Plan_SiO2`, `Plan_MgO`, `Plan_SM`, `BM_MC`, `BM_Ni`, `BM_Fe`, `BM_SiO2`, `BM_MgO`, `BM_Co`, `BM_Cr2O3`, `BM_P2O5`, `TOS_ASSAY_TYPE`, `TOS_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `TOS_Co`, `TOS_Cr2O3`, `TOS_P2O5`, `POS_ASSAY_TYPE`, `POS_ASSAY_STATUS`, `POS_ASSAY_CONTRACTOR`, `POS_WMT_CERT`, `POS_MC`, `POS_Ni`, `POS_Fe`, `POS_SiO2`, `POS_MgO`, `POS_Co`, `POS_Cr2O3`, `POS_P2O5`, `YARD_ASSAY_TYPE`, `YARD_ASSAY_STATUS`, `YARD_ASSAY_CONTRACTOR`, `YARD_WMT_CERT`, `YARD_MC`, `YARD_Ni`, `YARD_Fe`, `YARD_SiO2`, `YARD_MgO`, `YARD_Co`, `YARD_Cr2O3`, `YARD_P2O5`, `MATERIAL_BM`, `MATERIAL_CLASS_BM`, `MATERIAL_TOS`, `MATERIAL_CLASS_TOS`, `MATERIAL_POS`, `MATERIAL_CLASS_POS`, `MATERIAL_PLAN_NO_WA`, `MATERIAL_CLASS_PLAN_NO_WA`
- **`STOCK_MANAGEMENT_RE`** (117 cols): `YEAR`, `MONTH`, `YEAR_SALES`, `MONTH_SALES`, `WEEK`, `DATE`, `SURVEY_WEEK`, `SURVEY_TYPE`, `SURVEY_CLASS`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `STOCK_POINT`, `STOCK_TYPE`, `PLANT`, `PLANT_COMPANY`, `STOCK_AREA`, `AREA_LOCATION`, `STOCK_ID`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `RIT`, `WMT_METHOD`, `WMT`, `DATE_OUT`, `REJECT_DIRECT`, `ORIGIN_PIT`, `STOCK_STATUS`, `STOCK_LOGISTIC`, `REQUEST`, `REQUEST_DATE`, `REQUEST_PLANT`, `REQUEST_PLANT_CLASS`, `BATCH_ID`, `STOCK_PROD_DATE`, `STOCK_OPEN_DATE`, `STOCK_COMPLETE_DATE`, `STOCK_TRANSFER_DATE`, `STOCK_FINISH_DATE`, `STOCK_LAST_DATE`, `WMT_SENT`, `WMT_SENT_ORIGINAL`, `WMT_SENT_RATE`, `TO_SEND_RATE`, `TO_SEND_TOTAL_WMT`, `WMT_HAUL`, `WMT_RECLAIM`, `WMT_ADJ`, `AUTO_BALANCE`, `CERTIFIED`, `ASSAY_TYPE`, `Ni`, `MC`, `Fe`, `SiO2`, `MgO`, `Al2O3`, `Co`, `Cr2O3`, `P2O5`, `PLAN_MC`, `PLAN_Ni`, `PLAN_Fe`, `PLAN_SiO2`, `PLAN_MgO`, `Plan_SM`, `BM_MC`, `BM_Ni`, `BM_Fe`, `BM_SiO2`, `BM_MgO`, `BM_Co`, `BM_Cr2O3`, `BM_Ni_CORR`, `BM_PROD_Ni`, `TOS_ASSAY_TYPE`, `TOS_ASSAY_DATE`, `QC_PLAN_COMPO`, `TOS_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `TOS_Co`, `TOS_Cr2O3`, `POS_ASSAY_TYPE`, `POS_ASSAY_STATUS`, `POS_ASSAY_STATUS_%`, `POS_ASSAY_CONTRACTOR`, `POS_ASSAY_DATE`, `POS_WMT_CERT`, `POS_MC`, `POS_Ni`, `POS_Fe`, `POS_SiO2`, `POS_MgO`, `POS_Co`, `POS_Cr2O3`, `YARD_ASSAY_TYPE`, `YARD_ASSAY_STATUS`, `YARD_ASSAY_STATUS_%`, `YARD_ASSAY_CONTRACTOR`, `YARD_ASSAY_DATE`, `YARD_WMT_CERT`, `YARD_MC`, `YARD_Ni`, `YARD_Fe`, `YARD_SiO2`, `YARD_MgO`, `YARD_Co`, `YARD_Cr2O3`, `NTN_MC`, `NTN_Ni`, `NTN_Fe`, `MATERIAL_PLAN_NO_WA`
- **`STOCK_MANAGEMENT_RE_WITH_FENI_PLAN`** (118 cols): `YEAR`, `MONTH`, `YEAR_SALES`, `MONTH_SALES`, `WEEK`, `DATE`, `SURVEY_WEEK`, `SURVEY_TYPE`, `SURVEY_CLASS`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `STOCK_POINT`, `STOCK_TYPE`, `PLANT`, `PLANT_COMPANY`, `STOCK_AREA`, `AREA_LOCATION`, `STOCK_ID`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `RIT`, `WMT_METHOD`, `WMT`, `DATE_OUT`, `REJECT_DIRECT`, `ORIGIN_PIT`, `STOCK_STATUS`, `STOCK_LOGISTIC`, `REQUEST`, `REQUEST_DATE`, `REQUEST_PLANT`, `REQUEST_PLANT_CLASS`, `BATCH_ID`, `STOCK_PROD_DATE`, `STOCK_OPEN_DATE`, `STOCK_COMPLETE_DATE`, `STOCK_TRANSFER_DATE`, `STOCK_FINISH_DATE`, `STOCK_LAST_DATE`, `WMT_SENT`, `WMT_SENT_ORIGINAL`, `WMT_SENT_RATE`, `TO_SEND_RATE`, `TO_SEND_TOTAL_WMT`, `WMT_HAUL`, `WMT_RECLAIM`, `WMT_ADJ`, `AUTO_BALANCE`, `CERTIFIED`, `ASSAY_TYPE`, `Ni`, `MC`, `Fe`, `SiO2`, `MgO`, `Al2O3`, `Co`, `Cr2O3`, `P2O5`, `PLAN_MC`, `PLAN_Ni`, `PLAN_Fe`, `PLAN_SiO2`, `PLAN_MgO`, `Plan_SM`, `BM_MC`, `BM_Ni`, `BM_Fe`, `BM_SiO2`, `BM_MgO`, `BM_Co`, `BM_Cr2O3`, `BM_Ni_CORR`, `BM_PROD_Ni`, `TOS_ASSAY_TYPE`, `TOS_ASSAY_DATE`, `QC_PLAN_COMPO`, `TOS_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `TOS_Co`, `TOS_Cr2O3`, `POS_ASSAY_TYPE`, `POS_ASSAY_STATUS`, `POS_ASSAY_STATUS_%`, `POS_ASSAY_CONTRACTOR`, `POS_ASSAY_DATE`, `POS_WMT_CERT`, `POS_MC`, `POS_Ni`, `POS_Fe`, `POS_SiO2`, `POS_MgO`, `POS_Co`, `POS_Cr2O3`, `YARD_ASSAY_TYPE`, `YARD_ASSAY_STATUS`, `YARD_ASSAY_STATUS_%`, `YARD_ASSAY_CONTRACTOR`, `YARD_ASSAY_DATE`, `YARD_WMT_CERT`, `YARD_MC`, `YARD_Ni`, `YARD_Fe`, `YARD_SiO2`, `YARD_MgO`, `YARD_Co`, `YARD_Cr2O3`, `NTN_MC`, `NTN_Ni`, `NTN_Fe`, `MATERIAL_PLAN_NO_WA`, `FENI_RECLAIMING`
- **`STOCK_ORIGIN_PIT`** (2 cols): `STOCK_ID`, `ORIGIN_PIT`
- **`STOCK_ORIGIN_PIT_BY_WMT`** (3 cols): `DESTINATION_ID`, `ORIGIN_PIT`, `WMT`
- **`STOCK_POS_YARD`** (3 cols): `STOCK_TYPE`, `STOCK_AREA`, `STOCK_ID`
- **`STOCK_REQUESTS_TREATED`** (10 cols): `FIRST_DATE_SHARE`, `LATEST_DATE_SHARE`, `ORIGIN_ID`, `MAX_DATE_REQUEST`, `MIN_DATE_REQUEST`, `MAX_WMT_REQUEST`, `MIN_WMT_REQUEST`, `LATEST_DESTINATION_ID_REQUESTED`, `LATEST_DESTINATION_AREA_REQUESTED`, `REQUESTED_BY_IWIP`
- **`STOCK_REQUESTS_TREATED_2`** (9 cols): `FIRST_DATE_SHARE`, `LATEST_DATE_SHARE`, `ORIGIN_ID`, `MIN_DATE_REQUEST`, `MAX_DATE_REQUEST`, `MAX_WMT_SHARED`, `MIN_WMT_SHARED`, `LATEST_DESTINATION_ID_REQUESTED`, `LATEST_DESTINATION_AREA_REQUESTED`
- **`STOCK_SHAPE`** (9 cols): `id`, `name`, `CreationDa`, `Creator`, `EditDate`, `geom`, `new_dome_i`, `old_dome_i`, `menggantik`
- **`STOCK_SHAPE_LAST`** (3 cols): `STOCK_ID`, `EditDate`, `geom`
- **`STOCK_STATUS_FLOW`** (14 cols): `CONTRACTOR`, `STOCK_TYPE`, `STOCK_AREA`, `STOCK_ID`, `DATE_HAULAGE_START`, `DATE_HAULAGE_END`, `RECLAIMING_PLANT`, `DATE_RECLAIMING_START`, `DATE_RECLAIMING_END`, `WMT_HAUL`, `WMT_RECLAIM`, `DATE_REJECT_START`, `DATE_REJECT_END`, `ORIGIN_PIT`
- **`STOCK_STATUS_FULL`** (13 cols): `ORIGIN_PIT`, `STOCK_TYPE`, `STOCK_AREA`, `STOCK_ID`, `ORIGIN_ID`, `STOCK_STATUS`, `MATERIAL`, `HIGH_TURN`, `PRIORITY_RECLAIM`, `DATE_OPEN`, `DATE_COMPLETE`, `DATE_TRANSFER`, `DATE_FINISH`
- **`STOCK_STATUS_SIMPLE`** (8 cols): `STOCK_TYPE`, `STOCK_AREA`, `STOCK_ID`, `STATUS`, `MATERIAL`, `DATE_OPEN`, `DATE_CLOSE`, `REMARK`
- **`STOCK_STATUS_STATUS`** (15 cols): `CONTRACTOR`, `ORIGIN_PIT`, `STOCK_TYPE`, `STOCK_AREA`, `STOCK_ID`, `STOCK_STATUS`, `MATERIAL`, `HIGH_TURN`, `PRIORITY_RECLAIM`, `DATE_OPEN`, `DATE_COMPLETE`, `DATE_TRANSFER`, `DATE_FINISH`, `REMARK`, `PAD_ID`
- **`STOCK_TYPE_ALL`** (2 cols): `STOCK_TYPE`, `STOCK_ID`
- **`STOCK_WMT_EVOLUTION`** (16 cols): `DATE`, `YEAR`, `MONTH`, `WEEK`, `ORIGIN_PIT`, `STOCK_TYPE`, `STOCK_AREA`, `STOCK_ID`, `DATE_OPEN`, `DATE_COMPLETE`, `DATE_TRANSFER`, `DATE_FINISH`, `SURVEY_SEGMENT_DATE_NEXT`, `SURVEY_WMT`, `PROD_WMT`, `WMT_CUMULATIVE`
- **`SUM PROD WMT FOR CORR`** (6 cols): `YEAR`, `MONTH`, `contractor`, `pit`, `WMT_ACTUAL`, `FINAL_RECLASSIFICATION`
- **`SUM WMT SURVEY`** (7 cols): `YEAR`, `CONTRACTOR`, `MONTH`, `PIT`, `MATERIAL_ID`, `WMT_SURVEY`, `BCM_SURVEY`
- **`SURVEY POS CONSOLIDATED`** (6 cols): `DATE`, `TYPE OF SURVEY`, `SURVEY WEEK`, `DOME`, `WMT`, `STOCK TYPE`
- **`SURVEY_POS_DATED`** (15 cols): `ID`, `DATE`, `TYPE OF SURVEY`, `SURVEY WEEK`, `STOCK_AREA`, `DOME`, `IS_MAX_WMT`, `DOME ID`, `SURVEY METHOD`, `ORIGIN_PIT`, `VOLUME (LCM)`, `VOLUME (BCM)`, `ORIGINAL DENSITY`, `ADJUSTED DENSITY`, `WMT`
- **`SURVEY_POS_ESTIMATE_HAULAGE`** (9 cols): `DATE`, `TYPE OF SURVEY`, `SURVEY WEEK`, `DOME`, `WMT_SURVEY`, `WMT_PREVIOUS`, `WMT_EST_HAULAGE`, `ACTIVITY`, `STOCK TYPE`
- **`SURVEY_POS_FOR_PROD`** (8 cols): `DATE`, `SURVEY_TYPE`, `SURVEY_WEEK`, `MATERIAL`, `STOCK_TYPE`, `STOCK_ID`, `PIT`, `WMT`
- **`SURVEY_POS_TC`** (6 cols): `DATE`, `TYPE OF SURVEY`, `SURVEY WEEK`, `DOME`, `WMT`, `STOCK TYPE`
- **`SURVEY_STOCK_MAX`** (3 cols): `DOME`, `WMT`, `DATE`
- **`TEST_CAROTTE`** (25 cols): `YEAR`, `MONTH`, `PIT`, `CONTRACTOR_PILE`, `MATERIAL`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `WMT`, `BM_MC`, `BM_Ni`, `BM_Fe`, `CARROT_MC`, `CARROT_Ni`, `CARROT_Fe`, `DIL_BM_MC`, `DIL_BM_Ni`, `DIL_BM_Fe`, `DIL_CARROT_BM_MC`, `DIL_CARROT_BM_Ni`, `DIL_CARROT_BM_Fe`, `DEST_MC`, `DEST_Fe`, `DEST_Ni`
- **`TOS FOLLOW TREATED`** (12 cols): `DATE`, `POS DOME`, `POS`, `WMT_TOTAL`, `CONTRACTOR`, `MATERIAL`, `SHIFT`, `BLOCK ID`, `TOS`, `POS NEW`, `TYPE`, `ORIGIN`
- **`TOS FOLLOW TREATED 2`** (36 cols): `DATE`, `SHIFT`, `ORIGIN`, `TOS`, `PILE_ID`, `DESTINATION`, `POS`, `DOME_ID`, `CONTRACTOR`, `MATERIAL`, `TYPE`, `WMT_TOTAL`, `PLAN_Ni`, `PLAN_MC`, `PLAN_Fe`, `PLAN_SiO2`, `PLAN_MgO`, `TOS_Ni`, `TOS_Fe`, `TOS_MgO`, `TOS_SiO2`, `TOS_DMT`, `CAT_2025`, `BM_al2o3`, `BM_cao`, `BM_co`, `BM_cr2o3`, `BM_fe`, `BM_h2o`, `BM_mgo`, `BM_mno`, `BM_Ni`, `BM_p2o5`, `BM_prop`, `BM_sio2`, `BM_DMT`
- **`TOS_DUMP_COORDINATES_UNIQUE`** (7 cols): `TOS_TYPE`, `TOS_PIT`, `TOS_NUMBER`, `TOS_CONTRACTOR`, `TOS_X`, `TOS_Y`, `COUNT`
- **`TOS_Duplicate`** (37 cols): `Sampling_Contractor`, `Sampling_date`, `Original_Sample`, `Duplicate_Sample`, `Pit`, `Stock_ID`, `BLOCK_ID`, `ReturnDate`, `Assay_Type`, `Activity`, `Stock_type`, `Production_Contractor`, `Facies`, `Orig_Ni`, `Dup_Ni`, `Orig_Fe`, `Dup_Fe`, `Orig_Fe2O3`, `Dup_Fe2O3`, `Orig_MgO`, `Dup_MgO`, `Orig_SiO2`, `Dup_SiO2`, `Orig_Al2O3`, `Dup_Al2O3`, `Orig_Co`, `Dup_Co`, `Orig_CaO`, `Dup_CaO`, `Orig_Cr2O3`, `Dup_Cr2O3`, `Orig_P2O5`, `Dup_P2O5`, `Orig_MnO`, `Dup_MnO`, `Orig_MC`, `Dup_MC`
- **`TOS_PILES_WMT_WB_RIT_MINING`** (8 cols): `YEAR`, `MONTH`, `CONTRACTOR`, `DEPOSIT`, `TOT_RIT`, `TOS_PILE`, `WMT_WB`, `MATERIAL`
- **`TOS_PILE_FINAL_RECLASSIFICATION`** (2 cols): `TOS_PILE`, `FINAL_RECLASSIFICATION`
- **`TOS_PILE_INFO_TREATED`** (5 cols): `TOS_PILE`, `TOS`, `CONTRACTOR_PROD`, `MATERIAL_TYPE`, `PIT`
- **`TOS_PILE_PIT`** (3 cols): `TOS PILE`, `PIT`, `TYPE_PROD`
- **`TOS_STATUS_ERROR_TRANSFER_DATE`** (3 cols): `MIN_TRANSFER_DATE`, `MIN_COMPLETE_DATE`, `STOCK_ID`
- **`TOS_SURVEY_ESTIMATION`** (18 cols): `DATE`, `SHIFT`, `DATETIME`, `STOCK_TYPE`, `STOCK_AREA`, `STOCK_ID`, `STATUS`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `RIT`, `TF`, `WMT_SURVEY_EST`, `WMT_SURVEY_GAP`, `WMT_SURVEY`, `WMT_TRANSFER`, `WMT_ORI`, `WMT`
- **`TOS_SURVEY_ESTIMATION2`** (13 cols): `CONTRACTOR`, `DATE`, `SHIFT`, `SURVEY_TYPE`, `SURVEY_WEEK`, `SURVEY_METHOD`, `STOCK_AREA`, `STOCK_ID`, `STOCK_STATUS`, `LCM`, `BCM`, `LOOS_DENS`, `WMT`
- **`TOS_SURVEY_trial`** (10 cols): `DATE`, `CONTRACTOR`, `SHIFT`, `TOS_LOCATION`, `PILE_ID`, `PILE_STATUS`, `OMR_RIT`, `OMR_TF`, `WMT_MINING`, `WMT_MINING_CUMULATIVE`
- **`TSS_NO_MATCH_POINT`** (2 cols): `NEW_STATION`, `OLD_STATION`
- **`TSS_PREP`** (22 cols): `YEAR`, `MONTH`, `WEEK`, `CONTRACTOR`, `DATE`, `AREA`, `SUB_AREA`, `MANAGER`, `TYPE`, `MINE`, `STATION`, `OUTFALL`, `TSS`, `PH`, `TEMPERATURE`, `CONDUCTIVITY`, `TDS`, `TURBIDITY_NTU`, `TSS_LIMIT`, `COMPLIANCE`, `X`, `Y`
- **`UNIT_TRIPS_HUAFEI_RSF`** (10 cols): `DATE`, `SHIFT`, `COMPANY`, `NB_UNIT`, `TRIP`, `ORIGIN_KM`, `ORIGIN`, `DESTINATION_KM`, `DESTINATION`, `DT_COMPANY`
- **`VW_PRODUCTION_ACTIVITY_PIT`** (26 cols): `DATE`, `CONTRACTOR`, `SHIFT`, `AREA`, `SUB_AREA`, `ACTIVITY`, `ENTITY`, `MATERIAL`, `MATERIAL_CLASS`, `ORIGIN_ID_BLOCK_ID`, `PROD_ID`, `BLAST_ID`, `DESTINATION_AREA`, `DESTINATION_GROUP`, `DESTINATION_ID`, `RIT`, `EXCA_ID`, `ADT_ID`, `DT_ID`, `DOZER_ID`, `GRADER_ID`, `COMPACT_ID`, `WT_ID`, `RIG_ID`, `BCM`, `STATUS`
- **`WAITING_TIME_DIFFERENCE`** (20 cols): `TEAM`, `DATE`, `EQUIPMENT_ID`, `SHIFT`, `ORIGIN_ID`, `ORIGIN_AREA`, `DESTINATION`, `BLOCK_ID`, `RIT`, `WB_ID`, `LOADING_WAITING_TIME`, `LOADING_TIME`, `LOADING_DIFFERENCE_TIME`, `DUMPING_WAITING_TIME`, `DUMPING_TIME`, `DUMPING_DIFFERENCE_TIME`, `DRIVER_ID`, `PIT`, `FUEL_FILLING_TIME`, `REMARK`
- **`WAITING_TIME_FIX`** (20 cols): `TEAM`, `DATE`, `EQUIPMENT_ID`, `SHIFT`, `ORIGIN_ID`, `ORIGIN_AREA`, `BLOCK_ID`, `RIT`, `WB_ID`, `LOADING_WAITING_TIME`, `LOADING_TIME`, `LOADING_DIFFERENCE_TIME`, `DUMPING_WAITING_TIME`, `DUMPING_TIME`, `DUMPING_DIFFERENCE_TIME`, `DRIVER_ID`, `PIT`, `FUEL_FILLING_TIME`, `REMARK`, `DESTINATION`
- **`WEIGHBRIDGE_&_TRUCKCOUNT_TF_LAST`** (2 cols): `CONTRACTOR_HAUL`, `AVG_TF`
- **`WEIGHBRIDGE_&_TRUCKCOUNT_TF_PER_WEEK`** (6 cols): `YEAR`, `MONTH`, `WEEK`, `CONTRACTOR_HAUL`, `PIT_ORIGIN`, `AVG_TF`
- **`WMT_3RD_PARTY_LAST`** (7 cols): `DATE`, `STOCK_TYPE`, `STOCK_ID`, `CONTRACTOR`, `WMT_SENT`, `WMT_SENT_ORIGINAL`, `WMT_SENT_RATE`
- **`WMT_LAST_CERT`** (5 cols): `DATE`, `DOME`, `CONTRACTOR`, `WMT_POS_SENT`, `WMT_YARD_SENT`
- **`_LIMONITE_DAILY_STOCK`** (27 cols): `DATE`, `deposit_code`, `subpit`, `WMT`, `CF`, `DOME`, `TOS_PILE`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `MnO`, `Cr2O3`, `Al2O3`, `SM`, `MC`, `TYPE`, `prod_ID`, `contractor`, `TYPE OF SURVEY`, `SURVEY WEEK`, `DESTINATION`, `YEAR`, `MONTH`, `WEEK`, `OLD_ID_LIM_DUMP`
- **`_PROD_BLAST_ASSAYS`** (24 cols): `CONTRACTOR`, `DATE`, `shift`, `deposit_code`, `pit`, `subpit`, `prod_ID`, `block_id`, `material`, `CF`, `WMT`, `destination`, `TOS_PILE`, `Ni`, `Fe`, `SiO2`, `MgO`, `Co`, `SiO2/MgO`, `MC`, `status_blast`, `YEAR`, `MONTH`, `WEEK`
- **`_ore_screened_or_not`** (2 cols): `DOME`, `MATERIAL`
- **`_prod_lim_assays`** (24 cols): `DATE`, `deposit_code`, `subpit`, `TYPE`, `prod_ID`, `contractor`, `WMT`, `CF`, `DOME`, `TOS_PILE`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `MnO`, `Cr2O3`, `Al2O3`, `SM`, `MC`, `CaO`, `Fe2O3`, `P2O5`, `TYPE LIM`
- **`_prod_lim_assays_via_BM`** (24 cols): `DATE`, `deposit_code`, `subpit`, `TYPE`, `prod_ID`, `contractor`, `WMT`, `CF`, `DOME`, `TOS_PILE`, `Ni`, `Fe`, `Co`, `SiO2`, `MgO`, `MnO`, `Cr2O3`, `Al2O3`, `SM`, `MC`, `CaO`, `Fe2O3`, `P2O5`, `TYPE LIM`
- **`autoBM_GROUP`** (34 cols): `LAST_UPDATE`, `DEPOSIT`, `block_id`, `size (X)`, ` size(Y)`, ` size(Z)`, `VOLUME`, `MATERIAL_CLASS`, `DENSITY`, `WMT`, `DMT`, `Al2O3`, `CaO`, `Co`, `Cr2O3`, `Fe`, `H2O`, `MgO`, `MnO`, `Ni`, `P2O5`, `PROP`, `SiO2`, `CARROT_H2O`, `CARROT_Ni`, `CARROT_Fe`, `CARROT_SiO2`, `CARROT_MgO`, `CARROT_Co`, `CARROT_Cr2O3`, `Z`, `B`, `S`, `N`
- **`autoPLAN_Ni`** (6 cols): `STOCK_ID`, `MC`, `Ni`, `Fe`, `SiO2`, `MgO`
- **`autoQC_PLAN_NI_CF`** (22 cols): `LAST_UPDATE`, `YEAR`, `MONTH`, `DATE`, `MATERIAL`, `ORIGIN_PIT`, `CONTRACTOR_PILE`, `DIL_BM_MC`, `DIL_BM_Ni`, `DIL_BM_Fe`, `DIL_BM_SiO2`, `DIL_BM_MgO`, `DIL_BM_Co`, `DIL_BM_Cr2O3`, `DIL_TOS_MC`, `DIL_TOS_Ni`, `DIL_TOS_Fe`, `DIL_TOS_SiO2`, `DIL_TOS_MgO`, `DIL_TOS_Co`, `DIL_TOS_Cr2O3`, `DIL_PROP_BM_Ni`
- **`autoTOS_SURVEY_ESTIMATION_view`** (21 cols): `LAST_UPDATE`, `DATE`, `SHIFT`, `DATETIME`, `STOCK_TYPE`, `STOCK_AREA`, `STOCK_ID`, `CONTRACTOR_PILE`, `PIT`, `STATUS`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `RIT`, `TF`, `WMT_SURVEY_EST`, `WMT_SURVEY_GAP`, `WMT_SURVEY`, `WMT_TRANSFER`, `WMT_ORI`, `WMT`
- **`auto_view_QC_STOCK_ALL_VIA_ALL`** (90 cols): `LAST_UPDATE`, `STOCK_TYPE`, `STOCK_ID`, `Ni_`, `PLAN_MC`, `PLAN_Ni`, `PLAN_Fe`, `PLAN_SiO2`, `PLAN_MgO`, `DEF_ASSAY_TYPE`, `DEF_MC`, `DEF_Ni`, `DEF_Fe`, `DEF_SiO2`, `DEF_MgO`, `DEF_Al2O3`, `DEF_Co`, `DEF_Cr2O3`, `DEF_MnO`, `DEF_P2O5`, `BM_ASSAY_TYPE`, `BM_MC`, `BM_Ni`, `BM_Fe`, `BM_SiO2`, `BM_MgO`, `BM_Al2O3`, `BM_Co`, `BM_Cr2O3`, `BM_MnO`, `BM_P2O5`, `BM_Ni_CORR`, `BM_Fe_CORR`, `BM_SiO2_CORR`, `BM_MgO_CORR`, `TOS_ASSAY_TYPE`, `TOS_ASSAY_DATE`, `TOS_MC`, `TOS_Ni`, `TOS_Fe`, `TOS_SiO2`, `TOS_MgO`, `TOS_Al2O3`, `TOS_Co`, `TOS_Cr2O3`, `TOS_MnO`, `TOS_P2O5`, `POS_ASSAY_TYPE`, `POS_ASSAY_STATUS`, `POS_ASSAY_STATUS_%`, `POS_ASSAY_CONTRACTOR`, `POS_ASSAY_DATE`, `POS_WMT_CERT`, `POS_MC`, `POS_Ni`, `POS_Fe`, `POS_SiO2`, `POS_MgO`, `POS_Al2O3`, `POS_Co`, `POS_Cr2O3`, `POS_MnO`, `POS_P2O5`, `YARD_ASSAY_TYPE`, `YARD_ASSAY_STATUS`, `YARD_ASSAY_STATUS_%`, `YARD_ASSAY_CONTRACTOR`, `YARD_ASSAY_DATE`, `YARD_WMT_CERT`, `YARD_MC`, `YARD_Ni`, `YARD_Fe`, `YARD_SiO2`, `YARD_MgO`, `YARD_Al2O3`, `YARD_Co`, `YARD_Cr2O3`, `YARD_MnO`, `YARD_P2O5`, `ML_Ni`, `DIL_BM_MC`, `DIL_BM_Ni`, `DIL_BM_Fe`, `DIL_BM_SiO2`, `DIL_BM_MgO`, `DIL_TOS_MC`, `DIL_TOS_Ni`, `DIL_TOS_Fe`, `DIL_TOS_SiO2`, `DIL_TOS_MgO`
- **`block_prod`** (23 cols): `ID`, `contractor`, `Date`, `shift`, `deposit_code`, `pit`, `subpit`, `prod_ID`, `block_id`, `block_ID_2`, `CLASS_BM`, `material`, `RIT`, `TF_1`, `TF_2`, `WMT`, `WMT2`, `destination`, `TOS_PILE`, `status`, `status_blast`, `TYPE_PROD`, `BLAST_ID`
- **`equipments_status_last_breakdown`** (4 cols): `CONTRACTOR`, `ID_EQ`, `MAX_DATE_EQ`, `MAX_DATE_CONTRACTOR`
- **`geometry_columns`** (11 cols): `f_table_catalog`, `f_table_schema`, `f_table_name`, `f_geometry_column`, `coord_dimension`, `srid`, `geometry_type`, `qgis_xmin`, `qgis_ymin`, `qgis_xmax`, `qgis_ymax`
- **`test sa mere`** (11 cols): `YEAR`, `MONTH`, `WEEK`, `DATE`, `NBDAYS`, `CONTRACTOR`, `PIT`, `CLASS_MATERIAL`, `WMT_ROM_MONTHLY`, `WMT_DAILY`, `TYPE_DATA`
- **`trial cek tos follow vs haulage iwip `** (8 cols): `DATE`, `DOME_ID`, `POS`, `TS_WMT`, `DESTINATION_ID_CLEAN`, `DESTINATION_AREA_CLEAN`, `WMT_HAULAGE`, `SELISIH_WMT`
- **`vOSPAT_RESULTS`** (22 cols): `CONTRACTOR`, `TestDateTime`, `TestDateShift`, `TestShift`, `Tag`, `EmployeeID`, `Employee FamilyName`, `Employee FirstName`, `EmploymentStatus`, `EmployeePositionName`, `SupervisorPositionName`, `TerminalName`, `TerminalIPAddress`, `TerminalTag`, `EmployeeTag`, `EmployeeAge`, `ResultType`, `AttemptCount`, `ShiftTag`, `ResultScore`, `OutcomeType1`, `ResultClass`
- **`vw_HAULAGE_GROUP`** (11 cols): `DATE`, `SHIFT`, `CONTRACTOR`, `ACTIVITY`, `MATERIAL`, `ORIGIN_AREA`, `ORIGIN_ID`, `DESTINATION_AREA`, `DESTINATION_ID`, `RIT`, `WMT`
- **`w2_EQUIPMENTS`** (13 cols): `ID`, `CONTRACTOR`, `ID_EQ`, `OWNER`, `TYPE`, `DIGIT`, `MANUFACTURER`, `MODEL`, `CAPACITY`, `NB_TYRES`, `BUILD_YEAR`, `DIVISION`, `NEW_ID_EQ`
- **`w2_EQUIPMENTS_STATUS`** (17 cols): `ID`, `CONTRACTOR`, `DATE`, `SHIFT`, `ID_EQ`, `STATUS`, `ACTIVITY`, `LOCATION`, `LOCATION_DETAILS`, `HOUR_METER_START`, `HOUR_METER_END`, `USAGE_KM_METER`, `BD_START`, `BD_EST_RFU`, `BD_COMPARTMENT`, `BD_STATUS`, `REMARK`
- **`w2_PRODUCTION_PIT_HOURLY`** (19 cols): `ID`, `CONTRACTOR`, `DATE`, `SHIFT`, `TIME_GROUP`, `START_HOUR`, `END_HOUR`, `ACTIVITY_TYPE`, `MATERIAL`, `PIT`, `SUB_PIT`, `BLOCK_ID`, `PROD_ID`, `DESTINATION_AREA`, `PILE_ID`, `TRUCK_ID`, `EXCAVATOR_ID`, `RIT`, `COMMENT`

</details>

---

## FMS_DB

90 objects: **54 base tables**, 36 views. Every base table with rows was sampled; views are catalogued for columns (each is defined over base tables already covered).

### FMS_DB — index

| Table | Rows | Cols | Date range |
|---|---|---|---|
| [`FMS_PLAYBACK_TRACK_DATA`](#fms-db-fms-playback-track-data) | 26,429,474 | 18 | 2026-03-21 → 2026-07-30 |
| [`auto_kmFMS_PLAYBACK_TRACK_DATA`](#fms-db-auto-kmfms-playback-track-data) | 19,421,021 | 4 | — |
| [`FMS_ENTRY_EXIT_DATA`](#fms-db-fms-entry-exit-data) | 11,627,431 | 12 | 2026-06-08 → 2026-07-30 |
| [`FMS_SECURITY_INCIDENT_DATA`](#fms-db-fms-security-incident-data) | 5,347,725 | 36 | 2026-03-19 → 2026-07-30 |
| [`autoFMS_SECURITY_INCIDENT_KILOMETER`](#fms-db-autofms-security-incident-kilometer) | 4,168,389 | 4 | — |
| [`auto_spFMS_PLAYBACK_TRACK_DATA`](#fms-db-auto-spfms-playback-track-data) | 1,701,102 | 5 | — |
| [`FMS_INTERVENTION_EVENT_DATA`](#fms-db-fms-intervention-event-data) | 1,267,116 | 32 | 2026-04-07 → 2026-07-30 |
| [`FMS_PLAYBACK_TRACK_24H`](#fms-db-fms-playback-track-24h) | 1,111,436 | 14 | — |
| [`FMS_GPS_Historical`](#fms-db-fms-gps-historical) | 521,918 | 15 | — |
| [`FMS_PLAYBACK_STAY_DATA`](#fms-db-fms-playback-stay-data) | 388,046 | 43 | 2026-03-22 → 2026-07-30 |
| [`FMS_RISK_DATA`](#fms-db-fms-risk-data) | 316,302 | 19 | 2026-04-06 → 2026-07-30 |
| [`FMS_GEOFENCE_VISITS`](#fms-db-fms-geofence-visits) | 59,445 | 17 | — |
| [`FMS_CONGESTION_SEG`](#fms-db-fms-congestion-seg) | 35,156 | 9 | — |
| [`RES_EMPLOYEES`](#fms-db-res-employees) | 8,958 | 9 | — |
| [`FMS_GEOFENCES`](#fms-db-fms-geofences) | 3,490 | 17 | — |
| [`RADIO_REPROGRAM_TRACK`](#fms-db-radio-reprogram-track) | 3,478 | 21 | — |
| [`FMS_TOS_STATUS`](#fms-db-fms-tos-status) | 3,404 | 14 | — |
| [`FMS_TMS_TOKEN`](#fms-db-fms-tms-token) | 2,927 | 3 | — |
| [`FMS_EQUIPMENTS`](#fms-db-fms-equipments) | 1,411 | 7 | 2026-03-22 → 2026-07-29 |
| [`WT_DAILY_PLAN`](#fms-db-wt-daily-plan) | 1,241 | 10 | — |
| [`FMS_UNIT_INSTALLED`](#fms-db-fms-unit-installed) | 1,194 | 4 | — |
| [`FMS_TRUCK_ASSIGNMENTS`](#fms-db-fms-truck-assignments) | 408 | 10 | — |
| [`FMS_HAUL_CYCLES`](#fms-db-fms-haul-cycles) | 288 | 10 | 2026-06-26 → 2026-07-24 |
| [`FMS_QUALITY_DISPATCH`](#fms-db-fms-quality-dispatch) | 258 | 21 | 2026-06-23 → 2026-07-22 |
| [`FMS_DISPATCH_PLAN`](#fms-db-fms-dispatch-plan) | 105 | 16 | 2026-06-23 → 2026-07-22 |
| [`SHP_SED_POND`](#fms-db-shp-sed-pond) | 91 | 4 | — |
| [`FMS_ROADMAP`](#fms-db-fms-roadmap) | 87 | 21 | — |
| [`SAFETY_DPLAN`](#fms-db-safety-dplan) | 80 | 9 | — |
| [`LV_PLAN`](#fms-db-lv-plan) | 62 | 7 | — |
| [`LV_INFO`](#fms-db-lv-info) | 57 | 6 | — |
| [`FMS_GEOFENCE_ALERTS`](#fms-db-fms-geofence-alerts) | 46 | 29 | — |
| [`FMS_LV_ZONE_VISITS`](#fms-db-fms-lv-zone-visits) | 43 | 13 | — |
| [`FMS_LOGIN_IPS`](#fms-db-fms-login-ips) | 37 | 5 | — |
| [`FMS_USERS`](#fms-db-fms-users) | 30 | 8 | — |
| [`RES_SPEED_LIMIT_ZONES`](#fms-db-res-speed-limit-zones) | 27 | 16 | — |
| [`FMS_APP_STATE`](#fms-db-fms-app-state) | 23 | 3 | 2026-07-11 → 2026-07-30 |
| [`FMS_USER_ACTIVITY`](#fms-db-fms-user-activity) | 18 | 3 | — |
| [`FMS_ASSIGNMENTS`](#fms-db-fms-assignments) | 17 | 5 | 2026-07-05 → 2026-07-28 |
| [`FMS_JOB_RUNS`](#fms-db-fms-job-runs) | 15 | 5 | 2026-07-16 → 2026-07-30 |
| [`FMS_MESSAGES`](#fms-db-fms-messages) | 14 | 15 | — |
| [`RES_WATER_FILLING_POINTS`](#fms-db-res-water-filling-points) | 14 | 9 | — |
| [`FMS_SETTINGS`](#fms-db-fms-settings) | 7 | 3 | — |
| [`FMS_LV_DAILY_REPORTS`](#fms-db-fms-lv-daily-reports) | 6 | 12 | 2026-07-24 → 2026-07-29 |
| [`FMS_LV_VISIT_VERIFICATIONS`](#fms-db-fms-lv-visit-verifications) | 4 | 13 | — |
| [`RES_CRITICAL_ZONES`](#fms-db-res-critical-zones) | 4 | 5 | — |
| [`FMS_INSTANCES`](#fms-db-fms-instances) | 2 | 7 | — |
| [`FMS_DOCS`](#fms-db-fms-docs) | 1 | 4 | — |
| [`FMS_GEOFENCE_ALERT_RULES`](#fms-db-fms-geofence-alert-rules) | 1 | 17 | — |
| [`FMS_ROADMAP_DOC`](#fms-db-fms-roadmap-doc) | 1 | 5 | — |
| [`FMS_ROADMAP_META`](#fms-db-fms-roadmap-meta) | 1 | 2 | — |
| [`FMS_TRUCK_CYCLES`](#fms-db-fms-truck-cycles) | 1 | 16 | — |
| [`FMS_ERROR_FLOW`](#fms-db-fms-error-flow) | 0 | 8 | — |
| [`FMS_LV_MOVEMENTS`](#fms-db-fms-lv-movements) | 0 | 15 | — |
| [`LV_DRIVER_INFO`](#fms-db-lv-driver-info) | 0 | 6 | — |

### FMS_DB — table detail

<a id="fms-db-fms-playback-track-data"></a>

#### `FMS_PLAYBACK_TRACK_DATA`

**Rows:** 26,429,474  |  **Columns:** 18  |  **FETCH_DATE:** 2026-03-21 17:09:36 → 2026-07-30 12:05:44

> 26.4M raw GPS fixes, but keyed on plateNumber and containing only 219 SS###/E### support units. This is the table that produced the false '0 of 940' claim.

**Columns:** `FETCH_DATE` datetime, `plateNumber` nvarchar(50), `acc` float, `deviceType` nvarchar(255), `distance` float, `lng` float, `driving_time` float, `dump_energy` nvarchar(255), `receive_time` float, `loc_type` float, `speed` float, `engine` float, `oils` float, `course` float, `imei` bigint, `time` bigint, `interpolation_flag` float, `lat` float

**Identifier vocabularies:**

- `plateNumber` — 219 distinct. e.g. `SS074`, `SS027`, `SS042`, `SS095`, `SS040`, `SS203`, `SS125`, `SS008`, `SS207`, `SS020`, `SS129`, `SS039`
- `deviceType` — 4 distinct. e.g. `f6`, `lt_et100_v`, `smart_1c`, `xpad`

**Coordinate extent:** `lng` 0.0 → 128.10046; `lat` 0.0 → 0.822522

**Sample rows** (first 14 of 18 columns):

| FETCH_DATE | plateNumber | acc | deviceType | distance | lng | driving_time | dump_energy | receive_time | loc_type | speed | engine | oils | course |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-05-12T15:00:30.443 | SS074 | 1.0 | smart_1c | 6835.0 | 127.916742 | 4.0 |  | 1778398774705.0 | 0.0 | 0.0 |  | -1.0 | 341.0 |
| 2026-05-12T15:00:30.443 | SS074 | 1.0 |  | 2063.0 | 127.916574 | 122.0 |  | 1778398905725.0 | 0.0 | 0.0 |  | -1.0 | 157.0 |
| 2026-05-12T15:00:30.443 | SS074 | 1.0 |  | 134.0 | 127.916575 | 1.0 |  | 1778400726984.0 | 0.0 | 4.0 |  | -1.0 | 66.0 |
| 2026-05-12T15:00:30.443 | SS074 | 1.0 |  | 1575.0 | 127.916631 | 1.0 |  | 1778400726984.0 | 0.0 | 4.0 |  | -1.0 | 69.0 |
| 2026-05-12T15:00:30.443 | SS074 | 1.0 |  | 320.0 | 127.916654 | 122.0 |  | 1778400903025.0 | 0.0 | 0.0 |  | -1.0 | 69.0 |

<a id="fms-db-auto-kmfms-playback-track-data"></a>

#### `auto_kmFMS_PLAYBACK_TRACK_DATA`

**Rows:** 19,421,021  |  **Columns:** 4

> GPS fixes resolved to KM chainage. The link between raw tracks and named road segments.

**Columns:** `imei` bigint, `time` bigint, `DIRECTION` nvarchar(50), `SectionKM` float

**Sample rows**:

| imei | time | DIRECTION | SectionKM |
|---|---|---|---|
| 107015291859999 | 1778398774000 | KR | 11.0 |
| 107015291859999 | 1778398905000 | KR | 11.0 |
| 107015291859999 | 1778400709000 | KR | 11.0 |
| 107015291859999 | 1778400710000 | KR | 11.0 |
| 107015291859999 | 1778400902000 | KR | 11.0 |

<a id="fms-db-fms-entry-exit-data"></a>

#### `FMS_ENTRY_EXIT_DATA`

**Rows:** 11,627,431  |  **Columns:** 12  |  **FETCH_DATE:** 2026-06-08 11:48:17 → 2026-07-30 10:50:59

> 11.6M point-level stay events with stayTime at named locations.

**Columns:** `FETCH_DATE` datetime, `plateNumber` nvarchar(255), `startTime` bigint, `endTime` bigint, `truckId` bigint, `pointId` int, `orgName` nvarchar(255), `orgId` bigint, `poiTypeName` nvarchar(255), `pointName` nvarchar(255), `stayTime` float, `hasVideoAbility` nvarchar(50)

**Identifier vocabularies:**

- `plateNumber` — 954 distinct. e.g. `N479`, `N725`, `R279`, `R302`, `L128`, `N336`, `R271`, `N296`, `R310`, `N114`, `L777`, `R570`

**Sample rows**:

| FETCH_DATE | plateNumber | startTime | endTime | truckId | pointId | orgName | orgId | poiTypeName | pointName | stayTime | hasVideoAbility |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-06-08T14:16:24.257 | N689 | 1780149599000 | 1780149641000 | 7292458631101156097 | 33396 | RIM??? C ?? | 7190740880934963462 | 15km????? | 15KM????? | 42.0 | 1 |
| 2026-06-08T14:16:24.257 | N110 | 1780149600000 | 1780149624000 | 6965075089742366088 | 33395 | RIM??? C ?? | 7190740880934963462 | ??? | KR11KM | 24.0 | 1 |
| 2026-06-08T14:16:24.257 | N088 | 1780149600000 | 1780149618000 | 6965075185036953728 | 34248 | RIM??? C ?? | 7190740880934963462 | WBN_SpeedLimit_Test05 | KR KM13 | 18.0 | 1 |
| 2026-06-08T14:16:24.257 | L774 | 1780149600000 | 1780149630000 | 6965230194600971008 | 34216 | RIM??? E ?? | 7190741736405205894 | WBN_SpeedLimit_Test05 | CRD KM2 | 30.0 | 1 |
| 2026-06-08T14:16:24.257 | L321 | 1780149600000 | 1780149630000 | 6965269606797936004 | 34175 | RIM??? B ?? | 7190740352016450440 | WBN_SpeedLimit_Test05 | KR KM31 | 30.0 | 1 |

<a id="fms-db-fms-security-incident-data"></a>

#### `FMS_SECURITY_INCIDENT_DATA`

**Rows:** 5,347,725  |  **Columns:** 36  |  **FETCH_DATE:** 2026-03-19 09:10:31 → 2026-07-30 10:31:39

**Columns:** `FETCH_DATE` datetime, `id` nvarchar(100), `orgId` bigint, `speed` float, `checkDriverName` nvarchar(255), `endLat` float, `carrierName` nvarchar(255), `areaName` nvarchar(255), `endPrecision` float, `difftime` float, `startTime` bigint, `endLng` float, `driverNo` nvarchar(255), `lat` float, `limitSpeed` nvarchar(255), `mileage` float, `truckId` nvarchar(255), `address` nvarchar(255), `orgName` nvarchar(255), `lng` float, `startAddress` nvarchar(255), `updateTime` bigint, `eventType` nvarchar(255), `maxSpeed` float, `plateNumber` nvarchar(255), `markerType` nvarchar(255), `driverId` float, `classTypeName` nvarchar(255), `createTime` bigint, `speedPercent` nvarchar(255), `eventTypeName` nvarchar(255), `imei` nvarchar(255), `driverName` nvarchar(255), `endTime` bigint, `markerRemark` nvarchar(255), `endAddress` nvarchar(255)

**Identifier vocabularies:**

- `id` — 5,347,725 distinct. e.g. `107015291859043_10004_1772110463000`, `107015291859043_10004_1772112773000`, `107015291859043_10004_1772113778000`, `107015291859043_10004_1772130260000`, `107015291859043_10004_1772131172000`, `107015291859043_10004_1772148513000`, `107015291859043_10004_1772152145000`, `107015291859043_10004_1772154591000`, `107015291859043_10004_1772176499000`, `107015291859043_10004_1772177360000`, `107015291859043_10004_1772204011000`, `107015291859043_10004_1772214838000`
- `checkDriverName` — 2,276 distinct. e.g. `Marjondi Lungkang`, `Alwi Ariansyah`, `Muhammad Ilham`, `Arga Gaib`, `Sandi Kelana Pangaribuan`, `Pastian Mohlissi`, `Alwi`, `Fransiskus Mandagi`, `La Ode Muhammad Aswin`, `La Ode Nazal`, `Risat Alfian Lesnussa`, `Dedi Zulkarnain`
- `driverNo` — 2,311 distinct. e.g. `8240927104`, `8241002084`, `8241009127`, `8240708091`, `8241218057`, `8240122021`, `8241023045`, `8230421124`, `8240304020`, `8231121057`, `8240322123`, `8240927087`
- `truckId` — ? distinct. e.g. `7103991588669622657`, `7292458448363716866`, `7237175299467903112`, `7292458488561926408`, `7292458483830751493`, `7237172452340796547`, `7237172714300244103`, `7237171553182682240`, `6922135043045589275`, `7103991259836188037`, `7103988709699357060`, `7292459924758724872`

**Sample rows** (first 14 of 36 columns):

| FETCH_DATE | id | orgId | speed | checkDriverName | endLat | carrierName | areaName | endPrecision | difftime | startTime | endLng | driverNo | lat |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-03-21T08:30:30.750 | 107015291859043_10004_1772110463000 | 7190742966074476803 | 0.0 |  | 0.778727 | RIM |  | -1.0 | 2.0 | 1772110463000 | 128.037388 |  | 0.778852 |
| 2026-03-21T08:31:37.047 | 107015291859043_10004_1772112773000 | 7190742966074476803 | 0.0 |  | 0.717699 | RIM |  | -1.0 | 2.0 | 1772112773000 | 128.019495 |  | 0.717769 |
| 2026-03-21T08:31:54.313 | 107015291859043_10004_1772113778000 | 7190742966074476803 | 0.0 |  | 0.693851 | RIM |  | -1.0 | 14.0 | 1772113778000 | 127.980064 |  | 0.694366 |
| 2026-03-21T08:38:53.420 | 107015291859043_10004_1772130260000 | 7190742966074476803 | 0.0 |  | 0.701852 | RIM |  | -1.0 | 29.0 | 1772130260000 | 127.994408 |  | 0.700849 |
| 2026-03-21T08:39:11.760 | 107015291859043_10004_1772131172000 | 7190742966074476803 | 0.0 |  | 0.738165 | RIM |  | -1.0 | 2.0 | 1772131172000 | 128.034052 |  | 0.738091 |

<a id="fms-db-autofms-security-incident-kilometer"></a>

#### `autoFMS_SECURITY_INCIDENT_KILOMETER`

**Rows:** 4,168,389  |  **Columns:** 4

**Columns:** `Eventtypename` nvarchar(255), `id` nvarchar(100), `DIRECTION` nvarchar(50), `SectionKM` float

**Identifier vocabularies:**

- `id` — 4,168,389 distinct. e.g. `107015291859043_10004_1772131172000`, `107015291859043_10004_1772682625000`, `107015291859043_10004_1773379056000`, `107015291859043_10004_1773451354000`, `107015291859043_10004_1774002631000`, `107015291859043_10004_1774019903000`, `107015291859043_10004_1774077017000`, `107015291859043_10004_1774083752000`, `107015291859043_10004_1774096188000`, `107015291859043_10004_1774097133000`, `107015291859043_10004_1774123954000`, `107015291859043_10004_1774134738000`

**Sample rows**:

| Eventtypename | id | DIRECTION | SectionKM |
|---|---|---|---|
| Offline Event | 107015291859043_10004_1772131172000 | TOFU | 53.5 |
| Offline Event | 107015291859043_10004_1772682625000 | KR | 30.6 |
| Offline Event | 107015291859043_10004_1773379056000 | TOFU | 53.5 |
| Offline Event | 107015291859043_10004_1773451354000 | TOFU | 49.4 |
| Offline Event | 107015291859043_10004_1774002631000 | TOFU | 60.7 |

<a id="fms-db-auto-spfms-playback-track-data"></a>

#### `auto_spFMS_PLAYBACK_TRACK_DATA`

**Rows:** 1,701,102  |  **Columns:** 5

**Columns:** `imei` bigint, `time` bigint, `plateNumber` varchar(50), `SP_STATION` varchar(50), `SP_DISTANCE_M` int

**Identifier vocabularies:**

- `plateNumber` — 56 distinct. e.g. `W954`, `E821`, `E567`, `E613`, `X075`, `E819`, `E966`, `E985`, `E988`, `E855`, `E691`, `E863`

**Sample rows**:

| imei | time | plateNumber | SP_STATION | SP_DISTANCE_M |
|---|---|---|---|---|
| 131064219065687 | 1783609500000 | E814 |  |  |
| 131064219065687 | 1783615500000 | E814 |  |  |
| 131064219065687 | 1783611330000 | E814 |  |  |
| 131064219065687 | 1783610730000 | E814 |  |  |
| 131064219065687 | 1783611300000 | E814 |  |  |

<a id="fms-db-fms-intervention-event-data"></a>

#### `FMS_INTERVENTION_EVENT_DATA`

**Rows:** 1,267,116  |  **Columns:** 32  |  **FETCH_DATE:** 2026-04-07 16:43:10 → 2026-07-30 10:36:29

**Columns:** `FETCH_DATE` datetime, `checkDriverPhone` nvarchar(255), `riskLevel` float, `orgId` nvarchar(255), `riskId` nvarchar(255), `checkDriverName` nvarchar(255), `carrierName` nvarchar(255), `startTime` float, `mileage` nvarchar(255), `truckId` nvarchar(255), `eventId` nvarchar(255), `orgName` nvarchar(255), `duration` nvarchar(255), `voiceMsg` nvarchar(255), `dealUserName` nvarchar(255), `fileSize` nvarchar(255), `interveneTypeName` nvarchar(255), `statusName` nvarchar(255), `fileUrl` nvarchar(255), `interveneType` nvarchar(255), `sendTime` float, `status` nvarchar(255), `eventType` nvarchar(255), `intervener` nvarchar(255), `plateNumber` nvarchar(255), `totalDifftime` float, `interventionTypeName` nvarchar(255), `classTypeName` nvarchar(255), `eventTypeName` nvarchar(255), `imei` nvarchar(255), `endTime` nvarchar(255), `riskLevelName` nvarchar(255)

**Identifier vocabularies:**

- `checkDriverPhone` — 2,046 distinct. e.g. `8231020078`, `8241011091`, `8240302044`, `8230517011`, `8250908028`, `H240520435`, `8240320069`, `H240704785`, `H240512324`, `8231006002`, `8240304041`, `8240705004`
- `checkDriverName` — 2,035 distinct. e.g. `Fengki Suleman`, `Muhammad Rafiq`, `Rahmat Fadilah`, `Jabaru Kapitanhitu`, `Ryan Sahertian`, `Heru Indri`, `Reinaldi`, `Yudianto`, `Justan Friyono`, `Angga Barasi`, `Frederik Lumbaa`, `Nurhadi`
- `truckId` — 1,158 distinct. e.g. `7292459050464447238`, `6922135043683123464`, `7154829818062966530`, `7237172914452434049`, `7103989235295979909`, `6965230536554186888`, `6965254667492394368`, `7292458752098435329`, `7154830262390755080`, `6965080702090217608`, `7103988856198007168`, `6965275998850123909`
- `plateNumber` — 1,158 distinct. e.g. `N791`, `K544`, `R287`, `N502`, `N388`, `L726`, `SS083`, `N671`, `R280`, `L836`, `N291`, `L042`

**Sample rows** (first 14 of 32 columns):

| FETCH_DATE | checkDriverPhone | riskLevel | orgId | riskId | checkDriverName | carrierName | startTime | mileage | truckId | eventId | orgName | duration | voiceMsg |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-04-19T20:06:17.000 |  | 2.0 | 7190744540448426241 | 8783529426589322880 |  |  | 1776505575589.0 |  | 7292459050464447238 |  | RIM??? H ?? |  | Mengemudilah dengan aman. |
| 2026-04-20T00:06:07.443 |  | 1.0 | 7190742966074476803 | 8784153325853216643 |  |  | 1776524169288.0 |  | 6922135043683123464 |  | RIM??? G ?? |  | Fokuslah. Mengemudilah dengan aman. |
| 2026-04-20T00:06:07.443 |  | 1.0 | 7190742966074476803 | 8784153325853216643 |  |  | 1776524169288.0 |  | 6922135043683123464 |  | RIM??? G ?? |  | Mengemudilah dengan aman. |
| 2026-04-20T00:06:07.443 |  | 0.0 | 7190741266106286983 |  | Fengki Suleman |  | 1776524189000.0 |  | 7154829818062966530 | 107015291863388_10017_1776524189000_or… | RIM??? D ?? |  | Jangan mengemudi dengan kecepatan berl… |
| 2026-04-20T00:06:07.443 | 8231020078 | 1.0 | 7190740880934963462 | 8784150914598178689 | Muhammad Rafiq |  | 1776524097404.0 |  | 7237172914452434049 |  | RIM??? C ?? |  | Mengemudilah dengan aman. |

<a id="fms-db-fms-playback-track-24h"></a>

#### `FMS_PLAYBACK_TRACK_24H`

**Rows:** 1,111,436  |  **Columns:** 14

> Live GPS, 1-day window. 479 of 945 haul-truck devices report here.

**Columns:** `IMEI` varchar(32), `TS` bigint, `PLATE` varchar(32), `TRUCK_ID` varchar(40), `LAT` float, `LNG` float, `SPEED` float, `COURSE` float, `ACC` int, `LOC_TYPE` int, `DISTANCE` float, `INTERP` int, `RECEIVE_TIME` bigint, `UPDATED_AT` bigint

**Identifier vocabularies:**

- `PLATE` — 736 distinct. e.g. `K565`, `K566`, `K573`, `K579`, `K726`, `K583`, `K585`, `K536`, `K537`, `K596`, `K598`, `K699`
- `TRUCK_ID` — 736 distinct. e.g. `6922135043045589259`, `6922135043045589260`, `6922135043045589267`, `6922135043045589273`, `6922135043146252553`, `6922135043246915856`, `6922135043246915858`, `6922135043448242449`, `6922135043448242450`, `6922135043481796877`, `6922135043481796879`, `6922135043515351298`

**Coordinate extent:** `LAT` 0.455378 → 0.897833; `LNG` 127.880138 → 128.563213

**Sample rows**:

| IMEI | TS | PLATE | TRUCK_ID | LAT | LNG | SPEED | COURSE | ACC | LOC_TYPE | DISTANCE | INTERP | RECEIVE_TIME | UPDATED_AT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6922135043045589259 | 1785320850000 | K565 | 6922135043045589259 | 0.52964 | 127.899912 | 0.0 | 10.0 | 1 | 0 | 44182.0 | 1 | 1785320853163 | 1785323728602 |
| 6922135043045589259 | 1785323340000 | K565 | 6922135043045589259 | 0.529325 | 127.89976 | 10.0 | 250.0 | 1 | 0 | 3893.0 | 1 | 1785323343196 | 1785323728602 |
| 6922135043045589259 | 1785323360000 | K565 | 6922135043045589259 | 0.529218 | 127.899393 | 5.0 | 281.0 | 1 | 0 | 4339.0 | 1 | 1785323363180 | 1785323728602 |
| 6922135043045589259 | 1785323366000 | K565 | 6922135043045589259 | 0.529225 | 127.899353 | 0.0 | 279.0 | 1 | 0 | 452.0 | 1 | 1785323369103 | 1785323728602 |
| 6922135043045589259 | 1785323370000 | K565 | 6922135043045589259 | 0.529235 | 127.899323 | 5.0 | 286.0 | 1 | 0 | 352.0 | 1 | 1785323373210 | 1785323728602 |

<a id="fms-db-fms-gps-historical"></a>

#### `FMS_GPS_Historical`

**Rows:** 521,918  |  **Columns:** 15

> GPS with a PLATE column that DOES match haul trucks. 5-day retention window.

**Columns:** `IMEI` varchar(32), `TS` bigint, `PLATE` varchar(32), `TRUCK_ID` varchar(40), `LAT` float, `LNG` float, `SPEED` float, `COURSE` float, `ACC` int, `LOC_TYPE` int, `DISTANCE` float, `INTERP` int, `RECEIVE_TIME` bigint, `UPDATED_AT` bigint, `ARCHIVED_AT` bigint

**Identifier vocabularies:**

- `PLATE` — 696 distinct. e.g. `A843`, `A864`, `B280`, `B282`, `B284`, `B286`, `B287`, `B292`, `B293`, `B295`, `B296`, `B297`
- `TRUCK_ID` — 696 distinct. e.g. `6922135043045589259`, `6922135043045589262`, `6922135043045589264`, `6922135043045589267`, `6922135043045589271`, `6922135043045589273`, `6922135043146252553`, `6922135043246915856`, `6922135043246915858`, `6922135043448242449`, `6922135043448242450`, `6922135043548905735`

**Coordinate extent:** `LAT` 0.454042 → 0.8179133; `LNG` 127.862048 → 128.216675

**Sample rows** (first 14 of 15 columns):

| IMEI | TS | PLATE | TRUCK_ID | LAT | LNG | SPEED | COURSE | ACC | LOC_TYPE | DISTANCE | INTERP | RECEIVE_TIME | UPDATED_AT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6922135043045589259 | 1784360520000 | K565 | 6922135043045589259 | 0.7799 | 128.075532 | 11.0 | 222.0 | 1 | 0 | 3081433.0 | 1 | 1784360523900 | 1784363962961 |
| 6922135043045589259 | 1784360559000 | K565 | 6922135043045589259 | 0.778953 | 128.074473 | 22.0 | 253.0 | 1 | 0 | 16166.0 | 1 | 1784360561623 | 1784363962961 |
| 6922135043045589259 | 1784360566000 | K565 | 6922135043045589259 | 0.77893 | 128.074093 | 19.0 | 273.0 | 1 | 0 | 4237.0 | 1 | 1784360568630 | 1784363962961 |
| 6922135043045589259 | 1784360607000 | K565 | 6922135043045589259 | 0.778852 | 128.07294 | 14.0 | 243.0 | 1 | 0 | 13150.0 | 1 | 1784360609651 | 1784363962961 |
| 6922135043045589259 | 1784360610000 | K565 | 6922135043045589259 | 0.778775 | 128.072837 | 19.0 | 235.0 | 1 | 0 | 1431.0 | 1 | 1784360612915 | 1784363962961 |

<a id="fms-db-fms-playback-stay-data"></a>

#### `FMS_PLAYBACK_STAY_DATA`

**Rows:** 388,046  |  **Columns:** 43  |  **FETCH_DATE:** 2026-03-22 10:31:34 → 2026-07-30 12:10:53

> Stay events carrying speed, maxSpeed, limitSpeed, mileage and driver identity.

**Columns:** `FETCH_DATE` datetime, `id` nvarchar(50), `checkDriverPhone` nvarchar(255), `notes` nvarchar(255), `precision` float, `videos` nvarchar(255), `orgId` float, `speed` float, `checkDriverName` nvarchar(255), `endLat` float, `carrierName` nvarchar(255), `areaName` nvarchar(255), `endPrecision` float, `difftime` float, `pointNames` nvarchar(255), `startTime` float, `endLng` float, `driverNo` nvarchar(255), `lat` float, `limitSpeed` nvarchar(255), `mileage` float, `truckId` nvarchar(255), `imgs` nvarchar(255), `address` nvarchar(255), `orgName` nvarchar(255), `lng` float, `startAddress` nvarchar(255), `updateTime` float, `eventType` nvarchar(255), `maxSpeed` float, `plateNumber` nvarchar(255), `markerType` nvarchar(255), `driverId` nvarchar(255), `classTypeName` nvarchar(255), `createTime` float, `speedPercent` nvarchar(255), `eventTypeName` nvarchar(255), `imei` nvarchar(255), `driverName` nvarchar(255), `endTime` float, `markerRemark` nvarchar(255), `endAddress` nvarchar(255), `properties` nvarchar(255)

**Identifier vocabularies:**

- `id` — 388,050 distinct. e.g. `107015291859999_10009_1778400933000`, `107015291859999_10009_1778401748000`, `107015291859999_10009_1778402895000`, `107015291859999_10009_1778403147000`, `107015291859999_10009_1778404760000`, `107015291859999_10009_1778447866000`, `107015291859999_10009_1778448379000`, `107015291859999_10009_1778448660000`, `107015291859999_10009_1778455296000`, `107015291859999_10009_1778457483000`, `107015291859999_10009_1778461437000`, `107015291859999_10009_1778462453000`
- `driverNo` — 217 distinct. e.g. `8240201043`, `8240530027`, `8241031082`, `8240530029`, `8230629038`, `8241209053`, `8241028054`, `8240120057`, `8230704026`, `8240718095`, `8240718109`, `8241016028`
- `truckId` — 198 distinct. e.g. `6965254708328138880`, `6965307849656501640`, `6965301910186493312`, `7107580218260588673`, `6965297505127106697`, `7903985697848297350`, `7909775476602963462`, `6965401848505436935`, `6965297853724099971`, `6965317670233441672`, `7903986174858101509`, `7909775132737144326`
- `plateNumber` — 198 distinct. e.g. `SS074`, `SS027`, `SS042`, `SS095`, `SS040`, `SS203`, `SS125`, `SS008`, `SS039`, `SS020`, `SS207`, `SS129`
- `driverId` — 106 distinct. e.g. `2.05148e+018`, `2.04794e+018`, `1.87353e+018`, `1873526083484262400`, `2.05288e+018`, `2051477236439195648`, `1873525759717548032`, `2051477141652119552`, `1.87355e+018`, `2043845649333624832`, `2059426156779806720`, `1873535427059785728`
- `driverName` — 218 distinct. e.g. `FAHRUL UPARA`, `GUNTUR LA MANE`, `SAHARUDIN`, `IKRAM A. JAHUM`, `Heri Iswandi`, `BIELS MANUMPIL`, `ALVIAN ABDULLAH`, `AGUS ABDULAH`, `Hezron Lumamuly`, `FADRIL DANIAL`, `LA TUMBU`, `INDRAWAN DJA'U`

**Coordinate extent:** `lat` 0.445092 → 128.095887; `lng` 127.888718 → 128.100402

**Sample rows** (first 14 of 43 columns):

| FETCH_DATE | id | checkDriverPhone | notes | precision | videos | orgId | speed | checkDriverName | endLat | carrierName | areaName | endPrecision | difftime |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-05-12T15:04:50.257 | 107015291859999_10009_1778400933000 |  |  | -1.0 |  | 6.962944464e+18 | 0.0 |  | 0.48238 |  |  | -1.0 | 517.0 |
| 2026-05-12T15:04:50.257 | 107015291859999_10009_1778401748000 |  |  | -1.0 |  | 6.962944464e+18 | 0.0 |  | 0.478615 |  |  | -1.0 | 220.0 |
| 2026-05-12T15:04:50.257 | 107015291859999_10009_1778402895000 |  |  | -1.0 |  | 6.962944464e+18 | 0.0 |  | 0.479739 |  |  | -1.0 | 178.0 |
| 2026-05-12T15:04:50.257 | 107015291859999_10009_1778403147000 |  |  | -1.0 |  | 6.962944464e+18 | 0.0 |  | 0.480212 |  |  | -1.0 | 1144.0 |
| 2026-05-12T15:04:50.257 | 107015291859999_10009_1778404760000 |  |  | -1.0 |  | 6.962944464e+18 | 0.0 |  | 0.482281 |  |  | -1.0 | 42614.0 |

<a id="fms-db-fms-risk-data"></a>

#### `FMS_RISK_DATA`

**Rows:** 316,302  |  **Columns:** 19  |  **FETCH_DATE:** 2026-04-06 15:48:11 → 2026-07-30 10:33:58

**Columns:** `FETCH_DATE` datetime, `checkDriverPhone` nvarchar(255), `truckId` nvarchar(255), `orgName` nvarchar(255), `riskLevel` float, `interveneTypeNames` nvarchar(255), `eventCount` float, `plateNumber` nvarchar(255), `orgId` nvarchar(255), `riskId` nvarchar(255), `checkDriverName` nvarchar(255), `carrierName` nvarchar(255), `createTime` nvarchar(255), `startTime` float, `endTime` float, `riskLevelName` nvarchar(255), `eventTypesName` nvarchar(255), `mileage` float, `status` float

**Identifier vocabularies:**

- `truckId` — 1,135 distinct. e.g. `7103989736532085122`, `7909775461067260681`, `6965079577748309384`, `7103991359861950854`, `7103989847228156289`, `7103989047424714113`, `6965234481951410307`, `7154830115690777600`, `6965234952619428608`, `7014034532701832712`, `7154830318695091974`, `7292459469123095305`
- `plateNumber` — 1,135 distinct. e.g. `N414`, `SS124`, `L951`, `N340`, `N346`, `N466`, `L606`, `R279`, `L607`, `N188`, `R321`, `N705`
- `checkDriverName` — 1,733 distinct. e.g. ``, `Rusman Mahmud`, `Imam Rialdy Solihin`, `Bagus Setiawan`, `Paska Maluda`, `Markus Bongga Upa'`, `Nyoman Siswanto`, `Arwin Aswi`, `Refelan Buas`, `Muhammad Saud`, `Pastian Mohlissi`, `Indrawan Herman Maradesa`

**Sample rows** (first 14 of 19 columns):

| FETCH_DATE | checkDriverPhone | truckId | orgName | riskLevel | interveneTypeNames | eventCount | plateNumber | orgId | riskId | checkDriverName | carrierName | createTime | startTime |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-04-06T15:57:10.257 |  | 7103989736532085122 | RIM??? G ?? | 2.0 | Overspeed in the area | 9.0 | N414 | 7190742966074476803 | 8728088746446818177 |  | RIM | 2026-03-30 06:48:35 | 1774853314643.0 |
| 2026-04-06T15:57:10.257 |  | 7909775461067260681 | ???? HRM | 3.0 | Close EYE | 1.0 | SS124 | 7031941738457596167 | 8728088941465176071 |  | RIM | 2026-03-30 06:48:40 | 1774853320378.0 |
| 2026-04-06T15:57:10.257 |  | 6965079577748309384 | RIM??? D ?? | 2.0 | LookAround | 2.0 | L951 | 7190741266106286983 | 8728089136215099393 |  | RIM | 2026-03-30 06:48:46 | 1774853326252.0 |
| 2026-04-06T15:57:10.257 |  | 7103991359861950854 | RIM??? H ?? | 2.0 | Overspeed in the area | 2.0 | N340 | 7190744540448426241 | 8728089455384856584 |  | RIM | 2026-03-30 06:48:56 | 1774853335760.0 |
| 2026-04-06T15:57:10.257 |  | 7103989847228156289 | RIM??? H ?? | 2.0 | Overspeed in the area | 1.0 | N346 | 7190744540448426241 | 8728089579636918274 |  | RIM | 2026-03-30 06:48:59 | 1774853339463.0 |

<a id="fms-db-fms-geofence-visits"></a>

#### `FMS_GEOFENCE_VISITS`

**Rows:** 59,445  |  **Columns:** 17

> Enter/exit timestamps and DURATION_SEC per unit at typed geofences, with UNIT_TYPE naming haul trucks explicitly. Measured dwell at pits and weighbridges.

**Columns:** `EVENT_ID` varchar(36), `UNIT_ID` varchar(40), `UNIT_TYPE` varchar(40), `ORG_NAME` nvarchar(200), `GEOFENCE_ID` nvarchar(20), `GEOFENCE_NAME` nvarchar(200), `GEOFENCE_TYPE` varchar(40), `ENTER_TS` bigint, `EXIT_TS` bigint, `DURATION_SEC` int, `ENTER_LAT` float, `ENTER_LNG` float, `EXIT_LAT` float, `EXIT_LNG` float, `STATUS` varchar(12), `SOURCE` varchar(20), `CREATED_AT` bigint

**Identifier vocabularies:**

- `EVENT_ID` — 59,447 distinct. e.g. `f07086d6-add0-433a-9d20-17f4c59ab0fa`, `f7b012df-1e75-4278-8b3a-63e8617bc23c`, `7cac52bd-4e19-44f9-acce-29f7d70881d2`, `7dd859f6-fc18-40f8-b59d-fc4e08b24efe`, `9b885ad2-c48e-4bed-8092-447c6f753b12`, `07a2596b-67eb-4bca-9af8-40267732a975`, `7a8751b1-06a4-4710-9c37-44b441619920`, `0f0e60dc-4998-4561-b47a-39de9150ffb0`, `fbaac5d2-ec41-496d-b223-1f37a724ff25`, `c0d923d2-6878-4e28-be2f-0271c0b2debe`, `3131fc50-fda7-4b68-b1a5-8aadd1955181`, `9fde2e5e-5a83-4969-976d-886a9a3eff0a`
- `UNIT_ID` — 899 distinct. e.g. `A843`, `A844`, `A864`, `A865`, `A867`, `A875`, `B279`, `B280`, `B282`, `B284`, `B286`, `B287`
- `UNIT_TYPE` — 11 distinct. e.g. `LV`, `Service Truck`, `Compactor`, ``, `Haul Truck`, `Water Truck`, `Fuel Truck`, `Excavator`, `Grader`, `Light Vehicle`, `Loader`
- `GEOFENCE_ID` — 282 distinct. e.g. `154060c9`, `1b1fc35c`, `2224ef93`, `2e938c89`, `85d11afa`, `a2b62513`, `pos_012c8799`, `pos_0165e091`, `pos_01f9795a`, `pos_0238d9c1`, `pos_044ffd2b`, `pos_04ae53db`

**Sample rows** (first 14 of 17 columns):

| EVENT_ID | UNIT_ID | UNIT_TYPE | ORG_NAME | GEOFENCE_ID | GEOFENCE_NAME | GEOFENCE_TYPE | ENTER_TS | EXIT_TS | DURATION_SEC | ENTER_LAT | ENTER_LNG | EXIT_LAT | EXIT_LNG |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 00014d7f-f897-4361-8d1f-f9b16b2df0d2 | N469 | Haul Truck | RIM??? G ?? | a2b62513 | TF | pit | 1785361980000 | 1785363990000 | 2010 | 0.801267 | 128.027037 | 0.80481 | 128.022368 |
| 00022053-d1ba-4b6a-a4c1-23f2ea3a31e3 | R283 | Haul Truck | RIM??? D ?? | wb_wb_iwip_t12 | WB_IWIP_T12 | weighbridge | 1785211696000 | 1785211749000 | 53 | 0.508318 | 127.898747 | 0.506115 | 127.898498 |
| 00024379-7809-4388-96fb-36ecf23c7367 | R922 | Haul Truck | RIM??? E ?? | 2224ef93 | KR | pit | 1785050160000 | 1785051202000 | 1042 | 0.679645 | 127.975703 | 0.648738 | 127.973213 |
| 0004f26a-e851-453b-ac9a-f5444d306cbd | N417 | Haul Truck | RIM??? H ?? | 2224ef93 | KR | pit | 1785247028000 | 1785252030000 | 5002 | 0.649862 | 127.972642 | 0.683093 | 127.97617 |
| 00056077-e870-453e-bd05-82cde82dea17 | SS008 | Water Truck | ???? LOGISTICS | 2e938c89 | CBB | pit | 1785310961000 | 1785311741000 | 780 | 0.517541 | 127.940711 | 0.517541 | 127.940711 |

<a id="fms-db-fms-congestion-seg"></a>

#### `FMS_CONGESTION_SEG`

**Rows:** 35,156  |  **Columns:** 9

> Per segment, per hour, per direction: speed sum, fix count, truck count and traverse time. Segment-level speed, already aggregated.

**Columns:** `HOUR_TS` bigint, `SEG_ID` nvarchar(40), `DIR` char(4), `SUM_SPD` float, `FIX_N` int, `TRUCK_N` int, `UPDATED_AT` bigint, `SUM_TRAV_MS` float, `TRAV_N` int

**Identifier vocabularies:**

- `SEG_ID` — 95 distinct. e.g. `BLB KM17-18`, `BLB KM18-19`, `BLB KM19-20`, `BLB KM3-4`, `BLB KM5-6`, `BLB KM6-7`, `BLB KM7-8`, `BLB KM8-9`, `BLB KM9-10`, `CBB KM10-11`, `CBB KM11-12`, `CBB KM12-13`

**Sample rows**:

| HOUR_TS | SEG_ID | DIR | SUM_SPD | FIX_N | TRUCK_N | UPDATED_AT | SUM_TRAV_MS | TRAV_N |
|---|---|---|---|---|---|---|---|---|
| 1784077200000 | BLB KM17-18 | down | 1230.0 | 91 | 5 | 1784510901345 | 860000.0 | 4 |
| 1784077200000 | BLB KM17-18 | up   | 697.0 | 43 | 4 | 1784510901345 | 0.0 | 0 |
| 1784077200000 | BLB KM18-19 | down | 1404.0 | 108 | 5 | 1784510901345 | 695000.0 | 3 |
| 1784077200000 | BLB KM18-19 | up   | 740.0 | 57 | 5 | 1784510901345 | 0.0 | 0 |
| 1784077200000 | BLB KM19-20 | down | 659.0 | 41 | 2 | 1784510901345 | 0.0 | 0 |

<a id="fms-db-res-employees"></a>

#### `RES_EMPLOYEES`

**Rows:** 8,958  |  **Columns:** 9

> Operator register: employee ID, contractor, division, job title, grade.

**Columns:** `FULL_NAME` nvarchar(255), `GENDER` nvarchar(255), `ORIGIN` nvarchar(255), `ORIGIN_CLASS` nvarchar(255), `EMPLOYEE_ID` float, `CONTRACTOR` nvarchar(255), `DIVISION` nvarchar(255), `JOB_TITLE` nvarchar(255), `GRADE` float

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-fms-geofences"></a>

#### `FMS_GEOFENCES`

**Rows:** 3,490  |  **Columns:** 17

> 3,490 geofence polygons with LATLNGS, centre, type, PIT_ID and PILE_ID.

**Columns:** `GF_ID` nvarchar(20), `NAME` nvarchar(200), `TYPE` nvarchar(50), `SHAPE` nvarchar(20), `LATLNGS` nvarchar(-1), `CENTER_LAT` float, `CENTER_LNG` float, `RADIUS` float, `PIT_ID` nvarchar(50), `PILE_ID` nvarchar(100), `TOS_STATUS` nvarchar(50), `TOS_AREA` nvarchar(100), `TOS_PIT` nvarchar(50), `ELEVATIONS` nvarchar(-1), `SURVEY_DATE` nvarchar(50), `CREATED` bigint, `CREATED_BY` nvarchar(100)

**Identifier vocabularies:**

- `GF_ID` — 3,490 distinct. e.g. `154060c9`, `1b1fc35c`, `2224ef93`, `2e938c89`, `557c7057`, `85d11afa`, `a2b62513`, `pos_0002230b`, `pos_0008ca18`, `pos_003fb586`, `pos_0042cd84`, `pos_0064f1af`
- `PIT_ID` — 5 distinct. e.g. ``, `tf`, `cbb`, `blb`, `kr`
- `PILE_ID` — 3,170 distinct. e.g. ``, `M3_POS12_007`, `M1_POS12_018`, `ABM.451`, `LGS.CBB124`, `LGS.KR204`, `LGS.KR194`, `M2_POS12_009`, `LGS.BLB48`, `ABM.467`, `ABM.468`, `ACM.660`

**Sample rows** (first 14 of 17 columns):

| GF_ID | NAME | TYPE | SHAPE | LATLNGS | CENTER_LAT | CENTER_LNG | RADIUS | PIT_ID | PILE_ID | TOS_STATUS | TOS_AREA | TOS_PIT | ELEVATIONS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 154060c9 | BLB | pit | polygon | [[0.5437292501612401, 127.971453666687… | 0.544232369 | 127.9714936224 |  | blb |  |  |  |  |  |
| 1b1fc35c | KM 15 | water | circle |  | 0.5089639244 | 127.90353477 | 15.7473266505 |  |  |  | KR | WF-HR15 |  |
| 2224ef93 | KR | pit | polygon | [[0.672296355154009, 127.9667758941650… | 0.668477151 | 127.9763031006 | 1710.6506851987 | kr |  |  |  |  |  |
| 2e938c89 | CBB | pit | polygon | [[0.5444158647114278, 127.944717407226… | 0.5203757264 | 127.9370012283 |  | cbb |  |  |  |  |  |
| 557c7057 | TOS12 | loading | point |  | 0.5255983067 | 127.9320573807 |  |  |  |  |  |  |  |

<a id="fms-db-radio-reprogram-track"></a>

#### `RADIO_REPROGRAM_TRACK`

**Rows:** 3,478  |  **Columns:** 21

**Columns:** `No` float, `CONTRACTOR` nvarchar(255), `AREA` nvarchar(255), `DEPARTMENT` nvarchar(255), `EQUIPMENT_TYPE` nvarchar(255), `EQUIPMENT_ID` nvarchar(255), `RADIO_TYPE` nvarchar(255), `BRAND` nvarchar(255), `MODEL` nvarchar(255), `SERIAL_NO` nvarchar(255), `IS_REPROGRAMMABLE` nvarchar(255), `REPROGRAM_STATUS` nvarchar(255), `REPROGRAM_DATE` nvarchar(255), `TECHNICIAN` nvarchar(255), `SUB_TEAM` nvarchar(255), `NAME_USER` nvarchar(255), `POSITION` nvarchar(255), `RADIO_ID` nvarchar(255), `REMARKS` nvarchar(255), `STATUS_RAW` nvarchar(255), `SOURCE_FILE` nvarchar(255)

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-fms-tos-status"></a>

#### `FMS_TOS_STATUS`

**Rows:** 3,404  |  **Columns:** 14

**Columns:** `UPDATE_DATE` datetime, `OBJECTID` bigint, `GLOBALID` nvarchar(50), `EDIT_DATE` datetime, `PILE_ID` nvarchar(50), `STOCK_AREA` nvarchar(50), `OLD_PILE` nvarchar(50), `STOCKPILE_TEAM` nvarchar(50), `DATE` date, `STATUS` nvarchar(50), `GEOM` geography(-1), `FMS_UPDATED_BY` nvarchar(100), `FMS_UPDATED_AT` datetime, `FMS_PREV_STATUS` nvarchar(100)

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-fms-tms-token"></a>

#### `FMS_TMS_TOKEN`

**Rows:** 2,927  |  **Columns:** 3

**Columns:** `DATETIME` datetime, `FMS_USER` nvarchar(50), `FMS_TOKEN` nvarchar(500)

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-fms-equipments"></a>

#### `FMS_EQUIPMENTS`

**Rows:** 1,411  |  **Columns:** 7  |  **FETCH_DATE:** 2026-03-22 15:07:47 → 2026-07-29 14:44:32

> The equipment register that bridges the two databases: plateNumber matches weighbridge TRUCK_ID, truckId is the GPS device serial.

**Columns:** `FETCH_DATE` datetime, `truckId` nvarchar(50), `orgName` nvarchar(50), `plateNumber` nvarchar(50), `orgId` bigint, `imei` bigint, `active` nvarchar(50)

**Identifier vocabularies:**

- `truckId` — 1,411 distinct. e.g. `6916297240046994306`, `6916344653700925698`, `6921009760640961159`, `6922135043012034832`, `6922135043045589259`, `6922135043045589260`, `6922135043045589262`, `6922135043045589263`, `6922135043045589264`, `6922135043045589265`, `6922135043045589267`, `6922135043045589271`
- `plateNumber` — 1,411 distinct. e.g. `K977`, `K984`, `K523`, `K562`, `K565`, `K566`, `K568`, `K569`, `K570`, `K571`, `K573`, `K577`

**Sample rows**:

| FETCH_DATE | truckId | orgName | plateNumber | orgId | imei | active |
|---|---|---|---|---|---|---|
| 2026-07-29T14:44:32.497 | 6916297240046994306 | RIM??? E ?? | K977 | 7190741736405205894 | 107015291859617 | YES |
| 2026-07-29T14:44:32.497 | 6916344653700925698 | RIM??? A ?? | K984 | 7190739726259849477 | 131064219064862 | YES |
| 2026-05-14T14:44:30.313 | 6921009760640961159 | RIM??? C ?? | K523 | 7190740880934963462 | 131064219065221 | NO |
| 2026-04-12T14:44:23.520 | 6922135043012034832 | RIM??? B ?? | K562 | 7190740352016450440 | 107015291860264 | NO |
| 2026-07-29T14:44:32.497 | 6922135043045589259 | RIM??? E ?? | K565 | 7190741736405205894 | 131064219064892 | YES |

<a id="fms-db-wt-daily-plan"></a>

#### `WT_DAILY_PLAN`

**Rows:** 1,241  |  **Columns:** 10

**Columns:** `ID` int, `Shift_Date` date, `Vehicle_Number` varchar(20), `Region` varchar(10), `KM_From` int, `KM_To` int, `Primary_WF` varchar(50), `Target_Refills` int, `Created_Date` datetime, `Breakdown` varchar(3)

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-fms-unit-installed"></a>

#### `FMS_UNIT_INSTALLED`

**Rows:** 1,194  |  **Columns:** 4

> Which plates have a telematics device fitted and when it first reported.

**Columns:** `PLATE` nvarchar(60), `ORG` nvarchar(120), `FIRST_TS` bigint, `SEEDED` bit

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-fms-truck-assignments"></a>

#### `FMS_TRUCK_ASSIGNMENTS`

**Rows:** 408  |  **Columns:** 10

> Truck to EXCAVATOR assignment per shift, with pile, pit, material and destination. Loader identity in weighbridge truck format.

**Columns:** `PLAN_DATE` date, `SHIFT` float, `TRUCK` nvarchar(50), `PILE` nvarchar(100), `EXCAVATOR` nvarchar(100), `PIT` nvarchar(50), `MATERIAL` nvarchar(50), `DESTINATION` nvarchar(200), `IMPORTED_AT` datetime, `IMPORTED_BY` nvarchar(100)

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-fms-haul-cycles"></a>

#### `FMS_HAUL_CYCLES`

**Rows:** 288  |  **Columns:** 10  |  **PLAN_DATE:** 2026-06-26 → 2026-07-24

> Completed haul cycles with truck plate, excavator and dump timestamp.

**Columns:** `CYCLE_ID` int, `TRUCK_PLATE` nvarchar(50), `PLAN_DATE` date, `SHIFT` float, `PIT` nvarchar(50), `TOS_PILE` nvarchar(100), `EXCAVATOR` nvarchar(100), `DESTINATION` nvarchar(200), `MATERIAL` nvarchar(100), `DUMP_TS` datetime

**Identifier vocabularies:**

- `TRUCK_PLATE` — 59 distinct. e.g. `B279`, `B284`, `B287`, `B537`, `K536`, `K585`, `K605`, `K618`, `K802`, `K901`, `K982`, `L618`
- `EXCAVATOR` — 10 distinct. e.g. ``, `E021`, `E042`, `E049`, `E270`, `E295`, `E299`, `E692`, `M267`, `W659`

**Sample rows**:

| CYCLE_ID | TRUCK_PLATE | PLAN_DATE | SHIFT | PIT | TOS_PILE | EXCAVATOR | DESTINATION | MATERIAL | DUMP_TS |
|---|---|---|---|---|---|---|---|---|---|
| 1 | B279 | 2026-06-26T00:00:00.000 | 2.0 |  |  | E021 |  | Waste | 2026-06-26T22:40:39.917 |
| 2 | B279 | 2026-06-26T00:00:00.000 | 2.0 |  |  | E021 |  | Waste | 2026-06-26T22:40:56.183 |
| 3 | B279 | 2026-06-26T00:00:00.000 | 2.0 |  |  | E021 |  | Waste | 2026-06-26T22:42:11.293 |
| 4 | B279 | 2026-06-26T00:00:00.000 | 2.0 |  |  | E021 |  | Waste | 2026-06-26T22:42:45.750 |
| 5 | B279 | 2026-06-27T00:00:00.000 | 1.0 | BLB |  | M267 | FENI A | SAP | 2026-06-27T08:28:04.793 |

<a id="fms-db-fms-quality-dispatch"></a>

#### `FMS_QUALITY_DISPATCH`

**Rows:** 258  |  **Columns:** 21  |  **PLAN_DATE:** 2026-06-23 → 2026-07-22

> Quality-driven dispatch records.

**Columns:** `SRC_ID` int, `PLAN_DATE` date, `SHIFT` float, `PIT` nvarchar(50), `CONTRACTOR` nvarchar(100), `TOS_PILE` nvarchar(100), `CATEGORY` nvarchar(50), `CATEGORY_2` nvarchar(50), `WMT` float, `Ni_TOS` float, `Ni_BM` float, `Ni_Plan` float, `DOME` nvarchar(100), `DESTINATION` nvarchar(200), `STATUS` nvarchar(50), `EXCA` nvarchar(100), `DT` nvarchar(100), `HAUL_CONFIDENCE` nvarchar(100), `TYPE` nvarchar(50), `IMPORTED_AT` datetime, `IMPORTED_BY` nvarchar(100)

**Sample rows** (first 14 of 21 columns):

| SRC_ID | PLAN_DATE | SHIFT | PIT | CONTRACTOR | TOS_PILE | CATEGORY | CATEGORY_2 | WMT | Ni_TOS | Ni_BM | Ni_Plan | DOME | DESTINATION |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 89718 | 2026-06-24T00:00:00.000 | 1.0 | BLB | RIM | BLB.G.6921 | HGS | ACM | 5450.0 | 1.6372280702 | 1.428839294 | 1.5070908519 | ACM.685 | POS 14 |
| 89719 | 2026-06-24T00:00:00.000 | 1.0 | BLB | RIM | BLB.G.6974 | HGS | ABM | 4150.0 | 1.7734 | 1.6259968447 | 1.6746214968 | ABM.472 | POS 14 |
| 89720 | 2026-06-24T00:00:00.000 | 1.0 | BLB | RIM | BLB.G.6920 | HGS | ADM | 2850.0 | 1.5080520231 | 1.3663864553 | 1.4140523601 | BLB-A.258 | FENI A (3-4) |
| 89721 | 2026-06-24T00:00:00.000 | 1.0 | BLB | RIM | BLB.G.6928 | WCO | WCO | 2835.0 | 1.52 | 1.1756895894 | 1.3215722937 | BLB-A.259 | FENI A (3-4) |
| 89722 | 2026-06-24T00:00:00.000 | 1.0 | KRENE | RIM | KRENE.I.3268 | HGS | ADM | 500.0 | 1.639 | 1.5453675434 | 1.5026369886 | ACM.648 | POS 12  |

<a id="fms-db-fms-dispatch-plan"></a>

#### `FMS_DISPATCH_PLAN`

**Rows:** 105  |  **Columns:** 16  |  **PLAN_DATE:** 2026-06-23 → 2026-07-22

> Dispatch plan records.

**Columns:** `SRC_ID` int, `CONTRACTOR` nvarchar(100), `PLAN_DATE` date, `SHIFT` int, `TYPE` nvarchar(50), `MATERIAL` nvarchar(50), `COMPANY` nvarchar(50), `DISPATCH_ZONE` nvarchar(200), `ORIGIN` nvarchar(100), `DESTINATION` nvarchar(100), `BUYER` nvarchar(100), `NB_DT` float, `TF` float, `PRODUCTIVITY_TARGET` float, `IMPORTED_AT` datetime, `IMPORTED_BY` nvarchar(100)

**Sample rows** (first 14 of 16 columns):

| SRC_ID | CONTRACTOR | PLAN_DATE | SHIFT | TYPE | MATERIAL | COMPANY | DISPATCH_ZONE | ORIGIN | DESTINATION | BUYER | NB_DT | TF | PRODUCTIVITY_TARGET |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 57308 | RIM | 2026-06-23T00:00:00.000 | 1 | HAULAGE | SAP | WBN | KRENE to KM 27 | KRENE | POS 12 |  | 15.0 | 48.0 | 4.0 |
| 57309 | RIM | 2026-06-23T00:00:00.000 | 1 | DIRECT | SAP | WBN | TOFU to FENI A | TF | FENI A |  | 25.0 | 50.0 | 1.1 |
| 57310 | RIM | 2026-06-23T00:00:00.000 | 1 | DIRECT | SAP | WBN | BLB to FENI A | BLB | FENI A |  | 15.0 | 45.0 | 3.1 |
| 57311 | RIM | 2026-06-23T00:00:00.000 | 1 | HAULAGE | SAP | WBN | BLB to POS 14 | BLB | POS 14 |  | 20.0 | 45.0 | 4.0 |
| 57312 | RIM | 2026-06-23T00:00:00.000 | 2 | HAULAGE | SAP | WBN | KRENE to KM 27 | KRENE | POS 12 |  | 15.0 | 48.0 | 4.0 |

<a id="fms-db-shp-sed-pond"></a>

#### `SHP_SED_POND`

**Rows:** 91  |  **Columns:** 4

**Columns:** `STATION` varchar(50), `LAT_CALC` varchar(-1), `LONG_CALC` varchar(-1), `GEOM` geography(-1)

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-fms-roadmap"></a>

#### `FMS_ROADMAP`

**Rows:** 87  |  **Columns:** 21

**Columns:** `ID` nvarchar(64), `TITLE` nvarchar(300), `DETAIL` nvarchar(-1), `STATUS` nvarchar(20), `CATEGORY` nvarchar(80), `TARGET` nvarchar(40), `VERSION` nvarchar(40), `SORT` int, `TS` bigint, `UPDATED_BY` nvarchar(80), `UPDATED_AT` bigint, `START_DATE` nvarchar(10), `END_DATE` nvarchar(10), `ITEM_TYPE` nvarchar(20), `PHASE` nvarchar(80), `OWNER` nvarchar(120), `PRIORITY` nvarchar(10), `COVERAGE` nvarchar(20), `ACCEPTANCE` nvarchar(-1), `DEPENDENCIES` nvarchar(-1), `SOURCE_REF` nvarchar(500)

**Identifier vocabularies:**

- `ID` — 87 distinct. e.g. `rm_fg01_01`, `rm_fg01_02`, `rm_fg01_03`, `rm_fg01_04`, `rm_fg01_05`, `rm_fg01_06`, `rm_fg01_07`, `rm_fg01_08`, `rm_fg01_09`, `rm_fg01_10`, `rm_fg01_11`, `rm_fg01_12`

**Sample rows** (first 14 of 21 columns):

| ID | TITLE | DETAIL | STATUS | CATEGORY | TARGET | VERSION | SORT | TS | UPDATED_BY | UPDATED_AT | START_DATE | END_DATE | ITEM_TYPE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rm_fg01_01 | Haul cycle state model | Configurable sequential states: Travel… | planned | Haul Cycle |  |  | 101 | 1786320000000 | slicing | 1786320000000 | 2026-08-10 | 2026-08-22 | task |
| rm_fg01_02 | Sequential enforcement & mandatory wei… | No advance to Dumping until weigh/samp… | planned | Haul Cycle |  |  | 102 | 1786665600000 | slicing | 1786665600000 | 2026-08-14 | 2026-08-26 | task |
| rm_fg01_03 | Action events capture | Arrival, first bucket, full, departure… | planned | Haul Cycle |  |  | 103 | 1787011200000 | slicing | 1787011200000 | 2026-08-18 | 2026-08-30 | task |
| rm_fg01_04 | Automatic event detection | Dynamic geofences on loading units (fo… | shipped | Haul Cycle |  |  | 104 | 1787356800000 | slicing | 1787356800000 | 2026-08-22 | 2026-09-03 | task |
| rm_fg01_05 | Manual event capture | Operator (OUI) and dispatcher manual t… | planned | Haul Cycle |  |  | 105 | 1787702400000 | slicing | 1787702400000 | 2026-08-26 | 2026-09-07 | task |

<a id="fms-db-safety-dplan"></a>

#### `SAFETY_DPLAN`

**Rows:** 80  |  **Columns:** 9

**Columns:** `Date` datetime, `Shift` nvarchar(255), `Dispatcher` nvarchar(255), `ID` float, `Group 1` nvarchar(255), `Group 2` nvarchar(255), `Group 3` nvarchar(255), `Group 4` nvarchar(255), `Date Uploaded` datetime

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-lv-plan"></a>

#### `LV_PLAN`

**Rows:** 62  |  **Columns:** 7

**Columns:** `Shift_Date` date, `Shift` varchar(10), `Vehicle_Number` varchar(50), `Region` varchar(20), `KM_From` decimal, `KM_To` decimal, `Date_Uploaded` datetime2

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-lv-info"></a>

#### `LV_INFO`

**Rows:** 57  |  **Columns:** 6

**Columns:** `Vehicle_Number` varchar(50), `Divisi` varchar(100), `Department` varchar(100), `Driver_DS` varchar(200), `Driver_NS` varchar(200), `Work_Location` varchar(200)

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-fms-geofence-alerts"></a>

#### `FMS_GEOFENCE_ALERTS`

**Rows:** 46  |  **Columns:** 29

**Columns:** `ALERT_ID` varchar(36), `VISIT_EVENT_ID` varchar(36), `RULE_ID` varchar(36), `UNIT_ID` varchar(40), `GEOFENCE_ID` nvarchar(20), `GEOFENCE_NAME` nvarchar(200), `SEVERITY` varchar(12), `ENTER_TS` bigint, `EXIT_TS` bigint, `ENTER_LAT` float, `ENTER_LNG` float, `EXIT_LAT` float, `EXIT_LNG` float, `STATUS` varchar(20), `CREATED_AT` bigint, `EMAIL_SENT` bit, `ESCALATED_AT` bigint, `ACK_AT` bigint, `ACK_BY` nvarchar(100), `VERIFICATION_RESULT` nvarchar(80), `ASSIGNED_DRIVER` nvarchar(160), `ACTUAL_DRIVER` nvarchar(160), `ACTION_TAKEN` nvarchar(500), `COMMENT` nvarchar(1000), `CLOSED_AT` bigint, `CLOSED_BY` nvarchar(100), `EMAIL_RECIPIENTS` nvarchar(1000), `ESCALATION_RECIPIENTS` nvarchar(1000), `EMAIL_CC` nvarchar(1000)

**Identifier vocabularies:**

- `ALERT_ID` — 46 distinct. e.g. `cde8bb34-72eb-49e3-b3b8-7e9cba59fd7f`, `0c2d344a-feb7-4846-be17-4741b102f309`, `dfeae14d-1ce2-41cb-9e56-853a10aebb26`, `f30a76b7-7bb8-4d10-a8a7-6cc7dd9695e0`, `f05091dd-6e10-4118-b8b7-f62201edcb9a`, `2bbc9710-a65c-4739-a2a1-462be4fbce52`, `1efd18d8-5378-42fe-9f63-2ef01ed784a4`, `c89bd223-74ed-4c11-8193-262f7397bad1`, `a4034d07-7d38-4936-97ad-cca714f53c79`, `110942a1-a2c0-4f5b-926e-a8e4b0df1731`, `ae8ab35d-d0d6-4a6c-a28d-d6bd522a7c9b`, `8ef67de0-b07d-4a04-a38b-b89c91d5e35b`
- `VISIT_EVENT_ID` — 46 distinct. e.g. `01df9ee6-270f-4392-a06e-7f476fb0d508`, `023b8243-8cca-43ae-a157-314ea371f06d`, `06bcb8d2-4b67-45eb-ad8a-52c20d029fb3`, `0be11193-aeeb-4a74-b317-56da1d3426be`, `1594f939-0204-42c4-88d5-8cf2728bde4b`, `18808a59-5909-47c9-9b93-d78b59bce775`, `1c1776bc-88dc-4a1c-8639-11883bde941f`, `1e8ae196-7659-4c24-a450-fc417089cf22`, `22781297-9e17-493a-a7c0-62b5a7d5bbbe`, `23a740cb-8e5b-45dc-a321-c0e3b503c78d`, `253c7248-3a2f-41d2-a019-b09e1fa5fb02`, `25793b45-a0b3-4d81-8c79-4e1491e3f248`
- `RULE_ID` — 1 distinct. e.g. `d93065c3-9ff2-439b-bbdb-be609204877d`
- `UNIT_ID` — 11 distinct. e.g. `WBN-LV-C25`, `WBN-LV-C30`, `WBN-LV-C36`, `WBN-LV-C40`, `WBN-LV-C44`, `WBN-LV-C46`, `WBN-LV-C51`, `WBN-LV-C88`, `WBN-LV-M57`, `WBN-LV-M81`, `WBN-LV-M92`
- `GEOFENCE_ID` — 1 distinct. e.g. `85d11afa`
- `ASSIGNED_DRIVER` — 11 distinct. e.g. ``, `Alvian`, `Arfandi Pane`, `Julialdri`, `Mikael Jiofani Momole`, `Muh. Agung`, `Rahmat Djalal`, `Ralf Cornelius Johanis Sorongan`, `Romario`, `Stevly`, `Thosan`

**Sample rows** (first 14 of 29 columns):

| ALERT_ID | VISIT_EVENT_ID | RULE_ID | UNIT_ID | GEOFENCE_ID | GEOFENCE_NAME | SEVERITY | ENTER_TS | EXIT_TS | ENTER_LAT | ENTER_LNG | EXIT_LAT | EXIT_LNG | STATUS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0174f7ab-f2e8-4139-a95c-fa28bb61a366 | b1e66aa2-e639-4eef-b474-fa14486b7217 | d93065c3-9ff2-439b-bbdb-be609204877d | WBN-LV-C25 | 85d11afa | Village | CRITICAL | 1785325814000 | 1785326677000 | 0.471605 | 127.929652 | 0.470887 | 127.91363 | OPEN |
| 01800592-d7fa-43ca-88c5-3c09bfbabc89 | 6971c5d5-0258-46a8-9c13-0e04bfdf178b | d93065c3-9ff2-439b-bbdb-be609204877d | WBN-LV-M57 | 85d11afa | Village | CRITICAL | 1784996790000 | 1785015795000 | 0.468455 | 127.939258 | 0.469138 | 127.939537 | OPEN |
| 03bf6b6a-a788-4e94-be22-2f169d3bc373 | 5b9f1987-7aaa-45a3-9522-c1315f5186fe | d93065c3-9ff2-439b-bbdb-be609204877d | WBN-LV-C46 | 85d11afa | Village | CRITICAL | 1785295920000 | 1785299370000 | 0.46913 | 127.937863 | 0.46881 | 127.946005 | OPEN |
| 0c2d344a-feb7-4846-be17-4741b102f309 | 3274ce4d-fc14-4972-be46-cfa1cc6a1ae8 | d93065c3-9ff2-439b-bbdb-be609204877d | WBN-LV-C88 | 85d11afa | Village | CRITICAL | 1784954955000 | 1784955229000 | 0.46917 | 127.937698 | 0.467463 | 127.926003 | CLOSED |
| 0cb99b76-fa3d-45e6-88dc-6d0cae6c46b6 | 18808a59-5909-47c9-9b93-d78b59bce775 | d93065c3-9ff2-439b-bbdb-be609204877d | WBN-LV-C25 | 85d11afa | Village | CRITICAL | 1784980797000 | 1784982548000 | 0.465733 | 127.928975 | 0.469878 | 127.914873 | OPEN |

<a id="fms-db-fms-lv-zone-visits"></a>

#### `FMS_LV_ZONE_VISITS`

**Rows:** 43  |  **Columns:** 13

**Columns:** `EVENT_ID` varchar(36), `PLATE` varchar(32), `ZONE_ID` nvarchar(20), `ZONE_NAME` nvarchar(200), `ENTER_TS` bigint, `EXIT_TS` bigint, `DURATION_SEC` int, `ENTER_LAT` float, `ENTER_LNG` float, `EXIT_LAT` float, `EXIT_LNG` float, `STATUS` varchar(12), `CREATED_AT` bigint

**Identifier vocabularies:**

- `EVENT_ID` — 43 distinct. e.g. `ffc1c821-62be-462e-93a1-e6d95d969400`, `0d5dc7b7-3cda-48da-9ac7-98b0e7036217`, `d5c47118-951a-4373-b8ce-bef36301421c`, `ea4e1b04-5fbe-466f-b3bf-d0c633c86adc`, `9f2b9fbe-2f59-41a0-a79f-9b7c1ef61b4d`, `8d50567f-8e6b-494f-a45b-0f5f1512dc94`, `03383695-9c77-4dae-8446-6128648e7a2e`, `b750cc91-2a9f-4a43-8e8b-c4b48fbb0905`, `b9eb9adf-bf7c-4591-9205-34b1e8a8c6c1`, `84b89c6a-be23-4778-bdeb-6fd81ce92431`, `63ed560b-a672-4554-b1ff-bd5ed6c71031`, `0d4af074-2a46-4501-931d-ead83cef309d`
- `PLATE` — 11 distinct. e.g. `WBN-LV-C25`, `WBN-LV-C30`, `WBN-LV-C36`, `WBN-LV-C40`, `WBN-LV-C44`, `WBN-LV-C46`, `WBN-LV-C51`, `WBN-LV-C88`, `WBN-LV-M57`, `WBN-LV-M81`, `WBN-LV-M92`
- `ZONE_ID` — 1 distinct. e.g. `85d11afa`

**Sample rows**:

| EVENT_ID | PLATE | ZONE_ID | ZONE_NAME | ENTER_TS | EXIT_TS | DURATION_SEC | ENTER_LAT | ENTER_LNG | EXIT_LAT | EXIT_LNG | STATUS | CREATED_AT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 02009781-745f-429f-9a59-0cf04655425f | WBN-LV-M57 | 85d11afa | Village | 1785031731000 | 1785033960000 | 2229 | 0.47029 | 127.938785 | 0.472328 | 127.91688 | EXITED | 1785031736827 |
| 03383695-9c77-4dae-8446-6128648e7a2e | WBN-LV-C25 | 85d11afa | Village | 1785038720000 | 1785039627000 | 907 | 0.463547 | 127.927207 | 0.472737 | 127.916788 | EXITED | 1785038728350 |
| 0406cd08-cf28-431c-bcb1-22f5d1834980 | WBN-LV-C88 | 85d11afa | Village | 1784954589000 | 1784956222000 | 1633 | 0.46751 | 127.92595 | 0.514362 | 127.901518 | EXITED | 1784954623951 |
| 096d6f56-85cf-43d2-b92a-9ec06ff08a72 | WBN-LV-M57 | 85d11afa | Village | 1784893125000 | 1784896418000 | 3293 | 0.47131 | 127.938328 | 0.469013 | 127.940392 | EXITED | 1784893144841 |
| 0ac661a2-d396-460a-b558-7a127e464ff3 | WBN-LV-M81 | 85d11afa | Village | 1785246420000 | 1785278640000 | 32220 | 0.470185 | 127.917377 | 0.799493 | 128.028287 | EXITED | 1785246429200 |

<a id="fms-db-fms-login-ips"></a>

#### `FMS_LOGIN_IPS`

**Rows:** 37  |  **Columns:** 5

**Columns:** `USERNAME` varchar(64), `IP` varchar(64), `HITS` int, `IS_ADMIN` bit, `UPDATED_AT` bigint

**Sample rows**:

| USERNAME | IP | HITS | IS_ADMIN | UPDATED_AT |
|---|---|---|---|---|
| aanas | 36.93.21.124 | 1 | False | 1784183931132 |
| aassegaff | 10.158.21.91 | 1 | False | 1784187896893 |
| codex-upload-test | 127.0.0.1 | 1 | False | 1784959255964 |
| crizkiana | 36.92.27.251 | 1 | True | 1785222454150 |
| crizkiana | 36.93.196.124 | 7 | False | 1785026109484 |

<a id="fms-db-fms-users"></a>

#### `FMS_USERS`

**Rows:** 30  |  **Columns:** 8

**Columns:** `USERNAME` nvarchar(100), `PASSWORD` nvarchar(300), `ROLE` nvarchar(50), `DISPLAY_NAME` nvarchar(200), `EMAIL` nvarchar(300), `ACTIVE` bit, `UPDATED_AT` bigint, `UPDATED_BY` nvarchar(100)

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-res-speed-limit-zones"></a>

#### `RES_SPEED_LIMIT_ZONES`

**Rows:** 27  |  **Columns:** 16

> Posted speed limit per segment with KM_From/KM_To.

**Columns:** `Segment Code` nvarchar(255), `Chainage Range (KM)` nvarchar(255), `Speed Limit (km/h)` float, `Geometry Type` nvarchar(255), `Area Type` nvarchar(255), `Loading/Unloading Category` nvarchar(255), `Operating Area` nvarchar(255), `Responsible Department` nvarchar(255), `Longitude` float, `Latitude` float, `Location Description` nvarchar(255), `Remarks` nvarchar(255), `KM_From` decimal, `KM_To` decimal, `Region_Code` varchar(10), `Is_Critical` bit

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-fms-app-state"></a>

#### `FMS_APP_STATE`

**Rows:** 23  |  **Columns:** 3  |  **UPDATED_AT:** 2026-07-11 11:15:22 → 2026-07-30 12:10:29

**Columns:** `NAME` nvarchar(160), `PAYLOAD` nvarchar(-1), `UPDATED_AT` datetime

**Sample rows**:

| NAME | PAYLOAD | UPDATED_AT |
|---|---|---|
| active_sessions.json | {"nbagus": "d67490c4-d137-412a-846c-73… | 2026-07-30T11:11:50.690 |
| app_config.json | {"access_suspended": true, "cycle_coll… | 2026-07-22T11:14:42.077 |
| contractors.json | {"contractors": ["ATC", "AWK", "BPMS",… | 2026-07-11T11:15:26.663 |
| dispatch_assignments.json | {} | 2026-07-29T12:40:28.320 |
| equipment_registry.json | {"ATC-P3-GKT-01": {"type": "Air Condit… | 2026-07-11T11:15:26.743 |

<a id="fms-db-fms-user-activity"></a>

#### `FMS_USER_ACTIVITY`

**Rows:** 18  |  **Columns:** 3

**Columns:** `USERNAME` nvarchar(100), `LAST_SEEN` bigint, `SOURCE` nvarchar(80)

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-fms-assignments"></a>

#### `FMS_ASSIGNMENTS`

**Rows:** 17  |  **Columns:** 5  |  **UPDATED:** 2026-07-05 16:19:11 → 2026-07-28 14:11:27

**Columns:** `ASSIGN_TYPE` nvarchar(30), `KEY_A` nvarchar(150), `KEY_B` nvarchar(150), `EXTRA` nvarchar(-1), `UPDATED` datetime

**Sample rows**:

| ASSIGN_TYPE | KEY_A | KEY_B | EXTRA | UPDATED |
|---|---|---|---|---|
| pile_excav | KRENE.I.3288 | E377 |  | 2026-07-05T16:19:11.883 |
| pile_excav | KRENE.I.3289 | E377 |  | 2026-07-06T09:41:49.643 |
| pile_excav | KRENE.I.3290 | E042 |  | 2026-07-06T09:42:07.277 |
| pile_excav | KRENE.I.3291 | E042 |  | 2026-07-08T08:08:15.370 |
| pile_excav | KRENE.I.3293 | E377 |  | 2026-07-08T08:08:16.767 |

<a id="fms-db-fms-job-runs"></a>

#### `FMS_JOB_RUNS`

**Rows:** 15  |  **Columns:** 5  |  **RUN_DATE:** 2026-07-16 → 2026-07-30

**Columns:** `JOB_NAME` varchar(64), `RUN_DATE` date, `RAN_AT` bigint, `INSTANCE` varchar(64), `ROWS_AFFECTED` int

**Sample rows**:

| JOB_NAME | RUN_DATE | RAN_AT | INSTANCE | ROWS_AFFECTED |
|---|---|---|---|---|
| gps_historical | 2026-07-16T00:00:00.000 | 1784176937295 | Rudolfs-MacBook-Air.local | 0.0 |
| gps_historical | 2026-07-17T00:00:00.000 | 1784251068453 | Rudolfs-MacBook-Air.local |  |
| gps_historical | 2026-07-18T00:00:00.000 | 1784333917043 | Rudolfs-MacBook-Air.local |  |
| gps_historical | 2026-07-19T00:00:00.000 | 1784425378761 | Rudolfs-MacBook-Air.local | 21819.0 |
| gps_historical | 2026-07-20T00:00:00.000 | 1784511297719 | Rudolfs-MacBook-Air.local | 279357.0 |

<a id="fms-db-fms-messages"></a>

#### `FMS_MESSAGES`

**Rows:** 14  |  **Columns:** 15

**Columns:** `ID` nvarchar(80), `FROM_USER` nvarchar(100), `FROM_NAME` nvarchar(200), `TO_ADDR` nvarchar(200), `SUBJECT` nvarchar(400), `BODY` nvarchar(-1), `CONTEXT` nvarchar(200), `SHIFT` float, `PLAN_DATE` nvarchar(20), `TS` bigint, `ANON` bit, `POPUP` bit, `PINNED` bit, `REPLY_TO` nvarchar(80), `READ_JSON` nvarchar(-1)

**Identifier vocabularies:**

- `ID` — 14 distinct. e.g. `msg_1784101276221_rdinkelmann`, `msg_1784101842600_rdinkelmann`, `msg_1784102803166_rdinkelmann`, `msg_1784188322376_rdinkelmann`, `msg_1784188344839_rdinkelmann`, `msg_1784188362443_rdinkelmann`, `msg_1784188602771_ytae`, `msg_1784188717939_rdinkelmann`, `msg_1784189635256_ytae`, `msg_1784344333735_rdinkelmann`, `msg_1784344422330_rdinkelmann`, `msg_1784344457787_rdinkelmann`

**Sample rows** (first 14 of 15 columns):

| ID | FROM_USER | FROM_NAME | TO_ADDR | SUBJECT | BODY | CONTEXT | SHIFT | PLAN_DATE | TS | ANON | POPUP | PINNED | REPLY_TO |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| msg_1784101276221_rdinkelmann | rdinkelmann | R. Dinkelmann | handover |  | Remember to assign the trucks | /dispatch |  |  | 1784101276221 | True | False | False |  |
| msg_1784101842600_rdinkelmann | rdinkelmann | R. Dinkelmann | user:sbell | Verify Tofu TOS | Hi Simon,  Please verify if Tall Tofu … |  |  |  | 1784101842600 | True | True | False |  |
| msg_1784102803166_rdinkelmann | rdinkelmann | R. Dinkelmann | user:ytae | Testing | etsting |  |  |  | 1784102803166 | True | True | False |  |
| msg_1784188322376_rdinkelmann | rdinkelmann | R. Dinkelmann | user:aassegaff | Special Agent | Hi my name is Kohli, how can i assist … |  |  |  | 1784188322376 | True | True | False |  |
| msg_1784188344839_rdinkelmann | rdinkelmann | R. Dinkelmann | user:aanas | Special Agent | Hi my name is Yusuf, how can i assist … |  |  |  | 1784188344839 | True | True | False |  |

<a id="fms-db-res-water-filling-points"></a>

#### `RES_WATER_FILLING_POINTS`

**Rows:** 14  |  **Columns:** 9

**Columns:** `Region` nvarchar(50), `Location` nvarchar(100), `Station ID` nvarchar(50), `Contractor` nvarchar(50), `Status` nvarchar(20), `Latitude` float, `Longitude` float, `Dispenser_Count` int, `Match_Radius_Meters` float

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-fms-settings"></a>

#### `FMS_SETTINGS`

**Rows:** 7  |  **Columns:** 3

**Columns:** `SKEY` varchar(64), `SVAL` nvarchar(400), `UPDATED_AT` bigint

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-fms-lv-daily-reports"></a>

#### `FMS_LV_DAILY_REPORTS`

**Rows:** 6  |  **Columns:** 12  |  **REPORT_DATE:** 2026-07-24 → 2026-07-29

**Columns:** `REPORT_DATE` date, `PERIOD_START` bigint, `PERIOD_END` bigint, `VISIT_COUNT` int, `UNIT_COUNT` int, `TOTAL_DURATION_SEC` bigint, `REPORT_HTML` nvarchar(-1), `RECIPIENTS` nvarchar(2000), `GENERATED_AT` bigint, `SENT_AT` bigint, `SEND_STATUS` nvarchar(40), `GENERATED_BY` nvarchar(100)

**Sample rows**:

| REPORT_DATE | PERIOD_START | PERIOD_END | VISIT_COUNT | UNIT_COUNT | TOTAL_DURATION_SEC | REPORT_HTML | RECIPIENTS | GENERATED_AT | SENT_AT | SEND_STATUS | GENERATED_BY |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-07-24T00:00:00.000 | 1784844000000 | 1784930400000 | 17 | 9 | 458243 | <!doctype html><html><body style="font… | r.dinkelmann77@gmail.com | 1784958417517 | 1784958417517.0 | SENT | system |
| 2026-07-25T00:00:00.000 | 1784930400000 | 1785016800000 | 9 | 4 | 43375 | <!doctype html><html><body style="font… | cindha.rizkiana@wedabaynickel.id | 1785025537601 | 1785025537601.0 | SENT | rdinkelmann |
| 2026-07-26T00:00:00.000 | 1785016800000 | 1785103200000 | 10 | 5 | 29688 | <!doctype html><html><body style="font… | bel.simon@wedabaynickel.id | 1785114657394 | 1785114657394.0 | SENT | rdinkelmann |
| 2026-07-27T00:00:00.000 | 1785103200000 | 1785189600000 | 4 | 3 | 3354 | <!doctype html><html><body style="font… | cindha.rizkiana@wedabaynickel.id | 1785222779712 |  | GENERATED | crizkiana |
| 2026-07-28T00:00:00.000 | 1785189600000 | 1785276000000 | 3 | 3 | 2770 | <!doctype html><html><body style="font… | cindha.rizkiana@wedabaynickel.id | 1785287724500 | 1785287724500.0 | SENT | rdinkelmann |

<a id="fms-db-fms-lv-visit-verifications"></a>

#### `FMS_LV_VISIT_VERIFICATIONS`

**Rows:** 4  |  **Columns:** 13

**Columns:** `VISIT_KEY` nvarchar(240), `PLATE` nvarchar(60), `ENTER_TS` bigint, `DETECTED_DRIVER` nvarchar(200), `IS_VALID` bit, `IMAGE_NAME` nvarchar(300), `IMAGE_MIME` nvarchar(100), `IMAGE_DATA` varbinary(-1), `IMAGE_SIZE` int, `UPDATED_BY` nvarchar(100), `UPDATED_AT` bigint, `IMAGE_UPLOADED_BY` nvarchar(100), `IMAGE_UPLOADED_AT` bigint

**Identifier vocabularies:**

- `PLATE` — 3 distinct. e.g. `WBN-LV-C46`, `WBN-LV-C88`, `WBN-LV-M57`
- `DETECTED_DRIVER` — 1 distinct. e.g. `Romario`

*Sample unavailable: could not serialise*

<a id="fms-db-res-critical-zones"></a>

#### `RES_CRITICAL_ZONES`

**Rows:** 4  |  **Columns:** 5

> Designated critical zones.

**Columns:** `ZoneID` int, `Region_Code` varchar(10), `KM_From` decimal, `KM_To` decimal, `Zone_Type` varchar(50)

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-fms-instances"></a>

#### `FMS_INSTANCES`

**Rows:** 2  |  **Columns:** 7

**Columns:** `INSTANCE_ID` nvarchar(120), `GIT_HASH` nvarchar(40), `GIT_SUBJECT` nvarchar(400), `GIT_TIME` nvarchar(40), `STARTED_AT` bigint, `LAST_BEAT` bigint, `HOST` nvarchar(120)

**Identifier vocabularies:**

- `INSTANCE_ID` — 2 distinct. e.g. `fms-prototype`, `Rudolfs-MacBook-Air.local`

**Sample rows**:

| INSTANCE_ID | GIT_HASH | GIT_SUBJECT | GIT_TIME | STARTED_AT | LAST_BEAT | HOST |
|---|---|---|---|---|---|---|
| fms-prototype | e96a337 | LV geofence visits: ignore stale/froze… | 2026-07-30 10:02:08 +0700 | 1784185805666 | 1785381058350 | fms-prototype |
| Rudolfs-MacBook-Air.local | e96a337 | LV geofence visits: ignore stale/froze… | 2026-07-30 10:02:08 +0700 | 1784089672452 | 1785380778831 | Rudolfs-MacBook-Air.local |

<a id="fms-db-fms-docs"></a>

#### `FMS_DOCS`

**Rows:** 1  |  **Columns:** 4

**Columns:** `DOC_KEY` varchar(64), `CONTENT` nvarchar(-1), `UPDATED_AT` bigint, `SRC_HASH` varchar(40)

**Sample rows**:

| DOC_KEY | CONTENT | UPDATED_AT | SRC_HASH |
|---|---|---|---|
| install_plan_report | <!doctype html><html><head><meta chars… | 1785228547801 | 5b371e1f6b3e0c4224afbb75af5362bf |

<a id="fms-db-fms-geofence-alert-rules"></a>

#### `FMS_GEOFENCE_ALERT_RULES`

**Rows:** 1  |  **Columns:** 17

**Columns:** `RULE_ID` varchar(36), `RULE_NAME` nvarchar(160), `GEOFENCE_ID` nvarchar(20), `GEOFENCE_NAME` nvarchar(200), `TRIGGER_EVENT` varchar(10), `UNIT_PREFIX` varchar(40), `MIN_DURATION_SEC` int, `SEVERITY` varchar(12), `RECIPIENT_ROLE` varchar(40), `EMAIL_TO` nvarchar(1000), `ESCALATE_AFTER_MIN` int, `ACTIVE` bit, `CREATED_AT` bigint, `CREATED_BY` nvarchar(100), `ESCALATION_EMAIL_TO` nvarchar(1000), `ENTRY_USERNAMES` nvarchar(2000), `ESCALATION_USERNAMES` nvarchar(2000)

**Identifier vocabularies:**

- `RULE_ID` — 1 distinct. e.g. `d93065c3-9ff2-439b-bbdb-be609204877d`
- `GEOFENCE_ID` — 1 distinct. e.g. `85d11afa`
- `UNIT_PREFIX` — 1 distinct. e.g. `WBN-LV-`

**Sample rows** (first 14 of 17 columns):

| RULE_ID | RULE_NAME | GEOFENCE_ID | GEOFENCE_NAME | TRIGGER_EVENT | UNIT_PREFIX | MIN_DURATION_SEC | SEVERITY | RECIPIENT_ROLE | EMAIL_TO | ESCALATE_AFTER_MIN | ACTIVE | CREATED_AT | CREATED_BY |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d93065c3-9ff2-439b-bbdb-be609204877d | Village LV entry | 85d11afa | Village | ENTER | WBN-LV- | 0 | CRITICAL | dispatcher |  | 5 | True | 1785315028177 | rdinkelmann |

<a id="fms-db-fms-roadmap-doc"></a>

#### `FMS_ROADMAP_DOC`

**Rows:** 1  |  **Columns:** 5

**Columns:** `ID` nvarchar(20), `DATA` nvarchar(-1), `DOC_VERSION` int, `UPDATED_AT` bigint, `UPDATED_BY` nvarchar(80)

**Identifier vocabularies:**

- `ID` — 1 distinct. e.g. `current`

**Sample rows**:

| ID | DATA | DOC_VERSION | UPDATED_AT | UPDATED_BY |
|---|---|---|---|---|
| current | {"schemaVersion": "3.0", "product": {"… | 5 | 1785318072994 | seed |

<a id="fms-db-fms-roadmap-meta"></a>

#### `FMS_ROADMAP_META`

**Rows:** 1  |  **Columns:** 2

**Columns:** `META_KEY` nvarchar(80), `META_VALUE` nvarchar(200)

**Sample rows**:

| META_KEY | META_VALUE |
|---|---|
| seed_version | 6 |

<a id="fms-db-fms-truck-cycles"></a>

#### `FMS_TRUCK_CYCLES`

**Rows:** 1  |  **Columns:** 16

> Live per-truck state machine: TRAVEL_EMPTY, LOAD, TRAVEL_LOADED, with GPS geofence events in TRANSITION_META.

**Columns:** `PLATE` nvarchar(50), `STATE` nvarchar(20), `EXCAVATOR` nvarchar(50), `SRC` nvarchar(160), `DUMP` nvarchar(200), `DUMP_PILE` nvarchar(160), `MAT` nvarchar(60), `PILE` nvarchar(160), `PIT` nvarchar(60), `PLAN_DATE` nvarchar(20), `SHIFT` nvarchar(10), `SINCE` bigint, `CYCLES` int, `STAMPS` nvarchar(-1), `UPDATED_AT` datetime, `TRANSITION_META` nvarchar(-1)

*Sample unavailable: Not connected to any MS SQL server*

<a id="fms-db-fms-error-flow"></a>

#### `FMS_ERROR_FLOW`

**Rows:** 0  |  **Columns:** 8

**Columns:** `Id` int, `ErrorNumber` int, `ErrorSeverity` int, `ErrorState` int, `ErrorProcedure` nvarchar(200), `ErrorLine` int, `ErrorMessage` nvarchar(-1), `ErrorDate` datetime

*Empty table.*

<a id="fms-db-fms-lv-movements"></a>

#### `FMS_LV_MOVEMENTS`

**Rows:** 0  |  **Columns:** 15

**Columns:** `EVENT_ID` varchar(36), `PLATE` varchar(32), `BOUNDARY_ID` nvarchar(20), `BOUNDARY_NAME` nvarchar(200), `GATE_ID` nvarchar(20), `GATE_NAME` nvarchar(200), `EXIT_TS` bigint, `RETURN_TS` bigint, `DURATION_SEC` int, `EXIT_LAT` float, `EXIT_LNG` float, `RETURN_LAT` float, `RETURN_LNG` float, `STATUS` varchar(12), `CREATED_AT` bigint

*Empty table.*

<a id="fms-db-lv-driver-info"></a>

#### `LV_DRIVER_INFO`

**Rows:** 0  |  **Columns:** 6

**Columns:** `Vehicle_Number` varchar(50), `Divisi` varchar(100), `Department` varchar(100), `Driver_DS` varchar(200), `Driver_NS` varchar(200), `Work_Location` varchar(200)

*Empty table.*

### FMS_DB — views (36)

<details><summary>Column lists for all 36 views</summary>

- **`CCR_RISK_EVENT_ACTIONS`** (43 cols): `Risk Shift Date`, `Risk Shift`, `Risk Shift Type`, `Event_Risk_Level`, `License Plate`, `Actual_Group`, `Actual_Group_Clean`, `Planned_Groups`, `Is_Within_Planned_Group`, `Driver`, `Start Time`, `End Time`, `Created Time`, `Number Of Event`, `Event type`, `Mileage(Km)`, `Risk_riskId`, `Intervention_Risk_Level`, `Risk Start Time`, `Release Time`, `Dispatcher`, `Intervention methods`, `Content`, `Send Result`, `Intervention_riskId`, `Risk_OpenTime_Seconds`, `Response_Time_Seconds`, `Intervention_Flag`, `Human_Intervention_Flag`, `Robot_Intervention_Flag`, `Real-Time Intercom Flag`, `Priority_Order`, `Event_Type_1`, `Event_Type_2`, `Event_Type_3`, `Event_Type_4`, `Event_Type_5`, `Primary_Event_Type`, `Latest_Event_Type`, `Multi_Event_Flag`, `Event_Type_Count`, `Is_Latest_Shift`, `Is_Previous_Shift`
- **`EQUIPMENTS_RADIO_STATUS`** (21 cols): `COMPANY`, `VENDER CLASIFICATION`, `BRAND`, `MODEL`, `EQUIPMENT_SIZE`, `FINANCE_STATUS`, `ID`, `EQUIPMENT_ID_CLEAN`, `EQUIPMENT_TYPE_CLEAN`, `OEM_PIN `, `MANUFACTURE_YEAR`, `HOURMETER`, `RADIO_TYPE`, `RADIO_BRAND`, `RADIO_MODEL`, `RADIO_SERIAL_NO`, `IS_REPROGRAMMABLE`, `REPROGRAM_STATUS`, `REPROGRAM_DATE`, `TECHNICIAN`, `SUB_TEAM`
- **`FMS_ENTRY_EXIT_CLEAN`** (12 cols): `FETCH_DATE`, `plateNumber`, `truckId`, `orgName`, `orgId`, `poiTypeName`, `pointName`, `pointId`, `stayTime`, `startTime`, `endTime`, `hasVideoAbility`
- **`FMS_EQUIPMENTS_CLEAN`** (4 cols): `EQ_ID`, `EQ_FMS_ID`, `DIVISION`, `imei`
- **`FMS_EQUIPMENTS_FILTER`** (4 cols): `EQ_ID`, `EQ_FMS_ID`, `DIVISION`, `imei`
- **`FMS_HRM_SUPERVISION`** (17 cols): `SOURCE`, `ACTIVITY`, `DATE`, `SHIFT`, `EQUIPMENT_ID`, `SECTIONKM`, `DIRECTION`, `ZONE`, `ACC_STATUS`, `DISTANCE_M`, `EQUIPMENT_TYPE`, `DATETIME_MIN`, `DATETIME_MAX`, `HOURS`, `LAT`, `LONG`, `LOCATION_JOB`
- **`FMS_INTERVENTION_EVENT_CLEAN`** (26 cols): `FETCH_DATE`, `Shift_Date`, `Shift`, `Risk Start Time`, `Risk End Time`, `Release Time`, `Mileage(Km)`, `eventId`, `Group`, `intervener`, `carrierName`, `License Plate`, `totalDifftime`, `Content`, `Processor`, `fileSize`, `Intervention methods`, `Send Result`, `fileUrl`, `interveneType`, `classTypeName`, `eventTypeName`, `Risk Level`, `riskLevel`, `riskId`, `status`
- **`FMS_PLAYBACK_STAY_CLEAN`** (12 cols): `plateNumber`, `eventTypeName`, `areaName`, `difftime_minutes`, `pointNames`, `Shift_Date`, `Shift`, `lat`, `lng`, `startTime`, `endTime`, `createTime`
- **`FMS_PLAYBACK_STAY_GROUP`** (4 cols): `plateNumber`, `DATE`, `SHIFT`, `difftime_hours`
- **`FMS_PLAYBACK_TRACK_CLEAN`** (23 cols): `FETCH_DATE`, `plateNumber`, `Shift_Date`, `Shift`, `ACC_STATUS`, `deviceType`, `distance_m`, `lng`, `driving_time`, `dump_energy`, `receive_time`, `loc_type`, `speed`, `ENGINE_STATUS`, `oils`, `course`, `imei`, `DATETIME`, `interpolation_flag`, `lat`, `DIRECTION`, `SectionKM`, `DIVISION`
- **`FMS_PLAYBACK_TRACK_SEGMENT_COVERED`** (27 cols): `FETCH_DATE`, `plateNumber`, `Shift_Date`, `Shift`, `ACC_STATUS`, `deviceType`, `distance_m`, `lng`, `driving_time`, `dump_energy`, `receive_time`, `loc_type`, `speed`, `ENGINE_STATUS`, `oils`, `course`, `imei`, `DATETIME`, `interpolation_flag`, `lat`, `DIRECTION`, `SectionKM`, `LAST_DIRECTION`, `LAST_SectionKM`, `DIRECTION_CHANGED`, `SectionKM_CHANGED`, `LANE`
- **`FMS_PLAYBACK_TRACK_WORKINGHOURS`** (5 cols): `DATE`, `SHIFT`, `EQUIPMENT_ID`, `WORKING_HOURS`, `distance_m`
- **`FMS_RISK_CLEAN`** (18 cols): `FETCH_DATE`, `Shift_Date`, `Shift`, `Group`, `Risk Level Code`, `Risk Level`, `Intervention Types`, `Number Of Event`, `License Plate`, `riskId`, `Driver`, `Carrier Name`, `Created Time`, `Start Time`, `End Time`, `Event type`, `Mileage(Km)`, `Status`
- **`FMS_SECURITY_INCIDENT_CLEAN`** (25 cols): `DATE`, `SHIFT`, `Eventtypename`, `Areaname`, `Vehiclenumber`, `checkDriverName`, `Drivername`, `DriverNo`, `Contractor`, `ContractorTeam`, `startTime`, `endTime`, `difftime`, `Startinglatitude`, `Startlongitude`, `Endlatitude`, `Endlongitude`, `Shift2`, `Maximumspeed`, `Drivingmileage`, `DIRECTION`, `SectionKM`, `ID`, `markerType`, `markerRemark`
- **`FMS_SECURITY_INCIDENT_KILOMETER`** (4 cols): `Eventtypename`, `id`, `DIRECTION`, `SectionKM`
- **`IDLE_EVENTS_WT`** (29 cols): `ID`, `Event_Type_Name`, `Area_Name`, `Area_Event`, `Vehicle_Number`, `Contractor`, `Driver_Name`, `Contractor_Team`, `Start_Time`, `End_Time`, `Duration_Seconds`, `Duration_Minutes`, `Start_Longitude`, `Start_Latitude`, `End_Latitude`, `End_Longitude`, `Shift`, `Driving_Mileage`, `Source_File`, `Import_Date`, `Shift_Date`, `WF_Station_ID`, `WF_Location`, `WF_Status`, `Dispenser_Count`, `Match_Radius_Meters`, `WF_Match_Status`, `Is_Latest_Shift`, `Is_Previous_Shift`
- **`KIMPER_MISSING_FMS_ID`** (3 cols): `checkDriverName`, `driverNo`, `DriverID`
- **`LV_GEOFENCE_EVENTS`** (29 cols): `Event_Type_Name`, `Geofence Zone`, `Location`, `Vehicle_Number`, `Driver_Name`, `DriverNo`, `Contractor`, `Contractor_Team`, `Start_Time`, `End_Time`, `Start_Longitude`, `Start_Latitude`, `End_Latitude`, `End_Longitude`, `Shift`, `Maximum_Speed`, `Driving_Mileage`, `Source_File`, `Import_Date`, `Is_Critical`, `Critical_Zone_Type`, `SectionDirection`, `SectionKM`, `difftime`, `Shift_Date`, `Event_Category`, `LV_Geofence_Flag`, `Is_Latest_Shift`, `Is_Previous_Shift`
- **`OSPAT_RESULTS`** (22 cols): `CONTRACTOR`, `TestDateTime`, `TestDateShift`, `TestShift`, `Tag`, `EmployeeID`, `Employee FamilyName`, `Employee FirstName`, `EmploymentStatus`, `EmployeePositionName`, `SupervisorPositionName`, `TerminalName`, `TerminalIPAddress`, `TerminalTag`, `EmployeeTag`, `EmployeeAge`, `ResultType`, `AttemptCount`, `ShiftTag`, `ResultScore`, `OutcomeType1`, `ResultClass`
- **`OVERSPEED_EVENTS`** (32 cols): `Event_Type_Name`, `Geofence Zone`, `Location`, `Location_Speed`, `Vehicle_Number`, `Driver_Name`, `DriverNo`, `Contractor`, `Start_Time`, `Contractor_Team`, `End_Time`, `Start_Longitude`, `Start_Latitude`, `End_Latitude`, `End_Longitude`, `Shift`, `Maximum_Speed`, `Driving_Mileage`, `Speed_Limit`, `Actual_Overspeed`, `Source_File`, `Import_Date`, `Is_Critical`, `Critical_Zone_Type`, `SectionDirection`, `SectionKM`, `difftime`, `Shift_Date`, `Speed_Class1`, `OS_Flag1`, `Is_Latest_Shift`, `Is_Previous_Shift`
- **`OVERSPEED_VEHICLE_SUMMARY`** (4 cols): `Shift_Date`, `Contractor_Team`, `Event_Type_Name`, `Vehicle_Count`
- **`VW_DISPATCHER_DIM`** (1 cols): `Dispatcher`
- **`VW_DISPATCHER_INCIDENT_REVIEW`** (19 cols): `id`, `truckId`, `Vehicle_Number`, `Event_Type`, `Area`, `Org`, `Max_Speed`, `Speed_Limit`, `Remark`, `Event_Time_UTC`, `Event_Date`, `Event_Count`, `Disposition`, `Is_Confirmed`, `Is_FA_Recognition`, `Is_FA_Camera`, `Is_Misjudgement`, `Is_False_Alarm`, `Dispatcher`
- **`VW_DISPATCHER_MONTHLY_KPI`** (13 cols): `Dispatcher`, `Month_Start`, `Human_Interventions`, `Avg_RT_min`, `Avg_ROT_min`, `Send_Success_Pct`, `Risk_Events`, `Reviewed`, `Risk_Confirmed`, `FA_Recognition`, `FA_Camera`, `Misjudgement`, `Risk_Confirmation_Pct`
- **`VW_FMS_EVENTS`** (33 cols): `Event_Type_Name`, `Area_Name`, `Area_Event`, `Vehicle_Number`, `Driver_Name`, `Contractor`, `Contractor_Team`, `Start_Time`, `End_Time`, `Start_Longitude`, `Start_Latitude`, `End_Latitude`, `End_Longitude`, `Shift`, `Maximum_Speed`, `Driving_Mileage`, `Speed_Limit`, `Actual_Overspeed`, `Source_File`, `Import_Date`, `Is_Critical`, `Critical_Zone_Type`, `Shift_Date`, `Shift_No`, `DIRECTION`, `SectionKM`, `checkDriverName`, `DriverNo`, `difftime`, `ID`, `markerType`, `Validation`, `markerRemark`
- **`VW_FMS_LV_VISIT_EVIDENCE`** (24 cols): `VISIT_KEY`, `PLATE`, `ENTER_TS`, `EXIT_TS`, `GEOFENCE_ID`, `GEOFENCE_NAME`, `ENTER_LAT`, `ENTER_LNG`, `EXIT_LAT`, `EXIT_LNG`, `DURATION_SEC`, `DETECTED_DRIVER`, `IS_VALID`, `IMAGE_NAME`, `IMAGE_MIME`, `IMAGE_SIZE`, `HAS_IMAGE`, `FACE_IMAGE_BYTES`, `UPLOADED_BY_USERNAME`, `UPLOADED_BY_NAME`, `UPLOADED_BY_EMAIL`, `UPLOADED_AT`, `LAST_UPDATED_BY`, `LAST_UPDATED_AT`
- **`VW_LV_ACTIVE_PLAN`** (13 cols): `Plan_Date`, `Active_Date`, `Shift`, `Vehicle_Number`, `Divisi`, `Department`, `Driver_DS`, `Driver_NS`, `Work_Location`, `Region`, `KM_From`, `KM_To`, `Date_Uploaded`
- **`VW_SAFETY_DPLAN`** (5 cols): `DATE`, `Shift`, `Dispatcher`, `ID`, `Groups`
- **`VW_WT_DAILY_PLAN`** (11 cols): `ID`, `Shift_Date`, `Vehicle_Number`, `Region`, `KM_From`, `KM_To`, `Primary_WF`, `Target_Refills`, `Created_Date`, `Breakdown`, `rn`
- **`VW_WT_PLAN_BREAKDOWN_STATUS`** (3 cols): `Shift_Date`, `Vehicle_Number`, `Breakdown`
- **`VW_WT_REFILL_CYCLES`** (11 cols): `Shift_Date`, `Vehicle_Number`, `WF_Station_ID`, `WF_Location`, `Refill_Sequence`, `Refill_End_Time`, `Next_Refill_End_Time`, `Max_Cycle_End_Time`, `Primary_WF`, `Is_Planned_WF_Refill`, `Refill_WF_Status`
- **`VW_WT_REFILL_CYCLE_SUMMARY`** (19 cols): `Shift_Date`, `Vehicle_Number`, `Refill_Sequence`, `WF_Station_ID`, `WF_Location`, `Refill_End_Time`, `Next_Refill_End_Time`, `Max_Cycle_End_Time`, `Planned_Region`, `KM_From`, `KM_To`, `Primary_WF`, `Target_Refills`, `Track_Points_After_Refill`, `In_Zone_Track_Points_After_Refill`, `In_Other_Zone_Track_Points_After_Refill`, `Total_Distance_After_Refill_KM`, `In_Zone_Distance_After_Refill_KM`, `In_Other_Zone_Distance_After_Refill_KM`
- **`VW_WT_TRACK_PLAN_SUMMARY`** (16 cols): `Shift_Date`, `Vehicle_Number`, `Planned_Region`, `KM_From`, `KM_To`, `Primary_WF`, `Target_Refills`, `Total_Track_Points`, `In_Zone_Track_Points`, `Out_Of_Zone_Track_Points`, `Zone_Compliance_Pct`, `Total_Distance_Travelled_KM`, `In_Zone_Distance_Travelled_KM`, `Out_Of_Zone_Distance_Travelled_KM`, `Is_Latest_Shift`, `Is_Previous_Shift`
- **`VW_WT_TRACK_PLAN_SUMMARY_FINAL`** (21 cols): `Shift_Date`, `Vehicle_Number`, `Planned_Region`, `KM_From`, `KM_To`, `Primary_WF`, `Target_Refills`, `Total_Track_Points`, `In_Zone_Track_Points`, `Out_Of_Zone_Track_Points`, `Zone_Compliance_Pct`, `Total_Distance_Travelled_KM`, `In_Zone_Distance_Travelled_KM`, `Out_Of_Zone_Distance_Travelled_KM`, `Is_Latest_Shift`, `Is_Previous_Shift`, `Watering_KM_In_Zone_After_Refill`, `Watering_Track_Points_In_Zone_After_Refill`, `Watering_KM_In_Other_Zone_After_Refill`, `Watering_Track_Points_In_Other_Zone_After_Refill`, `Missing_Plan_Flag`
- **`VW_WT_ZONE_COVERAGE`** (10 cols): `Shift_Date`, `Region`, `KM_From`, `KM_To`, `Track_Points_In_Zone`, `Trucks_In_Zone`, `Post_Refill_KM_In_Zone`, `No_Coverage_Flag`, `Is_Latest_Shift`, `Is_Previous_Shift`
- **`WATER_POINTS_GEOFENCE`** (13 cols): `Region`, `Location`, `Station ID`, `Contractor`, `Status`, `Latitude`, `Longitude`, `Dispenser_Count`, `Match_Radius_Meters`, `Min_Lat`, `Max_Lat`, `Min_Lng`, `Max_Lng`

</details>

---

## Cross-Database Analysis

Everything below was measured against the live databases. Where a question in
the brief could not be answered, that is stated rather than filled in.

### ID format comparison

The two databases use **three different identifier namespaces**, and confusing
them is what produced the original false conclusion.

| Namespace | Where | Format | Example |
|---|---|---|---|
| Fleet number | `HAULAGE_IWIP_CLEAN.TRUCK_ID` | letter + 3 digits | `A342`, `R707`, `N051` |
| Fleet number | `FMS_EQUIPMENTS.plateNumber` | letter + 3 digits | `A843`, `B279`, `N469` |
| Device serial | `FMS_EQUIPMENTS.truckId` | 19-digit | `6922135043045589259` |
| Device serial | `FMS_GPS_Historical.TRUCK_ID` | 19-digit | `6922135043045589259` |
| IMEI | `FMS_PLAYBACK_TRACK_DATA.imei` | 15-digit | `107015291859999` |

**Haul truck IDs in WBN_DATABASE** (20 examples): `A342`, `A409`, `A450`,
`A486`, `A487`, `A527`, `A530`, `A531`, `A533`, `A535`, `A537`, `A551`, `A553`,
`A560`, `A561`, `A562`, `A565`, `A592`, `A602`, `A604` — 3,236 distinct.

**Equipment IDs in the FMS GPS tables** (20 examples): `6922135043045589259`,
`6922135043045589262`, `6922135043045589264`, `6922135043045589267`,
`6922135043045589271`, `6922135043045589273`, `6922135043146252553`,
`6922135043246915856`, … — 696 distinct in `FMS_GPS_Historical`.

| Comparison | Result |
|---|---|
| `HAULAGE_IWIP_CLEAN.TRUCK_ID` vs `FMS_GPS_Historical.TRUCK_ID` | **0 of 3,236** |
| `HAULAGE_IWIP_CLEAN.TRUCK_ID` vs `FMS_EQUIPMENTS.truckId` | **0 of 3,236** |
| `HAULAGE_IWIP_CLEAN.TRUCK_ID` vs `FMS_EQUIPMENTS.plateNumber` | **945 of 1,411 match** |
| `HAULAGE_IWIP_CLEAN.TRUCK_ID` vs `FMS_GEOFENCE_VISITS.UNIT_ID` (Haul Truck) | **613 of 644 (95.2%)** |

**Is the "namespace split" real?** No — it was a **mapping issue**, and the
mapping table already exists. `FMS_EQUIPMENTS` carries both keys on the same
row: `plateNumber` joins to the weighbridge, `truckId` joins to the GPS tables.

```
HAULAGE_IWIP_CLEAN.TRUCK_ID  =  FMS_EQUIPMENTS.plateNumber
                                FMS_EQUIPMENTS.truckId      =  FMS_GPS_Historical.TRUCK_ID
```

`FMS_GPS_Historical` and `FMS_PLAYBACK_TRACK_24H` also carry a `PLATE` column,
so they join to the weighbridge **directly**, without the bridge table.

### GPS coverage check

| Question | Answer |
|---|---|
| Haul trucks with a telematics device | **945 of 1,411 registered units** |
| Reporting in `FMS_PLAYBACK_TRACK_24H` | **479 (50.7%)** |
| Reporting in `FMS_GPS_Historical` | **455 (48.1%)** |
| Sampling interval | **3 seconds** (median gap; p95 = 4 s) |
| Coordinate extent | lat 0.446–0.898, lng 127.86–128.56 — Halmahera |
| Speed values | median 17 km/h, p95 30, max 79 — physical for a haul road |
| Haul-truck visits to **pit** geofences | **15,100** across BLB, CBB, KR, TF |
| Haul-truck visits to **weighbridge** geofences | **19,378** |
| Haul-truck visits to **dumping** geofences | **1,202** |
| Haul-truck visits to **loading** geofences | **835** |

**Conclusion: GPS covers haul trucks.** The `FMS_GEOFENCE_VISITS` table settles
it on geography rather than identifiers — 43,763 rows are explicitly typed
`Haul Truck`, recorded entering and leaving named pits and weighbridges with
GPS-sourced coordinates. Vehicles that repeatedly enter TF, KR and the IWIP
weighbridges are doing haul work regardless of what any registry calls them.

The earlier claim that **0 of 940 haul trucks appear in the GPS feed** was
derived from `FMS_PLAYBACK_TRACK_DATA` alone. On that table it is true: its 219
plates are `SS###`/`E###` support units. The error was generalising one table
to the whole database, and reading Chinese org names (`工程`, `后勤`) as vehicle
classes when they are contractor groupings — exactly as the site operator said.

**The genuine constraint is retention.**

| Table | Coverage | Overlaps the trip extract (2025-12-27 → 2026-07-09)? |
|---|---|---|
| `FMS_GEOFENCE_VISITS` | 2025-12-07 → 2026-07-30, 89 days | **Yes** |
| `FMS_PLAYBACK_TRACK_DATA` | 2026-03-21 → 2026-07-30 | Yes, but no haul trucks |
| `FMS_ENTRY_EXIT_DATA` | 2026-06-08 → 2026-07-30 | Partial |
| `FMS_CONGESTION_SEG` | 2026-07-15 → 2026-07-30 | No |
| `FMS_GPS_Historical` | 2026-07-15 → 2026-07-20 | No |
| `FMS_PLAYBACK_TRACK_24H` | 2026-07-29 → 2026-07-30 | No |

So: raw tracks and derived segment speeds are a **rolling live feed** of days to
two weeks. They cannot be retro-fitted onto the six-month trip history the
current models were trained on, but they can drive a forward-looking simulator
and they accumulate from now. `FMS_GEOFENCE_VISITS` is the exception that
overlaps today.

### Segment / KM section definitions

Segments are defined by **road code + kilometre chainage**, consistently across
five tables.

| Source | Rows | Granularity |
|---|---|---|
| `ALL_HR_KM_SECTIONS` | 27 | named sections with `KM_START`/`KM_END` and junctions |
| `HAUL_ROAD_STA` | 3,122 | chainage points every 25 m with WKT `POINT Z` |
| `DISPATCH ROADS` | 222 | per-route fraction across 27 section columns |
| `RES_SPEED_LIMIT_ZONES` | 27 | posted limit per segment |
| `FMS_CONGESTION_SEG` | 95 `SEG_ID` | 1 km segments, directional |

The eight named roads and their chainage extent, from `HAUL_ROAD_STA`:

| Road | KM from | KM to | Points |
|---|---|---|---|
| TOFU | 39.000 | 67.800 | 1,153 |
| KR | 7.875 | 38.975 | 674 |
| BLB | 2.450 | 19.825 | 416 |
| CBB | 6.300 | 17.125 | 431 |
| CBBB | 14.700 | 16.800 | 85 |
| CRD | 0.000 | 7.850 | 259 |
| HFC | 5.525 | 6.425 | 37 |
| CSW | 4.025 | 5.675 | 67 |

**Does it match the corridor in `simulator_api.py`?** **Yes, exactly.** Checked
against the database rather than assumed:

| Corridor landmark | KM | Confirmed by |
|---|---|---|
| TF (Tofu) | 67.8 | TOFU chainage ends at **67.800** |
| KR | 39.0 | `TF KM39 - KM45` begins at KR NORTH; KR ends 38.975 |
| POS 12 | 27.0 | `KR KM26 - KM27` ends at **POS 12** |
| POS 10 | 17.0 | `KR KM15 - KM17` ends at **POS 10** |
| FENI 15 | 15.0 | `KR KM12 - KM15` ends at **FENI U** |
| FENI 0 | 0.0 | `CRD KM0 - KM2,5` begins at **FENI** |

Every landmark is a named junction at the same chainage. The corridor is
correct; the database simply expresses it at 25 m resolution.

`DISPATCH ROADS` is the most useful of the five: for each origin-destination
pair it gives the **fraction of the haul crossing each named section**. That is
a ready-made route-to-segment decomposition, and it is the missing link between
segment speeds and a route-level cycle time.

### HRM / maintenance data

**Exists: yes.**

| Table | Rows | Date range | Contents |
|---|---|---|---|
| `FMS_HRM_SUPERVISION` (view) | 76,552 | 2026-06-01 → 2026-07-30 | Per-machine work with `LAT`/`LONG`, `SECTIONKM`, `EQUIPMENT_TYPE`, `HOURS`, `DISTANCE_M` |
| `HRM_INSPECTION` | 30,610 | from 2024-10 | Road defects by `KM_START`/`KM_END`, `SEVERITY`, `TYPE`, `STATUS` |
| `HRM_MAJOR_ROADWORK` | 149 | from 2024-10 | Campaigns by KM range, fleet, material, percent complete |
| `HRM_CONTRACT_EQUIPMENT` | 198 | — | Equipment committed per section by contractor |

- **Equipment types:** graders (`GD`) and excavators (`EX`) appear in
  `FMS_HRM_SUPERVISION.EQUIPMENT_TYPE`; `HRM_CONTRACT_EQUIPMENT` also lists
  `EXCA` and `DT`.
- **GPS points:** yes — `FMS_HRM_SUPERVISION` carries `LAT`/`LONG` per work record.
- **Road markers:** yes — `SECTIONKM` gives the chainage worked, and
  `HRM_INSPECTION` gives a `KM_START`/`KM_END` range plus an `STA`/`IDLINK`
  chainage string such as `KR15+500`.

`HRM_INSPECTION` is the more valuable one for the simulator: 30,610
road-condition observations by KM and severity going back to 2024-10. Road
condition plausibly drives cycle-time variance and, unlike truck count, it is
not chosen in response to how the shift is going.

### FMS_CONGESTION_SEG analysis

| Property | Value |
|---|---|
| Rows | 34,988 |
| Date range | 2026-07-15 → 2026-07-30 |
| Distinct `SEG_ID` | **95** |
| Directions | `up`, `down` |
| Columns | `HOUR_TS`, `SEG_ID`, `DIR`, `SUM_SPD`, `FIX_N`, `TRUCK_N`, `SUM_TRAV_MS`, `TRAV_N`, `UPDATED_AT` |

**Source:** derived from the GPS feed. `FIX_N` counts the GPS fixes aggregated
into each segment-hour and `SUM_SPD` sums their speeds, so mean speed is
`SUM_SPD / FIX_N`. Its 2026-07-15 start matches `FMS_GPS_Historical` exactly,
confirming it is computed from those tracks rather than supplied separately.

**Vehicle types:** `TRUCK_N` counts distinct units contributing to that
segment-hour. The table carries no unit-type column, so it cannot be
decomposed into haul trucks versus other vehicles from this table alone —
that would need a join back to the track data via unit identity. Given the
feed is dominated by haul trucks, `TRUCK_N` is *predominantly* haul trucks,
but that is an inference, not a measurement.

**Measured values:** mean speed per segment-hour has a median of **17.2 km/h**
(p5 7.6, p95 26.5). `TRUCK_N` has a median of 10 and a max of 69.
`SUM_TRAV_MS`/`TRAV_N` give measured traverse time per segment.

Segments are 1 km, named by road: `BLB KM2-3` … `BLB KM19-20`, `CBB KM7-8` …
`CBB KM16-17`, `CBBB KM15-16`, `CBBB KM16-17`, `CRD KM0-1` … `CRD KM6-7`, plus
`KR` and `TF` ranges — 95 in total, matching the road vocabulary in
`ALL_HR_KM_SECTIONS`.

**This is the segment-level speed the simulator was told it could not have.**

### Large tables the earlier keyword scan missed

Dropping the keyword filter surfaced four high-volume WBN_DATABASE tables that
had never been examined, and one of them bears directly on a published blocker.

| Table | Rows | Date range | Why it matters |
|---|---|---|---|
| `EQUIPMENTS_HOURLY_STATUS` | 16,558,379 | → 2026-07-29 | Hourly equipment state: working / standby / breakdown / PM hours with reason codes and location. Direct measurement of availability, currently an *assumed* 85% input to the simulator. |
| `EQUIPMENTS_HOURLY_ACTIVITIES` | 4,682,656 | → 2026-07-29 | **`TRUCK_ID` + `EXCAVATOR_ID` + `DISTANCE` + `RIT` on the same row**, hourly, with origin/destination and material. |
| `EQUIPMENTS_STATUS` | 3,680,170 | 2024-10-01 → 2026-07-29 | Shift-level equipment status with hour meters and `USAGE_KM_METER`. |
| `DAY_WORKS` | 495,592 | 2024-10-15 → 2026-07-25 | Per-activity records with `OPERATOR_ID`, `UNIT_TYPE`, `ROAD_NAME`, `ROAD_STA_KM`/`ROAD_END_KM`, `LOADING_POINT`, `LOADING_RIT`, `DISTANCE_KM`. |

**On loader assignment.** `EQUIPMENTS_HOURLY_ACTIVITIES` pairs 1,382 trucks with
436 excavators across 4.68M hourly rows — vastly more than the 408 rows in
`FMS_TRUCK_ASSIGNMENTS`. But its truck vocabulary is `ADT153`, `ADT168`,
`ADT167/165`, not the weighbridge's `A342`/`R707`. **This is where the real
namespace split lives**, and it is worse than a format difference: some values
are compound (`ADT167/165`, `ADT143/168`), meaning one row can cover two trucks.

So the position is nuanced rather than simply "blocked":

- `FMS_TRUCK_ASSIGNMENTS` gives excavator identity in **weighbridge format**,
  joinable today, but only 408 rows from 2026-01 onward.
- `EQUIPMENTS_HOURLY_ACTIVITIES` gives excavator identity at **scale over two
  years**, but needs an `ADT###` → `A###` mapping that has not been found in
  either database and may not exist.

`DAY_WORKS.OPERATOR_ID` holds operator **names** (18,559 distinct) rather than
the numeric employee IDs in `RES_EMPLOYEES`, so joining operator identity to
production would need name matching — workable but lossy, and worth flagging
before anyone assumes operator effects are cheap to measure.

`EQUIPMENTS_HOURLY_STATUS` is the most immediately useful of the four. The plan
simulator currently takes availability as a caller-supplied assumption
(default 85%); this table measures working, standby, breakdown and PM hours
per equipment per hour, so that assumption can be replaced with a measured
figure per contractor and fleet.

### Summary: what data exists for the simulator

| Feature needed | Available? | Table | Notes |
|---|---|---|---|
| Segment-level speed | **Yes, 2 weeks only** | `FMS_CONGESTION_SEG` | 95 segments, directional, median 17.2 km/h. Does not overlap the trip extract. |
| Raw GPS for haul trucks | **Yes, days only** | `FMS_PLAYBACK_TRACK_24H`, `FMS_GPS_Historical` | 479 of 945 units at 3-second fixes. Rolling retention. |
| Queue time at loading | **Yes** | `WAITING_TIME`, `FMS_GEOFENCE_VISITS` | 9.0 min median at the shovel; 14.1 min median across the pit geofence. The ~5 min gap is queue and manoeuvring. |
| Queue time at dumping | **Yes** | `WAITING_TIME`, `FMS_GEOFENCE_VISITS` | `DUMPING_DIFFERENCE_TIME`; 1,202 dumping-geofence visits. |
| Loader assignment | **Yes, two sources** | `FMS_TRUCK_ASSIGNMENTS`, `EQUIPMENTS_HOURLY_ACTIVITIES` | 408 rows joinable today in weighbridge format; 4.68M rows over two years in `ADT###` format needing an unfound mapping. |
| HRM fleet impact | **Yes** | `HRM_INSPECTION`, `FMS_HRM_SUPERVISION` | 30,610 road-condition records by KM/severity since 2024-10. |
| KM section definitions | **Yes** | `ALL_HR_KM_SECTIONS`, `HAUL_ROAD_STA`, `DISPATCH ROADS` | 27 named sections, 25 m chainage, and per-route section fractions. |
| GPS for haul trucks | **Yes** | `FMS_EQUIPMENTS` bridges the namespaces | 945 of 1,411 plates match the weighbridge. The earlier "0 of 940" was wrong. |
| Real haul distances | **Yes** | `DISTANCE_HAULING`, `EQUIPMENTS_HOURLY_ACTIVITIES.DISTANCE`, `DAY_WORKS.DISTANCE_KM` | Three sources. Replaces the placeholder `distance_km` (57 of 65 routes default to 25.0 km). |
| Truck availability | **Yes** | `EQUIPMENTS_HOURLY_STATUS` | 16.5M rows of working/standby/breakdown/PM hours. Replaces the assumed 85% availability input. |
| Operator identity | **Partial** | `WAITING_TIME.DRIVER_ID`, `DAY_WORKS.OPERATOR_ID`, `RES_EMPLOYEES` | `WAITING_TIME` carries a numeric driver ID per haul (joinable); `DAY_WORKS` carries 18,559 operator *names*, which would need fuzzy matching to `RES_EMPLOYEES`. |

### What this changes, in priority order

1. **The GPS claim is corrected.** Haul trucks are instrumented at 3-second
   resolution. The limit is retention, not instrumentation.
2. **Re-test congestion on `FMS_CONGESTION_SEG`.** It has measured speed *and*
   `TRUCK_N` per segment-hour. The weighbridge test failed because deployment is
   endogenous; a segment-hour test does not share that weakness in the same way.
   This could overturn the second published negative.
3. **Validate dwell against `FMS_GEOFENCE_VISITS`** — 15,100 measured pit visits
   overlapping the training period.
4. **Replace `distance_km`** with `DISTANCE_HAULING`.
5. **Add road condition** from `HRM_INSPECTION` as a cycle-time feature.
6. **Loader assignment is not blocked** — `FMS_TRUCK_ASSIGNMENTS` uses
   weighbridge truck format, contradicting the earlier namespace-split finding.

Items 2 and 3 are the ones that could most change the product.

