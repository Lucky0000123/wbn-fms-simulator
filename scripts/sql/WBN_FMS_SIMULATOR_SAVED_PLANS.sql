-- WBN FMS Simulator — saved holding plans.
-- This table is ONLY the simulator's Plan-tab saves. It is not haulage, GPS,
-- weighbridge, or dispatch. Name is deliberate so it cannot be mistaken for
-- an operations table (HAULAGE_IWIP_CLEAN, WAITING_TIME, …).
--
-- Database: WBN_DATABASE
-- One row = one calendar date. plan_json is the exact saved-plan object the
-- app already writes to data/saved_plans/YYYY-MM-DD.json. Do not reshape it.
--
-- The app creates this table on first use if it is missing. Running this
-- script by hand is optional and idempotent.

IF OBJECT_ID(N'dbo.WBN_FMS_SIMULATOR_SAVED_PLANS', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.WBN_FMS_SIMULATOR_SAVED_PLANS (
        plan_date   DATE          NOT NULL,
        plan_json   NVARCHAR(MAX) NOT NULL,
        saved_at    DATETIME2     NULL,
        uploaded_at DATETIME2     NOT NULL
            CONSTRAINT DF_WBN_FMS_SIMULATOR_SAVED_PLANS_uploaded
            DEFAULT (SYSUTCDATETIME()),
        CONSTRAINT PK_WBN_FMS_SIMULATOR_SAVED_PLANS PRIMARY KEY (plan_date)
    );
END
GO
