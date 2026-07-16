"""餐廳、分類與餐點資料模型。"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.types import MoneyAmount, UTCDateTime
from backend.models.utils import utc_now

if TYPE_CHECKING:
    from backend.models.cart import CartItem
    from backend.models.order import Order, OrderItem
    from backend.models.user import User


class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), unique=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now
    )

    owner: Mapped["User"] = relationship(back_populates="restaurant")
    categories: Mapped[list["MenuCategory"]] = relationship(
        back_populates="restaurant", cascade="all, delete-orphan"
    )
    menu_items: Mapped[list["MenuItem"]] = relationship(back_populates="restaurant")
    orders: Mapped[list["Order"]] = relationship(back_populates="restaurant")


class MenuCategory(Base):
    __tablename__ = "menu_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    restaurant: Mapped[Restaurant] = relationship(back_populates="categories")
    menu_items: Mapped[list["MenuItem"]] = relationship(back_populates="category")


class MenuItem(Base):
    __tablename__ = "menu_items"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_menu_item_price_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("menu_categories.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(MoneyAmount())
    is_sold_out: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utc_now, onupdate=utc_now
    )

    restaurant: Mapped[Restaurant] = relationship(back_populates="menu_items")
    category: Mapped[MenuCategory | None] = relationship(back_populates="menu_items")
    cart_items: Mapped[list["CartItem"]] = relationship(back_populates="menu_item")
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="menu_item")
