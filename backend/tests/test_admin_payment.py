"""todo.md 階段二與 3.1 的管理員／退款 API 測試。"""

from fastapi.testclient import TestClient

from backend.database import SessionLocal
from backend.seed_admin import create_initial_admin
from backend.tests.test_phase_one import (
    PASSWORD,
    add_to_cart,
    auth,
    create_order,
    login,
    prepare_menu,
)


def create_admin_and_login(client: TestClient) -> str:
    with SessionLocal() as db:
        create_initial_admin(
            db,
            email="admin@example.com",
            password=PASSWORD,
            phone=None,
            name="平台管理員",
        )
    return login(client, "admin@example.com")


def test_admin_can_list_and_suspend_restaurant_and_suspension_blocks_access(
    client: TestClient,
) -> None:
    context = prepare_menu(client)
    admin_token = create_admin_and_login(client)

    list_response = client.get("/admin/restaurants", headers=auth(admin_token))
    assert list_response.status_code == 200
    assert [restaurant["id"] for restaurant in list_response.json()] == [
        context["restaurant_id"]
    ]

    suspend_response = client.patch(
        f"/admin/restaurants/{context['restaurant_id']}",
        json={"is_active": False},
        headers=auth(admin_token),
    )
    assert suspend_response.status_code == 200
    assert suspend_response.json()["is_active"] is False

    login_response = client.post(
        "/auth/login",
        json={"email": "restaurant@example.com", "password": PASSWORD},
    )
    assert login_response.status_code == 403
    assert login_response.json()["detail"] == "餐廳已停權"

    existing_token_response = client.get(
        "/restaurants/me", headers=auth(str(context["restaurant_token"]))
    )
    assert existing_token_response.status_code == 403
    assert existing_token_response.json()["detail"] == "餐廳已停權"


def test_non_admin_cannot_manage_restaurant(client: TestClient) -> None:
    context = prepare_menu(client)

    response = client.patch(
        f"/admin/restaurants/{context['restaurant_id']}",
        json={"is_active": False},
        headers=auth(str(context["consumer_token"])),
    )

    assert response.status_code == 403


def test_admin_can_manage_categories_in_restaurant_scope(client: TestClient) -> None:
    context = prepare_menu(client)
    admin_token = create_admin_and_login(client)

    create_response = client.post(
        "/admin/menu-categories",
        json={
            "restaurant_id": context["restaurant_id"],
            "name": "管理員分類",
            "sort_order": 2,
        },
        headers=auth(admin_token),
    )
    assert create_response.status_code == 201
    category = create_response.json()
    assert category["restaurant_id"] == context["restaurant_id"]

    list_response = client.get(
        f"/admin/menu-categories?restaurant_id={context['restaurant_id']}",
        headers=auth(admin_token),
    )
    assert list_response.status_code == 200
    assert [item["name"] for item in list_response.json()] == ["主餐", "管理員分類"]

    update_response = client.patch(
        f"/admin/menu-categories/{category['id']}",
        json={"name": "管理後分類", "sort_order": 3},
        headers=auth(admin_token),
    )
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "管理後分類"
    assert update_response.json()["sort_order"] == 3

    delete_response = client.delete(
        f"/admin/menu-categories/{category['id']}",
        headers=auth(admin_token),
    )
    assert delete_response.status_code == 204


def test_admin_overview_contains_restaurant_and_order_status_counts(
    client: TestClient,
) -> None:
    context = prepare_menu(client)
    add_to_cart(client, context)
    create_order(client, context)
    admin_token = create_admin_and_login(client)

    response = client.get("/admin/overview", headers=auth(admin_token))

    assert response.status_code == 200
    payload = response.json()
    assert payload["restaurants"] == {"total": 1, "active": 1, "suspended": 0}
    assert payload["orders"]["total"] == 1
    assert payload["orders"]["by_status"]["pending"] == 1
    assert all(
        count == 0
        for order_status, count in payload["orders"]["by_status"].items()
        if order_status != "pending"
    )


def test_pending_consumer_cancellation_refunds_and_preparing_order_cannot_cancel(
    client: TestClient,
) -> None:
    context = prepare_menu(client)
    add_to_cart(client, context)
    pending_order = create_order(client, context)

    refund_response = client.patch(
        f"/orders/{pending_order['id']}/status",
        json={"status": "cancelled"},
        headers=auth(str(context["consumer_token"])),
    )
    assert refund_response.status_code == 200
    assert refund_response.json()["status"] == "cancelled"
    assert refund_response.json()["payment"]["status"] == "refunded"
    assert refund_response.json()["payment"]["refunded_at"] is not None

    add_to_cart(client, context)
    preparing_order = create_order(client, context)
    for target_status in ("accepted", "preparing"):
        transition_response = client.patch(
            f"/orders/{preparing_order['id']}/status",
            json={"status": target_status},
            headers=auth(str(context["restaurant_token"])),
        )
        assert transition_response.status_code == 200

    reject_response = client.patch(
        f"/orders/{preparing_order['id']}/status",
        json={"status": "cancelled"},
        headers=auth(str(context["consumer_token"])),
    )
    assert reject_response.status_code == 409

    current_response = client.get(
        f"/orders/{preparing_order['id']}",
        headers=auth(str(context["consumer_token"])),
    )
    assert current_response.status_code == 200
    assert current_response.json()["status"] == "preparing"
    assert current_response.json()["payment"]["status"] == "paid"
