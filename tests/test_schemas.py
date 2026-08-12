"""Tests for Phase 1 Pydantic schemas."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.common import BandScore
from app.schemas.health import LivenessResponse, ReadinessResponse


@pytest.mark.parametrize(
    "value",
    [
        Decimal("0"),
        Decimal("0.5"),
        Decimal("5"),
        Decimal("5.5"),
        Decimal("9"),
    ],
)
def test_valid_ielts_band_values(value: Decimal) -> None:
    score = BandScore(value=value)

    assert score.value == value


@pytest.mark.parametrize(
    "value",
    [Decimal("-0.5"), Decimal("5.3"), Decimal("9.5")],
)
def test_invalid_ielts_band_values(value: Decimal) -> None:
    with pytest.raises(ValidationError):
        BandScore(value=value)


def test_liveness_response_has_stable_defaults() -> None:
    response = LivenessResponse()

    assert response.model_dump() == {
        "status": "ok",
        "service": "ielts-learning-agent",
    }


@pytest.mark.parametrize(
    ("status", "database"),
    [("ready", "available"), ("not_ready", "unavailable")],
)
def test_readiness_response_accepts_consistent_states(
    status: str,
    database: str,
) -> None:
    response = ReadinessResponse(status=status, database=database)

    assert response.status == status
    assert response.database == database


@pytest.mark.parametrize(
    ("status", "database"),
    [("ready", "unavailable"), ("not_ready", "available")],
)
def test_readiness_response_rejects_inconsistent_states(
    status: str,
    database: str,
) -> None:
    with pytest.raises(ValidationError, match="database availability"):
        ReadinessResponse(status=status, database=database)
