"""配送任務與定位歷史資料模型。"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.types import UTCDateTime
from backend.models.utils import utc_now

if TYPE_CHECKING:
    from backend.models.order import Order
    from backend.models.user import User


class DeliveryAssignment(Base):
    """一筆訂單最多對應一位外送員的配送任務。"""

    __tablename__ = "delivery_assignments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), unique=True
    )
    courier_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    claimed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    picked_up_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    delivered_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    order: Mapped["Order"] = relationship(back_populates="delivery_assignment")
    courier: Mapped["User"] = relationship()
    locations: Mapped[list["DeliveryLocation"]] = relationship(
        back_populates="delivery_assignment", cascade="all, delete-orphan"
    )


class DeliveryLocation(Base):
    """配送任務的單次位置回報。"""

    __tablename__ = "delivery_locations"
    __table_args__ = (
        Index(
            "ix_delivery_locations_assignment_recorded_at",
            "delivery_assignment_id",
            "recorded_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    delivery_assignment_id: Mapped[int] = mapped_column(
        ForeignKey("delivery_assignments.id", ondelete="RESTRICT"), index=True
    )
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6, asdecimal=True))
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6, asdecimal=True))
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)

    delivery_assignment: Mapped["DeliveryAssignment"] = relationship(
        back_populates="locations"
    )
