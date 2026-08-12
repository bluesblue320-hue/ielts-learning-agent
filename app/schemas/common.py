"""Stable foundation domain value schemas."""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field


IeltsBand = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("9"), multiple_of=Decimal("0.5")),
]


class BandScore(BaseModel):
    """Validated IELTS band value without evaluation behavior."""

    value: IeltsBand
