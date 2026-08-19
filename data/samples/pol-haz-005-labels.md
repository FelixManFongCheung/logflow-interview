# Shipment Policy — Hazardous goods labeling (POL-HAZ-005)

**Document owner:** Compliance — Dangerous Goods  
**Effective date:** 2025-09-01 | **Version:** 4.1 | **Regulatory basis:** ADR 2025 (EU ground transport)  
**Applies to:** ADR-classified outbound and inbound pallets at LOGFLOWS tenant warehouses

## Scope
Applies to ADR-classified outbound pallets staged for road transport. Covers labeling, staging segregation, driver verification, and handoff to approved ADR carriers. Does **not** cover air freight (IATA), sea freight (IMDG), or customs brokerage.

## Labeling requirements
Each pallet must show the **UN number** and **class diamond** on **two adjacent sides** before staging at the dock. Labels must be ADR-compliant size (minimum 100 mm × 100 mm for diamonds) and unobstructed by stretch wrap.

For mixed-UN consolidation pallets, use the **overpack label** plus all inner UN numbers listed on the transport document.

## ADR reference table (common LOGFLOWS lanes)

| UN number | Proper shipping name (abbr.) | Class | Label type | Segregation group |
|-----------|------------------------------|-------|------------|-------------------|
| UN1203 | Gasoline | 3 | Flammable liquid | SG1 |
| UN1760 | Corrosive liquid, n.o.s. | 8 | Corrosive | SG8 |
| UN3077 | Environmentally hazardous solid | 9 | Miscellaneous | SG9 |
| UN1993 | Flammable liquid, n.o.s. | 3 | Flammable liquid | SG1 |

Missing, illegible, or wrong-class diamonds: **do not load**. Create compliance hold `HLD-ADR-*` and notify Compliance (ext. 3301).

## Staging and dock rules
- ADR pallets stage only at doors **D-ADR-1** and **D-ADR-2** with yellow floor markings.
- Minimum 5 m separation from non-ADR freight unless compatibility table ADR 7.5.2 allows otherwise.
- Fire extinguisher (6 kg ABC) must be present at ADR doors during loading — checked at shift start.

## Driver check (pre-departure)
1. Driver presents valid ADR driver certificate and vehicle kit checklist.
2. Driver photographs labels on **two sides** of each ADR pallet; photos attach to trip `TR-*` in TMS.
3. Driver signs electronic dangerous goods declaration (eDGD) in TMS before seal application.
4. Missing diamonds, wrong UN, or damaged labels: **do not load** — see escalation below.

## Escalation

| Issue | Action |
|-------|--------|
| Label missing at pick | Stop pick; Compliance re-label before staging |
| Label damaged at dock | Re-label; re-photograph; delay dispatch |
| Wrong UN on pallet vs. WMS | Quarantine pallet; inventory cycle count |

## Customer restrictions
Some retail customers (including **ACME Retail**) do not accept ADR deliveries at store sites. Route ADR freight to approved hubs only — see customer handling notes. ACME store delivery lanes must be ADR-free.

## Out of scope
Customs brokerage, air freight IATA packing, freight rates, carrier ADR surcharges, and tenant-specific exemption certificates (stored in Compliance vault, not this document).
