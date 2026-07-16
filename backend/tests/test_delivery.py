"""todo.md 階段四 4.1～4.4 的配送 API 整合測試。"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.database import SessionLocal
from backend.models.delivery import DeliveryAssignment, DeliveryLocation
from backend.models.enums import OrderStatus
from backend.models.order import Order
from backend.seed_admin import create_initial_admin


PASSWORD = "ValidPass123!"


def register(client: TestClient, email: str, role: str, name: str) -> dict[str, Any]:
    response = client.post(
        "/auth/register",
        json={"email": email, "password": PASSWORD, "role": role, "name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, email: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def assert_utc(value: str) -> None:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.utcoffset() == timedelta(0)


def prepare_ready_order(client: TestClient) -> dict[str, Any]:
    register(client, "restaurant@example.com", "restaurant", "測試餐廳主")
    register(client, "consumer@example.com", "consumer", "測試消費者")
    courier_a = register(client, "courier-a@example.com", "courier", "外送員 A")
    courier_b = register(client, "courier-b@example.com", "courier", "外送員 B")

    restaurant_token = login(client, "restaurant@example.com")
    consumer_token = login(client, "consumer@example.com")
    courier_a_token = login(client, "courier-a@example.com")
    courier_b_token = login(client, "courier-b@example.com")

    restaurant_response = client.post(
        "/restaurants",
        json={"name": "配送測試餐廳", "address": "測試路 1 號"},
        headers=auth(restaurant_token),
    )
    assert restaurant_response.status_code == 201, restaurant_response.text
    restaurant_id = restaurant_response.json()["id"]
    menu_response = client.post(
        f"/restaurants/{restaurant_id}/menu-items",
        json={"name": "配送測試餐點", "price": "88.50"},
        headers=auth(restaurant_token),
    )
    assert menu_response.status_code == 201, menu_response.text

    cart_response = client.post(
        "/cart/items",
        json={"menu_item_id": menu_response.json()["id"], "quantity": 1},
        headers=auth(consumer_token),
    )
    assert cart_response.status_code == 200, cart_response.text
    order_response = client.post("/orders", headers=auth(consumer_token))
    assert order_response.status_code == 201, order_response.text
    order = order_response.json()

    for target_status in ("accepted", "preparing", "ready_for_pickup"):
        status_response = client.patch(
            f"/orders/{order['id']}/status",
            json={"status": target_status},
            headers=auth(restaurant_token),
        )
        assert status_response.status_code == 200, status_response.text

    return {
        "order": order,
        "restaurant_token": restaurant_token,
        "consumer_token": consumer_token,
        "courier_a": courier_a,
        "courier_b": courier_b,
        "courier_a_token": courier_a_token,
        "courier_b_token": courier_b_token,
    }


def claim_order(client: TestClient, context: dict[str, Any]) -> dict[str, Any]:
    response = client.post(
        f"/orders/{context['order']['id']}/claim",
        headers=auth(str(context["courier_a_token"])),
    )
    assert response.status_code == 201, response.text
    return response.json()


def mark_picked_up(client: TestClient, context: dict[str, Any]) -> None:
    response = client.patch(
        f"/orders/{context['order']['id']}/status",
        json={"status": "picked_up"},
        headers=auth(str(context["courier_a_token"])),
    )
    assert response.status_code == 200, response.text


def test_tc_4_1_01_courier_lists_only_unclaimed_ready_orders(
    client: TestClient,
) -> None:
    context = prepare_ready_order(client)
    order_id = context["order"]["id"]

    response = client.get(
        "/orders/available", headers=auth(str(context["courier_a_token"]))
    )
    assert response.status_code == 200, response.text
    available = response.json()
    assert [order["id"] for order in available] == [order_id]
    assert available[0]["status"] == OrderStatus.READY_FOR_PICKUP.value
    assert "consumer_user_id" not in available[0]

    forbidden_response = client.get(
        "/orders/available", headers=auth(str(context["consumer_token"]))
    )
    assert forbidden_response.status_code == 403

    claim_order(client, context)
    after_claim_response = client.get(
        "/orders/available", headers=auth(str(context["courier_b_token"]))
    )
    assert after_claim_response.status_code == 200
    assert after_claim_response.json() == []

    assigned_response = client.get(
        "/orders?role=courier", headers=auth(str(context["courier_a_token"]))
    )
    assert assigned_response.status_code == 200
    assert [order["id"] for order in assigned_response.json()] == [order_id]


def test_tc_4_2_claim_conflict_keeps_exactly_one_assignment(
    client: TestClient,
) -> None:
    context = prepare_ready_order(client)
    order_id = context["order"]["id"]

    created = claim_order(client, context)
    assert created["order_id"] == order_id
    assert created["courier_user_id"] == context["courier_a"]["id"]
    assert_utc(created["claimed_at"])

    conflicting_response = client.post(
        f"/orders/{order_id}/claim",
        headers=auth(str(context["courier_b_token"])),
    )
    assert conflicting_response.status_code == 409
    assert "已被" in conflicting_response.json()["detail"]

    with SessionLocal() as db:
        assignments = db.scalars(
            select(DeliveryAssignment).where(DeliveryAssignment.order_id == order_id)
        ).all()
        assert len(assignments) == 1
        assert assignments[0].courier_user_id == context["courier_a"]["id"]
        assert (
            db.scalar(
                select(func.count())
                .select_from(DeliveryAssignment)
                .where(DeliveryAssignment.order_id == order_id)
            )
            == 1
        )


def test_claim_rejects_order_that_is_not_ready_for_pickup(client: TestClient) -> None:
    context = prepare_ready_order(client)
    order_id = context["order"]["id"]
    with SessionLocal() as db:
        order = db.get(Order, order_id)
        assert order is not None
        order.status = OrderStatus.PREPARING
        db.commit()

    response = client.post(
        f"/orders/{order_id}/claim",
        headers=auth(str(context["courier_a_token"])),
    )
    assert response.status_code == 409


def test_tc_4_3_01_and_02_location_requires_assignment_and_delivery_state(
    client: TestClient,
) -> None:
    context = prepare_ready_order(client)
    order_id = context["order"]["id"]
    claim_order(client, context)

    before_pickup_response = client.post(
        f"/orders/{order_id}/locations",
        json={"latitude": "25.033000", "longitude": "121.565400"},
        headers=auth(str(context["courier_a_token"])),
    )
    assert before_pickup_response.status_code == 409

    mark_picked_up(client, context)
    foreign_courier_response = client.post(
        f"/orders/{order_id}/locations",
        json={"latitude": "25.033000", "longitude": "121.565400"},
        headers=auth(str(context["courier_b_token"])),
    )
    assert foreign_courier_response.status_code == 403
    invalid_coordinate_response = client.post(
        f"/orders/{order_id}/locations",
        json={"latitude": "91.000000", "longitude": "121.565400"},
        headers=auth(str(context["courier_a_token"])),
    )
    assert invalid_coordinate_response.status_code == 422

    location_response = client.post(
        f"/orders/{order_id}/locations",
        json={"latitude": "25.033000", "longitude": "121.565400"},
        headers=auth(str(context["courier_a_token"])),
    )
    assert location_response.status_code == 201, location_response.text
    location = location_response.json()
    assert Decimal(location["latitude"]) == Decimal("25.033000")
    assert Decimal(location["longitude"]) == Decimal("121.565400")
    assert_utc(location["recorded_at"])

    with SessionLocal() as db:
        assignment = db.scalar(
            select(DeliveryAssignment).where(DeliveryAssignment.order_id == order_id)
        )
        assert assignment is not None
        assert assignment.picked_up_at is not None
        stored_location = db.get(DeliveryLocation, location["id"])
        assert stored_location is not None
        assert stored_location.latitude == Decimal("25.033000")
        assert stored_location.longitude == Decimal("121.565400")


def test_delivery_status_transitions_require_claim_owner_and_stamp_completion(
    client: TestClient,
) -> None:
    context = prepare_ready_order(client)
    order_id = context["order"]["id"]
    claim_order(client, context)
    mark_picked_up(client, context)

    foreign_transition = client.patch(
        f"/orders/{order_id}/status",
        json={"status": "delivering"},
        headers=auth(str(context["courier_b_token"])),
    )
    assert foreign_transition.status_code == 403
    delivering_response = client.patch(
        f"/orders/{order_id}/status",
        json={"status": "delivering"},
        headers=auth(str(context["courier_a_token"])),
    )
    assert delivering_response.status_code == 200
    delivered_response = client.patch(
        f"/orders/{order_id}/status",
        json={"status": "delivered"},
        headers=auth(str(context["courier_a_token"])),
    )
    assert delivered_response.status_code == 200

    with SessionLocal() as db:
        assignment = db.scalar(
            select(DeliveryAssignment).where(DeliveryAssignment.order_id == order_id)
        )
        assert assignment is not None
        assert assignment.picked_up_at is not None
        assert assignment.delivered_at is not None


def test_tc_4_4_location_access_is_limited_to_order_parties(
    client: TestClient,
) -> None:
    context = prepare_ready_order(client)
    order_id = context["order"]["id"]
    claim_order(client, context)
    mark_picked_up(client, context)

    first_location = client.post(
        f"/orders/{order_id}/locations",
        json={"latitude": "25.033000", "longitude": "121.565400"},
        headers=auth(str(context["courier_a_token"])),
    )
    assert first_location.status_code == 201, first_location.text
    second_location = client.post(
        f"/orders/{order_id}/locations",
        json={"latitude": "25.034000", "longitude": "121.566400"},
        headers=auth(str(context["courier_a_token"])),
    )
    assert second_location.status_code == 201, second_location.text

    latest_response = client.get(
        f"/orders/{order_id}/locations/latest",
        headers=auth(str(context["consumer_token"])),
    )
    assert latest_response.status_code == 200, latest_response.text
    assert latest_response.json()["id"] == second_location.json()["id"]
    history_response = client.get(
        f"/orders/{order_id}/locations",
        headers=auth(str(context["restaurant_token"])),
    )
    assert history_response.status_code == 200, history_response.text
    assert [item["id"] for item in history_response.json()] == [
        first_location.json()["id"],
        second_location.json()["id"],
    ]

    with SessionLocal() as db:
        create_initial_admin(
            db,
            email="admin@example.com",
            password=PASSWORD,
            name="配送管理員",
            phone=None,
        )
    admin_token = login(client, "admin@example.com")
    admin_response = client.get(
        f"/orders/{order_id}/locations/latest", headers=auth(admin_token)
    )
    assert admin_response.status_code == 200

    register(client, "other-consumer@example.com", "consumer", "其他消費者")
    other_consumer_token = login(client, "other-consumer@example.com")
    leakage_response = client.get(
        f"/orders/{order_id}/locations/latest", headers=auth(other_consumer_token)
    )
    assert leakage_response.status_code == 403
