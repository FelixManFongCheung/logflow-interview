# Inbound Receiving SOP (SOP-006)

**Document owner:** Inbound Operations | **Version:** 5.0 | **Effective date:** 2026-01-01  
**Applies to:** All inbound trailers at LOGFLOWS tenant warehouses (EU)  
**Related docs:** WH-ESC-002 (escalations), SOP-001 (reefer outbound), POL-HAZ-005 (ADR inbound)

## Purpose
This procedure covers every inbound trailer arriving at a LOGFLOWS tenant warehouse: appointment control, seal integrity, temperature capture, discrepancy holds, and WMS receipt posting. Do not skip steps to save time during peak — a missed seal photo or unposted short is a **process failure**, not a minor admin miss.

## Pre-arrival (T-60 to T-0)
Sixty minutes before the booked slot:

1. Gate clerk confirms appointment in WMS (status must be `CONFIRMED`).
2. Print expected ASN lines and attach to inbound clipboard `IB-*`.
3. Stage an empty door with working leveler; cones placed if door is shared.
4. If carrier ETA slips **> 15 minutes**, record delay code on appointment and notify **Docken coordinator** (see WH-ESC-002).
5. Do not give the door to another carrier without coordinator approval.

Radios on **DOCK-1**. After 21:00 local, **night supervisor** owns the door board.

## Seal, ID, and trailer condition
On arrival:

1. Verify driver photo ID matches transport order carrier and name.
2. Photograph seal **before** cutting; upload to WMS trip record.
3. Record seal number on inbound ticket; must match CMR/eCMR.
4. Walk-around: check for obvious damage, leak, or odor. ADR placards must match POL-HAZ-005 before doors open.

**Stop conditions** — do not open trailer:
- Seal broken, missing, or number mismatch
- No appointment or wrong site ASN
- ADR placard present but shipment not flagged ADR in WMS

Page **QC** and **security**; hold driver in gate office; photograph discrepancy.

## Temperature-controlled inbound
For reefer inbound, read logger and cab display **before first pallet moves**.

| Product class | Accept band (°C) | If out of band |
|---------------|------------------|----------------|
| Chilled | 2 to 8 | Do not unload; QC on QC-1 within 10 min |
| Frozen | -25 to -18 | Do not unload; QC on QC-1 within 10 min |
| Deep freeze | -30 to -25 | Do not unload; notify tenant QA |

QC decides quarantine (`HLD-QC-*`) or reject. This SOP does not replace **SOP-001** for outbound cold-chain delays on the same trailer.

## Unload, count, and holds
Unload against ASN line by line. Scan each handling unit (LPN or SSCC).

**Hold cage (red ticket)** required for:
- Short, over, or damaged cartons
- SKU not on ASN
- Temperature suspicion after partial unload (stop and re-seal)

Red ticket must include: SKU, expected qty, actual qty, photo, driver name, timestamp.

Do **not** put hold stock on an active pick face. Empty pick face on a live wave → escalate per **WH-ESC-002** after hold ticket is created.

After last pallet: clerk and driver both sign inbound ticket. **Photo-only POD is not accepted** for inbound.

## System close and exceptions
- Post receipt in WMS before driver leaves yard (status `RECEIVED`).
- WMS down: use paper inbound pack; enter within **30 minutes** of recovery.
- Never leave trailer sealed to building overnight without posted receipt or explicit **night-supervisor hold** code `NS-HOLD-*`.
- ADR label issues on inbound: follow **POL-HAZ-005** — do not stage at standard doors until labels verified.

## KPIs (informational)
Target dock-to-receipt time: **≤ 45 minutes** for standard dry; **≤ 60 minutes** for reefer with QC read. Missed KPI alone is not an escalation — repeated misses on same lane trigger ops review.

## Out of scope
Customer freight rates, customs brokerage, air IATA packing, and carrier payment disputes.
