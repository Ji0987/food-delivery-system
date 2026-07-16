"""外送搶單、配送任務與位置追蹤的業務邏輯。"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.models.delivery import DeliveryAssignment, DeliveryLocation
from backend.models.enums import OrderStatus
from backend.models.order import Order
from backend.models.user import User
from backend.services.exceptions import (
    ConflictRuleError,
    NotFoundRuleError,
    PermissionRuleError,
)
from backend.services.order_service import ensure_can_view_order, get_order


LOCATION_REPORTABLE_STATUSES = {
    OrderStatus.PICKED_UP,
    OrderStatus.DELIVERING,
}


def list_available_orders(db: Session) -> list[Order]:
    """回傳尚未被任何外送員搶走的待取餐訂單。"""

    statement = (
        select(Order)
        .outerjoin(DeliveryAssignment, DeliveryAssignment.order_id == Order.id)
        .where(
            Order.status == OrderStatus.READY_FOR_PICKUP,
            DeliveryAssignment.id.is_(None),
        )
        .options(selectinload(Order.items))
        .order_by(Order.created_at, Order.id)
    )
    return list(db.scalars(statement).all())


def claim_order(db: Session, order_id: int, courier: User) -> DeliveryAssignment:
    """以資料庫唯一約束保證同一訂單僅能被一人搶走。"""

    order = db.get(Order, order_id)
    if order is None:
        raise NotFoundRuleError("找不到訂單")
    if order.status != OrderStatus.READY_FOR_PICKUP:
        raise ConflictRuleError("此訂單目前不可搶單")

    existing_assignment = db.scalar(
        select(DeliveryAssignment).where(DeliveryAssignment.order_id == order.id)
    )
    if existing_assignment is not None:
        raise ConflictRuleError("訂單已被其他外送員搶走")

    assignment = DeliveryAssignment(order_id=order.id, courier_user_id=courier.id)
    db.add(assignment)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise ConflictRuleError("訂單已被其他外送員搶走") from error
    db.refresh(assignment)
    return assignment


def _get_owned_assignment(
    db: Session, order_id: int, courier: User
) -> tuple[Order, DeliveryAssignment]:
    order = db.get(Order, order_id)
    if order is None:
        raise NotFoundRuleError("找不到訂單")

    assignment = db.scalar(
        select(DeliveryAssignment).where(DeliveryAssignment.order_id == order.id)
    )
    if assignment is None or assignment.courier_user_id != courier.id:
        raise PermissionRuleError("外送員只能操作自己已搶單的配送任務")
    return order, assignment


def record_location(
    db: Session,
    order_id: int,
    courier: User,
    *,
    latitude: Decimal,
    longitude: Decimal,
) -> DeliveryLocation:
    """在配送已開始的前提下寫入外送員定位紀錄。"""

    order, assignment = _get_owned_assignment(db, order_id, courier)
    if order.status not in LOCATION_REPORTABLE_STATUSES:
        raise ConflictRuleError("訂單尚未進入可回報位置的配送階段")

    location = DeliveryLocation(
        delivery_assignment_id=assignment.id,
        latitude=latitude,
        longitude=longitude,
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


def _get_assignment_for_view(db: Session, order_id: int) -> DeliveryAssignment:
    assignment = db.scalar(
        select(DeliveryAssignment).where(DeliveryAssignment.order_id == order_id)
    )
    if assignment is None:
        raise NotFoundRuleError("此訂單尚無配送任務")
    return assignment


def get_latest_location(db: Session, order_id: int, actor: User) -> DeliveryLocation:
    """回傳訂單最新一筆位置；先驗證訂單關係人資格。"""

    order = get_order(db, order_id)
    ensure_can_view_order(db, order, actor)
    assignment = _get_assignment_for_view(db, order.id)
    location = db.scalar(
        select(DeliveryLocation)
        .where(DeliveryLocation.delivery_assignment_id == assignment.id)
        .order_by(DeliveryLocation.recorded_at.desc(), DeliveryLocation.id.desc())
    )
    if location is None:
        raise NotFoundRuleError("尚無定位紀錄")
    return location


def get_location_history(
    db: Session, order_id: int, actor: User
) -> list[DeliveryLocation]:
    """回傳訂單定位歷史；未授權者不會得知是否有任務或位置。"""

    order = get_order(db, order_id)
    ensure_can_view_order(db, order, actor)
    assignment = _get_assignment_for_view(db, order.id)
    return list(
        db.scalars(
            select(DeliveryLocation)
            .where(DeliveryLocation.delivery_assignment_id == assignment.id)
            .order_by(DeliveryLocation.recorded_at, DeliveryLocation.id)
        ).all()
    )
