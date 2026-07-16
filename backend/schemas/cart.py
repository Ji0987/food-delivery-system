"""購物車 schema。"""

from pydantic import Field

from backend.schemas.common import Money, ORMModel


class CartItemCreate(ORMModel):
    menu_item_id: int
    quantity: int = Field(default=1, ge=1)


class CartItemUpdate(ORMModel):
    quantity: int = Field(ge=1)


class CartItemResponse(ORMModel):
    id: int
    menu_item_id: int
    name: str
    unit_price: Money
    quantity: int
    subtotal: Money
    is_sold_out: bool


class CartResponse(ORMModel):
    id: int
    items: list[CartItemResponse]
    total_amount: Money
