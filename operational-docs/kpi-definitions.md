# KPI Definitions — Ops Assistant Metrics Guide

## Overview
This document defines every metric used by the Ops Assistant system. Each KPI includes its definition, how it's calculated, target ranges, and guidance on what actions to take when metrics are off-target. Use this as the reference for understanding what the Co-Pilot is reporting.

---

## 1. Orders Per Hour (OPH)

### Definition
The total number of orders processed per hour across all stations in the store.

### Calculation
```
Orders Per Hour = COUNT(orders completed in the last 60 minutes)
```
When measured for a specific station, it counts only orders assigned to that station.

### Target Ranges

| Rating | OPH (full store) | Interpretation |
|--------|-----------------|----------------|
| Excellent | > 110% of hourly target | Operating above expectations |
| On Track | 90–110% of hourly target | Normal operations |
| Behind | 70–89% of hourly target | Falling behind — investigate staffing or equipment |
| Critical | < 70% of hourly target | Significant issue — immediate action needed |

### Hourly Targets
Hourly targets vary by time of day and day of week. They are configured in the `HourlyTargets` table and reflect historical averages plus seasonal adjustments. Targets are reviewed and updated monthly by store management.

### What to Do When Off-Target
- **Behind (70–89%):** Check if a station is bottlenecked. Look at individual station OPH and capacity. A single overloaded station can drag down the whole store.
- **Critical (<70%):** Check for equipment failures, staffing gaps (no-show or unplanned absence), or an unusually low-traffic period. If traffic is normal but OPH is low, there's a throughput problem.

---

## 2. Capacity Percentage (Utilization)

### Definition
How much of a station's maximum throughput capacity is being used. A station at 100% capacity is operating at its theoretical maximum given current staffing.

### Calculation
```
Capacity % = (Current Orders Per Hour / (Staff Count × Per-Person Throughput)) × 100
```

Per-person throughput benchmarks:
| Station | Orders/Hour/Person |
|---------|--------------------|
| Hot Bar | 27 (midpoint of 25–30 range) |
| Cold Bar | 25 (midpoint of 22–28 range) |
| Food Station | 22 (midpoint of 20–25 range) |

**Example:** Cold bar with 2 staff and 52 orders/hour:
```
Capacity % = (52 / (2 × 25)) × 100 = 104%
```
This means cold bar is over capacity — orders are arriving faster than they can be made.

### Target Ranges

| Rating | Capacity % | Interpretation |
|--------|-----------|----------------|
| Underutilized | < 50% | Station is overstaffed — consider reallocating |
| Comfortable | 50–75% | Healthy operating range, has headroom for surges |
| Busy | 75–95% | Operating efficiently, limited surge absorption |
| At Capacity | 95–100% | No headroom — any increase in orders will create a queue |
| Overloaded | > 100% | Bottleneck — orders are queuing faster than completion. Wait times will climb. |

### What to Do When Off-Target
- **Underutilized (<50%):** This station has excess staff. Consider moving one person to a busier station.
- **At Capacity (95–100%):** Monitor closely. If order mix trends suggest an increase, proactively move staff now.
- **Overloaded (>100%):** Immediate action required. See Cold Bar Surge Playbook or Staffing Guidelines for reallocation rules. Every minute above 100% means growing wait times.

---

## 3. Average Wait Time (seconds)

### Definition
The average time between when an order enters the queue and when it is completed (handed to the customer), measured in seconds.

### Calculation
```
Avg Wait Time = AVG(CompletedTime - OrderTime) for orders completed in the measurement window
```
For active (in-progress) orders, estimated wait is:
```
Estimated Wait = Current Time - OrderTime
```

### Target Ranges

| Rating | Wait Time | Customer Experience |
|--------|----------|-------------------|
| Excellent | < 2 minutes (120 sec) | Customer delighted — fast, smooth experience |
| Good | 2–3 minutes (120–180 sec) | Customer satisfied — acceptable wait |
| Acceptable | 3–4 minutes (180–240 sec) | Customer notices the wait — edge of tolerance |
| Poor | 4–6 minutes (240–360 sec) | Customer frustrated — likely to mention it |
| Critical | > 6 minutes (360+ sec) | Customer upset — high risk of complaint or walkout |

### What to Do When Off-Target
- **Acceptable (3–4 min):** Check which station has the highest wait. Usually one station is dragging the average up. Consider preemptive reallocation.
- **Poor (4–6 min):** Activate the relevant surge playbook (cold bar or mobile). Reallocate staff immediately.
- **Critical (>6 min):** Escalate to shift supervisor. Consider temporary menu simplification or mobile order throttling. Apologize proactively to waiting customers.

### Station-Specific Wait Time Benchmarks

| Station | Good | Acceptable | Poor |
|---------|------|-----------|------|
| Hot Bar | < 2 min | 2–3.5 min | > 3.5 min |
| Cold Bar | < 2.5 min | 2.5–4 min | > 4 min |
| Food Station | < 3 min | 3–5 min | > 5 min |

Cold bar and food station have slightly higher acceptable times due to more complex preparation.

---

## 4. Pace vs Target Percentage

### Definition
How the store's current hourly order rate compares to the target for this specific hour and day of week. This is the single most important "are we on track?" metric.

### Calculation
```
Pace vs Target % = (Total Orders Per Hour / Hourly Target) × 100
```

### Target Ranges

| Rating | Pace % | Interpretation |
|--------|--------|----------------|
| Ahead | > 110% | Exceeding expectations — ensure staffing can sustain it |
| On Track | 90–110% | Normal — no action needed |
| Slightly Behind | 80–89% | Worth monitoring — check if a station is underperforming |
| Behind | 70–79% | Action needed — likely a staffing or bottleneck issue |
| Critical | < 70% | Major issue — investigate immediately |

### What to Do When Off-Target
- **Ahead (>110%):** Great news, but verify that wait times aren't climbing. High pace with rising waits means quality is dropping.
- **Slightly Behind (80–89%):** Look at the order mix. If mobile is high, orders may be coming in but backing up. Check station capacity.
- **Behind (<80%):** There's a throughput problem. Check: Is a station overloaded? Is a person missing? Is equipment down?

### Important Nuances
- Pace can be "on track" while a specific station is in crisis. Always check pace AND station-level metrics together.
- A pace above 110% in a low-target hour (e.g., 7pm) is less impressive than 95% during a high-target hour (e.g., 8am).
- Weather, local events, and holidays can make targets inaccurate. Use pace as a guide, not an absolute judgment.

---

## 5. Active Orders

### Definition
The total number of orders currently in either "queued" or "in_progress" status — work that is waiting to be done or actively being made.

### Target Ranges

| Rating | Active Orders (full store) | Interpretation |
|--------|--------------------------|----------------|
| Light | < 5 | Very manageable — low pressure |
| Normal | 5–15 | Standard operating load |
| Heavy | 15–25 | High load — monitor wait times closely |
| Overloaded | > 25 | Too many orders in queue — action needed immediately |

### Per-Station Guidance
- Any single station with > 8 active orders needs attention
- If a station's active orders exceed its orders-per-hour rate ÷ 6 (i.e., more than 10 minutes of backlog), it's falling behind

---

## 6. Pending Mobile Orders

### Definition
The number of mobile orders with status "pending" that are scheduled for pickup in the next 30 minutes. These are orders customers have placed but the store hasn't started making yet.

### Target Ranges

| Rating | Pending Mobile Orders | Interpretation |
|--------|----------------------|----------------|
| Normal | < 5 | Standard mobile volume |
| Elevated | 5–10 | Above normal — start monitoring drink type breakdown |
| Surge | > 10 | Mobile surge — activate Mobile Order Surge Playbook |

### What to Do When Off-Target
- **Elevated (5–10):** Check what type of drinks dominate. If mostly cold, cold bar should prepare. Brief the team.
- **Surge (>10):** Activate the Mobile Order Surge Playbook. Begin pre-staging cups and batch prep immediately.

---

## 7. Order Mix Percentages

### Definition
The breakdown of orders by drink type (hot, cold, food) and by channel (in-store, mobile, drive-thru), expressed as percentages of total orders in the last 30 minutes.

### Normal Ranges (varies by season and time of day)

**By Drink Type:**
| Season | Hot | Cold | Food |
|--------|-----|------|------|
| Winter (Nov–Feb) | 55–65% | 20–30% | 10–20% |
| Spring/Fall | 40–50% | 35–45% | 10–20% |
| Summer (Jun–Aug) | 25–35% | 50–60% | 10–20% |

**By Channel:**
| Metric | Normal Range | Watch Threshold |
|--------|-------------|-----------------|
| In-Store | 50–70% | — |
| Mobile | 20–35% | > 45% = mobile surge likely |
| Drive-Thru | 10–20% | > 30% = consider adding drive-thru staff |

### What to Do When Off-Target
- **Cold drinks > 60%:** Ensure cold bar staffing is adequate. If only 1 person, move someone to cold bar.
- **Mobile > 45%:** Activate mobile surge awareness. Check pending mobile orders for surge indicators.
- **Food > 25%:** Ensure food station has dedicated staff, especially during meal hours.

---

## Metric Refresh Rates

| Metric | How Often Updated | Data Source |
|--------|------------------|-------------|
| Orders Per Hour | Every 5 minutes (rolling 60-min window) | LiveOrders table |
| Capacity % | Every 5 minutes | StationMetrics table |
| Average Wait Time | Real-time (per order completion) | LiveOrders table |
| Pace vs Target | Every 5 minutes | Calculated from OPH and HourlyTargets |
| Active Orders | Real-time | LiveOrders table (queued + in_progress) |
| Pending Mobile Orders | Real-time | MobileOrderQueue table |
| Order Mix | Every 5 minutes (rolling 30-min window) | LiveOrders table |
