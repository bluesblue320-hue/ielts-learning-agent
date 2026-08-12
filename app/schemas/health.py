"""Response schemas for foundation health APIs."""

from typing import Literal

from pydantic import BaseModel, model_validator


class LivenessResponse(BaseModel):
    """Response returned when the application process is alive."""

    status: Literal["ok"] = "ok"
    service: str = "ielts-learning-agent"


class ReadinessResponse(BaseModel):
    """Response describing whether required database access is available."""

    status: Literal["ready", "not_ready"]
    database: Literal["available", "unavailable"]

    @model_validator(mode="after")
    def validate_consistent_status(self) -> "ReadinessResponse":
        """Keep the overall and database readiness states consistent."""
        is_consistent = (self.status == "ready") == (self.database == "available")
        if not is_consistent:
            raise ValueError("readiness status must match database availability")
        return self
