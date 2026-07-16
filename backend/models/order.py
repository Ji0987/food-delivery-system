"""訂單、訂單快照與模擬付款資料模型。"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import OrderStatus, PaymentStatus
from backend.models.types import MoneyAmount, UTCDateTime
from backend.models.utils import utc_now

if TYPE_CHECKING:
    from backend.models.delivery import DeliveryAssignment
    from backend.models.menu import MenuItem, Restaurant
    from backend.models.user import User


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_order_total_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    consumer_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        Enum(
            OrderStatus,
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
            validate_strings=True,
            create_constraint=True,
        ),
        default=OrderStatus.PENDING,
        index=True,
    )
    total_amount: Mapped[Decimal] = mapped_column(MoneyAmount())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now
    )

    consumer: Mapped["User"] = relationship(back_populates="orders")
    restaurant: Mapped["Restaurant"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    payment: Mapped["Payment"] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    delivery_assignment: Mapped["DeliveryAssignment | None"] = relationship(
        back_populates="order", uselist=False, cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity >= 1", name="ck_order_item_quantity_positive"),
        CheckConstraint(
            "unit_price_snapshot >= 0", name="ck_order_item_price_nonnegative"
        ),
        CheckConstraint("subtotal >= 0", name="ck_order_item_subtotal_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    menu_item_id: Mapped[int] = mapped_column(
        ForeignKey("menu_items.id", ondelete="RESTRICT"), index=True
    )
    item_name_snapshot: Mapped[str] = mapped_column(String(100))
    unit_price_snapshot: Mapped[Decimal] = mapped_column(MoneyAmount())
    quantity: Mapped[int] = mapped_column()
    subtotal: Mapped[Decimal] = mapped_column(MoneyAmount())

    order: Mapped[Order] = relationship(back_populates="items")
    menu_item: Mapped["MenuItem"] = relationship(back_populates="order_items")


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_payment_amount_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), unique=True
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
            validate_strings=True,
            create_constraint=True,
        ),
        default=PaymentStatus.UNPAID,
    )
    amount: Mapped[Decimal] = mapped_column(MoneyAmount())
    paid_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    refunded_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    order: Mapped[Order] = relationship(back_populates="payment")
