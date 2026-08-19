# Cold Chain SOP (SOP-001)

**Document owner:** Quality Control — Network Operations  
**Effective date:** 2026-01-15 | **Version:** 3.2 | **Review cycle:** Quarterly  
**Applies to:** All LOGFLOWS tenant DCs running reefer outbound (EU region)  
**Related docs:** SOP-006 (inbound receiving), INC-2026-014 (logger gap case study)

## Scope
Applies to all temperature-controlled (reefer) outbound deliveries for tenant warehouses. Covers pre-departure checks, in-transit monitoring, delay handling, and proof-of-delivery requirements. Does not cover ambient or controlled-atmosphere (CA) fruit lanes — see SOP-008.

## Pre-departure checks (dock staging)
Before a reefer trailer leaves the yard, the dock clerk must complete the following in WMS under trip id `TR-*`:

1. Confirm set-point matches the product class on the pick list (see temperature band table).
2. Download logger trace for the last 24 hours; gap longer than 5 minutes requires QC sign-off.
3. Photograph the trailer temperature display and attach to the trip record.
4. Verify seal number matches the outbound transport order; broken seal = do not dispatch.

Reefers staged more than 45 minutes before departure must be re-checked hourly. After 21:00 local, night supervisor signs off on any reefer held over 2 hours.

## Delay procedure
If a cold-chain delivery is delayed more than 30 minutes past the booked customer slot:

1. Notify the Quality Control (QC) on-call within 10 minutes (radio **QC-1** or TMS alert code `CC-DELAY-30`).
2. Record the current trailer temperature from the cab display **and** the data logger; both readings go on the delay form.
3. If temperature has exceeded the allowed band for more than 15 consecutive minutes, quarantine the load and do not deliver. Create hold ticket `HLD-QC-*` in WMS.
4. If temperature is still in band, proceed and add a delay note on the proof of delivery. Customer must receive SMS/email via TMS template `COLD-DELAY-NOTICE` if delay exceeds 60 minutes.

Drivers must not restart the reefer unit during QC review unless instructed by QC on-call.

## Allowed temperature band

| Product class | Min (°C) | Max (°C) | Set-point default | Action if out of band > 15 min |
|---------------|----------|----------|-------------------|--------------------------------|
| Chilled       | 2        | 8        | 4                 | Quarantine load; do not deliver |
| Frozen        | -25      | -18      | -20               | Quarantine load; do not deliver |
| Deep freeze   | -30      | -25      | -28               | Quarantine load; notify tenant QA |
| Ambient (exempt) | —     | —        | —                 | Not covered by this SOP; use standard delay procedure |

Logger readings must be recorded at check-in, at departure, and at any delay over 30 minutes. Acceptable logger models: Sensitech Temptale Ultra, ELPRO LIBERO CE.

## Customer-specific overrides
Some tenants publish stricter bands in customer handling notes. Where a customer document specifies a narrower range, the **customer document wins** for that lane. ACME Retail chilled max is 6°C (see CUST-ACME-003) — treat as 2°C to 6°C for ACME outbound.

## Escalation

| Situation | First contact | Backup (10 min no response) |
|-----------|---------------|-----------------------------|
| In-band delay, customer waiting | QC on-call (QC-1) | Night supervisor |
| Out-of-band temperature | QC on-call (QC-1) | Tenant QA lead + Transport manager |
| Logger gap during transit | QC on-call (QC-1) | Follow INC-2026-014 interim controls |

After 21:00 local, all cold-chain escalations route through the night supervisor (ext. 4410).

## Out of scope
Freight rates, customs brokerage, air-freight IATA packing, and carrier contract penalties are not covered here.
