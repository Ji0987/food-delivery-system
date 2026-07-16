"""使用者資料模型。"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import UserRole
from backend.models.types import UTCDateTime
from backend.models.utils import utc_now

if TYPE_CHECKING:
    from backend.models.cart import Cart
    from backend.models.menu import Restaurant
    from backend.models.order import Order


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
            validate_strings=True,
            create_constraint=True,
        )
    )
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now
    )

    restaurant: Mapped["Restaurant | None"] = relationship(back_populates="owner")
    cart: Mapped["Cart | None"] = relationship(back_populates="consumer")
    orders: Mapped[list["Order"]] = relationship(back_populates="consumer")
