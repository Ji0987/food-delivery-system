"""消費者購物車 API。"""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import DatabaseSession, require_role
from backend.models.cart import Cart
from backend.models.enums import UserRole
from backend.models.user import User
from backend.schemas.cart import (
    CartItemCreate,
    CartItemResponse,
    CartItemUpdate,
    CartResponse,
)
from backend.services import cart_service
from backend.services.exceptions import ConflictRuleError, NotFoundRuleError


router = APIRouter(tags=["cart"])
ConsumerActor = Annotated[User, Depends(require_role(UserRole.CONSUMER))]


def _to_response(cart: Cart) -> CartResponse:
    items = [
        CartItemResponse(
            id=item.id,
            menu_item_id=item.menu_item_id,
            name=item.menu_item.name,
            unit_price=item.menu_item.price,
            quantity=item.quantity,
            subtotal=item.menu_item.price * item.quantity,
            is_sold_out=item.menu_item.is_sold_out,
        )
        for item in sorted(cart.items, key=lambda value: value.id)
    ]
    total = sum((item.subtotal for item in items), start=Decimal("0.00"))
    return CartResponse(id=cart.id, items=items, total_amount=total)


def _handle_cart_error(error: Exception) -> HTTPException:
    if isinstance(error, NotFoundRuleError):
        return HTTPException(status_code=404, detail=error.detail)
    if isinstance(error, ConflictRuleError):
        return HTTPException(status_code=409, detail=error.detail)
    return HTTPException(status_code=500, detail="購物車操作失敗")


@router.get("/cart", response_model=CartResponse)
def get_cart(db: DatabaseSession, actor: ConsumerActor) -> CartResponse:
    return _to_response(cart_service.get_or_create_cart(db, actor))


@router.post("/cart", response_model=CartResponse)
@router.post("/cart/items", response_model=CartResponse)
def add_cart_item(
    payload: CartItemCreate, db: DatabaseSession, actor: ConsumerActor
) -> CartResponse:
    try:
        cart = cart_service.add_item(db, actor, payload.menu_item_id, payload.quantity)
    except (ConflictRuleError, NotFoundRuleError) as error:
        raise _handle_cart_error(error) from error
    return _to_response(cart)


@router.patch("/cart/{cart_item_id}", response_model=CartResponse)
@router.patch("/cart/items/{cart_item_id}", response_model=CartResponse)
def update_cart_item(
    cart_item_id: int,
    payload: CartItemUpdate,
    db: DatabaseSession,
    actor: ConsumerActor,
) -> CartResponse:
    try:
        cart = cart_service.update_item(db, actor, cart_item_id, payload.quantity)
    except (ConflictRuleError, NotFoundRuleError) as error:
        raise _handle_cart_error(error) from error
    return _to_response(cart)


@router.delete("/cart/{cart_item_id}", response_model=CartResponse)
@router.delete("/cart/items/{cart_item_id}", response_model=CartResponse)
def delete_cart_item(
    cart_item_id: int, db: DatabaseSession, actor: ConsumerActor
) -> CartResponse:
    try:
        cart = cart_service.remove_item(db, actor, cart_item_id)
    except (ConflictRuleError, NotFoundRuleError) as error:
        raise _handle_cart_error(error) from error
    return _to_response(cart)
