# Warehouse Escalation Procedure (WH-ESC-002)

**Document owner:** Warehouse Operations — Central Dispatch  
**Effective date:** 2025-11-01 | **Version:** 2.4  
**Applies to:** All shift teams at LOGFLOWS-managed tenant warehouses (EU)

## Purpose
Defines when floor staff must escalate beyond normal supervisor coverage, who to contact, and what information to include. Escalation is not a failure — it protects safety, OTIF, and inventory accuracy.

## Severity levels

| Level | Name | Examples | Max response time |
|-------|------|----------|-------------------|
| P1 | Safety / regulatory | Injury, forklift collision, ADR leak, fire alarm | Immediate — call emergency services first |
| P2 | Customer impact | Missed ACME window, reefer dispatch blocked, wrong SKU on live wave | 10 minutes to shift lead |
| P3 | Operational | Empty pick face, dock blocked, WMS scanner outage | 20 minutes to shift lead |
| P4 | Admin | Label reprint, minor count variance < 2 units | Handle at team lead; no page |

## When to escalate (P2/P3 triggers)
Escalate to the shift lead when:

- A pick face is empty for an SKU on an active wave for more than **20 minutes** (include wave id, SKU, aisle, and units short).
- A dock door is blocked (broken leveler, trailer stuck, spill) and the next appointment is within **45 minutes**.
- WMS is offline and receipts or picks cannot be confirmed for more than **15 minutes** — invoke paper pack per SOP-006.
- A reefer trailer is staged outbound but QC has not released temperature checks (cross-ref SOP-001).
- A safety incident (near miss or injury) occurs — **always P1**.

## How to escalate
1. Page the shift lead on radio **OPS-LEAD** with: site code, location (aisle/door), wave or trip id, impact summary, and what you already tried.
2. If no response in **10 minutes**, page the warehouse manager on **OPS-MGR**.
3. P1 safety incidents skip the wait: call **112** (or local emergency number) first, then notify the manager and security.
4. Log every escalation in the shift handover book and WMS note field `ESC-*` within 30 minutes of resolution.

## Dock and appointment rules
- Do **not** reassign dock appointments without the **Docken coordinator** (day shift ext. 2205, night ext. 4412).
- Do **not** break a seal or open a reefer inbound without receiving clearance per SOP-006.
- Carrier no-shows after 30 minutes: record code `NS-30` and release the door only with coordinator approval.

## Contacts (EU network — demo tenant)

| Role | Day (06:00–21:00) | Night (21:00–06:00) |
|------|-------------------|---------------------|
| Shift lead | Radio OPS-LEAD | Radio OPS-LEAD |
| Warehouse manager | ext. 2201 | Night supervisor ext. 4410 |
| Docken coordinator | ext. 2205 | ext. 4412 |
| QC on-call (cold chain) | Radio QC-1 | Radio QC-1 → night supervisor |

Site-specific extensions are in the WMS **Site Directory** tile. This document does not list customer freight rates or HR disciplinary procedures.

## Do not
- Do not reassign dock appointments without the Docken coordinator.
- Do not put hold stock from receiving onto an active pick face (see SOP-006).
- Do not override a QC quarantine hold to meet a dispatch deadline.
