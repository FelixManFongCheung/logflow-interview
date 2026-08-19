"""API response envelopes with HTTP status codes set at the router layer."""

from typing import Generic, Literal, TypeVar

from fastapi import Response
from pydantic import BaseModel, Field

T = TypeVar("T")


class BaseResponse(BaseModel):
    """Shared fields for success and error API envelopes."""

    success: bool
    message: str | None = None


class ErrorResponse(BaseResponse):
    """Failed request envelope returned with 4xx/5xx status codes."""

    success: Literal[False] = False
    error_code: str = Field(..., min_length=1, max_length=64)
    detail: str = Field(..., min_length=1, max_length=2000)


class CorrectResponse(BaseResponse, Generic[T]):
    """Successful request envelope returned with 2xx status codes."""

    success: Literal[True] = True
    data: T


class HealthData(BaseModel):
    """Liveness payload."""

    status: str = "ok"


def respond_correct(
    response: Response,
    data: T,
    *,
    status_code: int = 200,
    message: str | None = None,
) -> CorrectResponse[T]:
    """Bind a 2xx status and return a success envelope."""
    response.status_code = status_code
    return CorrectResponse(data=data, message=message)


def respond_error(
    response: Response,
    *,
    error_code: str,
    detail: str,
    status_code: int = 500,
    message: str | None = None,
) -> ErrorResponse:
    """Bind a 4xx/5xx status and return an error envelope."""
    response.status_code = status_code
    return ErrorResponse(error_code=error_code, detail=detail, message=message)
