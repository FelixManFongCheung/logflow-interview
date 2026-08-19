"""FastAPI routes for ingest, query, and health."""

from fastapi import APIRouter, Response

from app.api.ingest import router as ingest_router
from app.api.query import router as query_router
from app.schema.responses import CorrectResponse, HealthData, respond_correct

router = APIRouter()

router.include_router(ingest_router, prefix="/ingest", tags=["ingest"])
router.include_router(query_router, prefix="/documents/query", tags=["query"])


@router.get(
    "/health",
    response_model=CorrectResponse[HealthData],
    responses={
        200: {"model": CorrectResponse[HealthData], "description": "Service is healthy"},
    },
)
async def health(response: Response) -> CorrectResponse[HealthData]:
    """Liveness probe for local Docker and frontend checks."""
    return respond_correct(response, HealthData(), status_code=200, message="service_healthy")
