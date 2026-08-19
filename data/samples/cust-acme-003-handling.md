# Customer Handling Notes — ACME Retail (CUST-ACME-003)

**Customer code:** ACME-DE | **Tenant:** logflows-demo | **Lane:** DE national store delivery  
**Account manager:** L. Fischer (not in this document) | **Last updated:** 2026-02-20  
**Related docs:** SOP-001 (cold chain — ACME override band), SOP-006 (inbound if cross-dock)

## Account overview
ACME Retail operates 340 stores in Germany. LOGFLOWS handles chilled and ambient store deliveries from Hamburg DC (HAM-01) and Berlin cross-dock (BER-XD). This sheet covers delivery windows, site constraints, and POD rules — **not** pricing, rebates, or fuel surcharges.

## Delivery windows

| Store tier | Sites | Inbound window (local) | Late policy |
|------------|-------|------------------------|-------------|
| Tier A (high volume) | 001–050 | 06:00–09:30 | Rebook same day only if slot open; otherwise next day |
| Tier B (standard) | 051–200 | 06:00–11:00 | After 11:00 → rebook; **do not wait on site** |
| Tier C (rural) | 201–340 | 07:00–12:00 | 30-minute grace with store manager call |

All times are **store local**. TMS enforces hard stops — drivers cannot check in after window close.

## Site access and equipment

| Store code pattern | Dock type | Tail-lift | Notes |
|--------------------|-----------|-----------|-------|
| A1–A4 | Dock leveler | Not required | CHEP exchange mandatory |
| B1–B9 | Ground bay | Required | Max vehicle height 3.2 m |
| C* (rural) | Street unload | Required | Call store 30 min before arrival |

## Special handling
- **Pallet exchange:** ACME requires **CHEP pallets only**; LPR blue pallets rejected at gate.
- **Mixed SKU pallets:** Not allowed for chilled — one SKU per pallet face visible.
- **POD:** Must include **wet-ink store stamp** on signed delivery note. Photo POD and ePOD without stamp are **not accepted** and will be billed as failed delivery.
- **Temperature:** ACME chilled max is **6°C** (stricter than network default 8°C in SOP-001). Frozen follows network band.
- **Hazardous:** ACME stores do not accept ADR deliveries — route ADR lanes to HUB-ADR only (not covered in rate card here).

## Exceptions and escalation
- If ACME rejects a load for temperature, keep trailer sealed, notify QC (SOP-001), and open CRM case `ACME-QC-*`.
- Shortages: store signs short on POD; do not leave extra unpalletized cartons "as a favor."
- Night deliveries are **not authorized** unless CRM shows approved exception id `ACME-NIGHT-*`.

## Contacts
Store inbound desk phone numbers and regional ACME logistics contacts are in **TMS → Customer Master → ACME-DE**. Freight rates, accessorial charges, and invoice disputes are handled by Revenue Operations — not listed in this knowledge base.

## Out of scope
Freight rates, payment terms, marketing co-op funds, and customs documentation for non-EU origin goods.
