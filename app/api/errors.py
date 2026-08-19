"""Central safe API failure mapping for writing evaluation."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.llm.provider import ProviderError, ProviderErrorCategory
from app.memory.errors import (
    EpisodeNotFoundError,
    MemoryInvariantError,
    MemoryPersistenceError,
)
from app.schemas.errors import APIErrorCode, APIErrorDetail, APIErrorResponse
from app.services.learning_application import (
    CrossOwnerConflictError,
    EvaluationNotFoundError,
    LearnerNotFoundError,
    LearningPersistenceError,
    LearningSourceError,
)
from app.services.writing_persistence import WritingPersistenceError
from app.services.practice_completion import (
    PracticeCompletionPersistenceError,
    PracticeCompletionNotFoundError,
    PracticeCompletionOwnershipError,
    PracticeNotSubmittedError,
)
from app.services.practice_generation import (
    GeneratedPracticeAuthorityError,
    PracticeGenerationPersistenceError,
    RecommendationNotFoundError,
    RecommendationOwnershipError,
)
from app.services.practice_submission import (
    PracticeSubmissionPersistenceError,
    PracticeNotFoundError,
    PracticeOwnershipError,
)


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


async def learner_not_found_handler(
    request: Request,
    error: LearnerNotFoundError,
) -> JSONResponse:
    del request, error
    return _response(
        status.HTTP_404_NOT_FOUND,
        APIErrorCode.LEARNER_NOT_FOUND,
        "Learner not found.",
    )


async def evaluation_not_found_handler(
    request: Request,
    error: EvaluationNotFoundError,
) -> JSONResponse:
    del request, error
    return _response(
        status.HTTP_404_NOT_FOUND,
        APIErrorCode.EVALUATION_NOT_FOUND,
        "Writing evaluation not found.",
    )


async def cross_owner_conflict_handler(
    request: Request,
    error: CrossOwnerConflictError,
) -> JSONResponse:
    del request, error
    return _response(
        status.HTTP_409_CONFLICT,
        APIErrorCode.EVALUATION_CONFLICT,
        "Writing evaluation is already applied to another learner.",
    )


async def learning_source_error_handler(
    request: Request,
    error: LearningSourceError,
) -> JSONResponse:
    del request, error
    return _response(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        APIErrorCode.LEARNING_SOURCE_INVALID,
        "Persisted evaluation source data is invalid.",
    )


async def learning_persistence_error_handler(
    request: Request,
    error: LearningPersistenceError,
) -> JSONResponse:
    del request, error
    return _response(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        APIErrorCode.PERSISTENCE_UNAVAILABLE,
        "Learning data is temporarily unavailable.",
    )


async def practice_persistence_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    del request, error
    return _response(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        APIErrorCode.PERSISTENCE_UNAVAILABLE,
        "Writing practice data is temporarily unavailable.",
    )


async def generated_practice_authority_error_handler(
    request: Request,
    error: GeneratedPracticeAuthorityError,
) -> JSONResponse:
    del request, error
    return _response(
        status.HTTP_502_BAD_GATEWAY,
        APIErrorCode.PROVIDER_INVALID_RESPONSE,
        "Writing practice generator returned an invalid response.",
    )


async def episode_not_found_handler(
    request: Request,
    error: EpisodeNotFoundError,
) -> JSONResponse:
    del request, error
    return _response(
        status.HTTP_404_NOT_FOUND,
        APIErrorCode.EPISODE_NOT_FOUND,
        "Learning episode was not found.",
    )


async def memory_persistence_error_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    del request, error
    return _response(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        APIErrorCode.PERSISTENCE_UNAVAILABLE,
        "Learning memory data is temporarily unavailable.",
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
    register_learning_error_handlers(application)


def register_learning_error_handlers(application: FastAPI) -> None:
    """Register safe Phase 3 learning-application error responses."""

    application.add_exception_handler(
        LearnerNotFoundError,
        learner_not_found_handler,
    )
    application.add_exception_handler(
        EvaluationNotFoundError,
        evaluation_not_found_handler,
    )
    application.add_exception_handler(
        CrossOwnerConflictError,
        cross_owner_conflict_handler,
    )
    application.add_exception_handler(
        LearningSourceError,
        learning_source_error_handler,
    )
    application.add_exception_handler(
        LearningPersistenceError,
        learning_persistence_error_handler,
    )
    for error_type in (
        PracticeGenerationPersistenceError,
        PracticeSubmissionPersistenceError,
        PracticeCompletionPersistenceError,
    ):
        application.add_exception_handler(error_type, practice_persistence_error_handler)
    application.add_exception_handler(
        GeneratedPracticeAuthorityError,
        generated_practice_authority_error_handler,
    )
    for error_type in (
        PracticeCompletionNotFoundError,
        PracticeNotFoundError,
        RecommendationNotFoundError,
    ):
        application.add_exception_handler(error_type, practice_not_found_handler)
    for error_type in (
        PracticeCompletionOwnershipError,
        PracticeOwnershipError,
        RecommendationOwnershipError,
        PracticeNotSubmittedError,
    ):
        application.add_exception_handler(error_type, practice_conflict_handler)
    application.add_exception_handler(EpisodeNotFoundError, episode_not_found_handler)
    for error_type in (
        MemoryPersistenceError,
        MemoryInvariantError,
    ):
        application.add_exception_handler(error_type, memory_persistence_error_handler)


async def practice_not_found_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    del request, error
    return _response(
        status.HTTP_404_NOT_FOUND,
        APIErrorCode.PRACTICE_NOT_FOUND,
        "Writing practice was not found.",
    )


async def practice_conflict_handler(
    request: Request,
    error: Exception,
) -> JSONResponse:
    del request, error
    return _response(
        status.HTTP_409_CONFLICT,
        APIErrorCode.PRACTICE_CONFLICT,
        "Writing practice cannot be used in its current state.",
    )
