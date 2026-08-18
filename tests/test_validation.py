"""Schema validation tests (no database required)."""

import pytest
from pydantic import ValidationError

from app.schemas import IngestRequest, QueryRequest


def test_query_requires_question() -> None:
    """Empty question is rejected before retrieval."""
    with pytest.raises(ValidationError):
        QueryRequest(tenant_id="logflows-demo", user_id="ops-user-01", question="")


def test_ingest_requires_documents() -> None:
    """Ingest with an empty document list is rejected."""
    with pytest.raises(ValidationError):
        IngestRequest(tenant_id="logflows-demo", documents=[])


def test_query_happy_shape() -> None:
    """Assignment query body is accepted."""
    body = QueryRequest(
        tenant_id="logflows-demo",
        user_id="ops-user-01",
        question="What should we do if a cold-chain delivery is delayed?",
    )
    assert body.role == "ops"
