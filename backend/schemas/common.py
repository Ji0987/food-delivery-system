"""Pydantic schema 共用型別。"""

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


Money = Annotated[
    Decimal,
    Field(ge=Decimal("0.00"), max_digits=10, decimal_places=2),
]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)
