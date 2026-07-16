"""餐廳與菜單 schema。"""

from datetime import datetime

from pydantic import Field

from backend.schemas.common import Money, ORMModel


class RestaurantCreate(ORMModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    address: str | None = None
    phone: str | None = Field(default=None, max_length=20)


class RestaurantResponse(ORMModel):
    id: int
    name: str
    description: str | None
    address: str | None
    phone: str | None
    is_active: bool
    created_at: datetime


class MenuCategoryCreate(ORMModel):
    name: str = Field(min_length=1, max_length=50)
    sort_order: int = 0


class MenuCategoryUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    sort_order: int | None = None


class MenuCategoryResponse(ORMModel):
    id: int
    restaurant_id: int
    name: str
    sort_order: int


class MenuItemCreate(ORMModel):
    category_id: int | None = None
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    price: Money
    is_sold_out: bool = False


class MenuItemUpdate(ORMModel):
    category_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    price: Money | None = None
    is_sold_out: bool | None = None


class MenuItemResponse(ORMModel):
    id: int
    restaurant_id: int
    category_id: int | None
    name: str
    description: str | None
    price: Money
    is_sold_out: bool
    created_at: datetime
    updated_at: datetime


class RestaurantMenuResponse(ORMModel):
    restaurant: RestaurantResponse
    categories: list[MenuCategoryResponse]
    items: list[MenuItemResponse]
