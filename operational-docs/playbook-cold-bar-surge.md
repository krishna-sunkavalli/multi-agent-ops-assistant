# Cold Bar Surge Playbook

## Overview
This playbook provides step-by-step guidance for managing cold bar overload situations. Cold bar surges are the most common bottleneck during warm weather, afternoons, and weekend mornings when iced and blended drink demand spikes.

## Trigger Conditions

A cold bar surge is declared when **any two** of the following are true:

| Condition | Threshold | How to Check |
|-----------|-----------|-------------|
| Cold bar utilization | > 100% for more than 5 minutes | Station metrics dashboard or Co-Pilot status |
| Cold drink order mix | > 60% of total orders | Order mix breakdown |
| Cold drink wait time | Exceeds 4 minutes | Average wait time by station |
| Cold bar active queue | > 10 orders queued or in-progress | Active order count |
| Mobile cold orders pending | > 5 cold drink mobile orders in next 15 minutes | Mobile order pipeline |

## Recommended Actions (in priority order)

### Action 1: Reallocate Staff from Hot Bar
**When:** Hot bar utilization is below 70%
**What:** Move one barista from hot bar to cold bar
**Expected Impact:** Reduces cold bar wait time by 30–40% within 10 minutes
**Constraint:** Never reduce hot bar below 1 barista

To determine who to move:
- Prefer the barista with the most cold bar experience
- If equal experience, move the person whose shift ends latest (more remaining time)
- Avoid moving someone who just started a complex hot drink order

### Action 2: Initiate Batch Prep for High-Volume Cold Drinks
**When:** Cold bar queue exceeds 8 orders OR mobile pipeline shows 5+ cold orders incoming
**What:** Begin batch preparation of the top 3 cold drinks:
1. **Iced Latte** — pre-pull espresso shots (up to 6 at a time), stage cups with ice
2. **Cold Brew** — pre-pour cold brew into cups, stage with lids
3. **Iced Mocha** — pre-pump mocha sauce into cups, stage with ice

**Expected Impact:** Batch prep can absorb 15–20% additional volume without adding staff
**Constraint:** Only batch prep drinks that are in the current top 3 of the order mix. Do not batch prep drinks that aren't being ordered.

### Action 3: Pre-Stage Supplies
**When:** Surge is expected to last more than 20 minutes
**What:**
- Restock cold cups (all sizes) at cold bar station
- Ensure ice bins are full (request ice refill from back of house if below 50%)
- Move backup milk (oat, almond, whole) to cold bar reach-in
- Stage extra cold brew kegs if cold brew is in top 3

### Action 4: Temporarily Pause Mobile Ordering for Cold Drinks
**When:** Cold bar wait time exceeds 6 minutes AND cold bar utilization is above 130%
**What:** Use the POS system to temporarily disable mobile ordering for cold drink categories
**Expected Impact:** Reduces incoming cold bar volume by 20–35% (depending on mobile mix)
**Duration:** Maximum 15 minutes. Re-enable and reassess.
**Constraint:** This is a last resort. Notify the shift supervisor before pausing. Log the pause in the shift report.

### Action 5: Escalate to Shift Supervisor
**When:** Cold bar wait time exceeds 8 minutes despite Actions 1–3, OR the surge has lasted more than 30 minutes
**What:** Contact shift supervisor to:
- Approve calling in additional staff
- Authorize overtime for current staff
- Consider temporary menu simplification (e.g., suspend blended drinks)

## Recovery Indicators

The surge is resolving when:
- Cold bar utilization drops below 90% for 5 consecutive minutes
- Average cold drink wait time returns below 3 minutes
- Active cold bar queue is under 5 orders

**When recovered:**
1. Return reallocated staff to their original station
2. Stop batch prep (use up what's staged, don't make more)
3. Re-enable mobile ordering if it was paused
4. Document the surge in the shift report (time, duration, actions taken, peak wait time)

## Staffing Minimums During Surge Response

| Station | Minimum Staff | Notes |
|---------|--------------|-------|
| Hot bar | 1 barista | Can drop to 1 only if hot bar utilization < 70% |
| Cold bar | 2 baristas (3 during active surge) | Target 3 during any surge event |
| Food station | 1 person | Must maintain during meal hours (11am–2pm, 5pm–7pm) |
| Register/POS | 1 person | Cannot be reallocated during open hours |

## Historical Context

Based on analysis of the last 12 months:
- Cold bar surges occur most frequently between 2pm–5pm on weekdays and 10am–1pm on weekends
- Average surge duration is 25 minutes
- 78% of surges are resolved with Action 1 (staff reallocation) alone
- Surges requiring Action 4 (mobile pause) occur approximately twice per week in summer months
