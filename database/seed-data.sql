-- Ops Assistant: Demo Seed Data
-- Scenario: Store running with cold bar bottleneck + incoming mobile surge

-- Clear existing data to ensure idempotent seeding
DELETE FROM dbo.MobileOrderQueue WHERE StoreId = 'STORE-001';
DELETE FROM dbo.LiveOrders WHERE StoreId = 'STORE-001';
DELETE FROM dbo.StationMetrics WHERE StoreId = 'STORE-001';
DELETE FROM dbo.StaffAssignments WHERE StoreId = 'STORE-001';
DELETE FROM dbo.HourlyTargets WHERE StoreId = 'STORE-001';

-- Staffing
INSERT INTO dbo.StaffAssignments (StoreId, EmployeeName, Station, ShiftStart, ShiftEnd, IsActive)
VALUES 
    ('STORE-001', 'Sarah', 'hot_bar', DATEADD(HOUR, 6, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), DATEADD(HOUR, 14, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), 1),
    ('STORE-001', 'Mike', 'hot_bar', DATEADD(HOUR, 6, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), DATEADD(HOUR, 14, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), 1),
    ('STORE-001', 'Lisa', 'cold_bar', DATEADD(HOUR, 6, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), DATEADD(HOUR, 14, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), 1),
    ('STORE-001', 'James', 'cold_bar', DATEADD(HOUR, 6, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), DATEADD(HOUR, 14, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), 1),
    ('STORE-001', 'Emma', 'food', DATEADD(HOUR, 6, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), DATEADD(HOUR, 14, CAST(CAST(SYSUTCDATETIME() AS DATE) AS DATETIME2)), 1);

-- Station metrics (cold bar overloaded)
INSERT INTO dbo.StationMetrics (StoreId, Station, OrdersPerHour, CapacityPct, StaffCount, AvgWaitSecs)
VALUES
    ('STORE-001', 'hot_bar', 35, 60.00, 2, 120),
    ('STORE-001', 'cold_bar', 52, 125.00, 2, 310),
    ('STORE-001', 'food', 15, 40.00, 1, 90);

-- Hourly targets (all days, operating hours 6am-10pm)
-- DayOfWeek: 0=Mon, 6=Sun (Python weekday convention)
-- SQL Server DATEPART(WEEKDAY) returns 1=Sun..7=Sat → convert: (DATEPART(WEEKDAY,...)+5)%7
INSERT INTO dbo.HourlyTargets (StoreId, HourOfDay, DayOfWeek, TargetOrders, MinStaff) VALUES
-- Monday (0)
('STORE-001', 6, 0, 40, 3), ('STORE-001', 7, 0, 60, 4), ('STORE-001', 8, 0, 85, 5),
('STORE-001', 9, 0, 90, 5), ('STORE-001', 10, 0, 80, 5), ('STORE-001', 11, 0, 75, 4),
('STORE-001', 12, 0, 85, 5), ('STORE-001', 13, 0, 80, 5), ('STORE-001', 14, 0, 70, 4),
('STORE-001', 15, 0, 65, 4), ('STORE-001', 16, 0, 70, 4), ('STORE-001', 17, 0, 75, 4),
('STORE-001', 18, 0, 60, 3), ('STORE-001', 19, 0, 45, 3), ('STORE-001', 20, 0, 30, 2),
('STORE-001', 21, 0, 20, 2),
-- Tuesday (1)
('STORE-001', 6, 1, 40, 3), ('STORE-001', 7, 1, 60, 4), ('STORE-001', 8, 1, 85, 5),
('STORE-001', 9, 1, 90, 5), ('STORE-001', 10, 1, 80, 5), ('STORE-001', 11, 1, 75, 4),
('STORE-001', 12, 1, 85, 5), ('STORE-001', 13, 1, 80, 5), ('STORE-001', 14, 1, 70, 4),
('STORE-001', 15, 1, 65, 4), ('STORE-001', 16, 1, 70, 4), ('STORE-001', 17, 1, 75, 4),
('STORE-001', 18, 1, 60, 3), ('STORE-001', 19, 1, 45, 3), ('STORE-001', 20, 1, 30, 2),
('STORE-001', 21, 1, 20, 2),
-- Wednesday (2)
('STORE-001', 6, 2, 40, 3), ('STORE-001', 7, 2, 60, 4), ('STORE-001', 8, 2, 85, 5),
('STORE-001', 9, 2, 90, 5), ('STORE-001', 10, 2, 80, 5), ('STORE-001', 11, 2, 75, 4),
('STORE-001', 12, 2, 85, 5), ('STORE-001', 13, 2, 80, 5), ('STORE-001', 14, 2, 70, 4),
('STORE-001', 15, 2, 65, 4), ('STORE-001', 16, 2, 70, 4), ('STORE-001', 17, 2, 75, 4),
('STORE-001', 18, 2, 60, 3), ('STORE-001', 19, 2, 45, 3), ('STORE-001', 20, 2, 30, 2),
('STORE-001', 21, 2, 20, 2),
-- Thursday (3)
('STORE-001', 6, 3, 40, 3), ('STORE-001', 7, 3, 60, 4), ('STORE-001', 8, 3, 85, 5),
('STORE-001', 9, 3, 90, 5), ('STORE-001', 10, 3, 80, 5), ('STORE-001', 11, 3, 75, 4),
('STORE-001', 12, 3, 85, 5), ('STORE-001', 13, 3, 80, 5), ('STORE-001', 14, 3, 70, 4),
('STORE-001', 15, 3, 65, 4), ('STORE-001', 16, 3, 70, 4), ('STORE-001', 17, 3, 75, 4),
('STORE-001', 18, 3, 60, 3), ('STORE-001', 19, 3, 45, 3), ('STORE-001', 20, 3, 30, 2),
('STORE-001', 21, 3, 20, 2),
-- Friday (4)
('STORE-001', 6, 4, 45, 3), ('STORE-001', 7, 4, 70, 4), ('STORE-001', 8, 4, 95, 5),
('STORE-001', 9, 4, 100, 6), ('STORE-001', 10, 4, 95, 5), ('STORE-001', 11, 4, 85, 5),
('STORE-001', 12, 4, 95, 5), ('STORE-001', 13, 4, 90, 5), ('STORE-001', 14, 4, 80, 5),
('STORE-001', 15, 4, 75, 4), ('STORE-001', 16, 4, 80, 5), ('STORE-001', 17, 4, 85, 5),
('STORE-001', 18, 4, 70, 4), ('STORE-001', 19, 4, 55, 3), ('STORE-001', 20, 4, 35, 2),
('STORE-001', 21, 4, 25, 2),
-- Saturday (5)
('STORE-001', 6, 5, 50, 3), ('STORE-001', 7, 5, 75, 4), ('STORE-001', 8, 5, 100, 6),
('STORE-001', 9, 5, 105, 6), ('STORE-001', 10, 5, 95, 5), ('STORE-001', 11, 5, 90, 5),
('STORE-001', 12, 5, 95, 5), ('STORE-001', 13, 5, 90, 5), ('STORE-001', 14, 5, 85, 5),
('STORE-001', 15, 5, 80, 5), ('STORE-001', 16, 5, 85, 5), ('STORE-001', 17, 5, 90, 5),
('STORE-001', 18, 5, 75, 4), ('STORE-001', 19, 5, 60, 3), ('STORE-001', 20, 5, 40, 3),
('STORE-001', 21, 5, 30, 2),
-- Sunday (6)
('STORE-001', 6, 6, 35, 2), ('STORE-001', 7, 6, 55, 3), ('STORE-001', 8, 6, 80, 5),
('STORE-001', 9, 6, 85, 5), ('STORE-001', 10, 6, 80, 5), ('STORE-001', 11, 6, 75, 4),
('STORE-001', 12, 6, 80, 5), ('STORE-001', 13, 6, 75, 4), ('STORE-001', 14, 6, 65, 4),
('STORE-001', 15, 6, 60, 3), ('STORE-001', 16, 6, 65, 4), ('STORE-001', 17, 6, 70, 4),
('STORE-001', 18, 6, 55, 3), ('STORE-001', 19, 6, 40, 3), ('STORE-001', 20, 6, 25, 2),
('STORE-001', 21, 6, 15, 2);

-- Mobile order surge incoming
INSERT INTO dbo.MobileOrderQueue (StoreId, OrderId, ScheduledTime, DrinkType, Status)
VALUES
    ('STORE-001', NEWID(), DATEADD(MINUTE, 5, SYSUTCDATETIME()), 'cold', 'pending'),
    ('STORE-001', NEWID(), DATEADD(MINUTE, 8, SYSUTCDATETIME()), 'cold', 'pending'),
    ('STORE-001', NEWID(), DATEADD(MINUTE, 10, SYSUTCDATETIME()), 'cold', 'pending'),
    ('STORE-001', NEWID(), DATEADD(MINUTE, 12, SYSUTCDATETIME()), 'hot', 'pending'),
    ('STORE-001', NEWID(), DATEADD(MINUTE, 15, SYSUTCDATETIME()), 'cold', 'pending'),
    ('STORE-001', NEWID(), DATEADD(MINUTE, 18, SYSUTCDATETIME()), 'cold', 'pending'),
    ('STORE-001', NEWID(), DATEADD(MINUTE, 20, SYSUTCDATETIME()), 'cold', 'pending'),
    ('STORE-001', NEWID(), DATEADD(MINUTE, 25, SYSUTCDATETIME()), 'cold', 'pending');
