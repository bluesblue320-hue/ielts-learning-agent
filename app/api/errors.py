"""Central safe API failure mapping for writing evaluation."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.llm.provider import ProviderError, ProviderErrorCategory
from app.schemas.errors import APIErrorCode, APIErrorDetail, APIErrorResponse
from app.services.writing_persistence import WritingPersistenceError


@dataclass(frozen=True, slots=True)
class ProviderAPIErrorPolicy:
    status_code: int
    code: APIErrorCode
    message: str


PROVIDER_API_ERROR_POLICIES: Final = MappingProxyType(
    {
        ProviderErrorCategory.CONFIGURATION: ProviderAPIErrorPolicy(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            APIErrorCode.PROVIDER_CONFIGURATION,
            "Writing evaluation provider is not configured.",
        ),
        ProviderErrorCategory.AUTHENTICATION: ProviderAPIErrorPolicy(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            APIErrorCode.PROVIDER_AUTHENTICATION,
            "Writing evaluation provider authentication failed.",
        ),
        ProviderErrorCategory.BILLING: ProviderAPIErrorPolicy(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            APIErrorCode.PROVIDER_BILLING_UNAVAILABLE,
            "Writing evaluation provider account is unavailable.",
        ),
        ProviderErrorCategory.TIMEOUT: ProviderAPIErrorPolicy(
            status.HTTP_504_GATEWAY_TIMEOUT,
            APIErrorCode.PROVIDER_TIMEOUT,
            "Writing evaluation provider timed out.",
        ),
        ProviderErrorCategory.RATE_LIMIT: ProviderAPIErrorPolicy(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            APIErrorCode.PROVIDER_RATE_LIMITED,
            "Writing evaluation provider is rate limited.",
        ),
        ProviderErrorCategory.TRANSIENT: ProviderAPIErrorPolicy(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            APIErrorCode.PROVIDER_UNAVAILABLE,
            "Writing evaluation provider is temporarily unavailable.",
        ),
        ProviderErrorCategory.INVALID_RESPONSE: ProviderAPIErrorPolicy(
            status.HTTP_502_BAD_GATEWAY,
            APIErrorCode.PROVIDER_INVALID_RESPONSE,
            "Writing evaluation provider returned an invalid response.",
        ),
        ProviderErrorCategory.REQUEST_REJECTED: ProviderAPIErrorPolicy(
            status.HTTP_502_BAD_GATEWAY,
            APIErrorCode.PROVIDER_REQUEST_REJECTED,
            "Writing evaluation provider rejected the request.",
        ),
    }
)


def _response(
    status_code: int,
    code: APIErrorCode,
    message: str,
    *,
    fields: list[str] | None = None,
) -> JSONResponse:
    payload = APIErrorResponse(
        error=APIErrorDetail(
            code=code,
            message=message,
            fields=fields or [],
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
    )


async def provider_error_handler(
    request: Request,
    error: ProviderError,
) -> JSONResponse:
    del request
    policy = PROVIDER_API_ERROR_POLICIES[error.category]
    return _response(policy.status_code, policy.code, policy.message)


async def persistence_error_handler(
    request: Request,
    error: WritingPersistenceError,
) -> JSONResponse:
    del request, error
    return _response(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        APIErrorCode.PERSISTENCE_UNAVAILABLE,
        "Writing evaluation could not be persisted.",
    )


async def request_validation_error_handler(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    del request
    fields = sorted(
        {
            ".".join(str(part) for part in item["loc"] if part != "body")
            for item in error.errors()
        }
        - {""}
    )
    return _response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        APIErrorCode.REQUEST_INVALID,
        "Request validation failed.",
        fields=fields,
    )


def register_error_handlers(application: FastAPI) -> None:
    """Register centralized error responses without exposing exception text."""

    application.add_exception_handler(ProviderError, provider_error_handler)
    application.add_exception_handler(
        WritingPersistenceError,
        persistence_error_handler,
    )
    application.add_exception_handler(
        RequestValidationError,
        request_validation_error_handler,
    )
