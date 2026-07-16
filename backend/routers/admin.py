"""管理員的餐廳、餐點分類與營運總覽 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select

from backend.dependencies import DatabaseSession, require_role
from backend.models.enums import OrderStatus, UserRole
from backend.models.menu import MenuCategory, Restaurant
from backend.models.order import Order
from backend.models.user import User
from backend.schemas.admin import (
    AdminMenuCategoryCreate,
    AdminOverviewResponse,
    OrderOverview,
    RestaurantActivationUpdate,
    RestaurantOverview,
)
from backend.schemas.menu import (
    MenuCategoryResponse,
    MenuCategoryUpdate,
    RestaurantResponse,
)


router = APIRouter(prefix="/admin", tags=["admin"])
AdminActor = Annotated[User, Depends(require_role(UserRole.ADMIN))]


@router.get("/restaurants", response_model=list[RestaurantResponse])
def list_restaurants(db: DatabaseSession, _actor: AdminActor) -> list[Restaurant]:
    """列出所有餐廳，包含已停權的資料。"""

    return list(db.scalars(select(Restaurant).order_by(Restaurant.id)).all())


@router.patch("/restaurants/{restaurant_id}", response_model=RestaurantResponse)
def set_restaurant_activation(
    restaurant_id: int,
    payload: RestaurantActivationUpdate,
    db: DatabaseSession,
    _actor: AdminActor,
) -> Restaurant:
    """啟用或停權指定餐廳，不會刪除既有訂單與餐點。"""

    restaurant = db.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=404, detail="找不到餐廳")
    restaurant.is_active = payload.is_active
    db.commit()
    db.refresh(restaurant)
    return restaurant


@router.get("/menu-categories", response_model=list[MenuCategoryResponse])
def list_menu_categories(
    db: DatabaseSession,
    _actor: AdminActor,
    restaurant_id: Annotated[int | None, Query(gt=0)] = None,
) -> list[MenuCategory]:
    """跨餐廳列出分類；可選擇以餐廳 ID 篩選。"""

    statement = select(MenuCategory)
    if restaurant_id is not None:
        statement = statement.where(MenuCategory.restaurant_id == restaurant_id)
    return list(
        db.scalars(
            statement.order_by(
                MenuCategory.restaurant_id,
                MenuCategory.sort_order,
                MenuCategory.id,
            )
        ).all()
    )


@router.post(
    "/menu-categories",
    response_model=MenuCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_menu_category(
    payload: AdminMenuCategoryCreate,
    db: DatabaseSession,
    _actor: AdminActor,
) -> MenuCategory:
    """為指定餐廳建立分類，維持分類屬於單一餐廳的既有資料模型。"""

    if db.get(Restaurant, payload.restaurant_id) is None:
        raise HTTPException(status_code=404, detail="找不到餐廳")
    category = MenuCategory(**payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/menu-categories/{category_id}", response_model=MenuCategoryResponse)
def update_menu_category(
    category_id: int,
    payload: MenuCategoryUpdate,
    db: DatabaseSession,
    _actor: AdminActor,
) -> MenuCategory:
    """更新分類名稱或排序，不移動分類至其他餐廳。"""

    category = db.get(MenuCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="找不到分類")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/menu-categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu_category(
    category_id: int,
    db: DatabaseSession,
    _actor: AdminActor,
) -> Response:
    """刪除指定餐廳分類；既有餐點保留並依外鍵規則改為未分類。"""

    category = db.get(MenuCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="找不到分類")
    db.delete(category)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/overview", response_model=AdminOverviewResponse)
def get_overview(db: DatabaseSession, _actor: AdminActor) -> AdminOverviewResponse:
    """回傳餐廳與訂單的最小營運統計，管理員僅檢視不修改訂單。"""

    restaurant_total = db.scalar(select(func.count(Restaurant.id))) or 0
    restaurant_active = (
        db.scalar(
            select(func.count(Restaurant.id)).where(Restaurant.is_active.is_(True))
        )
        or 0
    )
    order_total = db.scalar(select(func.count(Order.id))) or 0
    status_counts = {order_status.value: 0 for order_status in OrderStatus}
    for order_status, count in db.execute(
        select(Order.status, func.count(Order.id)).group_by(Order.status)
    ):
        status_counts[order_status.value] = count

    return AdminOverviewResponse(
        restaurants=RestaurantOverview(
            total=restaurant_total,
            active=restaurant_active,
            suspended=restaurant_total - restaurant_active,
        ),
        orders=OrderOverview(total=order_total, by_status=status_counts),
    )
