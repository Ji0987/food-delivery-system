"""訂單建立、查詢與狀態轉換 API。"""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.dependencies import CurrentUser, DatabaseSession
from backend.models.delivery import DeliveryAssignment
from backend.models.enums import UserRole
from backend.models.menu import Restaurant
from backend.models.order import Order
from backend.schemas.order import OrderResponse, OrderStatusUpdate
from backend.services.exceptions import (
    ConflictRuleError,
    NotFoundRuleError,
    PermissionRuleError,
)
from backend.services.order_service import (
    create_order_from_cart,
    ensure_can_view_order,
    get_order,
    transition_order,
)


router = APIRouter(prefix="/orders", tags=["orders"])


def _to_http_error(error: Exception) -> HTTPException:
    if isinstance(error, NotFoundRuleError):
        return HTTPException(status_code=404, detail=error.detail)
    if isinstance(error, PermissionRuleError):
        return HTTPException(status_code=403, detail=error.detail)
    if isinstance(error, ConflictRuleError):
        return HTTPException(status_code=409, detail=error.detail)
    return HTTPException(status_code=500, detail="訂單操作失敗")


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(db: DatabaseSession, actor: CurrentUser) -> Order:
    if actor.role != UserRole.CONSUMER:
        raise HTTPException(status_code=403, detail="只有消費者可以建立訂單")
    try:
        return create_order_from_cart(db, actor)
    except ConflictRuleError as error:
        db.rollback()
        raise _to_http_error(error) from error


@router.get("", response_model=list[OrderResponse])
def list_orders(
    db: DatabaseSession, actor: CurrentUser, role: str | None = None
) -> list[Order]:
    statement = select(Order).options(
        selectinload(Order.items), selectinload(Order.payment)
    )
    if actor.role == UserRole.CONSUMER:
        statement = statement.where(Order.consumer_user_id == actor.id)
    elif actor.role == UserRole.RESTAURANT:
        if role not in (None, UserRole.RESTAURANT.value):
            raise HTTPException(status_code=422, detail="role 查詢參數不合法")
        restaurant = db.scalar(
            select(Restaurant).where(Restaurant.owner_user_id == actor.id)
        )
        if restaurant is None:
            return []
        statement = statement.where(Order.restaurant_id == restaurant.id)
    elif actor.role == UserRole.COURIER:
        if role not in (None, UserRole.COURIER.value):
            raise HTTPException(status_code=422, detail="role 查詢參數不合法")
        statement = statement.join(
            DeliveryAssignment,
            DeliveryAssignment.order_id == Order.id,
        ).where(DeliveryAssignment.courier_user_id == actor.id)
    else:
        raise HTTPException(status_code=403, detail="目前角色無權列出訂單")
    return list(db.scalars(statement.order_by(Order.id.desc())).all())


@router.get("/{order_id}", response_model=OrderResponse)
def read_order(order_id: int, db: DatabaseSession, actor: CurrentUser) -> Order:
    try:
        order = get_order(db, order_id)
        ensure_can_view_order(db, order, actor)
    except (NotFoundRuleError, PermissionRuleError) as error:
        raise _to_http_error(error) from error
    return order


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: int,
    payload: OrderStatusUpdate,
    db: DatabaseSession,
    actor: CurrentUser,
) -> Order:
    try:
        order = get_order(db, order_id)
        return transition_order(db, order, payload.status, actor)
    except (NotFoundRuleError, PermissionRuleError, ConflictRuleError) as error:
        db.rollback()
        raise _to_http_error(error) from error
