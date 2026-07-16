"""外送搶單與位置追蹤 API 的請求／回應模型。"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import Field

from backend.models.enums import OrderStatus
from backend.schemas.common import Money, ORMModel
from backend.schemas.order import OrderItemResponse


Latitude = Annotated[
    Decimal,
    Field(
        ge=Decimal("-90"),
        le=Decimal("90"),
        max_digits=8,
        decimal_places=6,
    ),
]
Longitude = Annotated[
    Decimal,
    Field(
        ge=Decimal("-180"),
        le=Decimal("180"),
        max_digits=9,
        decimal_places=6,
    ),
]


class AvailableOrderResponse(ORMModel):
    """外送員搶單前可見的最小訂單資訊。"""

    id: int
    restaurant_id: int
    status: OrderStatus
    total_amount: Money
    created_at: datetime
    items: list[OrderItemResponse]


class DeliveryAssignmentResponse(ORMModel):
    id: int
    order_id: int
    courier_user_id: int
    claimed_at: datetime
    picked_up_at: datetime | None
    delivered_at: datetime | None


class DeliveryLocationCreate(ORMModel):
    latitude: Latitude
    longitude: Longitude


class DeliveryLocationResponse(ORMModel):
    id: int
    delivery_assignment_id: int
    latitude: Latitude
    longitude: Longitude
    recorded_at: datetime
