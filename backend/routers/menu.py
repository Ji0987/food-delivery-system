"""餐廳與菜單管理／瀏覽 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from backend.dependencies import DatabaseSession, require_role
from backend.models.enums import UserRole
from backend.models.menu import MenuCategory, MenuItem, Restaurant
from backend.models.user import User
from backend.schemas.menu import (
    MenuCategoryCreate,
    MenuCategoryResponse,
    MenuCategoryUpdate,
    MenuItemCreate,
    MenuItemResponse,
    MenuItemUpdate,
    RestaurantCreate,
    RestaurantMenuResponse,
    RestaurantResponse,
)


router = APIRouter(tags=["restaurants", "menu"])
RestaurantActor = Annotated[User, Depends(require_role(UserRole.RESTAURANT))]
ConsumerActor = Annotated[User, Depends(require_role(UserRole.CONSUMER))]
MenuViewer = Annotated[
    User,
    Depends(require_role(UserRole.CONSUMER, UserRole.RESTAURANT)),
]


def _get_owned_restaurant(
    db: DatabaseSession, restaurant_id: int, actor: User
) -> Restaurant:
    restaurant = db.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise HTTPException(status_code=404, detail="找不到餐廳")
    if restaurant.owner_user_id != actor.id:
        raise HTTPException(status_code=403, detail="只能管理自己的餐廳")
    return restaurant


def _validate_category(
    db: DatabaseSession, restaurant_id: int, category_id: int | None
) -> None:
    if category_id is None:
        return
    category = db.get(MenuCategory, category_id)
    if category is None or category.restaurant_id != restaurant_id:
        raise HTTPException(status_code=422, detail="分類不屬於此餐廳")


@router.post(
    "/restaurants",
    response_model=RestaurantResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_restaurant(
    payload: RestaurantCreate, db: DatabaseSession, actor: RestaurantActor
) -> Restaurant:
    existing = db.scalar(select(Restaurant).where(Restaurant.owner_user_id == actor.id))
    if existing is not None:
        raise HTTPException(status_code=409, detail="一個帳號目前僅能建立一間餐廳")

    restaurant = Restaurant(owner_user_id=actor.id, **payload.model_dump())
    db.add(restaurant)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="此帳號已建立餐廳") from error
    db.refresh(restaurant)
    return restaurant


@router.get("/restaurants", response_model=list[RestaurantResponse])
def list_restaurants(db: DatabaseSession, _actor: ConsumerActor) -> list[Restaurant]:
    return list(
        db.scalars(
            select(Restaurant)
            .where(Restaurant.is_active.is_(True))
            .order_by(Restaurant.id)
        ).all()
    )


@router.get("/restaurants/me", response_model=RestaurantResponse)
def get_my_restaurant(db: DatabaseSession, actor: RestaurantActor) -> Restaurant:
    restaurant = db.scalar(
        select(Restaurant).where(Restaurant.owner_user_id == actor.id)
    )
    if restaurant is None:
        raise HTTPException(status_code=404, detail="尚未建立餐廳")
    return restaurant


@router.get("/restaurants/{restaurant_id}/menu", response_model=RestaurantMenuResponse)
def get_restaurant_menu(
    restaurant_id: int, db: DatabaseSession, actor: MenuViewer
) -> RestaurantMenuResponse:
    restaurant = db.scalar(
        select(Restaurant)
        .where(Restaurant.id == restaurant_id)
        .options(
            selectinload(Restaurant.categories),
            selectinload(Restaurant.menu_items),
        )
    )
    if restaurant is None:
        raise HTTPException(status_code=404, detail="找不到餐廳")
    if actor.role == UserRole.CONSUMER and not restaurant.is_active:
        raise HTTPException(status_code=404, detail="找不到餐廳")
    if actor.role == UserRole.RESTAURANT and restaurant.owner_user_id != actor.id:
        raise HTTPException(status_code=403, detail="只能查看自己的餐廳菜單")
    return RestaurantMenuResponse(
        restaurant=RestaurantResponse.model_validate(restaurant),
        categories=[
            MenuCategoryResponse.model_validate(category)
            for category in sorted(
                restaurant.categories, key=lambda item: (item.sort_order, item.id)
            )
        ],
        items=[
            MenuItemResponse.model_validate(item)
            for item in sorted(restaurant.menu_items, key=lambda item: item.id)
        ],
    )


@router.post(
    "/restaurants/{restaurant_id}/categories",
    response_model=MenuCategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_menu_category(
    restaurant_id: int,
    payload: MenuCategoryCreate,
    db: DatabaseSession,
    actor: RestaurantActor,
) -> MenuCategory:
    _get_owned_restaurant(db, restaurant_id, actor)
    category = MenuCategory(restaurant_id=restaurant_id, **payload.model_dump())
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


@router.patch("/menu-categories/{category_id}", response_model=MenuCategoryResponse)
def update_menu_category(
    category_id: int,
    payload: MenuCategoryUpdate,
    db: DatabaseSession,
    actor: RestaurantActor,
) -> MenuCategory:
    category = db.get(MenuCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="找不到分類")
    _get_owned_restaurant(db, category.restaurant_id, actor)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category


@router.delete("/menu-categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu_category(
    category_id: int, db: DatabaseSession, actor: RestaurantActor
) -> Response:
    category = db.get(MenuCategory, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="找不到分類")
    _get_owned_restaurant(db, category.restaurant_id, actor)
    db.delete(category)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/restaurants/{restaurant_id}/menu-items",
    response_model=MenuItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_menu_item(
    restaurant_id: int,
    payload: MenuItemCreate,
    db: DatabaseSession,
    actor: RestaurantActor,
) -> MenuItem:
    _get_owned_restaurant(db, restaurant_id, actor)
    _validate_category(db, restaurant_id, payload.category_id)
    menu_item = MenuItem(restaurant_id=restaurant_id, **payload.model_dump())
    db.add(menu_item)
    db.commit()
    db.refresh(menu_item)
    return menu_item


@router.patch("/menu-items/{menu_item_id}", response_model=MenuItemResponse)
def update_menu_item(
    menu_item_id: int,
    payload: MenuItemUpdate,
    db: DatabaseSession,
    actor: RestaurantActor,
) -> MenuItem:
    menu_item = db.get(MenuItem, menu_item_id)
    if menu_item is None:
        raise HTTPException(status_code=404, detail="找不到餐點")
    _get_owned_restaurant(db, menu_item.restaurant_id, actor)
    if "category_id" in payload.model_fields_set:
        _validate_category(db, menu_item.restaurant_id, payload.category_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(menu_item, field, value)
    db.commit()
    db.refresh(menu_item)
    return menu_item


@router.delete("/menu-items/{menu_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_menu_item(
    menu_item_id: int, db: DatabaseSession, actor: RestaurantActor
) -> Response:
    menu_item = db.get(MenuItem, menu_item_id)
    if menu_item is None:
        raise HTTPException(status_code=404, detail="找不到餐點")
    _get_owned_restaurant(db, menu_item.restaurant_id, actor)
    db.delete(menu_item)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="餐點已有購物車或歷史訂單參照，無法硬刪除",
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
