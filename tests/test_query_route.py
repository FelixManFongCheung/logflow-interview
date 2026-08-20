"""Query route tests."""

import pytest
from fastapi import Response
from pydantic import ValidationError

from app.api import query as query_api
from app.schema.schemas import QueryRequest


@pytest.mark.asyncio
async def test_query_happy_path_uses_retrieval_and_returns_citations(monkeypatch: pytest.MonkeyPatch) -> None:
    """Strong hits call the LLM and return citations."""
    hits = [
        {
            "document_id": "sop-001",
            "chunk_id": "logflows-demo:sop-001:0",
            "score": 0.82,
            "title": "Cold Chain SOP",
            "header_path": "Root > Delay",
            "metadata": {"h1": "Root"},
            "content": "If delayed more than 30 minutes, notify QC.",
            "is_primary_hit": True,
        }
    ]

    async def fake_hybrid_search(
        tenant_id: str,
        question: str,
        match_count: int | None = None,
        role: str = "ops",
    ) -> list[dict]:
        return hits

    async def fake_generate_answer(question: str, context_blocks: list[str]) -> str:
        assert "PRIMARY SOURCE" in context_blocks[0]
        assert "document_id: sop-001" in context_blocks[0]
        assert "header_path:" in context_blocks[0]
        return "Notify QC within 10 minutes and document logger status."

    monkeypatch.setattr(query_api, "hybrid_search", fake_hybrid_search)
    monkeypatch.setattr(query_api, "generate_answer", fake_generate_answer)

    body = QueryRequest(
        tenant_id="logflows-demo",
        user_id="ops-user-01",
        role="ops",
        question="What should we do if a cold-chain delivery is delayed?",
    )
    result = await query_api.query(body, Response())

    assert result.success is True
    assert result.data.insufficient_evidence is False
    assert "Notify QC" in result.data.answer
    assert len(result.data.citations) == 1
    assert result.data.citations[0].document_id == "sop-001"


@pytest.mark.asyncio
async def test_query_citations_exclude_section_context_siblings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Section-expanded siblings feed the LLM but are not returned as citations."""
    hits = [
        {
            "document_id": "sop-001",
            "chunk_id": "logflows-demo:sop-001:3",
            "score": 0.82,
            "is_primary_hit": True,
            "title": "Cold Chain SOP",
            "header_path": "Root > Delay",
            "metadata": {"h2": "Delay procedure"},
            "content": "Step 1: notify QC.",
        },
        {
            "document_id": "sop-001",
            "chunk_id": "logflows-demo:sop-001:4",
            "score": 0.82,
            "is_primary_hit": False,
            "title": "Cold Chain SOP",
            "header_path": "Root > Delay",
            "metadata": {"h2": "Delay procedure"},
            "content": "Step 2: record temperature.",
        },
    ]

    captured: dict[str, list[str]] = {}

    async def fake_hybrid_search(
        tenant_id: str,
        question: str,
        match_count: int | None = None,
        role: str = "ops",
    ) -> list[dict]:
        return hits

    async def fake_generate_answer(question: str, context_blocks: list[str]) -> str:
        captured["context_blocks"] = context_blocks
        return "Follow the delay procedure [sop-001]."

    monkeypatch.setattr(query_api, "hybrid_search", fake_hybrid_search)
    monkeypatch.setattr(query_api, "generate_answer", fake_generate_answer)

    body = QueryRequest(
        tenant_id="logflows-demo",
        user_id="ops-user-01",
        role="ops",
        question="What should we do if a cold-chain delivery is delayed?",
    )
    result = await query_api.query(body, Response())

    assert result.success is True
    assert len(result.data.citations) == 1
    assert result.data.citations[0].chunk_id == "logflows-demo:sop-001:3"
    assert len(captured["context_blocks"]) == 2
    assert "SECTION CONTEXT" in captured["context_blocks"][1]


@pytest.mark.asyncio
async def test_query_insufficient_evidence_skips_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Low-score hits refuse without calling the LLM."""

    async def fake_hybrid_search(
        tenant_id: str,
        question: str,
        match_count: int | None = None,
        role: str = "ops",
    ) -> list[dict]:
        return [
            {
                "document_id": "doc-1",
                "chunk_id": "logflows-demo:doc-1:0",
                "score": 0.05,
                "title": "Unknown",
                "header_path": None,
                "metadata": {},
                "content": "weak hit",
            }
        ]

    async def fake_generate_answer(question: str, context_blocks: list[str]) -> str:
        raise AssertionError("LLM should not run when evidence is insufficient")

    monkeypatch.setattr(query_api, "hybrid_search", fake_hybrid_search)
    monkeypatch.setattr(query_api, "generate_answer", fake_generate_answer)

    body = QueryRequest(
        tenant_id="logflows-demo",
        user_id="ops-user-01",
        role="ops",
        question="What is ACME freight rate to Hamburg?",
    )
    result = await query_api.query(body, Response())

    assert result.success is True
    assert result.data.insufficient_evidence is True
    assert result.data.citations == []
    assert result.message == "insufficient_evidence"


@pytest.mark.asyncio
async def test_query_passes_tenant_and_role_to_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tenant and role from request should be passed into retrieval call."""
    observed: dict[str, str] = {}

    async def fake_hybrid_search(
        tenant_id: str,
        question: str,
        match_count: int | None = None,
        role: str = "ops",
    ) -> list[dict]:
        observed["tenant_id"] = tenant_id
        observed["role"] = role
        return []

    async def fake_generate_answer(question: str, context_blocks: list[str]) -> str:
        raise AssertionError("LLM should not run when no evidence")

    monkeypatch.setattr(query_api, "hybrid_search", fake_hybrid_search)
    monkeypatch.setattr(query_api, "generate_answer", fake_generate_answer)

    body = QueryRequest(
        tenant_id="tenant-abc",
        user_id="cs-user-01",
        role="cs",
        question="Show warehouse escalation process.",
    )
    result = await query_api.query(body, Response())

    assert observed["tenant_id"] == "tenant-abc"
    assert observed["role"] == "cs"
    assert result.data.insufficient_evidence is True


def test_query_request_rejects_malformed_payload() -> None:
    """Malformed input is rejected at schema validation layer."""
    with pytest.raises(ValidationError):
        QueryRequest(
            tenant_id="",
            user_id="ops-user-01",
            role="ops",
            question="ok",
        )
