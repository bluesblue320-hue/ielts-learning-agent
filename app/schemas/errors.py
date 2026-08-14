"""Stable, safe API error response boundaries."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class APIErrorCode(StrEnum):
    REQUEST_INVALID = "request_invalid"
    PROVIDER_CONFIGURATION = "provider_configuration"
    PROVIDER_AUTHENTICATION = "provider_authentication"
    PROVIDER_BILLING_UNAVAILABLE = "provider_billing_unavailable"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_INVALID_RESPONSE = "provider_invalid_response"
    PROVIDER_REQUEST_REJECTED = "provider_request_rejected"
    PERSISTENCE_UNAVAILABLE = "persistence_unavailable"
    LEARNER_NOT_FOUND = "learner_not_found"
    EVALUATION_NOT_FOUND = "evaluation_not_found"
    EVALUATION_CONFLICT = "evaluation_conflict"
    LEARNING_SOURCE_INVALID = "learning_source_invalid"


class APIErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: APIErrorCode
    message: str = Field(min_length=1)
    fields: list[str] = Field(default_factory=list)


class APIErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: APIErrorDetail
