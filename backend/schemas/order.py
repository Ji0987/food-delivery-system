"""訂單 schema。"""

from datetime import datetime

from backend.models.enums import OrderStatus, PaymentStatus
from backend.schemas.common import Money, ORMModel


class OrderItemResponse(ORMModel):
    id: int
    menu_item_id: int
    item_name_snapshot: str
    unit_price_snapshot: Money
    quantity: int
    subtotal: Money


class PaymentResponse(ORMModel):
    status: PaymentStatus
    amount: Money
    paid_at: datetime | None
    refunded_at: datetime | None


class OrderResponse(ORMModel):
    id: int
    consumer_user_id: int
    restaurant_id: int
    status: OrderStatus
    total_amount: Money
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemResponse]
    payment: PaymentResponse


class OrderStatusUpdate(ORMModel):
    status: OrderStatus
