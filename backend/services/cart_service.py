"""購物車業務規則。"""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models.cart import Cart, CartItem
from backend.models.menu import MenuItem
from backend.models.user import User
from backend.models.utils import utc_now
from backend.services.exceptions import ConflictRuleError, NotFoundRuleError


def get_or_create_cart(db: Session, consumer: User) -> Cart:
    cart = db.scalar(
        select(Cart)
        .where(Cart.consumer_user_id == consumer.id)
        .options(selectinload(Cart.items).selectinload(CartItem.menu_item))
    )
    if cart is not None:
        return cart

    cart = Cart(consumer_user_id=consumer.id)
    db.add(cart)
    db.commit()
    return get_cart(db, consumer.id)


def get_cart(db: Session, consumer_id: int) -> Cart:
    cart = db.scalar(
        select(Cart)
        .where(Cart.consumer_user_id == consumer_id)
        .options(selectinload(Cart.items).selectinload(CartItem.menu_item))
        .execution_options(populate_existing=True)
    )
    if cart is None:
        raise NotFoundRuleError("找不到購物車")
    return cart


def add_item(db: Session, consumer: User, menu_item_id: int, quantity: int) -> Cart:
    menu_item = db.get(MenuItem, menu_item_id)
    if menu_item is None:
        raise NotFoundRuleError("找不到餐點")
    if menu_item.is_sold_out:
        raise ConflictRuleError("餐點已售罄，無法加入購物車")

    cart = get_or_create_cart(db, consumer)
    if any(
        item.menu_item.restaurant_id != menu_item.restaurant_id for item in cart.items
    ):
        raise ConflictRuleError("購物車暫不允許混合不同餐廳的餐點")

    existing_item = next(
        (item for item in cart.items if item.menu_item_id == menu_item.id), None
    )
    if existing_item is None:
        db.add(
            CartItem(
                cart_id=cart.id,
                menu_item_id=menu_item.id,
                quantity=quantity,
            )
        )
    else:
        existing_item.quantity += quantity

    cart.updated_at = utc_now()
    db.commit()
    return get_cart(db, consumer.id)


def update_item(db: Session, consumer: User, cart_item_id: int, quantity: int) -> Cart:
    cart = get_or_create_cart(db, consumer)
    item = next((item for item in cart.items if item.id == cart_item_id), None)
    if item is None:
        raise NotFoundRuleError("找不到購物車項目")
    if item.menu_item.is_sold_out:
        raise ConflictRuleError("餐點已售罄，無法修改數量")

    item.quantity = quantity
    cart.updated_at = utc_now()
    db.commit()
    return get_cart(db, consumer.id)


def remove_item(db: Session, consumer: User, cart_item_id: int) -> Cart:
    cart = get_or_create_cart(db, consumer)
    item = next((item for item in cart.items if item.id == cart_item_id), None)
    if item is None:
        raise NotFoundRuleError("找不到購物車項目")

    db.delete(item)
    cart.updated_at = utc_now()
    db.commit()
    return get_cart(db, consumer.id)
