-- Ops Assistant: Azure SQL Schema
-- Core tables for real-time operational data
-- Idempotent: safe to re-run on an existing database.

IF OBJECT_ID('dbo.LiveOrders', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.LiveOrders (
        OrderId         UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
        OrderTime       DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        OrderType       NVARCHAR(20) NOT NULL,  -- 'in_store', 'mobile', 'drive_thru'
        DrinkType       NVARCHAR(20) NOT NULL,  -- 'hot', 'cold', 'food'
        Station         NVARCHAR(20) NOT NULL,  -- 'hot_bar', 'cold_bar', 'food'
        Status          NVARCHAR(20) NOT NULL,  -- 'queued', 'in_progress', 'completed'
        WaitTimeSecs    INT NULL,
        CompletedTime   DATETIME2 NULL,
        StoreId         NVARCHAR(20) NOT NULL
    );
END
GO

IF OBJECT_ID('dbo.StationMetrics', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.StationMetrics (
        MetricId        INT IDENTITY PRIMARY KEY,
        StoreId         NVARCHAR(20) NOT NULL,
        Station         NVARCHAR(20) NOT NULL,
        Timestamp       DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
        OrdersPerHour   INT NOT NULL,
        CapacityPct     DECIMAL(5,2) NOT NULL,   -- e.g., 120.50 means 120.5%
        StaffCount      INT NOT NULL,
        AvgWaitSecs     INT NOT NULL
    );
END
GO

IF OBJECT_ID('dbo.StaffAssignments', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.StaffAssignments (
        AssignmentId    INT IDENTITY PRIMARY KEY,
        StoreId         NVARCHAR(20) NOT NULL,
        EmployeeName    NVARCHAR(100) NOT NULL,
        Station         NVARCHAR(20) NOT NULL,
        ShiftStart      DATETIME2 NOT NULL,
        ShiftEnd        DATETIME2 NOT NULL,
        IsActive        BIT NOT NULL DEFAULT 1
    );
END
GO

IF OBJECT_ID('dbo.HourlyTargets', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.HourlyTargets (
        TargetId        INT IDENTITY PRIMARY KEY,
        StoreId         NVARCHAR(20) NOT NULL,
        HourOfDay       INT NOT NULL,           -- 0-23
        DayOfWeek       INT NOT NULL,           -- 0=Mon, 6=Sun
        TargetOrders    INT NOT NULL,
        MinStaff        INT NOT NULL
    );
END
GO

IF OBJECT_ID('dbo.MobileOrderQueue', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.MobileOrderQueue (
        QueueId         INT IDENTITY PRIMARY KEY,
        StoreId         NVARCHAR(20) NOT NULL,
        OrderId         UNIQUEIDENTIFIER NOT NULL,
        ScheduledTime   DATETIME2 NOT NULL,
        DrinkType       NVARCHAR(20) NOT NULL,
        Status          NVARCHAR(20) NOT NULL   -- 'pending', 'accepted', 'preparing'
    );
END
GO

-- View for current store snapshot
-- StaffCount is derived LIVE from StaffAssignments (source of truth)
-- so that staff moves are reflected immediately without waiting for
-- the next traffic-simulator metrics refresh.
CREATE OR ALTER VIEW dbo.vw_CurrentStoreStatus AS
SELECT 
    s.StoreId,
    s.Station,
    s.OrdersPerHour,
    s.CapacityPct,
    ISNULL(sa.LiveStaffCount, s.StaffCount) AS StaffCount,
    s.AvgWaitSecs,
    (SELECT COUNT(*) FROM dbo.LiveOrders o 
     WHERE o.StoreId = s.StoreId AND o.Station = s.Station 
     AND o.Status IN ('queued', 'in_progress')) AS ActiveOrders,
    (SELECT COUNT(*) FROM dbo.MobileOrderQueue m 
     WHERE m.StoreId = s.StoreId AND m.DrinkType = 
        CASE s.Station WHEN 'cold_bar' THEN 'cold' WHEN 'hot_bar' THEN 'hot' ELSE 'food' END
     AND m.Status = 'pending') AS PendingMobileOrders
FROM dbo.StationMetrics s
OUTER APPLY (
    SELECT COUNT(*) AS LiveStaffCount
    FROM dbo.StaffAssignments a
    WHERE a.StoreId = s.StoreId AND a.Station = s.Station AND a.IsActive = 1
) sa
WHERE s.Timestamp = (
    SELECT MAX(Timestamp) FROM dbo.StationMetrics 
    WHERE StoreId = s.StoreId AND Station = s.Station
);
