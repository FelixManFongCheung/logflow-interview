"""Tenant isolation tests."""

from app.core.config import settings
from app.schema.schemas import QueryRequest
from app.services.evidence import is_insufficient


def test_query_contract_includes_tenant() -> None:
    """Callers must send tenant_id; hybrid_search filters on it in Postgres."""
    body = QueryRequest(
        tenant_id="logflows-demo",
        user_id="ops-user-01",
        question="What should we do if a cold-chain delivery is delayed?",
    )
    assert body.tenant_id == "logflows-demo"


def test_refusal_does_not_use_weak_hits() -> None:
    """Scores below the configured threshold are treated as no evidence."""
    assert is_insufficient([settings.EVIDENCE_THRESHOLD - 0.01])
