"""Pydantic boundary schemas."""

from app.schemas.common import BandScore, IeltsBand
from app.schemas.errors import APIErrorCode, APIErrorDetail, APIErrorResponse
from app.schemas.health import LivenessResponse, ReadinessResponse
from app.schemas.writing import (
    CriterionBandScores,
    CriterionEvaluation,
    EvaluationMetadata,
    ProviderEvaluationPayload,
    WritingCriteria,
    WritingCriterion,
    WritingEvaluationResponse,
    WritingEvaluationResult,
    WritingSubmission,
    aggregate_product_band,
    count_words,
)

__all__ = [
    "APIErrorCode",
    "APIErrorDetail",
    "APIErrorResponse",
    "BandScore",
    "CriterionBandScores",
    "CriterionEvaluation",
    "EvaluationMetadata",
    "IeltsBand",
    "LivenessResponse",
    "ReadinessResponse",
    "ProviderEvaluationPayload",
    "WritingCriteria",
    "WritingCriterion",
    "WritingEvaluationResponse",
    "WritingEvaluationResult",
    "WritingSubmission",
    "aggregate_product_band",
    "count_words",
]
