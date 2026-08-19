# Incident Report INC-2026-014 — Reefer logger gap

**Report type:** Quality / Cold chain | **Status:** Closed — corrective actions in progress  
**Incident date:** 2026-03-12 | **Closed date:** 2026-03-28  
**Reporter:** M. Schulz (Transport Supervisor, HAM-01) | **Severity:** P2 (customer impact avoided)

## Summary
On 2026-03-12, shipment **SH-8891** (chilled yogurt, 18 pallets, Hamburg DC → ACME Berlin store 014) recorded a **22-minute data gap** on the Sensitech Temptale Ultra logger after a traffic delay on the A10 near Hanover. Customer delivery window was 06:00–09:30 (Tier A). Actual arrival: 09:18 — within window but at risk.

## Timeline (all times CET)

| Time | Event |
|------|-------|
| 04:55 | Trailer departs HAM-01; logger active; set-point 4°C |
| 07:40 | Traffic delay reported; driver calls dispatch |
| 07:42 | QC on-call notified per SOP-001 (`CC-DELAY-30`) |
| 07:48 | Cab display read 5°C; logger still logging |
| 08:05–08:27 | **Logger gap** — no datapoints (device firmware freeze after power fluctuation) |
| 08:30 | Traffic clears; cab display 5°C |
| 08:45 | QC reviews manual cab readings + post-gap logger trace |
| 09:18 | Delivery at ACME 014; wet-ink POD obtained |

## What happened
Driver followed **SOP-001 delay procedure** and notified QC within 10 minutes. During the delay, cab display temperature remained at **5°C** (within ACME 2°C–6°C band and network chilled band). QC could not rely on logger trace for the gap period but accepted parallel evidence: cab photos, dispatcher GPS idle log, and post-gap logger recovery showing 5°C continuity.

QC released the load for delivery with notation `QC-REL-8891-CONDITIONAL`. No customer rejection. No quarantine.

## Root cause
Logger USB power bus reset during driver cab HVAC cycle while idling in traffic. Firmware v2.1.4 known issue — vendor patch v2.1.7 available.

## Corrective and preventive actions

| Action | Owner | Due | Status |
|--------|-------|-----|--------|
| Install spare logger in all HAM-01 reefers | Fleet maintenance | 2026-04-15 | In progress (12/18 units) |
| Upgrade Temptale firmware to v2.1.7 | QC | 2026-04-30 | Planned |
| Add logger gap > 5 min as auto-escalation in TMS | Engineering | 2026-05-15 | Backlog |
| Brief drivers on cab photo capture during delays | Transport | 2026-03-20 | Complete |

## Regulatory and policy notes
This incident does **not** change the 30-minute delay notification rule or 15-minute out-of-band quarantine rule in **SOP-001**. If temperature had exceeded band during the gap, load would have been quarantined regardless of eventual recovery.

## Out of scope
Carrier penalty calculation, insurance claim, and ACME chargeback — pending Revenue Ops review (not documented here).
