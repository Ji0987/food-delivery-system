"""訂單建立、查詢權限與狀態機的唯一實作位置。"""

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models.cart import Cart, CartItem
from backend.models.delivery import DeliveryAssignment
from backend.models.enums import OrderStatus, PaymentStatus, UserRole
from backend.models.menu import MenuItem, Restaurant
from backend.models.order import Order, OrderItem, Payment
from backend.models.types import MONEY_QUANTUM
from backend.models.user import User
from backend.models.utils import utc_now
from backend.services.exceptions import (
    ConflictRuleError,
    NotFoundRuleError,
    PermissionRuleError,
)


@dataclass(frozen=True)
class TransitionRule:
    target: OrderStatus
    actor_role: UserRole


ORDER_TRANSITIONS: dict[OrderStatus, tuple[TransitionRule, ...]] = {
    OrderStatus.PENDING: (
        TransitionRule(OrderStatus.ACCEPTED, UserRole.RESTAURANT),
        TransitionRule(OrderStatus.CANCELLED, UserRole.CONSUMER),
    ),
    OrderStatus.ACCEPTED: (
        TransitionRule(OrderStatus.REJECTED, UserRole.RESTAURANT),
        TransitionRule(OrderStatus.PREPARING, UserRole.RESTAURANT),
    ),
    OrderStatus.PREPARING: (
        TransitionRule(OrderStatus.READY_FOR_PICKUP, UserRole.RESTAURANT),
    ),
    OrderStatus.READY_FOR_PICKUP: (
        TransitionRule(OrderStatus.PICKED_UP, UserRole.COURIER),
    ),
    OrderStatus.PICKED_UP: (TransitionRule(OrderStatus.DELIVERING, UserRole.COURIER),),
    OrderStatus.DELIVERING: (TransitionRule(OrderStatus.DELIVERED, UserRole.COURIER),),
    OrderStatus.DELIVERED: (TransitionRule(OrderStatus.COMPLETED, UserRole.CONSUMER),),
}


def get_order(db: Session, order_id: int) -> Order:
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items), selectinload(Order.payment))
    )
    if order is None:
        raise NotFoundRuleError("找不到訂單")
    return order


def create_order_from_cart(db: Session, consumer: User) -> Order:
    cart = db.scalar(
        select(Cart)
        .where(Cart.consumer_user_id == consumer.id)
        .options(selectinload(Cart.items).selectinload(CartItem.menu_item))
    )
    if cart is None or not cart.items:
        raise ConflictRuleError("購物車是空的，無法建立訂單")

    menu_item_ids = [cart_item.menu_item_id for cart_item in cart.items]
    fresh_menu_items = db.scalars(
        select(MenuItem).where(MenuItem.id.in_(menu_item_ids)).with_for_update()
    ).all()
    items_by_id = {item.id: item for item in fresh_menu_items}

    if len(items_by_id) != len(menu_item_ids):
        raise ConflictRuleError("購物車包含已不存在的餐點")
    if any(item.is_sold_out for item in fresh_menu_items):
        raise ConflictRuleError("購物車包含已售罄餐點，無法建立訂單")

    restaurant_ids = {item.restaurant_id for item in fresh_menu_items}
    if len(restaurant_ids) != 1:
        raise ConflictRuleError("購物車暫不允許跨餐廳下單")
    restaurant_id = restaurant_ids.pop()

    order_items: list[OrderItem] = []
    total_amount = Decimal("0.00")
    for cart_item in cart.items:
        menu_item = items_by_id[cart_item.menu_item_id]
        unit_price = Decimal(menu_item.price).quantize(MONEY_QUANTUM)
        subtotal = (unit_price * cart_item.quantity).quantize(MONEY_QUANTUM)
        total_amount += subtotal
        order_items.append(
            OrderItem(
                menu_item_id=menu_item.id,
                item_name_snapshot=menu_item.name,
                unit_price_snapshot=unit_price,
                quantity=cart_item.quantity,
                subtotal=subtotal,
            )
        )

    total_amount = total_amount.quantize(MONEY_QUANTUM)
    order = Order(
        consumer_user_id=consumer.id,
        restaurant_id=restaurant_id,
        status=OrderStatus.PENDING,
        total_amount=total_amount,
        items=order_items,
    )
    order.payment = Payment(
        status=PaymentStatus.PAID,
        amount=total_amount,
        paid_at=utc_now(),
    )
    db.add(order)
    for cart_item in list(cart.items):
        db.delete(cart_item)
    cart.updated_at = utc_now()

    db.commit()
    return get_order(db, order.id)


def ensure_can_view_order(db: Session, order: Order, actor: User) -> None:
    if actor.role == UserRole.ADMIN:
        return
    if actor.role == UserRole.CONSUMER and order.consumer_user_id == actor.id:
        return
    if actor.role == UserRole.RESTAURANT:
        restaurant = db.scalar(
            select(Restaurant).where(Restaurant.owner_user_id == actor.id)
        )
        if restaurant is not None and restaurant.id == order.restaurant_id:
            return
    if actor.role == UserRole.COURIER:
        assignment = db.scalar(
            select(DeliveryAssignment).where(
                DeliveryAssignment.order_id == order.id,
                DeliveryAssignment.courier_user_id == actor.id,
            )
        )
        if assignment is not None:
            return
    raise PermissionRuleError("無權查看此訂單")


def transition_order(
    db: Session, order: Order, target_status: OrderStatus, actor: User
) -> Order:
    rules = ORDER_TRANSITIONS.get(order.status, ())
    matching_rule = next((rule for rule in rules if rule.target == target_status), None)
    if matching_rule is None:
        raise ConflictRuleError(
            f"不可將訂單由 {order.status.value} 轉換為 {target_status.value}"
        )
    if actor.role != matching_rule.actor_role:
        raise PermissionRuleError("目前角色無權執行此狀態轉換")

    assignment: DeliveryAssignment | None = None
    if actor.role == UserRole.RESTAURANT:
        restaurant = db.scalar(
            select(Restaurant).where(Restaurant.owner_user_id == actor.id)
        )
        if restaurant is None or restaurant.id != order.restaurant_id:
            raise PermissionRuleError("餐廳只能更新自己的訂單")
    elif actor.role == UserRole.CONSUMER:
        if order.consumer_user_id != actor.id:
            raise PermissionRuleError("消費者只能更新自己的訂單")
    elif actor.role == UserRole.COURIER:
        assignment = db.scalar(
            select(DeliveryAssignment).where(
                DeliveryAssignment.order_id == order.id,
                DeliveryAssignment.courier_user_id == actor.id,
            )
        )
        if assignment is None:
            raise PermissionRuleError("外送員只能更新自己已搶單的訂單")

    if target_status == OrderStatus.CANCELLED:
        if order.payment.status != PaymentStatus.PAID:
            raise ConflictRuleError("只有已付款訂單可以執行模擬退款")
    order.status = target_status
    order.updated_at = utc_now()
    if target_status == OrderStatus.PICKED_UP:
        if assignment is None:
            raise PermissionRuleError("外送員只能更新自己已搶單的訂單")
        assignment.picked_up_at = utc_now()
    elif target_status == OrderStatus.DELIVERED:
        if assignment is None:
            raise PermissionRuleError("外送員只能更新自己已搶單的訂單")
        assignment.delivered_at = utc_now()
    if target_status == OrderStatus.CANCELLED:
        order.payment.status = PaymentStatus.REFUNDED
        order.payment.refunded_at = utc_now()

    db.commit()
    return get_order(db, order.id)
