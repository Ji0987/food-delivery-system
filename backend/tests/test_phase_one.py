"""todo.md 階段一 1.1～1.7 的 API 測試。"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.database import SessionLocal
from backend.models.cart import CartItem
from backend.models.enums import UserRole
from backend.models.order import Order
from backend.models.user import User
from backend.seed_admin import create_initial_admin


PASSWORD = "ValidPass123!"


def register(
    client: TestClient, email: str, role: str, name: str = "測試使用者"
) -> dict[str, Any]:
    response = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "role": role,
            "name": name,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, email: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def assert_utc_iso8601(value: str) -> None:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.utcoffset() == timedelta(0)


def prepare_menu(
    client: TestClient, *, sold_out: bool = False, price: str = "120.50"
) -> dict[str, Any]:
    register(client, "restaurant@example.com", "restaurant", "測試餐廳主")
    register(client, "consumer@example.com", "consumer", "測試消費者")
    restaurant_token = login(client, "restaurant@example.com")
    consumer_token = login(client, "consumer@example.com")

    restaurant_response = client.post(
        "/restaurants",
        json={"name": "測試餐廳", "description": "整合測試"},
        headers=auth(restaurant_token),
    )
    assert restaurant_response.status_code == 201, restaurant_response.text
    restaurant_id = restaurant_response.json()["id"]

    category_response = client.post(
        f"/restaurants/{restaurant_id}/categories",
        json={"name": "主餐", "sort_order": 1},
        headers=auth(restaurant_token),
    )
    assert category_response.status_code == 201, category_response.text

    menu_item_response = client.post(
        f"/restaurants/{restaurant_id}/menu-items",
        json={
            "category_id": category_response.json()["id"],
            "name": "招牌餐點",
            "price": price,
            "is_sold_out": sold_out,
        },
        headers=auth(restaurant_token),
    )
    assert menu_item_response.status_code == 201, menu_item_response.text
    return {
        "restaurant_id": restaurant_id,
        "menu_item_id": menu_item_response.json()["id"],
        "restaurant_token": restaurant_token,
        "consumer_token": consumer_token,
    }


def add_to_cart(
    client: TestClient, context: dict[str, Any], quantity: int = 1
) -> dict[str, Any]:
    response = client.post(
        "/cart/items",
        json={"menu_item_id": context["menu_item_id"], "quantity": quantity},
        headers=auth(str(context["consumer_token"])),
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_order(client: TestClient, context: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/orders", headers=auth(str(context["consumer_token"])))
    assert response.status_code == 201, response.text
    return response.json()


def test_root_health_check(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.parametrize(
    "role",
    [
        UserRole.CONSUMER.value,
        UserRole.RESTAURANT.value,
        UserRole.COURIER.value,
    ],
)
def test_tc_1_2_01_public_roles_can_register_and_login(
    client: TestClient, role: str
) -> None:
    email = f"{role}@example.com"
    created = register(client, email, role)
    assert created["role"] == role
    assert_utc_iso8601(created["created_at"])
    assert login(client, email)

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        assert user.password_hash != PASSWORD
        assert user.password_hash.startswith("$2")


def test_tc_1_2_02_duplicate_email_is_rejected_case_insensitively(
    client: TestClient,
) -> None:
    register(client, "duplicate@example.com", "consumer")
    response = client.post(
        "/auth/register",
        json={
            "email": "DUPLICATE@example.com",
            "password": PASSWORD,
            "role": "consumer",
            "name": "重複帳號",
        },
    )
    assert response.status_code == 409


def test_login_response_includes_backward_compatible_token_and_user(
    client: TestClient,
) -> None:
    register(client, "owner@example.com", "restaurant", "王老闆")

    response = client.post(
        "/auth/login",
        json={"email": "owner@example.com", "password": PASSWORD},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["access_token"]
    assert payload["token_type"] == "bearer"
    assert payload["user"]["email"] == "owner@example.com"
    assert payload["user"]["role"] == "restaurant"
    assert payload["user"]["name"] == "王老闆"
    assert_utc_iso8601(payload["user"]["created_at"])


def test_tc_1_2_03_admin_cannot_self_register(client: TestClient) -> None:
    response = client.post(
        "/auth/register",
        json={
            "email": "admin@example.com",
            "password": PASSWORD,
            "role": "admin",
            "name": "未授權管理員",
        },
    )
    assert response.status_code == 422
    assert (
        "Admin accounts cannot be created through public registration." in response.text
    )
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "admin@example.com"))
        assert user is None


def test_tc_1_2_04_preprovisioned_admin_can_login(client: TestClient) -> None:
    with SessionLocal() as db:
        admin = create_initial_admin(
            db,
            email="admin@example.com",
            password=PASSWORD,
            phone=None,
            name="預先建立的管理員",
        )
        assert admin.role is UserRole.ADMIN

    assert login(client, "admin@example.com")


def test_tc_1_3_01_menu_item_can_be_created_and_browsed(
    client: TestClient,
) -> None:
    context = prepare_menu(client)
    response = client.get(
        f"/restaurants/{context['restaurant_id']}/menu",
        headers=auth(str(context["consumer_token"])),
    )
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["name"] == "招牌餐點"
    assert item["price"] == "120.50"
    assert item["is_sold_out"] is False


def test_tc_1_3_02_sold_out_state_is_visible_to_consumer(
    client: TestClient,
) -> None:
    context = prepare_menu(client)
    update_response = client.patch(
        f"/menu-items/{context['menu_item_id']}",
        json={"is_sold_out": True},
        headers=auth(str(context["restaurant_token"])),
    )
    assert update_response.status_code == 200

    menu_response = client.get(
        f"/restaurants/{context['restaurant_id']}/menu",
        headers=auth(str(context["consumer_token"])),
    )
    assert menu_response.status_code == 200
    assert menu_response.json()["items"][0]["is_sold_out"] is True


def test_restaurant_can_get_own_restaurant_and_menu(client: TestClient) -> None:
    context = prepare_menu(client)

    restaurant_response = client.get(
        "/restaurants/me",
        headers=auth(str(context["restaurant_token"])),
    )
    assert restaurant_response.status_code == 200
    assert restaurant_response.json()["id"] == context["restaurant_id"]

    menu_response = client.get(
        f"/restaurants/{context['restaurant_id']}/menu",
        headers=auth(str(context["restaurant_token"])),
    )
    assert menu_response.status_code == 200
    assert menu_response.json()["items"][0]["id"] == context["menu_item_id"]


def test_restaurant_self_lookup_enforces_role_and_ownership(
    client: TestClient,
) -> None:
    context = prepare_menu(client)

    consumer_response = client.get(
        "/restaurants/me",
        headers=auth(str(context["consumer_token"])),
    )
    assert consumer_response.status_code == 403

    register(client, "other-owner@example.com", "restaurant")
    other_token = login(client, "other-owner@example.com")
    missing_response = client.get("/restaurants/me", headers=auth(other_token))
    assert missing_response.status_code == 404

    foreign_menu_response = client.get(
        f"/restaurants/{context['restaurant_id']}/menu",
        headers=auth(other_token),
    )
    assert foreign_menu_response.status_code == 403


def test_tc_1_5_01_available_item_can_be_added_to_cart(
    client: TestClient,
) -> None:
    context = prepare_menu(client, price="99.90")
    cart = add_to_cart(client, context, quantity=3)
    assert cart["items"][0]["quantity"] == 3
    assert cart["total_amount"] == "299.70"


def test_tc_1_5_02_sold_out_item_is_rejected_without_database_write(
    client: TestClient,
) -> None:
    context = prepare_menu(client, sold_out=True)
    response = client.post(
        "/cart/items",
        json={"menu_item_id": context["menu_item_id"], "quantity": 1},
        headers=auth(str(context["consumer_token"])),
    )
    assert response.status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(CartItem)) == 0


def test_tc_1_6_01_order_has_price_snapshot_total_and_paid_payment(
    client: TestClient,
) -> None:
    context = prepare_menu(client, price="10.25")
    add_to_cart(client, context, quantity=3)
    order = create_order(client, context)

    assert order["status"] == "pending"
    assert order["total_amount"] == "30.75"
    assert order["payment"]["status"] == "paid"
    assert order["payment"]["amount"] == "30.75"
    assert order["items"][0]["item_name_snapshot"] == "招牌餐點"
    assert order["items"][0]["unit_price_snapshot"] == "10.25"
    assert order["items"][0]["subtotal"] == "30.75"

    cart_response = client.get("/cart", headers=auth(str(context["consumer_token"])))
    assert cart_response.json()["items"] == []

    with SessionLocal() as db:
        stored_order = db.get(Order, order["id"])
        assert stored_order is not None
        assert stored_order.total_amount == Decimal("30.75")


def test_tc_1_6_02_sold_out_recheck_prevents_invalid_order(
    client: TestClient,
) -> None:
    context = prepare_menu(client)
    add_to_cart(client, context)
    sold_out_response = client.patch(
        f"/menu-items/{context['menu_item_id']}",
        json={"is_sold_out": True},
        headers=auth(str(context["restaurant_token"])),
    )
    assert sold_out_response.status_code == 200

    order_response = client.post(
        "/orders", headers=auth(str(context["consumer_token"]))
    )
    assert order_response.status_code == 409
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Order)) == 0


def test_tc_1_7_01_restaurant_can_accept_pending_order(
    client: TestClient,
) -> None:
    context = prepare_menu(client)
    add_to_cart(client, context)
    order = create_order(client, context)

    response = client.patch(
        f"/orders/{order['id']}/status",
        json={"status": "accepted"},
        headers=auth(str(context["restaurant_token"])),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "accepted"

    consumer_view = client.get(
        f"/orders/{order['id']}",
        headers=auth(str(context["consumer_token"])),
    )
    assert consumer_view.json()["status"] == "accepted"


def test_tc_1_7_02_illegal_status_jump_is_rejected_and_unchanged(
    client: TestClient,
) -> None:
    context = prepare_menu(client)
    add_to_cart(client, context)
    order = create_order(client, context)

    response = client.patch(
        f"/orders/{order['id']}/status",
        json={"status": "delivering"},
        headers=auth(str(context["restaurant_token"])),
    )
    assert response.status_code == 409
    current = client.get(
        f"/orders/{order['id']}",
        headers=auth(str(context["consumer_token"])),
    )
    assert current.json()["status"] == "pending"


def test_tc_1_7_03_consumer_cannot_perform_restaurant_transition(
    client: TestClient,
) -> None:
    context = prepare_menu(client)
    add_to_cart(client, context)
    order = create_order(client, context)

    response = client.patch(
        f"/orders/{order['id']}/status",
        json={"status": "accepted"},
        headers=auth(str(context["consumer_token"])),
    )
    assert response.status_code == 403


def test_restaurant_status_flow_reaches_ready_for_pickup(
    client: TestClient,
) -> None:
    context = prepare_menu(client)
    add_to_cart(client, context)
    order = create_order(client, context)

    for target_status in ("accepted", "preparing", "ready_for_pickup"):
        response = client.patch(
            f"/orders/{order['id']}/status",
            json={"status": target_status},
            headers=auth(str(context["restaurant_token"])),
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == target_status


def test_other_restaurant_cannot_view_or_update_order(
    client: TestClient,
) -> None:
    context = prepare_menu(client)
    add_to_cart(client, context)
    order = create_order(client, context)

    register(client, "other-restaurant@example.com", "restaurant")
    other_token = login(client, "other-restaurant@example.com")
    other_restaurant = client.post(
        "/restaurants",
        json={"name": "其他餐廳"},
        headers=auth(other_token),
    )
    assert other_restaurant.status_code == 201

    read_response = client.get(f"/orders/{order['id']}", headers=auth(other_token))
    assert read_response.status_code == 403
    update_response = client.patch(
        f"/orders/{order['id']}/status",
        json={"status": "accepted"},
        headers=auth(other_token),
    )
    assert update_response.status_code == 403


def test_consumer_can_cancel_pending_order_with_simulated_refund(
    client: TestClient,
) -> None:
    context = prepare_menu(client)
    add_to_cart(client, context)
    order = create_order(client, context)

    response = client.patch(
        f"/orders/{order['id']}/status",
        json={"status": "cancelled"},
        headers=auth(str(context["consumer_token"])),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["payment"]["status"] == "refunded"


def test_unauthenticated_cart_request_returns_401(client: TestClient) -> None:
    response = client.get("/cart")
    assert response.status_code == 401


def test_cross_restaurant_cart_is_rejected_under_temporary_assumption(
    client: TestClient,
) -> None:
    context = prepare_menu(client)
    add_to_cart(client, context)

    register(client, "second-restaurant@example.com", "restaurant")
    second_token = login(client, "second-restaurant@example.com")
    restaurant_response = client.post(
        "/restaurants",
        json={"name": "第二間餐廳"},
        headers=auth(second_token),
    )
    second_restaurant_id = restaurant_response.json()["id"]
    second_item_response = client.post(
        f"/restaurants/{second_restaurant_id}/menu-items",
        json={"name": "第二間餐廳餐點", "price": "50.00"},
        headers=auth(second_token),
    )
    assert second_item_response.status_code == 201

    response = client.post(
        "/cart/items",
        json={"menu_item_id": second_item_response.json()["id"], "quantity": 1},
        headers=auth(str(context["consumer_token"])),
    )
    assert response.status_code == 409


def test_referenced_menu_item_hard_delete_returns_conflict(
    client: TestClient,
) -> None:
    context = prepare_menu(client)
    add_to_cart(client, context)
    create_order(client, context)

    response = client.delete(
        f"/menu-items/{context['menu_item_id']}",
        headers=auth(str(context["restaurant_token"])),
    )
    assert response.status_code == 409


def test_api_and_sqlite_round_trip_return_utc_aware_datetimes(
    client: TestClient,
) -> None:
    context = prepare_menu(client)

    restaurant_response = client.get(
        "/restaurants/me",
        headers=auth(str(context["restaurant_token"])),
    )
    menu_response = client.get(
        f"/restaurants/{context['restaurant_id']}/menu",
        headers=auth(str(context["consumer_token"])),
    )
    add_to_cart(client, context)
    order = create_order(client, context)

    assert_utc_iso8601(restaurant_response.json()["created_at"])
    menu_item = menu_response.json()["items"][0]
    assert_utc_iso8601(menu_item["created_at"])
    assert_utc_iso8601(menu_item["updated_at"])
    assert_utc_iso8601(order["created_at"])
    assert_utc_iso8601(order["updated_at"])
    assert_utc_iso8601(order["payment"]["paid_at"])

    with SessionLocal() as db:
        restaurant_owner = db.scalar(
            select(User).where(User.email == "restaurant@example.com")
        )
        assert restaurant_owner is not None
        assert restaurant_owner.created_at.utcoffset() == timedelta(0)
