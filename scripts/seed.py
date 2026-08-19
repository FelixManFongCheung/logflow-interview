"""Load sample logistics documents into a tenant via the ingest API helpers."""

import argparse
import asyncio
from pathlib import Path

from app.core.db import close_db, init_db
from app.services.retriever import ingest_documents

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"

DOCS = [
    {
        "id": "sop-001",
        "title": "Cold Chain SOP",
        "file": "sop-001-cold-chain.md",
        "visibility": "all",
    },
    {
        "id": "wh-esc-002",
        "title": "Warehouse Escalation Procedure",
        "file": "wh-esc-002-escalation.md",
        "visibility": "ops",
    },
    {
        "id": "cust-acme-003",
        "title": "Customer Handling Notes — ACME Retail",
        "file": "cust-acme-003-handling.md",
        "visibility": "all",
    },
    {
        "id": "inc-2026-014",
        "title": "Incident Report INC-2026-014 — Reefer logger gap",
        "file": "inc-2026-014-logger.md",
        "visibility": "ops",
    },
    {
        "id": "pol-haz-005",
        "title": "Shipment Policy — Hazardous goods labeling",
        "file": "pol-haz-005-labels.md",
        "visibility": "all",
    },
    {
        "id": "sop-006",
        "title": "Inbound Receiving SOP",
        "file": "sop-006-inbound-receiving.md",
        "visibility": "all",
    },
]


async def main(tenant_id: str) -> None:
    """Ingest bundled sample documents."""
    await init_db()
    documents = []
    for spec in DOCS:
        text = (SAMPLES / spec["file"]).read_text()
        documents.append(
            {
                "id": spec["id"],
                "title": spec["title"],
                "text": text,
                "visibility": spec["visibility"],
            }
        )
    result = await ingest_documents(tenant_id, documents)
    print(f"ingested tenant={tenant_id} documents={result['documents']} chunks={result['chunks']}")
    await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed sample logistics documents.")
    parser.add_argument("--tenant-id", default="logflows-demo")
    args = parser.parse_args()
    asyncio.run(main(args.tenant_id))
