"""Tests for API response envelopes."""

from fastapi import Response

from app.schema.responses import CorrectResponse, HealthData, respond_correct, respond_error
from app.schema.schemas import IngestResponse, QueryResponse


def test_correct_response_envelope() -> None:
    """Success envelope wraps payload data."""
    http_response = Response()
    body = respond_correct(
        http_response,
        HealthData(),
        status_code=200,
        message="service_healthy",
    )
    assert http_response.status_code == 200
    assert body.success is True
    assert body.data.status == "ok"
    assert body.message == "service_healthy"


def test_error_response_envelope() -> None:
    """Error envelope sets non-2xx status."""
    http_response = Response()
    body = respond_error(
        http_response,
        error_code="ingest_failed",
        detail="connection refused",
        status_code=502,
        message="document_ingest_failed",
    )
    assert http_response.status_code == 502
    assert body.success is False
    assert body.error_code == "ingest_failed"
    assert body.detail == "connection refused"


def test_query_payload_fits_correct_response() -> None:
    """Query business payload nests under CorrectResponse.data."""
    payload = QueryResponse(
        answer="notify QC",
        citations=[],
        confidence="medium",
        insufficient_evidence=False,
    )
    wrapped = CorrectResponse(data=payload, message="query_answered")
    assert wrapped.success is True
    assert wrapped.data.answer == "notify QC"


def test_ingest_payload_fits_correct_response() -> None:
    """Ingest counts nest under CorrectResponse.data."""
    payload = IngestResponse(tenant_id="logflows-demo", documents=6, chunks=50)
    wrapped = CorrectResponse(data=payload, message="documents_ingested")
    assert wrapped.data.chunks == 50
    assert wrapped.data.chunks == 50
