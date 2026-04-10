# Mobile Order Surge Playbook

## Overview
Mobile orders can create sudden demand spikes because customers place orders in bursts (e.g., an office placing 8 orders at once for a 10:15am pickup). Unlike in-store traffic, mobile surges arrive with no visual warning — the orders appear in the queue simultaneously. This playbook provides proactive response procedures.

## Trigger Conditions

A mobile order surge is declared when **any** of the following are true:

| Condition | Threshold | How to Check |
|-----------|-----------|-------------|
| Pending mobile orders (next 30 min) | > 150% of same-window yesterday | Mobile order pipeline / Co-Pilot forecast |
| Mobile order share of total orders | > 45% of order mix | Order mix breakdown |
| Mobile cold drink orders incoming | > 8 cold drinks in next 15 minutes | Mobile order pipeline by drink type |
| Burst detection | > 5 mobile orders received within 3 minutes | Real-time order feed |

## Severity Levels

| Level | Condition | Response |
|-------|-----------|----------|
| **Watch** | Mobile orders 120–150% of historical | Monitor closely, begin pre-staging |
| **Active Surge** | Mobile orders > 150% of historical | Execute Actions 1–3 immediately |
| **Critical Surge** | Mobile orders > 200% of historical OR wait times > 6 min | Execute all actions including throttling |

## Recommended Actions

### Action 1: Pre-Stage Cups and Supplies (Lead Time: Immediate)
**When:** Watch level or higher
**What:**
- Pull mobile order tickets and sort by scheduled pickup time
- Pre-label cups for the next 10 mobile orders (write names and drink details)
- Stage cups in chronological order on the mobile order staging area
- Ensure mobile pickup shelf is clear and organized

**Expected Impact:** Reduces per-order assembly time by 15–20 seconds, prevents confusion during high volume

### Action 2: Batch Prep Popular Items (Lead Time: 5 minutes)
**When:** Active Surge level
**What:** Identify the dominant drink type in the mobile pipeline and begin batch prep:

**If cold drinks dominate (>60% of mobile orders):**
- Pre-pull espresso shots in batches of 4–6
- Pre-fill cups with ice
- Pre-pour cold brew into 8–10 cups
- Stage milk alternatives (oat, almond) at cold bar

**If hot drinks dominate (>60% of mobile orders):**
- Pre-pull espresso shots in batches of 4–6
- Pre-steam milk in large pitchers (whole, oat)
- Stage cups with sleeves

**Expected Impact:** Batch prep absorbs 15–25% additional volume without adding headcount

### Action 3: Alert Staff and Reposition (Lead Time: 2 minutes)
**When:** Active Surge level
**What:**
1. Verbally announce to the floor: "Mobile surge incoming — [X] orders in the next [Y] minutes"
2. Designate one person as the **mobile order coordinator** — this person:
   - Manages the mobile order queue priority
   - Stages completed orders on the pickup shelf
   - Communicates timing to customers who arrive early
3. If possible, move one person from the lowest-utilization station to support the busiest station receiving mobile orders (usually cold bar)

**Constraint:** The mobile order coordinator should be the person at the register/POS if in-store foot traffic is low. If in-store is also busy, the shift supervisor should step in as coordinator.

### Action 4: Adjust Pickup Time Estimates (Lead Time: Immediate)
**When:** Active Surge and current wait time > 4 minutes
**What:**
- Update the mobile app's estimated pickup time to reflect actual wait (if POS system supports dynamic ETA)
- Standard adjustment: add 3–5 minutes to the default estimate during surge
- This sets customer expectations and reduces "where's my order?" interactions

### Action 5: Throttle Mobile Orders (Last Resort)
**When:** Critical Surge — mobile wait times exceed 8 minutes OR total station utilization exceeds 140%
**What:**
- Temporarily increase minimum mobile order lead time to 20 minutes (default is 10 minutes)
- If available, enable "high demand" messaging in the mobile app
- In extreme cases, temporarily pause mobile ordering for the most impacted drink category

**Duration:** Maximum 15 minutes, then reassess
**Constraint:** Requires shift supervisor approval. Document in shift report.

## Timing Guidance

| Time After Trigger | Expected Action |
|-------------------|-----------------|
| 0–2 minutes | Announce surge to floor, begin pre-staging cups (Action 1) |
| 2–5 minutes | Start batch prep for dominant drink type (Action 2) |
| 5–7 minutes | Reposition staff if needed (Action 3) |
| 7–10 minutes | Adjust ETAs if wait times climbing (Action 4) |
| 10+ minutes | Consider throttling only if KPIs are critical (Action 5) |

## Recovery

The surge is subsiding when:
- Pending mobile orders return to within 110% of historical average
- Mobile order wait times drop below 3 minutes
- Mobile pickup shelf has fewer than 3 uncollected orders

**Recovery steps:**
1. Return repositioned staff to original stations
2. Stop batch prep (use up staged items)
3. Re-enable normal mobile order lead times
4. Restock supplies consumed during surge (cups, lids, ice, milk)
5. Document in shift report: trigger time, peak volume, actions taken, resolution time

## Common Mobile Surge Patterns

| Pattern | When | Typical Duration | Notes |
|---------|------|-----------------|-------|
| Morning office orders | 8:30–9:30am weekdays | 20–30 minutes | Usually hot drinks, clustered by office building |
| Lunch pre-orders | 11:00–11:30am weekdays | 15–20 minutes | Mixed hot/cold, often include food |
| Afternoon pick-me-up | 2:00–3:30pm weekdays | 30–45 minutes | Mostly cold drinks, more gradual buildup |
| Weekend brunch | 10:00am–12:00pm Sat/Sun | 45–60 minutes | Mixed, high volume, sustained |
| Event-driven | Variable | Variable | Nearby events (sports, concerts) can cause unexpected spikes |
